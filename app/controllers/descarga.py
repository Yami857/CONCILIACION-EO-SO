"""Controller de la descarga del reporte Excel (AGENTS.md §5)."""

from io import BytesIO

from flask import Blueprint, current_app, flash, redirect, send_file, session, url_for

from app.services.almacenamiento import ruta_salida
from app.services.exportacion import generar_xlsx, leer_filas_exportables

bp_descarga = Blueprint("descarga", __name__)

# Nombre y tipo del archivo descargable (AGENTS.md §5).
NOMBRE_ARCHIVO = "conciliacion_EO_SO.xlsx"
TIPO_XLSX = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@bp_descarga.get("/descargar")
def descargar():
    """Entrega el reporte `.xlsx` de la carga actual, sin volver a llamar a la IA.

    Recibe: nada (lee el identificador opaco de la caché desde
    `session["salida_actual"]` y reconstruye la ruta dentro de
    `instance/salidas`; allí quedaron las filas ya armadas con el análisis del
    agente).
    Devuelve: el `.xlsx` como descarga (`conciliacion_EO_SO.xlsx`), o una
    redirección a la pantalla principal con el mensaje
    "Revisar: vuelva a cargar el archivo de movimientos." cuando no hay caché,
    cuando el identificador no permite una ruta contenida, cuando el archivo ya
    no existe o cuando está dañado. No requiere llave de IA: el análisis se
    reutiliza del archivo guardado (corrección de seguridad R1).
    """
    ident = session.get("salida_actual")
    ruta = ruta_salida(current_app.instance_path, ident)
    if ruta is None or not ruta.is_file():
        # Sin caché, con identificador manipulado o con el archivo borrado: se
        # limpia la sesión y se pide cargar de nuevo. Nunca se lee fuera de
        # `instance/salidas`.
        session.pop("archivo_actual", None)
        session.pop("salida_actual", None)
        flash("Revisar: vuelva a cargar el archivo de movimientos.", "error")
        return redirect(url_for("main.inicio"))

    try:
        filas = leer_filas_exportables(ruta)
    except (OSError, ValueError):
        # Caché ilegible o dañada: se pide cargar de nuevo, sin caerse.
        session.pop("salida_actual", None)
        flash("Revisar: vuelva a cargar el archivo de movimientos.", "error")
        return redirect(url_for("main.inicio"))

    buffer = BytesIO()
    generar_xlsx(filas, buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=NOMBRE_ARCHIVO,
        mimetype=TIPO_XLSX,
    )
