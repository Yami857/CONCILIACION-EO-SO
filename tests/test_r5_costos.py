"""Pruebas de la regla R5 — Detección de anomalía de costo.

Fuente: AGENTS.md §3 R5 (`costo_eo_mayor = total_eo > total_so` sobre el Total
del documento; `diferencia_costo = total_eo - total_so` solo se reporta cuando
la EO es mayor) y §7 (50 cruces con `Total EO > Total SO`; distribución del
Costo Uni. ponderado: 55 mayores, 17 iguales, 17 menores).

Los esperados son los de `AGENTS.md` §7 y no se ajustan a lo que devuelva la
app; las comparaciones monetarias usan tolerancia de 0.005 por el redondeo a
2 decimales.
"""

from decimal import Decimal, localcontext

import pytest

from app.services.costos import r5_detectar_costo_mayor

# Cifras de control de AGENTS.md §7.
CRUCES_ESPERADOS = 89
CRUCES_TOTAL_EO_MAYOR = 50
CRUCES_UNITARIO_MAYOR = 55
CRUCES_UNITARIO_IGUAL = 17
CRUCES_UNITARIO_MENOR = 17

TOLERANCIA = 0.005

# Precisión para dividir sin perder centavos en la comprobación independiente.
PRECISION = 28


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



def _comparacion_unitaria_independiente(cruce):
    """Compara Total/Kilos de la EO contra la SO con una cuenta propia.

    Devuelve `1` si el unitario de la EO es mayor, `-1` si es menor, `0` si es
    igual y `None` si algún `Kilos` es 0 (no se puede dividir).
    """
    kilos_eo = float(cruce["kilos_eo"])
    kilos_so = float(cruce["kilos_so"])
    if kilos_eo == 0 or kilos_so == 0:
        return None

    with localcontext() as contexto:
        contexto.prec = PRECISION
        unitario_eo = Decimal(str(cruce["total_eo"])) / Decimal(str(kilos_eo))
        unitario_so = Decimal(str(cruce["total_so"])) / Decimal(str(kilos_so))

    if unitario_eo > unitario_so:
        return 1
    if unitario_eo < unitario_so:
        return -1
    return 0


# --- Insumo real -----------------------------------------------------------


def test_r5_hay_89_cruces_y_50_con_total_eo_mayor(pipeline_real):
    """89 cruces y 50 con `Total EO > Total SO` (AGENTS.md §7)."""
    cruces = pipeline_real["cruces"]
    cifras = pipeline_real["cifras"]

    assert len(cruces) == CRUCES_ESPERADOS
    assert cifras["cruces_total"] == CRUCES_ESPERADOS
    assert cifras["cruces_total_mayor"] == CRUCES_TOTAL_EO_MAYOR
    assert cifras["cruces_eo_mayor"] == CRUCES_TOTAL_EO_MAYOR
    assert sum(1 for cruce in cruces if cruce["costo_eo_mayor"]) == CRUCES_TOTAL_EO_MAYOR


def test_r5_costo_eo_mayor_compara_el_total_del_documento(pipeline_real):
    """`costo_eo_mayor` es verdadero exactamente cuando `total_eo > total_so`."""
    for cruce in pipeline_real["cruces"]:
        assert cruce["costo_eo_mayor"] is (cruce["total_eo"] > cruce["total_so"]), (
            f"{cruce['id_cruce']}: Total EO {cruce['total_eo']} vs "
            f"Total SO {cruce['total_so']}"
        )


def test_r5_diferencia_costo_es_total_eo_menos_total_so(pipeline_real):
    """`diferencia_costo == total_eo - total_so` en los 89 cruces."""
    for cruce in pipeline_real["cruces"]:
        esperado = cruce["total_eo"] - cruce["total_so"]
        assert abs(cruce["diferencia_costo"] - esperado) <= TOLERANCIA, (
            f"{cruce['id_cruce']}: diferencia_costo = "
            f"{cruce['diferencia_costo']}, esperado {esperado}"
        )


def test_r5_solo_los_cruces_con_eo_mayor_entran_en_la_suma_de_alertas(
    pipeline_real,
):
    """La cifra de alertas suma únicamente los 50 cruces con `Total EO > SO`."""
    cruces = pipeline_real["cruces"]

    suma_con_alerta = sum(
        cruce["diferencia_costo"] for cruce in cruces if cruce["costo_eo_mayor"]
    )
    suma_sin_alerta = sum(
        cruce["diferencia_costo"] for cruce in cruces if not cruce["costo_eo_mayor"]
    )
    suma_total = sum(cruce["diferencia_costo"] for cruce in cruces)

    assert abs(suma_con_alerta - pipeline_real["cifras"]["suma_diferencias_eo_mayor"]) <= TOLERANCIA
    assert abs(suma_total - pipeline_real["cifras"]["diferencia_global"]) <= TOLERANCIA
    # AGENTS.md §7: la suma global (272.865,75) es menor que la de las alertas
    # porque los 39 cruces restantes tienen diferencia negativa.
    assert suma_sin_alerta < 0


def test_r5_distribucion_costo_unitario_55_17_17(pipeline_real):
    """Costo Uni. ponderado: 55 mayores, 17 iguales y 17 menores (§7)."""
    cifras = pipeline_real["cifras"]

    assert cifras["cruces_unitario_mayor"] == CRUCES_UNITARIO_MAYOR
    assert cifras["cruces_unitario_igual"] == CRUCES_UNITARIO_IGUAL
    assert cifras["cruces_unitario_menor"] == CRUCES_UNITARIO_MENOR

    # Comprobación independiente: se vuelve a comparar Total/Kilos por cruce.
    comparaciones = [
        _comparacion_unitaria_independiente(cruce)
        for cruce in pipeline_real["cruces"]
    ]
    assert comparaciones.count(1) == CRUCES_UNITARIO_MAYOR
    assert comparaciones.count(0) == CRUCES_UNITARIO_IGUAL
    assert comparaciones.count(-1) == CRUCES_UNITARIO_MENOR
    assert comparaciones.count(None) == 0


def test_r5_las_3_categorias_unitarias_suman_los_89_cruces(pipeline_real):
    """No hay cruces unitarios fuera de las tres categorías de §7."""
    cifras = pipeline_real["cifras"]
    total = (
        cifras["cruces_unitario_mayor"]
        + cifras["cruces_unitario_igual"]
        + cifras["cruces_unitario_menor"]
    )

    assert total == CRUCES_ESPERADOS
    # AGENTS.md §7: el unitario marca más cruces (55) que el Total (50), y aun
    # así son 39 verdes porque el semáforo depende del Total (R7).
    assert cifras["cruces_unitario_mayor"] > cifras["cruces_total_mayor"]


# --- Caso límite: Kilos en 0 (no se divide) --------------------------------


def test_r5_kilos_cero_no_provoca_division_por_cero():
    """Un cruce con `Kilos = 0` no divide: se omite del cálculo unitario."""
    cruce_kilos_cero = {
        "id_cruce": "EO-2000-SO-1999",
        "total_eo": 500.0,
        "total_so": 400.0,
        "kilos_eo": 0,
        "kilos_so": 0,
    }
    cruce_kilos_so_cero = {
        "id_cruce": "EO-3000-SO-2999",
        "total_eo": 900.0,
        "total_so": 800.0,
        "kilos_eo": 10,
        "kilos_so": 0,
    }

    # No debe lanzar ZeroDivisionError.
    cruces, cifras = r5_detectar_costo_mayor([cruce_kilos_cero, cruce_kilos_so_cero])

    assert len(cruces) == 2
    assert cifras["cruces_unitario_mayor"] == 0
    assert cifras["cruces_unitario_igual"] == 0
    assert cifras["cruces_unitario_menor"] == 0
    # El Total sí se compara: ambos cruces tienen EO mayor.
    assert all(cruce["costo_eo_mayor"] for cruce in cruces)
    assert cifras["cruces_total_mayor"] == 2


def test_r5_kilos_cero_no_altera_la_suma_unitaria():
    """Con `Kilos = 0` la cifra unitaria no se calcula ni se inventa."""
    cruces_con_cero = [
        {
            "id_cruce": "EO-4000-SO-3999",
            "total_eo": 1000.0,
            "total_so": 100.0,
            "kilos_eo": 0,
            "kilos_so": 5,
        }
    ]

    _, cifras = r5_detectar_costo_mayor(cruces_con_cero)

    assert cifras["suma_diferencias_unitaria"] == 0.0
    assert cifras["diferencia_global"] == pytest.approx(900.0, abs=TOLERANCIA)


def test_r5_compara_el_total_y_no_el_costo_unitario_de_la_linea():
    """Un caso donde el unitario de la EO es menor pero el Total es mayor."""
    lineas_eo = [
        _linea(5000, **{"Cantidad": 10, "Kilos": 10, "Costo Uni.": 50, "Total": 500})
    ]
    lineas_so = [
        _linea(
            4999,
            **{
                "Tipo Doc.": "SO",
                "Cantidad": 1,
                "Kilos": 1,
                "Costo Uni.": 400,
                "Total": 400,
            },
        )
    ]

    _, cifras = r5_detectar_costo_mayor(
        [
            {
                "id_cruce": "EO-5000-SO-4999",
                "lineas_eo": lineas_eo,
                "lineas_so": lineas_so,
                "cantidad_eo": 10,
                "cantidad_so": 1,
                "kilos_eo": 10,
                "kilos_so": 1,
                "total_eo": 500.0,
                "total_so": 400.0,
            }
        ]
    )

    # Total EO (500) > Total SO (400) => anomalía, aunque el unitario de la EO
    # (50) sea menor que el de la SO (400).
    assert cifras["cruces_total_mayor"] == 1
    assert cifras["cruces_unitario_menor"] == 1
    assert cifras["diferencia_global"] == pytest.approx(100.0, abs=TOLERANCIA)
