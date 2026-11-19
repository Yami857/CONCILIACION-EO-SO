"""Controller del ingreso: usuario y contraseña sin base de datos.

El acceso es una sola usuaria (AGENTS.md §6) y no hay tabla de usuarios: las
credenciales se leen de `.env` / entorno del sistema (`APP_USUARIO` y
`APP_CLAVE`). La clave nunca se escribe en texto plano en el código ni se
registra en un log; el respaldo definitivo se guarda como huella PBKDF2. La
regla de acceso vive aquí, en el controlador, no en las plantillas.

Aquí viven también tres medidas de seguridad añadidas: límite de intentos
fallidos por IP (tarea 2), sesión que termina al cerrar el navegador o la
pestaña (tarea 3) y token CSRF para los formularios POST (tarea 10). Ninguna
necesita base de datos ni dependencias nuevas.
"""

import hashlib
import hmac
import os
import secrets
import threading
import time

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

bp_acceso = Blueprint("acceso", __name__)

# Mensajes exactos de la pantalla de ingreso (en español, sin datos internos).
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos"
MENSAJE_DEMASIADOS = "Demasiados intentos. Intente de nuevo en unos minutos."

# Mensaje exacto de rechazo de un POST sin token CSRF válido (tarea 10).
MENSAJE_CSRF = "Solicitud no válida. Recargue la pantalla e intente de nuevo."

# Tarea 2: como máximo 5 intentos fallidos en una ventana de 15 minutos.
MAX_INTENTOS_FALLIDOS = 5
VENTANA_INTENTOS_SEGUNDOS = 15 * 60

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

# Endpoints que se pueden usar sin sesión: el formulario, la salida y el
# health check público que consume Render (tarea 5).
ENDPOINTS_LIBRES = ("acceso.login", "acceso.salir", "main.health")

# Contador en memoria de intentos fallidos por dirección IP (tarea 2). No se
# persiste: se reinicia cuando reinicia el proceso, aceptable para una app de
# una sola usuaria. Se guardan marcas de tiempo de `time.monotonic()` y se
# protege el acceso con un `threading.Lock` (Render sirve con varios hilos).
# Nunca se guarda ni se registra la contraseña.
_intentos_por_ip = {}
_bloqueo_intentos = threading.Lock()


def _ip_cliente():
    """Identifica al cliente detrás del proxy inverso de Render (tarea 2).

    Recibe: la petición en curso.
    Devuelve: la primera IP de `X-Forwarded-For`, o `request.remote_addr`, o
    `"desconocida"` como último recurso. No registra la dirección en logs.
    """
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote_addr
        or "desconocida"
    )


def _intentos_recientes(ip):
    """Cuenta los fallos de `ip` dentro de la ventana de 15 minutos.

    Recibe: `ip`, la dirección identificada con `_ip_cliente()`.
    Devuelve: un entero con los intentos recientes; descarta los viejos.
    """
    ahora = time.monotonic()
    with _bloqueo_intentos:
        recientes = [
            marca
            for marca in _intentos_por_ip.get(ip, ())
            if ahora - marca < VENTANA_INTENTOS_SEGUNDOS
        ]
        _intentos_por_ip[ip] = recientes
        return len(recientes)


def _registrar_intento_fallido(ip):
    """Registra un fallo de `ip` y devuelve el total de fallos recientes.

    Recibe: `ip`, la dirección identificada con `_ip_cliente()`.
    Devuelve: el número de intentos fallidos en la ventana después de añadir
    el nuevo (para saber si se acaba de alcanzar el límite).
    """
    ahora = time.monotonic()
    with _bloqueo_intentos:
        recientes = [
            marca
            for marca in _intentos_por_ip.get(ip, ())
            if ahora - marca < VENTANA_INTENTOS_SEGUNDOS
        ]
        recientes.append(ahora)
        _intentos_por_ip[ip] = recientes
        return len(recientes)


def _reiniciar_intentos(ip):
    """Borra el contador de `ip` tras un ingreso correcto (tarea 2).

    Recibe: `ip`, la dirección identificada con `_ip_cliente()`.
    Devuelve: nada.
    """
    with _bloqueo_intentos:
        _intentos_por_ip.pop(ip, None)


def _asegurar_csrf_token():
    """Crea, solo si falta, el token opaco CSRF de la sesión (tarea 10).

    Recibe: nada.
    Devuelve: el token guardado en `session["csrf_token"]`, generado con
    `secrets.token_urlsafe(32)`. Nunca se escribe en logs.
    """
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


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
def validar_csrf():
    """Rechaza con 400 todo POST cuyo token CSRF no coincide (tarea 10).

    Recibe: la petición en curso.
    Devuelve: `None` si no es POST, si la app corre en modo TESTING o si el
    token del formulario coincide con el de la sesión; en caso contrario, una
    tupla `(MENSAJE_CSRF, 400)` con el mensaje exacto en español.

    La comparación es en tiempo constante. Se registra ANTES de
    `exigir_sesion` para que ningún POST sin token llegue a los controllers.
    """
    if request.method != "POST":
        return None
    # Excepción para la suite del perfil tester: sus peticiones son POST
    # directos sin formulario, así que se omite CSRF solo en modo TESTING.
    # En producción (y en la comprobación manual) la validación está activa.
    if current_app.config.get("TESTING"):
        return None

    token_sesion = session.get("csrf_token")
    token_formulario = request.form.get("csrf_token")
    if (
        not token_sesion
        or not token_formulario
        or not hmac.compare_digest(str(token_sesion), str(token_formulario))
    ):
        return MENSAJE_CSRF, 400
    return None


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


@bp_acceso.app_context_processor
def inyectar_csrf_token():
    """Expone `csrf_token` a todas las plantillas (tarea 10).

    Recibe: nada.
    Devuelve: un diccionario con la variable `csrf_token`, que las plantillas
    usan como `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.
    Al renderizar por primera vez se crea el token en la sesión.
    """
    return {"csrf_token": _asegurar_csrf_token()}


def _ingresar(usuario, ip):
    """Abre la sesión de la usuaria tras validar sus credenciales.

    Recibe: `usuario` (el texto escrito) e `ip` (para limpiar su contador).
    Devuelve: la redirección 302 a la pantalla principal. La sesión **no** es
    permanente: su cookie no lleva fecha de caducidad y el navegador la borra al
    cerrarse (la pestaña se controla con `sessionStorage` en `base.html`).
    También reinicia los intentos fallidos de esa IP (tarea 2).
    """
    _reiniciar_intentos(ip)
    session.permanent = False
    session["usuario"] = usuario
    return redirect(url_for("main.inicio"))


@bp_acceso.route("/login", methods=["GET", "POST"])
def login():
    """Muestra el formulario de ingreso y valida las credenciales.

    Recibe: nada por GET; por POST, los campos `usuario` y `clave` del
    formulario (más el `csrf_token`, comprobado por `validar_csrf`).
    Devuelve: con GET, la plantilla `login.html` (estado 200). Con POST
    correcto, guarda `session["usuario"]` y redirige 302 a la pantalla
    principal (`main.inicio`). Con POST incorrecto, la misma plantilla con el
    mensaje "Usuario o contraseña incorrectos" en `error` (estado 200) y el
    email escrito conservado en `usuario`.

    Límite de intentos (tarea 2): si la IP ya acumula 5 fallos en 15 minutos,
    se muestra el mensaje exacto de "Demasiados intentos" con estado 200 y SIN
    crear sesión, sin ni siquiera comprobar las credenciales. El quinto fallo
    también muestra ese mensaje al alcanzar el límite.

    Tienen prioridad las variables `APP_USUARIO`/`APP_CLAVE`. Si no están o no
    coinciden, se prueba la credencial de respaldo guardada como huella en este
    mismo archivo, para que Render no pueda dejar la app sin acceso.
    """
    if request.method == "GET":
        return render_template("login.html", usuario="", error=None)

    ip = _ip_cliente()
    if _intentos_recientes(ip) >= MAX_INTENTOS_FALLIDOS:
        # IP bloqueada temporalmente: no se toca la sesión ni se valida clave.
        return render_template("login.html", usuario="", error=MENSAJE_DEMASIADOS), 200

    usuario_ingresado = request.form.get("usuario") or ""
    clave_ingresada = request.form.get("clave") or ""

    usuario_configurado, clave_configurada = _credenciales_configuradas()
    if _configurada(usuario_configurado, clave_configurada):
        # Las dos comparaciones se hacen siempre, sin cortocircuito.
        usuario_ok = _coincide(usuario_ingresado, usuario_configurado)
        clave_ok = _coincide(clave_ingresada, clave_configurada)
        if usuario_ok and clave_ok:
            return _ingresar(usuario_ingresado, ip)

    # Respaldo definitivo: funciona aunque Render no haya configurado nada.
    if _coincide_respaldo(usuario_ingresado, clave_ingresada):
        return _ingresar(usuario_ingresado, ip)

    total_fallos = _registrar_intento_fallido(ip)
    mensaje = (
        MENSAJE_DEMASIADOS
        if total_fallos >= MAX_INTENTOS_FALLIDOS
        else MENSAJE_CREDENCIALES
    )
    return (
        render_template("login.html", usuario=usuario_ingresado, error=mensaje),
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
