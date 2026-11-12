"""Pruebas de la regla R3 — Emparejamiento EO ↔ SO.

Fuente: AGENTS.md §3 R3 (`SO.No. Físico = EO.No. Físico − 1`) y §7 (89 cruces,
0 EO sin pareja, 0 SO sin pareja, 5 EO con 2 líneas). Se corre sobre el insumo
real; la regla invertida `SO = EO + 1` se prueba como regresión.
"""

from collections import defaultdict

import pytest

from app.services.emparejamiento import r3_emparejar
from app.services.filtro import r2_filtrar_eo_so

# Cifras de control de AGENTS.md §7.
PARES_ESPERADOS = 89
FISICOS_EO_DOS_LINEAS = (1615164, 1615175, 1615241, 1615351, 1615435)

# AGENTS.md §3: la regla invertida del documento de contexto solo produce
# 16 coincidencias falsas.
COINCIDENCIAS_FALSAS_CON_MAS_UNO = 16


@pytest.fixture(scope="module")
def emparejamiento(registros):
    """Aplica R2 y R3 una vez sobre el insumo real."""
    registros_eo_so, _, _ = r2_filtrar_eo_so(registros["registros"])
    return r3_emparejar(registros_eo_so)


def test_r3_empareja_89_pares_sin_parejas_sueltas(emparejamiento):
    """89 pares, 0 EO sin pareja y 0 SO sin pareja (AGENTS.md §7)."""
    pares = emparejamiento["pares"]

    assert len(pares) == PARES_ESPERADOS
    assert emparejamiento["eo_sin_pareja"] == []
    assert emparejamiento["so_sin_pareja"] == []
    assert emparejamiento["fisicos_no_numericos"] == []

    # Cada EO y cada SO del insumo forman un cruce distinto.
    fisicos_eo = {par["fisico_eo"] for par in pares}
    fisicos_so = {par["fisico_so"] for par in pares}
    assert len(fisicos_eo) == PARES_ESPERADOS
    assert len(fisicos_so) == PARES_ESPERADOS


def test_r3_cada_so_es_eo_menos_uno(emparejamiento):
    """En los 89 pares se cumple `fisico_so == fisico_eo - 1`."""
    for par in emparejamiento["pares"]:
        assert par["fisico_so"] == par["fisico_eo"] - 1, (
            f"El par {par['id_cruce']} no cumple SO = EO − 1"
        )
        assert par["id_cruce"] == f"EO-{par['fisico_eo']}-SO-{par['fisico_so']}"


def test_r3_los_5_fisicos_conservan_sus_dos_lineas_eo(emparejamiento):
    """Los 5 físicos de AGENTS.md §7 agrupan 2 líneas EO cada uno."""
    lineas_por_fisico = {
        par["fisico_eo"]: len(par["lineas_eo"]) for par in emparejamiento["pares"]
    }

    fisicos_con_dos_lineas = sorted(
        fisico for fisico, cantidad in lineas_por_fisico.items() if cantidad == 2
    )
    assert fisicos_con_dos_lineas == sorted(FISICOS_EO_DOS_LINEAS)

    for fisico in FISICOS_EO_DOS_LINEAS:
        assert lineas_por_fisico[fisico] == 2, (
            f"La EO {fisico} debería conservar 2 líneas"
        )

    # En el insumo real las 89 SO tienen exactamente 1 línea.
    assert all(len(par["lineas_so"]) == 1 for par in emparejamiento["pares"])


def test_r3_ningun_fisico_duplicado_dentro_del_mismo_tipo(registros):
    """Cada `No. Físico` aparece una sola vez por tipo (excepto las 5 EO)."""
    registros_eo_so, _, _ = r2_filtrar_eo_so(registros["registros"])
    conteo = defaultdict(int)
    for registro in registros_eo_so:
        clave = (str(registro["Tipo Doc."]).strip(), int(registro["No. Físico"]))
        conteo[clave] += 1

    con_varias_lineas = {
        fisico for (tipo, fisico), cantidad in conteo.items() if cantidad > 1
    }
    assert con_varias_lineas == set(FISICOS_EO_DOS_LINEAS)


def test_r3_regresion_regla_invertida_eo_mas_uno_no_da_89(registros):
    """Con `SO = EO + 1` (documento de contexto invertido) NO hay 89 pares.

    Se rearma el agrupamiento con la regla invertida sobre los mismos datos,
    sin tocar el código de la app.
    """
    registros_eo_so, _, _ = r2_filtrar_eo_so(registros["registros"])

    eo_por_fisico = defaultdict(list)
    so_por_fisico = defaultdict(list)
    for registro in registros_eo_so:
        fisico = int(registro["No. Físico"])
        if str(registro["Tipo Doc."]).strip() == "EO":
            eo_por_fisico[fisico].append(registro)
        else:
            so_por_fisico[fisico].append(registro)

    pares_con_mas_uno = [
        fisico_eo
        for fisico_eo in eo_por_fisico
        if (fisico_eo + 1) in so_por_fisico
    ]

    assert len(pares_con_mas_uno) != PARES_ESPERADOS
    assert len(pares_con_mas_uno) == COINCIDENCIAS_FALSAS_CON_MAS_UNO
    assert len(pares_con_mas_uno) < PARES_ESPERADOS


def test_r3_no_numerico_no_lanza_excepcion():
    """Un `No. Físico` de texto se aísla en `fisicos_no_numericos`, sin caerse."""
    registros_memoria = [
        {"Tipo Doc.": "EO", "No. Físico": 1000},
        {"Tipo Doc.": "SO", "No. Físico": 999},
        {"Tipo Doc.": "EO", "No. Físico": "E81764"},
        {"Tipo Doc.": "SO", "No. Físico": "3686-1"},
    ]

    resultado = r3_emparejar(registros_memoria)

    assert len(resultado["pares"]) == 1
    par = resultado["pares"][0]
    assert par["fisico_eo"] == 1000
    assert par["fisico_so"] == 999
    assert "E81764" in resultado["fisicos_no_numericos"]
    assert "3686-1" in resultado["fisicos_no_numericos"]
    assert resultado["eo_sin_pareja"] == []
    assert resultado["so_sin_pareja"] == []
