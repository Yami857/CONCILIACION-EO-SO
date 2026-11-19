"""Fábrica de la aplicación Flask del Conciliador EO / SO."""

import os
import secrets
from pathlib import Path

from flask import Flask, flash, redirect, url_for

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

    # La sesión NO es permanente: la cookie no lleva Max-Age/Expires y el
    # navegador la elimina al cerrarse. Al cerrar solo la pestaña, el marcador
    # de `sessionStorage` de `base.html` obliga a entrar de nuevo.
    # La cookie nunca es legible desde JavaScript y SameSite=Lax se aplica
    # SIEMPRE (también en local), no solo en Render.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Tarea 4 — límite de tamaño de subida: 25 MB. Un cuerpo mayor provoca un
    # 413 que se convierte en un mensaje en español (ver el errorhandler abajo).
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

    # En Render (`RENDER=true`, siempre HTTPS detrás de su proxy) la cookie se
    # envía solo por HTTPS y se prefiere el esquema https para las URL. En local
    # no se activa nada de esto, para no romper http://127.0.0.1:5000.
    if os.environ.get("RENDER"):
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            PREFERRED_URL_SCHEME="https",
        )

    # Retención de datos reales: se purgan los archivos temporales de más de 24
    # horas sobre `app.instance_path`. El service crea `subidas` y `salidas` si
    # no existen; si falla, no tumba el arranque.
    purgar_antiguos(app.instance_path)

    # Registro de blueprints de app/controllers.
    from app.controllers.acceso import bp_acceso
    from app.controllers.carga import bp_carga
    from app.controllers.descarga import bp_descarga
    from app.controllers.main import bp_main
    from app.controllers.resultados import bp_resultados

    # El blueprint de acceso va primero: sus `before_app_request` son la única
    # puerta de entrada de las demás pantallas.
    app.register_blueprint(bp_acceso)
    app.register_blueprint(bp_main)
    app.register_blueprint(bp_carga)
    app.register_blueprint(bp_resultados)
    app.register_blueprint(bp_descarga)

    @app.errorhandler(413)
    def archivo_demasiado_grande(error):
        """Convierte el 413 técnico en un aviso en español (tarea 4).

        Recibe: el error 413 de Werkzeug (cuerpo de petición demasiado grande).
        Devuelve: un flash con la palabra «Revisar» y una redirección 302 a
        `main.inicio`, para que nunca se vea una página técnica de error.
        """
        flash("Revisar: el archivo es demasiado grande. El límite es 25 MB.", "error")
        return redirect(url_for("main.inicio"))

    return app
