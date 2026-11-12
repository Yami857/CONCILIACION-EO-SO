"""Controller de la pantalla de resultados: ejecuta R1 a R7."""

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)

from app.services.agente import aplicar_analisis, consultar_agente, texto_motivo
from app.services.agrupacion import r4_agrupar_por_cruce
from app.services.almacenamiento import ruta_salida, ruta_subida
from app.services.carga import r1_cargar_movimientos
from app.services.costos import r5_detectar_costo_mayor
from app.services.emparejamiento import r3_emparejar
from app.services.exportacion import (
    construir_filas_exportables,
    guardar_filas_exportables,
)
from app.services.filtro import r2_filtrar_eo_so
from app.services.revision import r6_marcar_revisar, r7_marcar_semaforos

bp_resultados = Blueprint("resultados", __name__)


def _limpiar_sesion():
    """Quita los identificadores temporales de la sesión.

    Recibe: nada.
    Devuelve: nada. Se usa cuando la sesión no permite reconstruir una ruta
    contenida dentro de `instance/` (corrección de seguridad R1).
    """
    session.pop("archivo_actual", None)
    session.pop("salida_actual", None)


def _guardar_salida(cruces, registros, ident):
    """Arma y guarda las filas del reporte para la descarga, sin llamar a la IA.

    Recibe: `cruces` (con el `analisis` del agente ya aplicado), `registros`
    (las filas EO/SO de R2, en el orden original del archivo) e `ident`, el
    identificador opaco de la carga actual.
    Devuelve: la ruta del JSON de caché en `instance/salidas` o `None` si el
    identificador no permite una ruta contenida. En sesión queda solo el
    identificador (`session["salida_actual"] = ident`), nunca la ruta, para que
    `/descargar` la reconstruya: la descarga no vuelve a consultar al agente
    (AGENTS.md §5; corrección de seguridad R1).
    """
    filas = construir_filas_exportables(cruces, registros)
    destino = ruta_salida(current_app.instance_path, ident)
    if destino is None:
        session.pop("salida_actual", None)
        return None

    destino = guardar_filas_exportables(filas, destino)
    session["salida_actual"] = ident
    return destino


@bp_resultados.get("/resultados")
def ver():
    """Arma el resumen de los cruces EO-SO de la carga actual (R1 a R7).

    Recibe: nada (lee el identificador opaco de la carga desde
    `session["archivo_actual"]` y reconstruye la ruta dentro de
    `instance/subidas`).
    Devuelve: la plantilla `resultados.html` con `resumen` (conteos de R2 a R7 y
    los conteos de líneas de §7: `lineas_eo`, `lineas_so` y `eo_con_dos_lineas`;
    `cruces` son los pares reales de R3 y `entradas` el total de filas de la
    tabla), `cruces` (con `estado_revision`, `semaforo`, `etiqueta_semaforo` y
    el `analisis` del agente de IA), `cifras`, `ia_disponible` y `ia_motivo`
    (texto corto en español, sin secretos); si la sesión no permite una ruta
    contenida o si no hay archivo en sesión, una redirección a la pantalla
    principal con un mensaje flash.
    """
    ident = session.get("archivo_actual")
    ruta = ruta_subida(current_app.instance_path, ident)
    if ruta is None:
        if ident:
            # Identificador manipulado (`../`, ruta absoluta) o de otro
            # formato: no se lee nada fuera de `instance/subidas` y se limpia
            # la sesión (corrección de seguridad R1).
            _limpiar_sesion()
            flash("Revisar: vuelva a cargar el archivo de movimientos.", "error")
            return redirect(url_for("main.inicio"))
        flash(
            "Revisar: no hay ningún archivo cargado. Seleccione el Excel de "
            "movimientos (.xlsx) e intente de nuevo.",
            "error",
        )
        return redirect(url_for("main.inicio"))

    if not ruta.is_file():
        flash(
            "Revisar: no hay ningún archivo cargado. Seleccione el Excel de "
            "movimientos (.xlsx) e intente de nuevo.",
            "error",
        )
        return redirect(url_for("main.inicio"))

    # R1: carga y validación del Excel guardado en la carga anterior.
    carga = r1_cargar_movimientos(ruta)
    if not carga["ok"]:
        flash(carga["mensaje"], "error")
        return redirect(url_for("main.inicio"))

    # R2: solo filas EO y SO.
    registros_eo_so, total_eo, total_so = r2_filtrar_eo_so(carga["registros"])

    # R3: emparejamiento SO = EO − 1 agrupando líneas por No. Físico.
    emparejamiento = r3_emparejar(registros_eo_so)
    pares = emparejamiento["pares"]

    # R4: un cruce por par, sumando todas las líneas de cada documento.
    cruces = r4_agrupar_por_cruce(pares)

    # R5: costo_eo_mayor por Total del documento, su diferencia y las cifras
    # de control de AGENTS.md §7.
    cruces, cifras = r5_detectar_costo_mayor(cruces)

    # Conteos de líneas de AGENTS.md §7, sobre los cruces reales: se toman
    # antes de que R6 agregue las entradas de los registros sin pareja.
    lineas_eo = sum(len(cruce["lineas_eo"]) for cruce in cruces)
    lineas_so = sum(len(cruce["lineas_so"]) for cruce in cruces)
    eo_con_dos_lineas = len(
        [cruce for cruce in cruces if len(cruce["lineas_eo"]) > 1]
    )

    # R6: marca "Revisar" (celdas vacías, No. Físico no numérico o duplicado)
    # y agrega las entradas de los registros que no formaron par.
    cruces, resumen_revision = r6_marcar_revisar(
        cruces, emparejamiento, registros_eo_so
    )

    # R7: semáforo rojo/verde con su texto, según el costo y el estado.
    cruces, resumen_semaforo = r7_marcar_semaforos(cruces)

    # Agente de IA: una sola llamada por lote, después de R7. Si falta la llave,
    # se agota el cupo, hay timeout o la respuesta no cumple el contrato, el
    # análisis de cada cruce queda en "no indicado" y la app sigue funcionando.
    resultado_ia = consultar_agente(cruces)
    cruces = aplicar_analisis(cruces, resultado_ia)
    ia_disponible = bool(resultado_ia.get("ok"))
    ia_motivo = "" if ia_disponible else texto_motivo(resultado_ia.get("motivo"))

    # Salida — Reporte Excel (AGENTS.md §5): se arman las filas del reporte una
    # sola vez, con el análisis que acaba de redactar el agente, y se guardan
    # para que `/descargar` NO vuelva a llamar a la IA.
    _guardar_salida(cruces, registros_eo_so, ident)

    # `pares` es la salida de R3: solo los cruces EO-SO reales. R6 agrega
    # entradas de revisión para los registros que no formaron par
    # (`EO-<fisico>-SIN-SO`, `SO-<fisico>-SIN-EO` y los `No. Físico` no
    # numéricos); esas entradas no son cruces y solo suman en `entradas`, el
    # total de filas de la tabla. `alertas_costo` es el conteo de R5.
    resumen = {
        "total_registros": len(registros_eo_so),
        "total_eo": total_eo,
        "total_so": total_so,
        "cruces": len(pares),
        "entradas": len(cruces),
        "sin_pareja": len(emparejamiento["eo_sin_pareja"])
        + len(emparejamiento["so_sin_pareja"]),
        # Conteos de líneas de AGENTS.md §7.
        "lineas_eo": lineas_eo,
        "lineas_so": lineas_so,
        "eo_con_dos_lineas": eo_con_dos_lineas,
        # Conteos de R6 y R7, calculados sobre los datos y no sobre etiquetas
        # escritas a mano.
        "en_revisar": resumen_revision["en_revisar"],
        "correctos": resumen_revision["correctos"],
        "alertas_costo": cifras["cruces_total_mayor"],
        "rojos": resumen_semaforo["rojos"],
        "verdes": resumen_semaforo["verdes"],
    }

    return render_template(
        "resultados.html",
        resumen=resumen,
        cruces=cruces,
        cifras=cifras,
        ia_disponible=ia_disponible,
        ia_motivo=ia_motivo,
    )
