"""Controller del ingreso: usuario y contraseña sin base de datos.

El acceso es una sola usuaria (AGENTS.md §6) y no hay tabla de usuarios: las
credenciales se leen de `.env` / entorno del sistema (`APP_USUARIO` y
`APP_CLAVE`). La clave nunca se escribe en texto plano en el código ni se
registra en un log; el respaldo definitivo se guarda como huella PBKDF2. La
regla de acceso vive aquí, en el controlador, no en las plantillas.
"""

import hashlib
import hmac
import os

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

bp_acceso = Blueprint("acceso", __name__)

# Mensaje exacto de la pantalla de ingreso (en español, sin datos internos).
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos"

# Variables de entorno que, si están definidas, tienen prioridad.
VARIABLE_USUARIO = "APP_USUARIO"
VARIABLE_CLAVE = "APP_CLAVE"

# Ingreso de respaldo, definitivo y guardado SIN la clave en texto plano.
# Render suele dejar las variables de entorno vacías al redesplegar; esta
# credencial internada en la app evita quedarse sin acceso. La clave real se
# deriva con PBKDF2-HMAC-SHA256 (300000 iteraciones) y se compara en tiempo
# constante. Cambiar estos tres valores cambia la clave de respaldo.
USUARIO_RESPALDO = "admon@montecillos.com"
SAL_RESPALDO = "17a2b8895a5d5538a21a3013460e19f5"
HASH_RESPALDO = "2b9c4deb0382b9650fed30e73b73b105d2203914c023194bd24df9d24e61f933"
ITERACIONES_RESPALDO = 300000

# Endpoints que se pueden usar sin sesión: el formulario y la salida.
ENDPOINTS_LIBRES = ("acceso.login", "acceso.salir")


def _credenciales_configuradas():
    """Lee `APP_USUARIO` y `APP_CLAVE` del entorno.

    Recibe: nada.
    Devuelve: `(usuario, clave)`, ambas cadenas. Si faltan o están vacías,
    devuelve cadenas vacías y la app no permite entrar (no hay usuario por
    defecto). No registra ni muestra los valores.
    """
    usuario = os.environ.get(VARIABLE_USUARIO) or ""
    clave = os.environ.get(VARIABLE_CLAVE) or ""
    return usuario, clave


def _configurada(usuario, clave):
    """Indica si las dos credenciales están presentes en el entorno.

    Recibe: `usuario` y `clave` leídos del entorno.
    Devuelve: `True` solo si ambas tienen contenido.
    """
    return bool(usuario.strip()) and bool(clave.strip())


def _coincide_respaldo(usuario, clave):
    """Valida la credencial de respaldo guardada como huella PBKDF2.

    Recibe: `usuario` y `clave` escritos en el formulario.
    Devuelve: `True` si coinciden con la credencial definitiva. La clave no
    está en texto plano en el repositorio: se deriva con PBKDF2 y se compara
    en tiempo constante. Se usa cuando las variables del entorno no sirven
    (están vacías o no son las correctas, lo que pasó en Render).
    """
    if not hmac.compare_digest(usuario.encode("utf-8"), USUARIO_RESPALDO.encode("utf-8")):
        return False
    derivada = hashlib.pbkdf2_hmac(
        "sha256",
        clave.encode("utf-8"),
        bytes.fromhex(SAL_RESPALDO),
        ITERACIONES_RESPALDO,
    )
    return hmac.compare_digest(derivada, bytes.fromhex(HASH_RESPALDO))


def _coincide(valor_ingresado, valor_configurado):
    """Compara dos textos en bytes con tiempo constante.

    Recibe: `valor_ingresado` (lo que escribió la usuaria) y
    `valor_configurado` (el valor del entorno).
    Devuelve: `True` si son idénticos. Se compara con
    `hmac.compare_digest` sobre bytes y no con `==`, para no filtrar
    información por el tiempo de respuesta y para que las tildes y demás
    acentos no provoquen errores.
    """
    return hmac.compare_digest(
        valor_ingresado.encode("utf-8"), valor_configurado.encode("utf-8")
    )


@bp_acceso.before_app_request
def exigir_sesion():
    """Regla de acceso: toda pantalla exige una sesión iniciada.

    Recibe: la petición en curso.
    Devuelve: `None` (deja pasar) cuando el endpoint es libre, cuando es el
    espacio del formulario de acceso o cuando la sesión ya tiene
    `session["usuario"]`; en cualquier otro caso, una redirección 302 a
    `/login`. Un endpoint desconocido (`request.endpoint is None`, por ejemplo
    un 404) no rompe: se deja pasar para que Flask responda su 404 normal.
    """
    if request.endpoint is None or request.endpoint in ENDPOINTS_LIBRES:
        return None
    if session.get("usuario"):
        return None
    return redirect(url_for("acceso.login"))


@bp_acceso.route("/login", methods=["GET", "POST"])
def login():
    """Muestra el formulario de ingreso y valida las credenciales.

    Recibe: nada por GET; por POST, los campos `usuario` y `clave` del
    formulario.
    Devuelve: con GET, la plantilla `login.html` (estado 200). Con POST
    correcto, guarda `session["usuario"]` y redirige 302 a la pantalla
    principal (`main.inicio`). Con POST incorrecto, la misma plantilla con el
    mensaje "Usuario o contraseña incorrectos" en `error` (estado 200) y el
    email escrito conservado en `usuario`.

    Tienen prioridad las variables `APP_USUARIO`/`APP_CLAVE`. Si no están o no
    coinciden, se prueba la credencial de respaldo guardada como huella en este
    mismo archivo, para que Render no pueda dejar la app sin acceso.
    """
    if request.method == "GET":
        return render_template("login.html", usuario="", error=None)

    usuario_ingresado = request.form.get("usuario") or ""
    clave_ingresada = request.form.get("clave") or ""

    usuario_configurado, clave_configurada = _credenciales_configuradas()
    if _configurada(usuario_configurado, clave_configurada):
        # Las dos comparaciones se hacen siempre, sin cortocircuito.
        usuario_ok = _coincide(usuario_ingresado, usuario_configurado)
        clave_ok = _coincide(clave_ingresada, clave_configurada)
        if usuario_ok and clave_ok:
            session["usuario"] = usuario_ingresado
            return redirect(url_for("main.inicio"))

    # Respaldo definitivo: funciona aunque Render no haya configurado nada.
    if _coincide_respaldo(usuario_ingresado, clave_ingresada):
        session["usuario"] = usuario_ingresado
        return redirect(url_for("main.inicio"))

    return (
        render_template(
            "login.html", usuario=usuario_ingresado, error=MENSAJE_CREDENCIALES
        ),
        200,
    )


@bp_acceso.get("/salir")
def salir():
    """Cierra la sesión y vuelve al formulario de ingreso.

    Recibe: nada.
    Devuelve: una redirección 302 a `/login` después de `session.clear()`.
    Funciona aunque no haya sesión iniciada (es un endpoint libre).
    """
    session.clear()
    return redirect(url_for("acceso.login"))
