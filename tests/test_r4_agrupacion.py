"""Pruebas de la regla R4 — Agrupación por cruce.

Fuente: AGENTS.md §3 R4 (un cruce = una EO y su SO; se suman TODAS las líneas
de cada documento antes de comparar) y §7 (89 cruces, 5 EO con 2 líneas:
físicos 1615164, 1615175, 1615241, 1615351 y 1615435).

Los esperados salen de `AGENTS.md`; las sumas se comprueban contra las filas
crudas del insumo real (leídas por R1), no contra los números que produce R4.
"""

import pytest

from app.services.agrupacion import r4_agrupar_por_cruce

# Cifras de control de AGENTS.md §7.
CRUCES_ESPERADOS = 89
FISICOS_EO_DOS_LINEAS = (1615164, 1615175, 1615241, 1615351, 1615435)

# Tolerancia de comparación monetaria: los montos se manejan a 2 decimales.
TOLERANCIA = 0.005

# Columnas que R4 suma por documento (AGENTS.md §3 R4).
CAMPOS_SUMADOS = ("Cantidad", "Kilos", "Total")


def _es_tipo(registro, tipo):
    """Indica si el registro es del tipo de documento indicado."""
    return str(registro.get("Tipo Doc.")).strip() == tipo


def _lineas_reales(registros, tipo, fisico):
    """Devuelve las filas crudas del insumo de un tipo y `No. Físico` dados."""
    return [
        registro
        for registro in registros["registros"]
        if _es_tipo(registro, tipo) and int(registro["No. Físico"]) == fisico
    ]


def _suma(lineas, campo):
    """Suma una columna sobre las líneas indicadas (cálculo independiente)."""
    return sum(float(linea[campo]) for linea in lineas)


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


# --- Insumo real -----------------------------------------------------------


def test_r4_hay_un_cruce_por_par_y_89_cruces(pipeline_real):
    """Los 89 pares de R3 producen 89 cruces, sin perder ni duplicar ninguno."""
    cruces = pipeline_real["cruces_r4"]
    pares = pipeline_real["emparejamiento"]["pares"]

    assert len(cruces) == CRUCES_ESPERADOS
    assert len(cruces) == len(pares)

    # Cada cruce conserva las mismas líneas de su par, en el mismo orden.
    for cruce, par in zip(cruces, pares):
        assert cruce["id_cruce"] == par["id_cruce"]
        assert cruce["lineas_eo"] == par["lineas_eo"]
        assert cruce["lineas_so"] == par["lineas_so"]


def test_r4_cada_cruce_suma_todas_las_lineas_de_sus_documentos(pipeline_real):
    """`cantidad`, `kilos` y `total` de cada cruce son la suma de sus líneas."""
    cruces = pipeline_real["cruces_r4"]

    for cruce in cruces:
        for campo in CAMPOS_SUMADOS:
            esperado_eo = _suma(cruce["lineas_eo"], campo)
            esperado_so = _suma(cruce["lineas_so"], campo)
            obtenido_eo = cruce[f"{campo.lower()}_eo"]
            obtenido_so = cruce[f"{campo.lower()}_so"]

            assert abs(obtenido_eo - esperado_eo) <= TOLERANCIA, (
                f"{cruce['id_cruce']}: {campo} EO del cruce = {obtenido_eo}, "
                f"suma de sus líneas = {esperado_eo}"
            )
            assert abs(obtenido_so - esperado_so) <= TOLERANCIA, (
                f"{cruce['id_cruce']}: {campo} SO del cruce = {obtenido_so}, "
                f"suma de sus líneas = {esperado_so}"
            )


def test_r4_los_5_fisicos_con_dos_lineas_eo_suman_sus_dos_lineas(
    registros, pipeline_real
):
    """Las 5 EO con 2 líneas (AGENTS.md §7) suman sus dos líneas en el cruce."""
    cruces_por_fisico = {cruce["fisico_eo"]: cruce for cruce in pipeline_real["cruces_r4"]}

    for fisico in FISICOS_EO_DOS_LINEAS:
        lineas = _lineas_reales(registros, "EO", fisico)
        assert len(lineas) == 2, f"La EO {fisico} debería tener 2 líneas en el insumo"

        cruce = cruces_por_fisico[fisico]
        assert len(cruce["lineas_eo"]) == 2

        for campo in CAMPOS_SUMADOS:
            esperado = _suma(lineas, campo)
            obtenido = cruce[f"{campo.lower()}_eo"]
            assert abs(obtenido - esperado) <= TOLERANCIA, (
                f"EO {fisico}: {campo} = {obtenido}, suma real de sus 2 líneas "
                f"= {esperado}"
            )
        # Con dos líneas, el Total del cruce no puede ser el de una sola línea.
        primer_total = float(lineas[0]["Total"])
        segundo_total = float(lineas[1]["Total"])
        assert abs(cruce["total_eo"] - primer_total) > TOLERANCIA
        assert abs(cruce["total_eo"] - segundo_total) > TOLERANCIA


def test_r4_bodega_y_usuario_del_cruce_salen_de_la_eo(registros, pipeline_real):
    """`bodega` y `usuario` del cruce coinciden con los de las líneas EO."""
    for cruce in pipeline_real["cruces_r4"]:
        lineas = _lineas_reales(registros, "EO", cruce["fisico_eo"])
        assert cruce["bodega"] == lineas[0]["Bodega"], cruce["id_cruce"]
        assert cruce["usuario"] == lineas[0]["Usuario Aplica"], cruce["id_cruce"]
        # Todas las líneas de un documento comparten bodega y usuario.
        assert all(linea["Bodega"] == cruce["bodega"] for linea in lineas)


def test_r4_id_cruce_tiene_formato_eo_fisico_so_fisico(pipeline_real):
    """`id_cruce` = `EO-<fisico_eo>-SO-<fisico_so>` (AGENTS.md §3 R4 y §4)."""
    for cruce in pipeline_real["cruces_r4"]:
        assert cruce["id_cruce"] == (
            f"EO-{cruce['fisico_eo']}-SO-{cruce['fisico_so']}"
        )
        assert cruce["fisico_so"] == cruce["fisico_eo"] - 1
        # Ningún identificador se repite: un cruce por par.
    ids = [cruce["id_cruce"] for cruce in pipeline_real["cruces_r4"]]
    assert len(set(ids)) == CRUCES_ESPERADOS


def test_r4_las_89_so_tienen_exactamente_una_linea(pipeline_real):
    """En el insumo real las 89 SO tienen 1 línea, y R4 conserva ese conteo."""
    cruces = pipeline_real["cruces_r4"]
    assert all(len(cruce["lineas_so"]) == 1 for cruce in cruces)
    # Exactamente 5 cruces tienen 2 líneas EO; el resto, 1.
    assert sum(1 for cruce in cruces if len(cruce["lineas_eo"]) == 2) == 5


# --- Caso límite: documento con varias líneas (AGENTS.md §8) ---------------


def test_r4_documento_con_varias_lineas_suma_antes_de_comparar():
    """Un documento con 2 líneas se suma en un solo cruce, no se compara aparte."""
    lineas_eo = [
        _linea(1000, **{"No. Documento": 10, "Cantidad": 8, "Kilos": 8, "Total": 800}),
        _linea(1000, **{"No. Documento": 10, "Cantidad": 2, "Kilos": 2, "Total": 200}),
    ]
    lineas_so = [
        _linea(
            999,
            **{
                "Tipo Doc.": "SO",
                "Descripción Documento": "SALIDA  TRANSFORMACION",
                "No. Documento": 9,
                "Cantidad": 5,
                "Kilos": 5,
                "Total": 500,
            }
        )
    ]

    cruces = r4_agrupar_por_cruce(
        [
            {
                "fisico_eo": 1000,
                "fisico_so": 999,
                "id_cruce": "EO-1000-SO-999",
                "lineas_eo": lineas_eo,
                "lineas_so": lineas_so,
            }
        ]
    )

    assert len(cruces) == 1
    cruce = cruces[0]
    assert len(cruce["lineas_eo"]) == 2
    assert abs(cruce["cantidad_eo"] - 10.0) <= TOLERANCIA
    assert abs(cruce["kilos_eo"] - 10.0) <= TOLERANCIA
    assert abs(cruce["total_eo"] - 1000.0) <= TOLERANCIA
    assert abs(cruce["total_so"] - 500.0) <= TOLERANCIA


@pytest.mark.parametrize("campo", CAMPOS_SUMADOS)
def test_r4_la_suma_usa_todas_las_lineas_y_no_solo_la_primera(campo):
    """La suma incluye la segunda línea: no toma únicamente la primera."""
    lineas_eo = [
        _linea(1000, **{"Cantidad": 8, "Kilos": 8, "Total": 800}),
        _linea(1000, **{"Cantidad": 2, "Kilos": 2, "Total": 200}),
    ]

    cruce = r4_agrupar_por_cruce(
        [
            {
                "fisico_eo": 1000,
                "fisico_so": 999,
                "id_cruce": "EO-1000-SO-999",
                "lineas_eo": lineas_eo,
                "lineas_so": [],
            }
        ]
    )[0]

    suma_total = _suma(lineas_eo, campo)
    solo_primera = float(lineas_eo[0][campo])
    obtenido = cruce[f"{campo.lower()}_eo"]

    assert abs(obtenido - suma_total) <= TOLERANCIA
    assert abs(obtenido - solo_primera) > TOLERANCIA
