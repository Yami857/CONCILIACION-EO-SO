"""Controller del ingreso: usuario y contraseña sin base de datos.

El acceso es una sola usuaria (AGENTS.md §6) y no hay tabla de usuarios: las
credenciales se leen de `.env` / entorno del sistema (`APP_USUARIO` y
`APP_CLAVE`). La clave nunca se escribe en el código, nunca se registra en un
log y nunca se devuelve al navegador (AGENTS.md §9). La regla de acceso vive
aquí, en el controlador, no en las plantillas.
"""

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

# Mensajes exactos de la pantalla de ingreso (en español, sin datos internos).
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos"
MENSAJE_SIN_CONFIGURAR = "El acceso no está configurado en el servidor."

# Endpoints que se pueden usar sin sesión: el formulario y la salida.
ENDPOINTS_LIBRES = ("acceso.login", "acceso.salir")


def _credenciales_configuradas():
    """Lee `APP_USUARIO` y `APP_CLAVE` del entorno.

    Recibe: nada.
    Devuelve: `(usuario, clave)`, ambas cadenas. Si faltan o están vacías,
    devuelve cadenas vacías y la app no permite entrar (no hay usuario por
    defecto). No registra ni muestra los valores.
    """
    usuario = os.environ.get("APP_USUARIO") or ""
    clave = os.environ.get("APP_CLAVE") or ""
    return usuario, clave


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
    email escrito conservado en `usuario`. Si `APP_USUARIO` o `APP_CLAVE`
    faltan o están vacías, ningún intento entra y el mensaje es
    "El acceso no está configurado en el servidor."
    """
    if request.method == "GET":
        return render_template("login.html", usuario="", error=None)

    usuario_ingresado = request.form.get("usuario") or ""
    clave_ingresada = request.form.get("clave") or ""

    usuario_configurado, clave_configurada = _credenciales_configuradas()
    if not usuario_configurado.strip() or not clave_configurada.strip():
        # Sin credenciales en el servidor no se permite ningún intento.
        return (
            render_template(
                "login.html", usuario=usuario_ingresado, error=MENSAJE_SIN_CONFIGURAR
            ),
            200,
        )

    # Las dos comparaciones se hacen siempre, sin cortocircuito.
    usuario_ok = _coincide(usuario_ingresado, usuario_configurado)
    clave_ok = _coincide(clave_ingresada, clave_configurada)

    if usuario_ok and clave_ok:
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
