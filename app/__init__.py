"""Fábrica de la aplicación Flask del Conciliador EO / SO."""

import os
import secrets
from pathlib import Path

from flask import Flask

from app.services.almacenamiento import purgar_antiguos

# Raíz del proyecto (un nivel arriba de app/).
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


def cargar_variables_entorno(ruta_env=None):
    """Carga pares CLAVE=VALOR desde el archivo .env si existe.

    No sobrescribe variables ya definidas en el entorno del sistema y no
    registra los valores en ningún log. Si el archivo no existe, no hace nada.
    """
    ruta = Path(ruta_env) if ruta_env else RAIZ_PROYECTO / ".env"
    if not ruta.is_file():
        return

    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


def create_app(instance_path=None):
    """Crea y configura la aplicación Flask y registra los blueprints.

    Recibe: `instance_path`, una ruta de instancia alternativa (opcional).
    Devuelve: la aplicación Flask configurada. Con `instance_path=None` se usa
    la carpeta `instance/` del proyecto (comportamiento normal); con una ruta
    explícita, los archivos temporales de trabajo se guardan allí (AGENTS.md §9:
    las carpetas de trabajo de las pruebas no ensucian `instance/`).
    """
    cargar_variables_entorno()

    if instance_path is None:
        app = Flask(__name__)
    else:
        app = Flask(__name__, instance_path=instance_path)

    # Clave de sesión: se lee de `SECRET_KEY` en `.env`/entorno. Si no existe,
    # se genera una nueva por proceso con `secrets.token_hex(32)`: nunca se usa
    # una cadena fija en el código (AGENTS.md §9). La clave no se registra ni se
    # muestra en pantalla.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config["JSON_AS_ASCII"] = False

    # Retención de datos reales: se purgan los archivos temporales de más de 24
    # horas sobre `app.instance_path`. El service crea `subidas` y `salidas` si
    # no existen; si falla, no tumba el arranque.
    purgar_antiguos(app.instance_path)

    # Registro de blueprints de app/controllers.
    from app.controllers.carga import bp_carga
    from app.controllers.descarga import bp_descarga
    from app.controllers.main import bp_main
    from app.controllers.resultados import bp_resultados

    app.register_blueprint(bp_main)
    app.register_blueprint(bp_carga)
    app.register_blueprint(bp_resultados)
    app.register_blueprint(bp_descarga)

    return app
