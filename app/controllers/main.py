"""Controller de la pantalla principal del Conciliador EO / SO."""

from flask import Blueprint, render_template

bp_main = Blueprint("main", __name__)


@bp_main.get("/")
def inicio():
    """Entrega la pantalla principal.

    Recibe: nada.
    Devuelve: la plantilla `inicio.html` (formulario de carga en español) con
    el título "Conciliador EO / SO".
    """
    return render_template("inicio.html")


@bp_main.get("/health")
def health():
    """Health check público para el monitor de Render (tarea 5).

    Recibe: nada.
    Devuelve: la tupla `("ok", 200, {"Content-Type": "text/plain; charset=utf-8"})`.
    Está en `ENDPOINTS_LIBRES`, así que no pide sesión y responde siempre igual.
    """
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}
