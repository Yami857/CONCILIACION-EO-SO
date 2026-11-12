"""Controller de la carga del archivo de movimientos (regla R1)."""

from flask import Blueprint, current_app, flash, redirect, request, session, url_for

from app.services.almacenamiento import (
    borrar_carga,
    nuevo_identificador,
    ruta_subida,
)
from app.services.carga import r1_cargar_movimientos

bp_carga = Blueprint("carga", __name__)


def _guardar_archivo(archivo):
    """Guarda el Excel subido en `instance/subidas` con un nombre opaco.

    Recibe: `archivo`, el FileStorage del formulario.
    Devuelve: `(ident, ruta)` del archivo guardado, o `(None, None)` si el
    identificador no permite una ruta contenida. El nombre base es un
    identificador opaco (`uuid4().hex`), nunca una ruta: la sesión guardará solo
    el identificador (corrección de seguridad R1). Crea la carpeta si no existe
    y nunca modifica el archivo original del usuario (AGENTS.md §9).
    """
    ident = nuevo_identificador()
    ruta = ruta_subida(current_app.instance_path, ident)
    if ruta is None:
        return None, None

    ruta.parent.mkdir(parents=True, exist_ok=True)
    archivo.stream.seek(0)
    archivo.save(ruta)
    return ident, ruta


@bp_carga.post("/cargar")
def cargar():
    """Recibe el Excel del formulario, lo guarda y pasa a los resultados.

    Recibe: la petición POST con el campo de archivo `archivo`.
    Devuelve: una redirección a `/resultados` si R1 acepta el archivo (con un
    mensaje flash de éxito) o a la pantalla principal con el error en español
    (con la palabra "Revisar") si R1 lo rechaza.
    """
    archivo = request.files.get("archivo")
    nombre = (archivo.filename or "").strip() if archivo is not None else ""

    ident = None
    ruta = None
    if archivo is not None and nombre.lower().endswith(".xlsx"):
        # Se guarda una copia propia del Excel y se valida esa copia, para que
        # el análisis posterior no dependa del archivo original del usuario.
        try:
            ident, ruta = _guardar_archivo(archivo)
        except OSError:
            flash(
                "Revisar: no se pudo guardar el archivo en el servidor. "
                "Cierre el archivo si está abierto en Excel e intente de nuevo.",
                "error",
            )
            return redirect(url_for("main.inicio"))

        if ruta is None:
            flash("Revisar: vuelva a cargar el archivo de movimientos.", "error")
            return redirect(url_for("main.inicio"))

        # Al cargar un archivo nuevo se borran el Excel y la caché de la carga
        # anterior de esta misma sesión (corrección de seguridad R1).
        borrar_carga(current_app.instance_path, session.get("archivo_actual"))

        resultado = r1_cargar_movimientos(ruta)
    else:
        # Sin archivo o con formato distinto a .xlsx: R1 responde el mensaje.
        resultado = r1_cargar_movimientos(archivo)

    if resultado["ok"]:
        # En sesión queda SOLO el identificador opaco, nunca la ruta.
        session["archivo_actual"] = ident
        # El reporte descargable anterior ya no corresponde a esta carga:
        # `/resultados` arma y guarda el nuevo (sin volver a llamar a la IA al
        # descargar).
        session.pop("salida_actual", None)
        flash(resultado["mensaje"], "success")
        return redirect(url_for("resultados.ver"))

    # R1 rechazó el archivo: se descarta la copia y no se genera reporte.
    if ruta is not None:
        try:
            ruta.unlink()
        except OSError:
            pass
    session.pop("archivo_actual", None)
    session.pop("salida_actual", None)
    flash(resultado["mensaje"], "error")
    return redirect(url_for("main.inicio"))
