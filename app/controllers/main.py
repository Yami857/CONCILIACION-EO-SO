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
