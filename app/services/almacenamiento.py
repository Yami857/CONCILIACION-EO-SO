"""Service del almacenamiento temporal de la app (corrección de seguridad R1).

Los archivos de trabajo viven en `instance/subidas` (el Excel copiado) y
`instance/salidas` (la caché JSON del reporte). La sesión guarda **solo un
identificador opaco** (`uuid4().hex`), nunca una ruta: así la cookie no expone
nombres de usuario ni rutas absolutas del equipo (AGENTS.md §9: secretos y
datos de la empresa fuera del repositorio y de la sesión).
"""

import re
import time
from pathlib import Path
from uuid import uuid4

# Subcarpetas de trabajo dentro de `instance/`.
SUBCARPETA_SUBIDAS = "subidas"
SUBCARPETA_SALIDAS = "salidas"

# Extensiones de cada tipo de archivo temporal.
EXTENSION_SUBIDA = ".xlsx"
EXTENSION_SALIDA = ".json"

# Antigüedad máxima de los archivos temporales (horas).
HORAS_RETENCION = 24

# Identificador aceptado: exactamente 32 caracteres hexadecimales en minúscula,
# el formato de `uuid4().hex`. Cualquier otra cosa es una manipulación.
_IDENTIFICADOR_VALIDO = re.compile(r"^[0-9a-f]{32}$")


# Corrección de seguridad R1 — identificadores opacos
# Recibe: nada.
# Devuelve: un identificador nuevo (`uuid4().hex`) para nombrar el Excel y su
#         caché. Nunca se forma con datos del usuario ni con rutas.
def nuevo_identificador():
    """Devuelve un identificador opaco para la carga actual."""
    return uuid4().hex


# Corrección de seguridad R1 — contención de rutas
# Recibe: `instance_path` (raíz de `instance/`), `subcarpeta` (`subidas` o
#         `salidas`), `ident` (el identificador de la sesión) y `extension`.
# Devuelve: la ruta resuelta dentro de la subcarpeta, o `None` cuando el
#         identificador no tiene el formato opaco o la ruta se sale de la
#         subcarpeta (por ejemplo `../`, una ruta absoluta o una unidad de
#         Windows). No crea carpetas ni lee archivos.
def _ruta_contenida(instance_path, subcarpeta, ident, extension):
    """Arma una ruta temporal y verifica que quede dentro de su subcarpeta."""
    if not isinstance(ident, str) or not _IDENTIFICADOR_VALIDO.match(ident):
        return None

    carpeta = (Path(instance_path) / subcarpeta).resolve()
    ruta = (carpeta / f"{ident}{extension}").resolve()

    # Validación de contención exigida por la corrección R1.
    if not ruta.is_relative_to(carpeta):
        return None
    return ruta


# Corrección de seguridad R1 — ruta del Excel de la carga
# Recibe: `instance_path` e `ident`.
# Devuelve: `instance/subidas/<ident>.xlsx` validada, o `None` si no cumple la
#         contención.
def ruta_subida(instance_path, ident):
    """Devuelve la ruta validada del Excel de la carga."""
    return _ruta_contenida(instance_path, SUBCARPETA_SUBIDAS, ident, EXTENSION_SUBIDA)


# Corrección de seguridad R1 — ruta de la caché del reporte
# Recibe: `instance_path` e `ident`.
# Devuelve: `instance/salidas/<ident>.json` validada, o `None` si no cumple la
#         contención.
def ruta_salida(instance_path, ident):
    """Devuelve la ruta validada de la caché del reporte."""
    return _ruta_contenida(instance_path, SUBCARPETA_SALIDAS, ident, EXTENSION_SALIDA)


# Corrección de seguridad R1 — limpieza al cargar un archivo nuevo
# Recibe: `instance_path` e `ident` de la carga anterior (puede ser `None`).
# Devuelve: nada. Borra el `.xlsx` y el `.json` de esa carga si existían. Nunca
#         lanza una excepción hacia el controller y nunca toca rutas fuera de
#         `instance/subidas` e `instance/salidas`.
def borrar_carga(instance_path, ident):
    """Borra el Excel y la caché de una carga anterior."""
    if not isinstance(ident, str) or not ident:
        return

    for ruta in (
        ruta_subida(instance_path, ident),
        ruta_salida(instance_path, ident),
    ):
        if ruta is None:
            continue
        try:
            ruta.unlink(missing_ok=True)
        except OSError:
            # Archivo bloqueado o ya borrado: la carga nueva sigue igual.
            pass


# Corrección de seguridad R1 — retención de datos reales
# Recibe: `instance_path` y, opcionalmente, las horas de retención (24).
# Devuelve: nada. Borra los `.xlsx` de `instance/subidas` y los `.json` de
#         `instance/salidas` con más de 24 horas de antigüedad. Crea las
#         carpetas si no existen; si no se pueden crear, no falla.
def purgar_antiguos(instance_path, horas=HORAS_RETENCION):
    """Purga los archivos temporales con más de 24 horas de antigüedad."""
    limite = time.time() - (horas * 3600)

    for subcarpeta, extension in (
        (SUBCARPETA_SUBIDAS, EXTENSION_SUBIDA),
        (SUBCARPETA_SALIDAS, EXTENSION_SALIDA),
    ):
        carpeta = Path(instance_path) / subcarpeta
        try:
            # La carpeta de trabajo se crea al arrancar si no existe.
            carpeta.mkdir(parents=True, exist_ok=True)
            archivos = list(carpeta.glob(f"*{extension}"))
        except OSError:
            continue

        for ruta in archivos:
            try:
                if ruta.is_file() and ruta.stat().st_mtime < limite:
                    ruta.unlink()
            except OSError:
                # Archivo bloqueado o ya borrado: se ignora.
                pass
