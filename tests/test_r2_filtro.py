"""Pruebas de la regla R2 — Filtro de registros EO / SO.

Fuente: AGENTS.md §2 (tipos de documento y sus conteos), §3 R2 y §7
(183 registros EO/SO, 94 EO y 89 SO). Se corre sobre el insumo real.
"""

import pytest

from app.services.filtro import TIPOS_EO_SO, r2_filtrar_eo_so

# Cifras de control de AGENTS.md §7.
REGISTROS_EO_SO = 183
FILAS_EO = 94
FILAS_SO = 89
FILAS_TOTALES = 4898
FILAS_DESCARTADAS = 4715

# Filas reales por tipo según AGENTS.md §2: deben quedar fuera del filtro.
FILAS_POR_TIPO_FUERA = {
    "FPC": 3724,
    "EAC": 657,
    "EFP": 260,
}


@pytest.fixture(scope="module")
def filtrado(registros):
    """Aplica R2 una vez sobre las 4.898 filas del insumo real."""
    return r2_filtrar_eo_so(registros["registros"])


def _conteo_por_tipo(lista_registros):
    """Cuenta cuántas filas hay de cada `Tipo Doc.`."""
    conteo = {}
    for registro in lista_registros:
        tipo = str(registro["Tipo Doc."]).strip()
        conteo[tipo] = conteo.get(tipo, 0) + 1
    return conteo


def test_r2_filtra_183_registros_con_94_eo_y_89_so(filtrado):
    """R2 deja 183 filas: 94 EO y 89 SO (AGENTS.md §7)."""
    registros_eo_so, total_eo, total_so = filtrado

    assert len(registros_eo_so) == REGISTROS_EO_SO
    assert total_eo == FILAS_EO
    assert total_so == FILAS_SO
    assert total_eo + total_so == len(registros_eo_so)


def test_r2_descarta_las_4715_filas_de_otros_tipos(registros, filtrado):
    """De las 4.898 filas del archivo, 4.715 no son EO ni SO."""
    registros_eo_so, _, _ = filtrado

    assert len(registros["registros"]) == FILAS_TOTALES
    assert len(registros["registros"]) - len(registros_eo_so) == FILAS_DESCARTADAS


def test_r2_solo_conserva_tipos_eo_y_so(filtrado):
    """Ningún registro conservado tiene un `Tipo Doc.` distinto de EO/SO."""
    registros_eo_so, _, _ = filtrado

    tipos_conservados = {str(r["Tipo Doc."]).strip() for r in registros_eo_so}
    assert tipos_conservados == set(TIPOS_EO_SO)
    assert tipos_conservados == {"EO", "SO"}


def test_r2_fpc_eac_y_efp_quedan_fuera(registros, filtrado):
    """FPC, EAC y EFP vienen en el archivo real pero no sobreviven al filtro."""
    registros_eo_so, _, _ = filtrado
    tipos_conservados = [str(r["Tipo Doc."]).strip() for r in registros_eo_so]
    conteo_original = _conteo_por_tipo(registros["registros"])

    for tipo, cantidad in FILAS_POR_TIPO_FUERA.items():
        # El tipo sí está en el insumo, con la cantidad de AGENTS.md §2.
        assert conteo_original.get(tipo) == cantidad
        # Y aun así no aparece en el resultado de R2.
        assert tipo not in tipos_conservados
