"""Configuración de pytest para el Conciliador EO / SO.

Agrega la raíz del proyecto a `sys.path` (el permiso de edición de @tester se
limita a `tests/`, por eso el pythonpath va aquí y no en `pyproject.toml`) y
define los fixtures compartidos por las pruebas de R1, R2 y R3.

El insumo real se copia a una carpeta temporal con `shutil.copy2`: el original
de `INSUMOS/` puede estar abierto en Excel y nunca se modifica.

Ruta del insumo real (decisión «b»): `INSUMOS/` está en `.gitignore`, así que un
clon del repositorio no trae el Excel real. La ruta se resuelve con la variable
de entorno `CONCILIADOR_INSUMO` si está definida; si no, se usa
`INSUMOS/MOVIMIENTOS 4-11-26.xlsx`. Cuando el archivo no existe, los fixtures que
lo necesitan hacen `pytest.skip` (SOLO por ausencia de este dato externo, nunca
para esconder un fallo de la app). Las pruebas que usan
`tests/fixtures/movimientos_prueba.xlsx` corren siempre.

Acceso (login): todas las rutas exigen sesión (`app/controllers/acceso.py`). El
fixture `cliente` entrega el cliente de Flask **con la sesión ya iniciada** y la
fixture autouse de sesión `entorno_de_acceso` fija `APP_USUARIO` y `APP_CLAVE`
con valores de prueba antes de crear la app, de modo que la suite no depende del
`.env` local. `cliente_anonimo` es el mismo cliente sin sesión, para las pruebas
del ingreso.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

# Raíz del proyecto: un nivel arriba de tests/.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from app import create_app  # noqa: E402  (después de ajustar sys.path)
from app.services.agrupacion import r4_agrupar_por_cruce  # noqa: E402
from app.services.carga import r1_cargar_movimientos  # noqa: E402
from app.services.costos import r5_detectar_costo_mayor  # noqa: E402
from app.services.emparejamiento import r3_emparejar  # noqa: E402
from app.services.filtro import r2_filtrar_eo_so  # noqa: E402

# Único insumo real disponible (AGENTS.md §2). `INSUMOS/` no se versiona.
NOMBRE_INSUMO_REAL = "MOVIMIENTOS 4-11-26.xlsx"
INSUMOS_POR_DEFECTO = RAIZ_PROYECTO / "INSUMOS" / NOMBRE_INSUMO_REAL

# Mensaje único del skip: deja claro que falta un dato externo, no que la app
# esté rota.
MENSAJE_SIN_INSUMO = (
    "Falta el insumo real: defina CONCILIADOR_INSUMO o coloque "
    f"{NOMBRE_INSUMO_REAL} en INSUMOS/ (no se versiona)."
)


def resolver_ruta_insumo():
    """Devuelve la ruta del insumo real, sin exigir que el archivo exista.

    Prioridad: variable de entorno `CONCILIADOR_INSUMO` (una ruta a un `.xlsx`);
    si no está definida, `INSUMOS/MOVIMIENTOS 4-11-26.xlsx` en la raíz del
    proyecto.
    """
    ruta_entorno = os.environ.get("CONCILIADOR_INSUMO")
    if ruta_entorno:
        return Path(ruta_entorno).expanduser()
    return INSUMOS_POR_DEFECTO


def exigir_insumo_real(ruta):
    """Hace `pytest.skip` si el insumo real no está disponible.

    El skip existe SOLO porque `INSUMOS/` no se versiona: un clon del repo no
    trae el Excel de la empresa y las cifras de control no se pueden reproducir
    sin él. No es un skip para esconder fallos: cuando el archivo está presente
    (esta máquina, o vía `CONCILIADOR_INSUMO`), todas las pruebas corren y
    cualquier diferencia con `AGENTS.md` falla.
    """
    if not ruta.is_file():
        pytest.skip(f"{MENSAJE_SIN_INSUMO} Ruta buscada: «{ruta}».")
    return ruta


@pytest.fixture(scope="session")
def ruta_insumo(tmp_path_factory):
    """Copia el insumo real a una carpeta temporal y devuelve la copia.

    Se usa una copia para no tocar nunca `INSUMOS/` (solo lectura) ni depender
    de si el Excel original está abierto en Excel. Si el insumo no existe, la
    prueba se omite con `MENSAJE_SIN_INSUMO`.
    """
    origen = exigir_insumo_real(resolver_ruta_insumo())

    carpeta = tmp_path_factory.mktemp("insumos")
    destino = carpeta / origen.name
    shutil.copy2(origen, destino)
    return destino


@pytest.fixture(scope="session")
def registros(ruta_insumo):
    """Carga el insumo real una sola vez con R1 y devuelve el resultado."""
    return r1_cargar_movimientos(ruta_insumo)


@pytest.fixture(scope="session")
def pipeline_real(registros):
    """Corre R2 a R5 una sola vez sobre el insumo real y devuelve sus salidas.

    Si el insumo real no está disponible, se omite (mismo motivo que
    `ruta_insumo`: `INSUMOS/` no se versiona). Se comprueba aquí también para
    que el motivo del skip quede explícito en este fixture.

    Devuelve un diccionario con los registros EO/SO de R2, su emparejamiento de
    R3, los cruces de R4 y los cruces con costo más las cifras de R5. Las
    pruebas de T2 (R4, R5, R6, R7 y cifras de control) lo reutilizan para no
    releer el Excel en cada archivo de pruebas.

    R6 y R7 no se aplican aquí: esas funciones agregan llaves a los cruces y
    cada prueba debe partir de una lista limpia.
    """
    exigir_insumo_real(resolver_ruta_insumo())

    registros_eo_so, total_eo, total_so = r2_filtrar_eo_so(registros["registros"])
    emparejamiento = r3_emparejar(registros_eo_so)
    cruces_r4 = r4_agrupar_por_cruce(emparejamiento["pares"])
    cruces_r5, cifras = r5_detectar_costo_mayor(cruces_r4)

    return {
        "registros_eo_so": registros_eo_so,
        "total_eo": total_eo,
        "total_so": total_so,
        "emparejamiento": emparejamiento,
        "cruces_r4": cruces_r4,
        "cruces": cruces_r5,
        "cifras": cifras,
    }


# --- Acceso (login) ---------------------------------------------------------
#
# La app exige sesión en todas las pantallas (`app/controllers/acceso.py`): sin
# `session["usuario"]` cualquier ruta responde 302 a `/login`. Las credenciales
# se leen de `APP_USUARIO` y `APP_CLAVE`, así que las pruebas definen valores
# propios ANTES de crear la app: el resultado no depende del `.env` local.
USUARIO_PRUEBA = "prueba@montecillos.com"
CLAVE_PRUEBA = "clave-de-prueba-2026"


@pytest.fixture(scope="session", autouse=True)
def entorno_de_acceso():
    """Fija `APP_USUARIO` y `APP_CLAVE` para toda la sesión de pytest.

    `create_app()` no sobrescribe variables ya presentes en el entorno (ver
    `cargar_variables_entorno`), de modo que estos valores ganan al `.env`. La
    fixture es autouse y de sesión para que existan antes de crear cualquier
    app. Las pruebas que necesitan el caso «sin configurar» borran estas
    variables con `monkeypatch` dentro de su propia prueba.
    """
    gestor = pytest.MonkeyPatch()
    gestor.setenv("APP_USUARIO", USUARIO_PRUEBA)
    gestor.setenv("APP_CLAVE", CLAVE_PRUEBA)
    yield USUARIO_PRUEBA, CLAVE_PRUEBA
    gestor.undo()


def iniciar_sesion(cliente, usuario=USUARIO_PRUEBA):
    """Deja una sesión iniciada en el cliente de pruebas y lo devuelve.

    Recibe: `cliente` (Flask test client) y `usuario` (por defecto el de
    prueba). Devuelve el mismo cliente con `session["usuario"]` puesto, sin
    pasar por el formulario de `/login`.
    """
    with cliente.session_transaction() as sesion:
        sesion["usuario"] = usuario
    return cliente


@pytest.fixture()
def app(tmp_path_factory):
    """Aplicación Flask de pruebas, creada con `create_app()`.

    Usa una carpeta de instancia temporal para no ensuciar `instance/` del
    proyecto (AGENTS.md §9).
    """
    aplicacion = create_app(instance_path=str(tmp_path_factory.mktemp("instancia")))
    aplicacion.config.update(TESTING=True)
    return aplicacion


@pytest.fixture()
def cliente_anonimo(app):
    """Cliente de pruebas SIN sesión iniciada (para probar el login)."""
    return app.test_client()


@pytest.fixture()
def cliente(app):
    """Cliente de pruebas con SESIÓN INICIADA.

    Todas las rutas exigen sesión desde que se agregó el login, así que este
    fixture entra con `session["usuario"]` ya puesto. Las pruebas existentes
    siguen comprobando exactamente lo mismo que antes (formulario, cifras,
    descargas) y dejan de recibir el 302 a `/login`.
    """
    return iniciar_sesion(app.test_client())
