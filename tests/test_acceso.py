"""Pruebas del ingreso (login) del Conciliador EO / SO.

Cubre la puerta de entrada de `app/controllers/acceso.py`:

- toda pantalla exige sesión y redirige a `/login` (302) cuando no la hay;
- `GET /login` muestra el formulario en español con «Usuario», «Contraseña» y
  el botón «Entrar»;
- las credenciales salen de `APP_USUARIO` y `APP_CLAVE` del entorno, no de una
  tabla de usuarios ni del código;
- con credenciales incorrectas no se crea sesión;
- con credenciales correctas se abre la sesión y `/` responde 200;
- `/salir` cierra la sesión (y funciona aunque no haya sesión);
- si faltan las variables del servidor, ningún intento entra;
- la cabecera muestra el usuario y el enlace «Salir» solo con sesión.

Las respuestas de Flask son UTF-8: los textos con tildes se comparan como
`bytes` codificados en UTF-8 para no depender de la consola de Windows.
"""

from urllib.parse import urlsplit

import pytest

from conftest import CLAVE_PRUEBA, USUARIO_PRUEBA

# Mensajes exactos de la pantalla de ingreso (`app/controllers/acceso.py`).
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos"
MENSAJE_SIN_CONFIGURAR = "El acceso no está configurado en el servidor."

# Rutas que exigen sesión (AGENTS.md §5: carga, resultados y descarga).
RUTAS_PROTEGIDAS = [
    ("GET", "/"),
    ("GET", "/resultados"),
    ("GET", "/descargar"),
    ("POST", "/cargar"),
]


def _texto(respuesta):
    """Devuelve el cuerpo HTML de la respuesta decodificado como UTF-8."""
    return respuesta.get_data(as_text=True)


def _ruta_redirigida(respuesta):
    """Ruta (sin esquema ni host) del encabezado `Location` de una respuesta."""
    return urlsplit(respuesta.headers["Location"]).path


def _sesion_iniciada(cliente):
    """`True` si el cliente de pruebas tiene `usuario` en la sesión."""
    with cliente.session_transaction() as sesion:
        return bool(sesion.get("usuario"))


# --- 1. La pantalla principal sin sesión redirige a /login -----------------


def test_acceso_sin_sesion_la_pantalla_principal_redirige_a_login(cliente_anonimo):
    """`GET /` sin sesión responde 302 y `Location` termina en `/login`."""
    respuesta = cliente_anonimo.get("/")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/login")
    assert _ruta_redirigida(respuesta) == "/login"


# --- 2. Todas las rutas protegidas redirigen a /login ----------------------


@pytest.mark.parametrize("metodo, ruta", RUTAS_PROTEGIDAS)
def test_acceso_sin_sesion_toda_ruta_protegida_redirige_a_login(
    cliente_anonimo, metodo, ruta
):
    """`/`, `/resultados`, `/descargar` y `POST /cargar` exigen sesión."""
    respuesta = cliente_anonimo.open(ruta, method=metodo)

    assert respuesta.status_code == 302, f"{metodo} {ruta}"
    assert _ruta_redirigida(respuesta) == "/login", f"{metodo} {ruta}"
    assert not _sesion_iniciada(cliente_anonimo)


# --- 3. El formulario de ingreso -------------------------------------------


def test_acceso_login_muestra_usuario_contrasena_y_boton_entrar(cliente_anonimo):
    """`GET /login` responde 200 con los dos campos y el botón «Entrar»."""
    respuesta = cliente_anonimo.get("/login")
    html = _texto(respuesta)

    assert respuesta.status_code == 200
    assert "Usuario".encode("utf-8") in respuesta.data
    assert "Contraseña".encode("utf-8") in respuesta.data
    assert "Entrar".encode("utf-8") in respuesta.data

    # Los campos que espera el controller: `usuario` y `clave`.
    assert 'name="usuario"' in html
    assert 'name="clave"' in html
    assert 'method="post"' in html


# --- 4. Clave incorrecta ---------------------------------------------------


def test_acceso_login_con_clave_incorrecta_no_entra_y_avisa(cliente_anonimo):
    """Clave mala: 200 con el mensaje de error y sin sesión creada."""
    respuesta = cliente_anonimo.post(
        "/login",
        data={"usuario": USUARIO_PRUEBA, "clave": "clave-equivocada"},
    )

    assert respuesta.status_code == 200
    assert MENSAJE_CREDENCIALES.encode("utf-8") in respuesta.data
    assert not _sesion_iniciada(cliente_anonimo)

    # La misma sesión sigue sin acceso a la pantalla principal.
    despues = cliente_anonimo.get("/")
    assert despues.status_code == 302
    assert _ruta_redirigida(despues) == "/login"


# --- 5. Usuario incorrecto con clave correcta ------------------------------


def test_acceso_login_con_usuario_incorrecto_no_entra_y_avisa(cliente_anonimo):
    """Usuario malo con clave buena: mismo mensaje y sin sesión."""
    respuesta = cliente_anonimo.post(
        "/login",
        data={"usuario": "otra-persona@montecillos.com", "clave": CLAVE_PRUEBA},
    )

    assert respuesta.status_code == 200
    assert MENSAJE_CREDENCIALES.encode("utf-8") in respuesta.data
    assert not _sesion_iniciada(cliente_anonimo)

    despues = cliente_anonimo.get("/")
    assert despues.status_code == 302
    assert _ruta_redirigida(despues) == "/login"


# --- 6. Credenciales correctas --------------------------------------------


def test_acceso_login_con_credenciales_correctas_entra_a_la_pantalla_principal(
    cliente_anonimo,
):
    """Usuario y clave buenos: 302 a `/` y `/` responde 200 con esa sesión."""
    respuesta = cliente_anonimo.post(
        "/login",
        data={"usuario": USUARIO_PRUEBA, "clave": CLAVE_PRUEBA},
    )

    assert respuesta.status_code == 302
    assert _ruta_redirigida(respuesta) == "/"
    assert _sesion_iniciada(cliente_anonimo)

    with cliente_anonimo.session_transaction() as sesion:
        assert sesion["usuario"] == USUARIO_PRUEBA

    principal = cliente_anonimo.get("/")
    assert principal.status_code == 200
    assert "Conciliador EO / SO".encode("utf-8") in principal.data


# --- 7. Salir con sesión ---------------------------------------------------


def test_acceso_salir_con_sesion_cierra_la_sesion(cliente):
    """`GET /salir` con sesión: 302 a `/login` y `/` vuelve a dar 302."""
    assert cliente.get("/").status_code == 200

    respuesta = cliente.get("/salir")

    assert respuesta.status_code == 302
    assert _ruta_redirigida(respuesta) == "/login"
    assert not _sesion_iniciada(cliente)

    despues = cliente.get("/")
    assert despues.status_code == 302
    assert _ruta_redirigida(despues) == "/login"


# --- 8. Salir sin sesión ---------------------------------------------------


def test_acceso_salir_sin_sesion_redirige_a_login_sin_fallar(cliente_anonimo):
    """`GET /salir` sin sesión: 302 a `/login`, sin excepción ni 500."""
    respuesta = cliente_anonimo.get("/salir")

    assert respuesta.status_code == 302
    assert _ruta_redirigida(respuesta) == "/login"
    assert not _sesion_iniciada(cliente_anonimo)


# --- 9. Servidor sin credenciales configuradas ----------------------------


@pytest.fixture()
def cliente_sin_credenciales(app, monkeypatch):
    """Cliente de una app cuyo servidor no tiene `APP_USUARIO`/`APP_CLAVE`.

    La app se crea primero (fixture `app`) y después se borran las variables,
    que es justo el estado que evalúa el controller en cada intento de ingreso.
    `monkeypatch` las restaura al terminar la prueba, sin afectar a las demás.
    """
    monkeypatch.delenv("APP_USUARIO", raising=False)
    monkeypatch.delenv("APP_CLAVE", raising=False)
    return app.test_client()


def test_acceso_sin_variables_el_login_avisa_que_no_esta_configurado(
    cliente_sin_credenciales,
):
    """Sin `APP_USUARIO`/`APP_CLAVE` ningún dato entra y se avisa en español."""
    respuesta = cliente_sin_credenciales.post(
        "/login",
        data={"usuario": USUARIO_PRUEBA, "clave": CLAVE_PRUEBA},
    )

    assert respuesta.status_code == 200
    assert MENSAJE_SIN_CONFIGURAR.encode("utf-8") in respuesta.data
    assert MENSAJE_CREDENCIALES.encode("utf-8") not in respuesta.data
    assert not _sesion_iniciada(cliente_sin_credenciales)

    despues = cliente_sin_credenciales.get("/")
    assert despues.status_code == 302
    assert _ruta_redirigida(despues) == "/login"


# --- 10. Cabecera: usuario y enlace «Salir» solo con sesión ---------------


def test_acceso_la_cabecera_muestra_usuario_y_salir_solo_con_sesion(cliente_anonimo):
    """El email y el enlace «Salir» aparecen con sesión y no en `/login`."""
    login = cliente_anonimo.get("/login")
    assert login.status_code == 200
    assert USUARIO_PRUEBA.encode("utf-8") not in login.data
    assert "Salir".encode("utf-8") not in login.data

    cliente_anonimo.post(
        "/login",
        data={"usuario": USUARIO_PRUEBA, "clave": CLAVE_PRUEBA},
    )
    principal = cliente_anonimo.get("/")

    assert principal.status_code == 200
    assert USUARIO_PRUEBA.encode("utf-8") in principal.data
    assert "Salir".encode("utf-8") in principal.data
    assert 'href="/salir"' in _texto(principal)
