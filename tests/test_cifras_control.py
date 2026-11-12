"""Pruebas de las cifras de control de AGENTS.md §7.

Todos los valores esperados de este archivo salen **textualmente** de
`AGENTS.md` §7 (calculados sobre `INSUMOS/MOVIMIENTOS 4-11-26.xlsx`: 4.898
filas, fecha 2026-11-04) y NO se ajustan a lo que devuelva la aplicación:

- Diferencia global `Total EO − Total SO` (89 cruces) = 272.865,75
- Suma de diferencias solo donde `Total EO > Total SO` (50 cruces) = 341.738,47
- Suma de diferencias de `Costo Uni.` ponderado por kilos (55 cruces) = 49.829,07
- Conteos: 4.898 filas, 183 registros EO/SO, 94 EO, 89 SO, 89 cruces, 0 sin pareja
- Montos: suma de `Total` de las EO = 1.697.243,98 y de las SO = 1.424.378,23

Las comparaciones monetarias usan tolerancia de 0.005 (medio centavo), porque
los montos se manejan con 2 decimales. Si una cifra no cuadra, es un hallazgo:
no se cambia el esperado ni la tolerancia.
"""

import pytest

from app.services.emparejamiento import r3_emparejar
from app.services.filtro import r2_filtrar_eo_so

# --- Cifras de control de AGENTS.md §7 (no modificar) ----------------------
FILAS_TOTALES = 4898
REGISTROS_EO_SO = 183
FILAS_EO = 94
FILAS_SO = 89
CRUCES = 89
SIN_PAREJA = 0

SUMA_TOTAL_EO = 1697243.98
SUMA_TOTAL_SO = 1424378.23
DIFERENCIA_GLOBAL = 272865.75
SUMA_DIFERENCIAS_EO_MAYOR = 341738.47
SUMA_DIFERENCIAS_UNITARIA = 49829.07

CRUCES_TOTAL_EO_MAYOR = 50
CRUCES_UNITARIO_MAYOR = 55
CRUCES_UNITARIO_IGUAL = 17
CRUCES_UNITARIO_MENOR = 17

# Tolerancia de comparación monetaria: medio centavo.
TOLERANCIA = 0.005


# --- Conteos ---------------------------------------------------------------


def test_control_filas_totales_4898(registros):
    """El insumo real tiene 4.898 filas (§7), no más ni menos."""
    assert registros["ok"] is True, registros["mensaje"]
    assert registros["filas"] == FILAS_TOTALES
    assert len(registros["registros"]) == FILAS_TOTALES


def test_control_183_registros_94_eo_y_89_so(pipeline_real):
    """183 registros EO/SO: 94 filas EO y 89 filas SO (§7)."""
    assert len(pipeline_real["registros_eo_so"]) == REGISTROS_EO_SO
    assert pipeline_real["total_eo"] == FILAS_EO
    assert pipeline_real["total_so"] == FILAS_SO
    assert pipeline_real["total_eo"] + pipeline_real["total_so"] == REGISTROS_EO_SO


def test_control_89_cruces_y_0_registros_sin_pareja(pipeline_real):
    """89 cruces EO–SO y 0 EO/SO sin pareja (§7)."""
    emparejamiento = pipeline_real["emparejamiento"]

    assert len(pipeline_real["cruces"]) == CRUCES
    assert pipeline_real["cifras"]["cruces_total"] == CRUCES
    assert len(emparejamiento["eo_sin_pareja"]) == SIN_PAREJA
    assert len(emparejamiento["so_sin_pareja"]) == SIN_PAREJA
    assert emparejamiento["fisicos_no_numericos"] == []


def test_control_todos_los_registros_eo_so_estan_dentro_de_un_cruce(pipeline_real):
    """Las 94 líneas EO y las 89 líneas SO quedan dentro de los cruces (§7)."""
    cruces = pipeline_real["cruces"]

    assert sum(len(cruce["lineas_eo"]) for cruce in cruces) == FILAS_EO
    assert sum(len(cruce["lineas_so"]) for cruce in cruces) == FILAS_SO


# --- Montos ----------------------------------------------------------------


def test_control_diferencia_global_272865_75(pipeline_real):
    """Diferencia global `Total EO − Total SO` = 272.865,75 (§7)."""
    obtenido = pipeline_real["cifras"]["diferencia_global"]

    assert obtenido == pytest.approx(DIFERENCIA_GLOBAL, abs=TOLERANCIA), (
        f"AGENTS.md §7 dice {DIFERENCIA_GLOBAL}; la app devolvió {obtenido}"
    )


def test_control_suma_diferencias_eo_mayor_341738_47(pipeline_real):
    """Suma de diferencias solo donde `Total EO > Total SO` = 341.738,47 (§7)."""
    obtenido = pipeline_real["cifras"]["suma_diferencias_eo_mayor"]

    assert obtenido == pytest.approx(SUMA_DIFERENCIAS_EO_MAYOR, abs=TOLERANCIA), (
        f"AGENTS.md §7 dice {SUMA_DIFERENCIAS_EO_MAYOR}; la app devolvió {obtenido}"
    )


def test_control_suma_diferencias_unitaria_49829_07(pipeline_real):
    """Suma de diferencias de Costo Uni. ponderado = 49.829,07 (§7)."""
    obtenido = pipeline_real["cifras"]["suma_diferencias_unitaria"]

    assert obtenido == pytest.approx(SUMA_DIFERENCIAS_UNITARIA, abs=TOLERANCIA), (
        f"AGENTS.md §7 dice {SUMA_DIFERENCIAS_UNITARIA}; la app devolvió {obtenido}"
    )


def test_control_suma_total_eo_1697243_98_y_total_so_1424378_23(pipeline_real):
    """Suma de `Total` de las EO y de las SO según §7, y su resta."""
    cruces = pipeline_real["cruces"]

    suma_eo = sum(cruce["total_eo"] for cruce in cruces)
    suma_so = sum(cruce["total_so"] for cruce in cruces)

    assert suma_eo == pytest.approx(SUMA_TOTAL_EO, abs=TOLERANCIA), (
        f"AGENTS.md §7 dice {SUMA_TOTAL_EO}; se sumó {suma_eo}"
    )
    assert suma_so == pytest.approx(SUMA_TOTAL_SO, abs=TOLERANCIA), (
        f"AGENTS.md §7 dice {SUMA_TOTAL_SO}; se sumó {suma_so}"
    )
    # La diferencia global debe ser la resta de los dos montos.
    assert (suma_eo - suma_so) == pytest.approx(DIFERENCIA_GLOBAL, abs=TOLERANCIA)


def test_control_diferencia_global_es_la_suma_de_las_diferencias_de_los_cruces(
    pipeline_real,
):
    """La cifra global coincide con sumar `diferencia_costo` en los 89 cruces."""
    cruces = pipeline_real["cruces"]
    suma = sum(cruce["diferencia_costo"] for cruce in cruces)

    assert suma == pytest.approx(pipeline_real["cifras"]["diferencia_global"], abs=TOLERANCIA)
    assert suma == pytest.approx(DIFERENCIA_GLOBAL, abs=TOLERANCIA)


def test_control_suma_alertas_es_la_de_los_50_cruces_con_eo_mayor(pipeline_real):
    """La cifra de 341.738,47 sale exactamente de los 50 cruces con alerta."""
    cruces = pipeline_real["cruces"]
    con_alerta = [cruce for cruce in cruces if cruce["costo_eo_mayor"]]

    assert len(con_alerta) == CRUCES_TOTAL_EO_MAYOR
    suma = sum(cruce["diferencia_costo"] for cruce in con_alerta)
    assert suma == pytest.approx(SUMA_DIFERENCIAS_EO_MAYOR, abs=TOLERANCIA)

    # Y ninguna de esas diferencias es negativa o cero por definición de R5.
    assert all(cruce["diferencia_costo"] > 0 for cruce in con_alerta)


# --- Distribución de los 89 cruces ----------------------------------------


def test_control_distribucion_50_mayores_55_17_17(pipeline_real):
    """50 por Total y 55 / 17 / 17 por Costo Uni. ponderado (§7)."""
    cifras = pipeline_real["cifras"]

    assert cifras["cruces_total_mayor"] == CRUCES_TOTAL_EO_MAYOR
    assert cifras["cruces_unitario_mayor"] == CRUCES_UNITARIO_MAYOR
    assert cifras["cruces_unitario_igual"] == CRUCES_UNITARIO_IGUAL
    assert cifras["cruces_unitario_menor"] == CRUCES_UNITARIO_MENOR
    assert (
        cifras["cruces_unitario_mayor"]
        + cifras["cruces_unitario_igual"]
        + cifras["cruces_unitario_menor"]
        == CRUCES
    )


def test_control_la_cifra_principal_es_la_suma_de_diferencias_de_total(pipeline_real):
    """La cifra principal de control es 341.738,47 (AGENTS.md §7)."""
    cifras = pipeline_real["cifras"]

    # Orden de magnitud relativo de §7, sin tocar los valores.
    assert cifras["suma_diferencias_eo_mayor"] > cifras["diferencia_global"]
    assert cifras["suma_diferencias_unitaria"] < cifras["diferencia_global"]
    assert cifras["suma_diferencias_eo_mayor"] > cifras["suma_diferencias_unitaria"]


def test_control_el_emparejamiento_no_cambia_al_recalcularlo(pipeline_real):
    """R3 devuelve los mismos 89 cruces si se recalcula desde cero."""
    registros_eo_so = pipeline_real["registros_eo_so"]
    otra_vez, _, _ = r2_filtrar_eo_so(registros_eo_so)
    emparejamiento = r3_emparejar(otra_vez)

    assert len(emparejamiento["pares"]) == CRUCES
    assert [par["id_cruce"] for par in emparejamiento["pares"]] == [
        cruce["id_cruce"] for cruce in pipeline_real["cruces"]
    ]
