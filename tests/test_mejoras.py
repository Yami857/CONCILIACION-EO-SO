"""Pruebas de las mejoras de seguridad, rendimiento y limpieza.

Cubre los comportamientos nuevos que no estaban en las entregas T1–T4:

1. `GET /health` público (tarea 5).
2. Configuración de sesión y límite de subida (tareas 3 y 4).
3. Token CSRF: todo POST sin token válido se rechaza con 400 (tarea 10).
4. Límite de 5 intentos fallidos por IP, reinicio tras ingreso correcto (tarea 2).
5. Caché del análisis de IA: una sola llamada por carga (rendimiento).
6. Contrato del agente: descarte elemento por elemento (AGENTS.md §4).
7. Sumas R4: una celda no numérica se ignora, no se cuenta como 0 falso.

Las credenciales de prueba vienen de `conftest.py` (fixture autouse). Los
clientes para CSRF usan `create_app(instance_path=<tmp_path>)` SIN `TESTING`,
porque la validación CSRF se omite a propósito cuando `TESTING` es True. Todos
los temporales son `tmp_path` / `tmp_path_factory`: nunca se tocan `instance/`
del proyecto ni `INSUMOS/`.
"""

import re
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from flask import template_rendered

from app import create_app
from app.controllers import acceso
from app.services.agrupacion import _sumar, r4_agrupar_por_cruce
from app.services.agente import validar_contrato
from conftest import CLAVE_PRUEBA, USUARIO_PRUEBA

# --- Textos exactos del código (en español) ---------------------------------
MENSAJE_CSRF = "Solicitud no válida. Recargue la pantalla e intente de nuevo."
MENSAJE_DEMASIADOS = "Demasiados intentos. Intente de nuevo en unos minutos."
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos"

# Archivo de prueba versionado dentro de tests/ (nunca en INSUMOS/).
RUTA_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "movimientos_prueba.xlsx"


def _texto(respuesta):
    """Cuerpo de la respuesta decodificado como UTF-8."""
    return respuesta.get_data(as_text=True)


def _ip_unica():
    """Dirección IP única por prueba para no contaminar el contador global."""
    return f"198.51.100.{uuid.uuid4().int % 253 + 1}"


def _subir(cliente, ruta):
    """Sube un `.xlsx` por `POST /cargar` con el cliente Flask."""
    with open(ruta, "rb") as archivo:
        return cliente.post(
            "/cargar",
            data={"archivo": (archivo, Path(ruta).name)},
            content_type="multipart/form-data",
        )


# --- 1. Health check público -------------------------------------------------


def test_mejoras_health_sin_sesion_responde_200_ok(cliente_anonimo):
    """`GET /health` responde 200 con cuerpo «ok» sin iniciar sesión."""
    respuesta = cliente_anonimo.get("/health")

    assert respuesta.status_code == 200
    assert _texto(respuesta) == "ok"
    assert respuesta.content_type.startswith("text/plain")


# --- 2. Configuración de sesión y de subida ----------------------------------


def test_mejoras_configuracion_de_sesion_y_limite_de_subida(app):
    """Sesión de 8 h, cookie HTTP-only, SameSite=Lax y límite de 25 MB."""
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=8)
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["MAX_CONTENT_LENGTH"] == 25 * 1024 * 1024


# --- 3. CSRF -----------------------------------------------------------------


@pytest.fixture()
def app_sin_testing(tmp_path):
    """App creada con `instance_path` temporal y SIN modo TESTING (CSRF activo)."""
    aplicacion = create_app(instance_path=str(tmp_path))
    assert aplicacion.config.get("TESTING", False) is False
    return aplicacion


def _token_del_formulario(respuesta):
    """Extrae el `csrf_token` del campo oculto renderizado por la plantilla."""
    encontrado = re.search(r'name="csrf_token"\s+value="([^"]+)"', _texto(respuesta))
    assert encontrado is not None, "la plantilla no expuso el token CSRF"
    return encontrado.group(1)


def test_mejoras_csrf_login_sin_token_devuelve_400(app_sin_testing):
    """`POST /login` sin token CSRF: 400 con el mensaje exacto y sin sesión."""
    cliente = app_sin_testing.test_client()

    respuesta = cliente.post(
        "/login", data={"usuario": USUARIO_PRUEBA, "clave": CLAVE_PRUEBA}
    )

    assert respuesta.status_code == 400
    assert MENSAJE_CSRF in _texto(respuesta)
    with cliente.session_transaction() as sesion:
        assert not sesion.get("usuario")


def test_mejoras_csrf_login_con_token_valido_entra(app_sin_testing):
    """Con el token del formulario, `POST /login` correcto redirige 302 a `/`."""
    cliente = app_sin_testing.test_client()
    token = _token_del_formulario(cliente.get("/login"))

    respuesta = cliente.post(
        "/login",
        data={
            "usuario": USUARIO_PRUEBA,
            "clave": CLAVE_PRUEBA,
            "csrf_token": token,
        },
    )

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/")
    with cliente.session_transaction() as sesion:
        assert sesion["usuario"] == USUARIO_PRUEBA


def test_mejoras_csrf_cargar_sin_token_devuelve_400(app_sin_testing):
    """Ya dentro, `POST /cargar` sin token CSRF: 400 con el mensaje exacto."""
    cliente = app_sin_testing.test_client()
    token = _token_del_formulario(cliente.get("/login"))
    cliente.post(
        "/login",
        data={
            "usuario": USUARIO_PRUEBA,
            "clave": CLAVE_PRUEBA,
            "csrf_token": token,
        },
    )

    with open(RUTA_FIXTURE, "rb") as archivo:
        respuesta = cliente.post(
            "/cargar",
            data={"archivo": (archivo, RUTA_FIXTURE.name)},
            content_type="multipart/form-data",
        )

    assert respuesta.status_code == 400
    assert MENSAJE_CSRF in _texto(respuesta)


def test_mejoras_csrf_cargar_con_token_valido_redirige(app_sin_testing):
    """Con token válido, `POST /cargar` con el fixture redirige 302."""
    cliente = app_sin_testing.test_client()
    token = _token_del_formulario(cliente.get("/login"))
    cliente.post(
        "/login",
        data={
            "usuario": USUARIO_PRUEBA,
            "clave": CLAVE_PRUEBA,
            "csrf_token": token,
        },
    )

    with open(RUTA_FIXTURE, "rb") as archivo:
        respuesta = cliente.post(
            "/cargar",
            data={
                "archivo": (archivo, RUTA_FIXTURE.name),
                "csrf_token": token,
            },
            content_type="multipart/form-data",
        )

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/resultados")


# --- 4. Límite de intentos fallidos por IP -----------------------------------


def test_mejoras_quinto_fallo_ya_avisa_demasiados_y_el_sexto_no_entra(
    cliente_anonimo,
):
    """5 fallos con la misma IP: el 5.º avisa «Demasiados intentos» y el 6.º no entra."""
    ip = _ip_unica()
    cabecera = {"X-Forwarded-For": ip}
    datos_malos = {"usuario": USUARIO_PRUEBA, "clave": "clave-equivocada"}

    for numero in range(1, 6):
        respuesta = cliente_anonimo.post(
            "/login", data=datos_malos, headers=cabecera
        )
        assert respuesta.status_code == 200, f"intento {numero}"
        if numero < 5:
            assert MENSAJE_CREDENCIALES in _texto(respuesta), f"intento {numero}"
        else:
            assert MENSAJE_DEMASIADOS in _texto(respuesta), f"intento {numero}"

    # Sexto intento, ahora con la clave correcta: no se crea sesión.
    respuesta = cliente_anonimo.post(
        "/login",
        data={"usuario": USUARIO_PRUEBA, "clave": CLAVE_PRUEBA},
        headers=cabecera,
    )
    assert respuesta.status_code == 200
    assert MENSAJE_DEMASIADOS in _texto(respuesta)
    with cliente_anonimo.session_transaction() as sesion:
        assert not sesion.get("usuario")


def test_mejoras_login_correcto_reinicia_el_contador(cliente_anonimo):
    """Tras un ingreso correcto el contador de fallos vuelve a cero."""
    ip = _ip_unica()
    cabecera = {"X-Forwarded-For": ip}
    datos_malos = {"usuario": USUARIO_PRUEBA, "clave": "clave-equivocada"}

    for _ in range(4):
        cliente_anonimo.post("/login", data=datos_malos, headers=cabecera)

    correcto = cliente_anonimo.post(
        "/login",
        data={"usuario": USUARIO_PRUEBA, "clave": CLAVE_PRUEBA},
        headers=cabecera,
    )
    assert correcto.status_code == 302
    assert acceso._intentos_por_ip.get(ip, []) == []

    # Si el contador no se hubiera reiniciado, el primer fallo posterior ya
    # mostraría «Demasiados intentos»; deben hacer falta 5 otra vez.
    for numero in range(1, 5):
        respuesta = cliente_anonimo.post(
            "/login", data=datos_malos, headers=cabecera
        )
        assert MENSAJE_CREDENCIALES in _texto(respuesta), f"fallo posterior {numero}"
    respuesta = cliente_anonimo.post(
        "/login", data=datos_malos, headers=cabecera
    )
    assert MENSAJE_DEMASIADOS in _texto(respuesta)


# --- 5. Caché del análisis de IA ---------------------------------------------


def test_mejoras_ia_se_consulta_una_vez_y_se_reutiliza_en_resultados_y_descarga(
    cliente, app, monkeypatch
):
    """1 llamada en la 1.ª visita; 0 en la 2.ª y en `/descargar` (caché)."""
    llamadas = []

    def agente_falso(cruces):
        llamadas.append(len(cruces))
        return {
            "ok": True,
            "motivo": "",
            "analisis": {
                cruce["id_cruce"]: f"Análisis de {cruce['id_cruce']}"
                for cruce in cruces
            },
        }

    monkeypatch.setattr(
        "app.controllers.resultados.consultar_agente", agente_falso
    )

    contextos = []

    def capturar_contexto(sender, template, context, **extra):
        if template.name == "resultados.html":
            contextos.append(dict(context))

    template_rendered.connect(capturar_contexto, app)
    try:
        # La carga no consulta al agente: eso pasa solo en /resultados.
        subida = _subir(cliente, RUTA_FIXTURE)
        assert subida.status_code == 302
        assert llamadas == []

        primera = cliente.get("/resultados")
        assert primera.status_code == 200
        assert len(llamadas) == 1, llamadas
        assert contextos[-1]["ia_disponible"] is True
        assert "Análisis de EO-3000-SO-2999" in _texto(primera)

        segunda = cliente.get("/resultados")
        assert segunda.status_code == 200
        assert len(llamadas) == 1, "la 2.ª visita no debe consultar al agente"
        assert contextos[-1]["ia_disponible"] is True
        assert "Análisis de EO-3000-SO-2999" in _texto(segunda)

        descarga = cliente.get("/descargar")
        assert descarga.status_code == 200
        assert descarga.mimetype.endswith("spreadsheetml.sheet")
        assert len(llamadas) == 1, "la descarga no debe consultar al agente"
    finally:
        template_rendered.disconnect(capturar_contexto, app)


# --- 6. Contrato del agente: descarte elemento por elemento ------------------


def _elemento(id_cruce, **cambios):
    """Arma un elemento válido del contrato de 4 llaves (AGENTS.md §4)."""
    base = {
        "id_cruce": id_cruce,
        "costo_eo_mayor": True,
        "analisis_anomalia": "Diferencia detectada.",
        "estado_revision": "Correcto",
    }
    base.update(cambios)
    return base


def test_mejoras_validar_contrato_conserva_validos_y_descarta_invalidos():
    """Los elementos válidos sobreviven; los inválidos se descartan completos."""
    datos = {
        "resultados": [
            _elemento("EO-1-SO-0", analisis_anomalia="Análisis uno."),
            {"id_cruce": "EO-2-SO-1", "costo_eo_mayor": True},  # faltan 2 llaves
            _elemento("EO-3-SO-2", estado_revision="Desconocido"),  # estado malo
            "esto no es un diccionario",
            _elemento("EO-4-SO-3", analisis_anomalia="   "),  # texto vacío
            _elemento(
                "EO-5-SO-4",
                analisis_anomalia="Análisis cinco.",
                estado_revision="Revisar",
                costo_eo_mayor=False,
            ),
        ]
    }

    assert validar_contrato(datos) == {
        "EO-1-SO-0": "Análisis uno.",
        "EO-5-SO-4": "Análisis cinco.",
    }


def test_mejoras_validar_contrato_devuelve_none_solo_si_no_queda_ninguno():
    """`None` solo cuando no sobrevive ningún elemento válido."""
    sin_validos = {
        "resultados": [
            _elemento("EO-1-SO-0", estado_revision="Mal"),
            {"id_cruce": "EO-2-SO-1"},
            42,
        ]
    }

    assert validar_contrato(sin_validos) is None
    assert validar_contrato({"resultados": []}) is None
    assert validar_contrato({"otra": []}) is None
    assert validar_contrato("no es un objeto") is None

    # Un solo elemento válido ya NO es None.
    assert validar_contrato(
        {"resultados": [_elemento("EO-9-SO-8", analisis_anomalia="Único.")]}
    ) == {"EO-9-SO-8": "Único."}


# --- 7. Sumas R4: celdas no numéricas ----------------------------------------


def test_mejoras_sumar_ignora_celdas_no_numericas():
    """`_sumar` ignora «N/A» en vez de contarlo como 0."""
    lineas = [
        {"Total": 1000.0},
        {"Total": "N/A"},
        {"Total": 25.5},
        {"Total": None},
    ]

    assert _sumar(lineas, "Total") == 1025.5


def test_mejoras_agrupacion_no_finge_cero_con_celda_no_numerica():
    """En un cruce real de R4, una línea EO con `Total="N/A"` no aporta 0 falso."""
    base = {
        "Bodega": 400,
        "Usuario Aplica": "CN03",
        "Cantidad": 10,
        "Kilos": 10,
        "Costo Uni.": 100,
    }
    eo_valida = {**base, "Tipo Doc.": "EO", "No. Físico": 6000, "Total": 1000}
    eo_no_numerica = {**base, "Tipo Doc.": "EO", "No. Físico": 6000, "Total": "N/A"}
    so = {**base, "Tipo Doc.": "SO", "No. Físico": 5999, "Total": 400}

    pares = [
        {
            "id_cruce": "EO-6000-SO-5999",
            "fisico_eo": 6000,
            "fisico_so": 5999,
            "lineas_eo": [eo_valida, eo_no_numerica],
            "lineas_so": [so],
        }
    ]
    cruces = r4_agrupar_por_cruce(pares)

    assert len(cruces) == 1
    assert cruces[0]["total_eo"] == 1000.0
    assert cruces[0]["total_so"] == 400.0
