"""Pruebas de las reglas R6 (`"Revisar"`) y R7 (semáforos).

Fuente: AGENTS.md §3 R6 y R7, §7 (0 cruces en Revisar, 89 correctos; 50 rojos y
39 verdes por las 50 alertas de costo) y §8 (casos límite: EO sin SO, SO sin
EO, `No. Físico` no numérico, celdas obligatorias vacías, físico duplicado,
campos numéricos inválidos y fecha inválida).

El archivo real se toma del fixture `pipeline_real`; los emparejamientos
sintéticos se construyen en memoria y nunca tocan `INSUMOS/`.
"""

import pytest

from app.services.agrupacion import r4_agrupar_por_cruce
from app.services.costos import r5_detectar_costo_mayor
from app.services.emparejamiento import r3_emparejar
from app.services.filtro import r2_filtrar_eo_so
from app.services.revision import (
    CORRECTO,
    REVISAR,
    ROJO,
    VERDE,
    r6_marcar_revisar,
    r7_marcar_semaforos,
)

# Cifras de control de AGENTS.md §7.
CRUCES_ESPERADOS = 89
EN_REVISAR_ESPERADOS = 0
CORRECTOS_ESPERADOS = 89
ROJOS_ESPERADOS = 50
VERDES_ESPERADOS = 39


def _linea(fisico, **cambios):
    """Arma una línea EO/SO completa en memoria, con las 14 columnas de §2."""
    base = {
        "Fecha": "2026-11-04",
        "Bodega": 400,
        "Tipo Doc.": "EO",
        "Descripción Documento": "ENTRADA  TRANSFORMACION",
        "No. Documento": 1,
        "No. Físico": fisico,
        "No. Artículo": 1000,
        "Descripción Artículo": "ARTICULO DE PRUEBA",
        "Cantidad": 10,
        "Unidad Med.": "KLG",
        "Kilos": 10,
        "Costo Uni.": 100,
        "Total": 1000,
        "Usuario Aplica": "CN03",
    }
    base.update(cambios)
    return base


def _linea_so(fisico, **cambios):
    """Línea de tipo SO completa; por defecto con Total menor que la EO."""
    base = {
        "Tipo Doc.": "SO",
        "Descripción Documento": "SALIDA  TRANSFORMACION",
        "No. Documento": 9,
        "Total": 900,
    }
    base.update(cambios)
    return _linea(fisico, **base)


def _correr_pipeline(registros_memoria):
    """Corre R2 a R7 en memoria y devuelve todas las salidas intermedias."""
    registros_eo_so, total_eo, total_so = r2_filtrar_eo_so(registros_memoria)
    emparejamiento = r3_emparejar(registros_eo_so)
    cruces = r4_agrupar_por_cruce(emparejamiento["pares"])
    cruces, cifras = r5_detectar_costo_mayor(cruces)
    cruces, resumen_revision = r6_marcar_revisar(
        cruces, emparejamiento, registros_eo_so
    )
    cruces, resumen_semaforo = r7_marcar_semaforos(cruces)
    return {
        "registros_eo_so": registros_eo_so,
        "total_eo": total_eo,
        "total_so": total_so,
        "emparejamiento": emparejamiento,
        "cruces": cruces,
        "cifras": cifras,
        "resumen_revision": resumen_revision,
        "resumen_semaforo": resumen_semaforo,
    }


def _ids_en_revisar(cruces):
    """Devuelve los identificadores de las entradas marcadas "Revisar"."""
    return [cruce["id_cruce"] for cruce in cruces if cruce["estado_revision"] == REVISAR]


# --- R6 con el archivo real ------------------------------------------------


def test_r6_archivo_real_0_en_revisar_y_89_correctos(pipeline_real):
    """Con el insumo real: 0 cruces en Revisar y 89 correctos (§7)."""
    revisados, resumen = r6_marcar_revisar(
        [dict(cruce) for cruce in pipeline_real["cruces"]],
        pipeline_real["emparejamiento"],
        pipeline_real["registros_eo_so"],
    )

    assert len(revisados) == CRUCES_ESPERADOS
    assert resumen["en_revisar"] == EN_REVISAR_ESPERADOS
    assert resumen["correctos"] == CORRECTOS_ESPERADOS
    assert _ids_en_revisar(revisados) == []
    # Las 5 EO con 2 líneas NO cuentan como "No. Físico" duplicado (§8).
    assert all(cruce["estado_revision"] == CORRECTO for cruce in revisados)


def test_r6_usa_las_etiquetas_exactas_en_espanol():
    """Las etiquetas de estado son exactamente "Correcto" y "Revisar" (R6)."""
    assert CORRECTO == "Correcto"
    assert REVISAR == "Revisar"


# --- R6 con emparejamientos sintéticos (AGENTS.md §8) ----------------------


def test_r6_so_sin_eo_genera_exactamente_una_entrada_so_fisico_sin_eo():
    """Una SO sin su EO (`No. Físico + 1` inexistente) queda en Revisar."""
    registros_memoria = [
        _linea(1000),
        _linea_so(999),
        # SO 2000 sin EO 2001: queda huérfana.
        _linea_so(2000),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruces = resultado["cruces"]

    assert resultado["emparejamiento"]["so_sin_pareja"] == [2000]
    assert resultado["emparejamiento"]["eo_sin_pareja"] == []
    assert len(cruces) == 2
    assert resultado["resumen_revision"]["en_revisar"] == 1
    assert resultado["resumen_revision"]["correctos"] == 1
    assert _ids_en_revisar(cruces) == ["SO-2000-SIN-EO"]

    huerfana = [c for c in cruces if c["id_cruce"] == "SO-2000-SIN-EO"][0]
    # No se inventan líneas ni una EO: el lado inexistente queda vacío y en 0.
    assert huerfana["lineas_eo"] == []
    assert len(huerfana["lineas_so"]) == 1
    assert huerfana["total_eo"] == 0
    assert huerfana["costo_eo_mayor"] is False
    assert huerfana["diferencia_costo"] == 0


def test_r6_eo_sin_so_genera_exactamente_una_entrada_eo_fisico_sin_so():
    """Una EO sin su SO (`No. Físico − 1` inexistente) queda en Revisar."""
    registros_memoria = [
        _linea(1000),
        _linea_so(999),
        # EO 3000 sin SO 2999: queda huérfana.
        _linea(3000),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruces = resultado["cruces"]

    assert resultado["emparejamiento"]["eo_sin_pareja"] == [3000]
    assert resultado["emparejamiento"]["so_sin_pareja"] == []
    assert len(cruces) == 2
    assert resultado["resumen_revision"]["en_revisar"] == 1
    assert _ids_en_revisar(cruces) == ["EO-3000-SIN-SO"]

    huerfana = [c for c in cruces if c["id_cruce"] == "EO-3000-SIN-SO"][0]
    assert huerfana["lineas_so"] == []
    assert len(huerfana["lineas_eo"]) == 1
    assert huerfana["total_so"] == 0
    assert huerfana["costo_eo_mayor"] is False


def test_r6_fisico_no_numerico_no_lanza_excepcion_y_queda_en_revisar():
    """`No. Físico` de texto (`E81764`) no rompe la app y va a Revisar (§8)."""
    registros_memoria = [
        _linea(1000),
        _linea_so(999),
        _linea("E81764"),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruces = resultado["cruces"]

    # Nunca se convierte a texto para comparar: se aísla y se marca.
    assert "E81764" in resultado["emparejamiento"]["fisicos_no_numericos"]
    assert resultado["emparejamiento"]["eo_sin_pareja"] == []
    assert resultado["resumen_revision"]["en_revisar"] == 1
    assert _ids_en_revisar(cruces) == ["EO-E81764-SIN-SO"]


def test_r6_linea_con_campo_obligatorio_vacio_marca_el_cruce_en_revisar():
    """Una celda obligatoria vacía en cualquier línea marca ese cruce (§8)."""
    registros_memoria = [
        _linea(1000),
        _linea_so(999, **{"Cantidad": None}),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruces = resultado["cruces"]

    assert len(cruces) == 1
    assert cruces[0]["estado_revision"] == REVISAR
    assert resultado["resumen_revision"]["en_revisar"] == 1
    assert resultado["resumen_revision"]["correctos"] == 0


def test_r6_campo_obligatorio_vacio_en_la_eo_tambien_marca_revisar():
    """El vacío se detecta en la EO igual que en la SO."""
    registros_memoria = [
        _linea(1000, **{"Usuario Aplica": ""}),
        _linea_so(999),
    ]

    resultado = _correr_pipeline(registros_memoria)

    assert resultado["cruces"][0]["estado_revision"] == REVISAR
    assert resultado["resumen_revision"]["en_revisar"] == 1


def test_r6_revisar_no_excluye_el_analisis_de_costo():
    """Un cruce puede ser `costo_eo_mayor = true` y `estado_revision = "Revisar"`."""
    registros_memoria = [
        _linea(1000, **{"Total": 5000}),
        _linea_so(999, **{"Total": 1000, "Descripción Artículo": None}),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruce = resultado["cruces"][0]

    assert cruce["costo_eo_mayor"] is True
    assert cruce["estado_revision"] == REVISAR
    assert cruce["diferencia_costo"] == 4000.0
    assert resultado["cifras"]["cruces_total_mayor"] == 1


def test_r6_fisico_duplicado_en_el_mismo_tipo_marca_revisar():
    """Dos documentos distintos con el mismo `No. Físico` del mismo tipo (§8)."""
    registros_memoria = [
        # Dos EO con el mismo físico 1000 pero distinto No. Documento.
        _linea(1000, **{"No. Documento": 10, "Total": 500}),
        _linea(1000, **{"No. Documento": 11, "Total": 500}),
        _linea_so(999),
    ]

    resultado = _correr_pipeline(registros_memoria)

    assert len(resultado["cruces"]) == 1
    assert resultado["cruces"][0]["estado_revision"] == REVISAR
    assert resultado["resumen_revision"]["en_revisar"] == 1


def test_r6_varias_lineas_del_mismo_documento_no_es_duplicado():
    """Dos líneas del MISMO documento (igual `No. Documento`) no son duplicado."""
    registros_memoria = [
        _linea(1000, **{"No. Documento": 10, "Total": 500}),
        _linea(1000, **{"No. Documento": 10, "Total": 500}),
        _linea_so(999),
    ]

    resultado = _correr_pipeline(registros_memoria)

    assert len(resultado["cruces"]) == 1
    assert resultado["cruces"][0]["estado_revision"] == CORRECTO
    assert resultado["resumen_revision"]["en_revisar"] == 0


def test_r6_el_estado_no_cambia_las_cifras_de_costo():
    """Marcar "Revisar" no altera los totales ni la diferencia del cruce."""
    registros_memoria = [
        _linea(1000, **{"Total": 1500}),
        _linea_so(999, **{"Total": 1000, "Kilos": None}),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruce = resultado["cruces"][0]

    assert cruce["estado_revision"] == REVISAR
    assert cruce["total_eo"] == 1500.0
    assert cruce["total_so"] == 1000.0
    assert cruce["diferencia_costo"] == 500.0
    assert resultado["cifras"]["diferencia_global"] == 500.0


# --- R6 con validación numérica y de fecha (M5, AGENTS.md §8) --------------
#
# §8: «`Cantidad`, `Kilos`, `Costo Uni.` o `Total` no numéricos, o `Fecha`
# inválida → "Revisar"; el valor inválido no se convierte en 0 en silencio».
# R4 (`_numero`) convierte en 0 cualquier valor no numérico para no romper la
# suma; la prueba demuestra que R6 detecta el dato crudo de la línea y marca el
# cruce en "Revisar" en lugar de aceptar ese 0 como un valor válido.


def test_r6_total_no_numerico_marca_revisar():
    """Un `Total` de texto (`"N/A"`) en una línea del cruce va a Revisar."""
    registros_memoria = [
        _linea(1000),
        _linea_so(999, **{"Total": "N/A"}),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruce = resultado["cruces"][0]

    assert len(resultado["cruces"]) == 1
    assert cruce["estado_revision"] == REVISAR
    assert cruce["id_cruce"] in _ids_en_revisar(resultado["cruces"])
    assert resultado["resumen_revision"] == {"en_revisar": 1, "correctos": 0}


def test_r6_cantidad_no_numerica_marca_revisar():
    """Una `Cantidad` de texto (`"x"`) en la EO también va a Revisar."""
    registros_memoria = [
        _linea(1000, **{"Cantidad": "x"}),
        _linea_so(999),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruce = resultado["cruces"][0]

    assert cruce["estado_revision"] == REVISAR
    assert resultado["resumen_revision"] == {"en_revisar": 1, "correctos": 0}


def test_r6_costo_unitario_no_numerico_marca_revisar_sin_anular_el_costo():
    """`Costo Uni.` no numérico → Revisar, pero el costo del cruce se conserva."""
    registros_memoria = [
        # Total EO 1000 > Total SO 900: la alerta de costo existe.
        _linea(1000, **{"Costo Uni.": "N/A"}),
        _linea_so(999, **{"Costo Uni.": "N/A"}),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruce = resultado["cruces"][0]

    assert cruce["estado_revision"] == REVISAR
    # "Revisar" no excluye el análisis de costo (R6) ni apaga el semáforo (R7).
    assert cruce["costo_eo_mayor"] is True
    assert cruce["diferencia_costo"] == 100.0
    assert cruce["semaforo"] == ROJO
    assert cruce["etiqueta_semaforo"] == "Rojo"
    assert resultado["resumen_revision"]["en_revisar"] == 1
    assert resultado["resumen_semaforo"] == {"rojos": 1, "verdes": 0}


def test_r6_kilos_no_numerico_marca_revisar_sin_anular_el_costo():
    """`Kilos` no numérico → Revisar; el Total y el semáforo no cambian."""
    registros_memoria = [
        _linea(1000, **{"Kilos": "N/A"}),
        _linea_so(999),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruce = resultado["cruces"][0]

    assert cruce["estado_revision"] == REVISAR
    assert cruce["costo_eo_mayor"] is True
    assert cruce["diferencia_costo"] == 100.0
    assert cruce["semaforo"] == ROJO
    assert resultado["resumen_revision"]["en_revisar"] == 1
    assert resultado["resumen_semaforo"] == {"rojos": 1, "verdes": 0}


@pytest.mark.parametrize("fecha_invalida", ["N/A", "31/02/2026", 20261104])
def test_r6_fecha_invalida_marca_revisar(fecha_invalida):
    """Una `Fecha` que no es fecha utilizable marca el cruce en Revisar (§8)."""
    registros_memoria = [
        _linea(1000),
        _linea_so(999, **{"Fecha": fecha_invalida}),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruce = resultado["cruces"][0]

    assert cruce["estado_revision"] == REVISAR
    assert resultado["resumen_revision"] == {"en_revisar": 1, "correctos": 0}


def test_r6_valores_invalidos_solo_afectan_al_cruce_que_los_trae():
    """El dato numérico inválido marca su cruce y no los demás del archivo."""
    registros_memoria = [
        # Cruce limpio: debe quedar Correcto.
        _linea(1000),
        _linea_so(999),
        # Cruce con una línea inválida: debe quedar en Revisar.
        _linea(2000, **{"Total": "N/A"}),
        _linea_so(1999),
    ]

    resultado = _correr_pipeline(registros_memoria)
    por_id = {cruce["id_cruce"]: cruce for cruce in resultado["cruces"]}

    assert por_id["EO-1000-SO-999"]["estado_revision"] == CORRECTO
    assert por_id["EO-2000-SO-1999"]["estado_revision"] == REVISAR
    assert resultado["resumen_revision"] == {"en_revisar": 1, "correctos": 1}


# --- R7 semáforos ----------------------------------------------------------


def test_r7_archivo_real_50_rojos_y_39_verdes(pipeline_real):
    """Con el insumo real: 50 rojos (las alertas) y 39 verdes (AGENTS.md §7)."""
    revisados, resumen_revision = r6_marcar_revisar(
        [dict(cruce) for cruce in pipeline_real["cruces"]],
        pipeline_real["emparejamiento"],
        pipeline_real["registros_eo_so"],
    )
    cruces, resumen_semaforo = r7_marcar_semaforos(revisados)

    assert resumen_revision["en_revisar"] == EN_REVISAR_ESPERADOS
    assert resumen_semaforo["rojos"] == ROJOS_ESPERADOS
    assert resumen_semaforo["verdes"] == VERDES_ESPERADOS
    assert resumen_semaforo["rojos"] + resumen_semaforo["verdes"] == CRUCES_ESPERADOS
    assert len([c for c in cruces if c["semaforo"] == ROJO]) == ROJOS_ESPERADOS
    assert len([c for c in cruces if c["semaforo"] == VERDE]) == VERDES_ESPERADOS


def test_r7_semaforo_rojo_si_costo_eo_mayor_o_revisar(pipeline_real):
    """Rojo = `costo_eo_mayor` y/o `estado_revision == "Revisar"` (R7)."""
    revisados, _ = r6_marcar_revisar(
        [dict(cruce) for cruce in pipeline_real["cruces"]],
        pipeline_real["emparejamiento"],
        pipeline_real["registros_eo_so"],
    )
    cruces, _ = r7_marcar_semaforos(revisados)

    for cruce in cruces:
        debe_ser_rojo = cruce["costo_eo_mayor"] or cruce["estado_revision"] == REVISAR
        assert cruce["semaforo"] == (ROJO if debe_ser_rojo else VERDE), cruce["id_cruce"]
        assert cruce["etiqueta_semaforo"] == ("Rojo" if debe_ser_rojo else "Verde")


def test_r7_todo_cruce_en_revisar_es_rojo():
    """Un cruce marcado "Revisar" siempre es rojo, aunque el costo no sea mayor."""
    registros_memoria = [
        # EO sin SO: va a Revisar y no tiene costo mayor.
        _linea(3000, **{"Total": 100}),
        # SO sin EO: también a Revisar.
        _linea_so(4000),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruces = resultado["cruces"]

    assert resultado["resumen_revision"]["en_revisar"] == 2
    assert resultado["resumen_semaforo"]["rojos"] == 2
    assert resultado["resumen_semaforo"]["verdes"] == 0
    for cruce in cruces:
        assert cruce["estado_revision"] == REVISAR
        assert cruce["costo_eo_mayor"] is False
        assert cruce["semaforo"] == ROJO
        assert cruce["etiqueta_semaforo"] == "Rojo"


def test_r7_verde_cuando_esta_correcto_y_el_total_eo_no_es_mayor():
    """Verde = "Correcto" y sin alerta de costo (R7)."""
    registros_memoria = [
        _linea(1000, **{"Total": 900}),
        _linea_so(999, **{"Total": 1200}),
    ]

    resultado = _correr_pipeline(registros_memoria)
    cruce = resultado["cruces"][0]

    assert cruce["estado_revision"] == CORRECTO
    assert cruce["costo_eo_mayor"] is False
    assert cruce["semaforo"] == VERDE
    assert cruce["etiqueta_semaforo"] == "Verde"
    assert resultado["resumen_semaforo"] == {"rojos": 0, "verdes": 1}


def test_r7_etiquetas_de_semaforo_van_en_espanol():
    """Las etiquetas del semáforo son "Rojo" y "Verde" (R7, texto en español)."""
    assert ROJO == "rojo"
    assert VERDE == "verde"

    rojo = {"costo_eo_mayor": True, "estado_revision": CORRECTO}
    verde = {"costo_eo_mayor": False, "estado_revision": CORRECTO}
    revisar = {"costo_eo_mayor": False, "estado_revision": REVISAR}

    r7_marcar_semaforos([rojo, verde, revisar])

    assert (rojo["semaforo"], rojo["etiqueta_semaforo"]) == (ROJO, "Rojo")
    assert (verde["semaforo"], verde["etiqueta_semaforo"]) == (VERDE, "Verde")
    assert (revisar["semaforo"], revisar["etiqueta_semaforo"]) == (ROJO, "Rojo")
