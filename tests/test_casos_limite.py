"""Pruebas de los casos límite de AGENTS.md §8 (entrega T3).

Fuente: `AGENTS.md` §2 (14 columnas reales), §3 (R1–R7), §7 (cifras de control)
y §8 completo (casos límite). Se usa el archivo de prueba
`tests/fixtures/movimientos_prueba.xlsx` (generado por
`tests/fixtures/generar_movimientos_prueba.py`), que vive dentro de `tests/`
porque `INSUMOS/` es de solo lectura y no contiene ese archivo.

Las variantes de cada caso se crean en `tmp_path` modificando una copia del
archivo de prueba: nunca se escribe en `INSUMOS/` ni en el archivo versionado.

Las pruebas de pantalla usan el cliente Flask de `tests/conftest.py` y sustituyen
la llamada real al agente (red externa) por una respuesta fija: las cifras y los
estados los calcula el código, no el agente (AGENTS.md §4 y §9).
"""

from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from app.services.agente import (
    NO_INDICADO,
    aplicar_analisis,
    consultar_agente,
    parsear_respuesta,
)
from app.services.agrupacion import r4_agrupar_por_cruce
from app.services.carga import COLUMNAS_OBLIGATORIAS, r1_cargar_movimientos
from app.services.costos import r5_detectar_costo_mayor
from app.services.emparejamiento import r3_emparejar
from app.services.exportacion import construir_filas_exportables
from app.services.revision import (
    CORRECTO,
    REVISAR,
    ROJO,
    VERDE,
    r6_marcar_revisar,
    r7_marcar_semaforos,
)
from app.services.filtro import r2_filtrar_eo_so

# Archivo de prueba versionado dentro de tests/ (nunca en INSUMOS/).
RUTA_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "movimientos_prueba.xlsx"

# Las 14 columnas reales, en el orden de AGENTS.md §2.
COLUMNAS = list(COLUMNAS_OBLIGATORIAS)

# Nombre de la hoja del insumo real: lleva un espacio final que R1 recorta.
NOMBRE_HOJA = "Movimientos por Tipo Documento "

# Valores esperados del archivo de prueba, calculados a mano con sus datos
# (no se copian de la salida de la app). Sirven para comprobar el archivo.
FILAS_PRUEBA = 10
FILAS_EO_PRUEBA = 5
FILAS_SO_PRUEBA = 4
CRUCES_PRUEBA = 4
DIFERENCIA_GLOBAL_PRUEBA = 7750.0
SUMA_ALERTAS_PRUEBA = 8000.0
SUMA_UNITARIA_PRUEBA = 400.0

# Físicos del archivo de prueba, para armar las variantes de cada caso.
FISICO_EO_DOS_LINEAS = 2000
FISICO_SO_DOS_LINEAS = 1999
FISICO_EO_ALERTA = 3000
FISICO_SO_ALERTA = 2999
FISICO_EO_SIN_ALERTA = 4000
FISICO_SO_SIN_ALERTA = 3999
FISICO_EO_INCOMPLETA = 5000
FISICO_SO_INCOMPLETA = 4999


# --- Helpers de archivos ---------------------------------------------------


def _leer_filas(ruta=RUTA_FIXTURE):
    """Devuelve `(encabezados, filas)` del primer libro/hoja del archivo."""
    libro = load_workbook(ruta, read_only=True, data_only=True)
    try:
        hoja = libro.worksheets[0]
        filas = [list(fila) for fila in hoja.iter_rows(values_only=True)]
    finally:
        libro.close()
    return filas[0], filas[1:]


def _escribir_xlsx(ruta, encabezados, filas):
    """Escribe un `.xlsx` con la hoja del insumo y devuelve su ruta."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = NOMBRE_HOJA
    hoja.append(list(encabezados))
    for fila in filas:
        hoja.append(list(fila))
    libro.save(ruta)
    libro.close()
    return ruta


def _copia(ruta, filas, encabezados=None):
    """Escribe una copia del archivo de prueba con las filas indicadas."""
    if encabezados is None:
        encabezados, _ = _leer_filas()
    return _escribir_xlsx(ruta, encabezados, filas)


def _filas_de_tipo(filas, tipo, fisico):
    """Filtra las filas por `Tipo Doc.` y `No. Físico` exactos."""
    i_tipo = COLUMNAS.index("Tipo Doc.")
    i_fisico = COLUMNAS.index("No. Físico")
    return [
        fila
        for fila in filas
        if str(fila[i_tipo]).strip() == tipo and fila[i_fisico] == fisico
    ]


def _quitar(filas, tipo, fisico):
    """Devuelve las filas sin el documento indicado (para dejarlo huérfano)."""
    i_tipo = COLUMNAS.index("Tipo Doc.")
    i_fisico = COLUMNAS.index("No. Físico")
    return [
        list(fila)
        for fila in filas
        if not (str(fila[i_tipo]).strip() == tipo and fila[i_fisico] == fisico)
    ]


def _cambiar(filas, tipo, fisico, columna, valor):
    """Devuelve una copia con `columna` cambiada en el documento indicado."""
    i_tipo = COLUMNAS.index("Tipo Doc.")
    i_fisico = COLUMNAS.index("No. Físico")
    i_columna = COLUMNAS.index(columna)
    nuevas = [list(fila) for fila in filas]
    for fila in nuevas:
        if str(fila[i_tipo]).strip() == tipo and fila[i_fisico] == fisico:
            fila[i_columna] = valor
    return nuevas


def _agregar(filas, nueva):
    """Devuelve una copia con una fila adicional al final."""
    return [list(fila) for fila in filas] + [list(nueva)]


def _fila_incompleta(fisico):
    """Fila EO a la que solo le quedan Fecha, Tipo Doc. y No. Físico."""
    fila = [None] * len(COLUMNAS)
    fila[COLUMNAS.index("Fecha")] = datetime(2026, 11, 4)
    fila[COLUMNAS.index("Tipo Doc.")] = "EO"
    fila[COLUMNAS.index("No. Físico")] = fisico
    return fila


# --- Helpers del pipeline --------------------------------------------------


def _correr_pipeline(registros):
    """Corre R2 a R7 en memoria y devuelve todas las salidas intermedias."""
    registros_eo_so, total_eo, total_so = r2_filtrar_eo_so(registros)
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


def _pipeline_de(ruta):
    """Carga un `.xlsx` con R1 y corre R2 a R7 sobre sus registros."""
    carga = r1_cargar_movimientos(ruta)
    assert carga["ok"] is True, carga["mensaje"]
    return _correr_pipeline(carga["registros"])


def _buscar(cruces, id_cruce):
    """Devuelve el cruce con ese identificador; falla si no existe."""
    encontrados = [cruce for cruce in cruces if cruce["id_cruce"] == id_cruce]
    assert len(encontrados) == 1, [c["id_cruce"] for c in cruces]
    return encontrados[0]


def _ids_en_revisar(cruces):
    """Identificadores de las entradas marcadas "Revisar"."""
    return [cruce["id_cruce"] for cruce in cruces if cruce["estado_revision"] == REVISAR]


def _subir(cliente, ruta, nombre=None):
    """Sube un archivo por el formulario `/cargar` con el cliente Flask."""
    with open(ruta, "rb") as archivo:
        return cliente.post(
            "/cargar",
            data={"archivo": (archivo, nombre or Path(ruta).name)},
            content_type="multipart/form-data",
        )


# --- Helpers de pantalla ---------------------------------------------------


@pytest.fixture()
def agente_fuera_de_contrato(monkeypatch):
    """Sustituye la llamada real al agente por una respuesta descartada.

    Simula exactamente lo que devuelve el código cuando la respuesta no cumple
    el contrato (AGENTS.md §8): `ok = False` y sin análisis. Evita además salir
    a la red durante las pruebas.
    """
    monkeypatch.setattr(
        "app.controllers.resultados.consultar_agente",
        lambda cruces: {"ok": False, "motivo": "contrato_invalido", "analisis": {}},
    )


def _seguir(cliente, respuesta):
    """Sigue la redirección de una respuesta y devuelve la página final."""
    ubicacion = respuesta.headers["Location"]
    return ubicacion, cliente.get(ubicacion)


# --- El archivo de prueba --------------------------------------------------


def test_fixture_movimientos_prueba_carga_10_filas_y_14_columnas():
    """El archivo de prueba es un `.xlsx` válido de 10 filas y 14 columnas."""
    carga = r1_cargar_movimientos(RUTA_FIXTURE)

    assert carga["ok"] is True, carga["mensaje"]
    assert carga["filas"] == FILAS_PRUEBA
    assert carga["filas"] >= 6  # AGENTS.md §9: al menos 6 filas
    assert carga["columnas"] == 14
    assert carga["hoja"] == NOMBRE_HOJA.strip()

    tipos = {str(registro["Tipo Doc."]).strip() for registro in carga["registros"]}
    assert {"EO", "SO"} <= tipos


def test_fixture_movimientos_prueba_cumple_so_es_eo_menos_uno():
    """Todos los pares del archivo de prueba cumplen `SO = EO − 1` (R3)."""
    resultado = _pipeline_de(RUTA_FIXTURE)
    pares = resultado["emparejamiento"]["pares"]

    assert len(pares) == CRUCES_PRUEBA
    assert resultado["emparejamiento"]["eo_sin_pareja"] == []
    assert resultado["emparejamiento"]["so_sin_pareja"] == []
    for par in pares:
        assert par["fisico_so"] == par["fisico_eo"] - 1, par["id_cruce"]


def test_fixture_movimientos_prueba_incluye_cruce_con_total_eo_notoriamente_mayor():
    """El archivo de prueba trae un cruce con Total EO muy superior al SO (§9)."""
    resultado = _pipeline_de(RUTA_FIXTURE)
    cruce = _buscar(resultado["cruces"], "EO-3000-SO-2999")

    assert cruce["total_eo"] == 10000.0
    assert cruce["total_so"] == 2000.0
    assert cruce["costo_eo_mayor"] is True
    assert cruce["diferencia_costo"] == 8000.0
    assert cruce["semaforo"] == ROJO


def test_fixture_movimientos_prueba_incluye_un_cruce_correcto_con_eo_igual_a_so():
    """El archivo de prueba trae un cruce Correcto con Total EO = Total SO."""
    resultado = _pipeline_de(RUTA_FIXTURE)
    cruce = _buscar(resultado["cruces"], "EO-2000-SO-1999")

    assert cruce["total_eo"] == cruce["total_so"] == 2000.0
    assert cruce["costo_eo_mayor"] is False
    assert cruce["diferencia_costo"] == 0.0
    assert cruce["estado_revision"] == CORRECTO
    assert cruce["semaforo"] == VERDE


def test_fixture_movimientos_prueba_incluye_un_cruce_en_revisar_por_dato_incompleto():
    """El archivo de prueba trae una EO con `Usuario Aplica` vacío → "Revisar"."""
    resultado = _pipeline_de(RUTA_FIXTURE)
    cruce = _buscar(resultado["cruces"], "EO-5000-SO-4999")

    assert cruce["estado_revision"] == REVISAR
    assert len(cruce["lineas_eo"]) == 1
    assert cruce["lineas_eo"][0]["Usuario Aplica"] is None
    assert resultado["resumen_revision"]["en_revisar"] == 1
    assert resultado["resumen_revision"]["correctos"] == 3


def test_fixture_movimientos_prueba_incluye_una_eo_de_dos_lineas_con_su_so():
    """La EO 2000 tiene 2 líneas y su SO 1999 una sola (caso del §8)."""
    resultado = _pipeline_de(RUTA_FIXTURE)
    cruce = _buscar(resultado["cruces"], "EO-2000-SO-1999")

    assert len(cruce["lineas_eo"]) == 2
    assert len(cruce["lineas_so"]) == 1
    assert cruce["cantidad_eo"] == 15.0
    assert cruce["kilos_eo"] == 15.0
    assert cruce["total_eo"] == 2000.0


# --- AGENTS.md §8: casos límite -------------------------------------------


def test_caso_archivo_vacio_responde_ok_false_con_revisar_sin_excepcion(tmp_path):
    """Archivo vacío (0 bytes): `ok=False`, mensaje con "Revisar" y sin reporte."""
    ruta = tmp_path / "vacio.xlsx"
    ruta.write_bytes(b"")

    resultado = r1_cargar_movimientos(ruta)

    assert isinstance(resultado, dict)
    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]
    assert resultado["registros"] == []
    assert resultado["filas"] == 0


def test_caso_xlsx_solo_con_encabezados_responde_revisar(tmp_path):
    """Un `.xlsx` con encabezados y sin filas de datos también es "Revisar"."""
    encabezados, _ = _leer_filas()
    ruta = _escribir_xlsx(tmp_path / "solo_encabezados.xlsx", encabezados, [])

    resultado = r1_cargar_movimientos(ruta)

    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]


def test_caso_formato_incorrecto_txt_responde_revisar(tmp_path):
    """Formato incorrecto (`.txt`): `ok=False` con "Revisar", sin excepción."""
    ruta = tmp_path / "movimientos.txt"
    ruta.write_text("Fecha;Bodega;Tipo Doc.\n2026-11-04;400;EO\n", encoding="utf-8")

    resultado = r1_cargar_movimientos(ruta)

    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]
    assert ".xlsx" in resultado["mensaje"]
    assert resultado["registros"] == []


def test_caso_faltan_columnas_el_mensaje_nombra_la_columna_que_falta(tmp_path):
    """Si falta una columna obligatoria, el mensaje dice cuál falta (§8)."""
    encabezados, filas = _leer_filas()
    indice_total = encabezados.index("Total")
    encabezados_sin_total = [
        columna for columna in encabezados if columna != "Total"
    ]
    filas_sin_total = [
        fila[:indice_total] + fila[indice_total + 1 :] for fila in filas
    ]
    ruta = _escribir_xlsx(
        tmp_path / "sin_total.xlsx", encabezados_sin_total, filas_sin_total
    )

    resultado = r1_cargar_movimientos(ruta)

    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]
    assert "Total" in resultado["mensaje"]
    assert resultado["registros"] == []


def test_caso_celda_obligatoria_vacia_marca_el_cruce_en_revisar(tmp_path):
    """Una celda obligatoria vacía en cualquier línea marca ese cruce (§8)."""
    _, filas = _leer_filas()
    # Se borra `Costo Uni.` de la SO del cruce que estaba correcto.
    filas_vacias = _cambiar(
        filas, "SO", FISICO_SO_DOS_LINEAS, "Costo Uni.", None
    )
    ruta = _copia(tmp_path / "celda_vacia.xlsx", filas_vacias)

    resultado = _pipeline_de(ruta)
    cruce = _buscar(resultado["cruces"], "EO-2000-SO-1999")

    assert cruce["estado_revision"] == REVISAR
    assert _ids_en_revisar(resultado["cruces"]) == [
        "EO-2000-SO-1999",
        "EO-5000-SO-4999",
    ]
    assert resultado["resumen_revision"]["correctos"] == 2
    # "Revisar" no altera los totales ni la comparación de costo (R6).
    assert cruce["total_eo"] == cruce["total_so"] == 2000.0
    assert cruce["costo_eo_mayor"] is False


def test_caso_fila_incompleta_genera_entrada_en_revisar(tmp_path):
    """Una fila incompleta (solo Fecha, Tipo y Físico) queda en "Revisar"."""
    _, filas = _leer_filas()
    ruta = _copia(
        tmp_path / "fila_incompleta.xlsx",
        _agregar(filas, _fila_incompleta(9000)),
    )

    resultado = _pipeline_de(ruta)

    assert "EO-9000-SIN-SO" in _ids_en_revisar(resultado["cruces"])
    entrada = _buscar(resultado["cruces"], "EO-9000-SIN-SO")
    assert entrada["estado_revision"] == REVISAR
    assert len(entrada["lineas_eo"]) == 1
    assert entrada["lineas_so"] == []
    # El resto del archivo sigue procesándose sin error.
    assert resultado["resumen_revision"]["correctos"] == 3


def test_caso_eo_sin_so_genera_entrada_eo_fisico_sin_so(tmp_path):
    """EO sin su SO (`No. Físico − 1` inexistente) → `EO-<fisico>-SIN-SO` (§8)."""
    _, filas = _leer_filas()
    ruta = _copia(
        tmp_path / "eo_sin_so.xlsx",
        _quitar(filas, "SO", FISICO_SO_DOS_LINEAS),
    )

    resultado = _pipeline_de(ruta)

    assert resultado["emparejamiento"]["eo_sin_pareja"] == [FISICO_EO_DOS_LINEAS]
    assert resultado["emparejamiento"]["so_sin_pareja"] == []
    # Las entradas sin pareja se agregan después de los cruces (R6); el orden
    # entre ellas no es parte de la regla, así que se compara como conjunto.
    assert set(_ids_en_revisar(resultado["cruces"])) == {
        "EO-2000-SIN-SO",
        "EO-5000-SO-4999",
    }
    assert len(_ids_en_revisar(resultado["cruces"])) == 2

    huerfana = _buscar(resultado["cruces"], "EO-2000-SIN-SO")
    assert huerfana["estado_revision"] == REVISAR
    # Se conservan las DOS líneas de la EO y no se inventa la SO.
    assert len(huerfana["lineas_eo"]) == 2
    assert huerfana["lineas_so"] == []
    assert huerfana["total_so"] == 0
    assert huerfana["costo_eo_mayor"] is False


def test_caso_so_sin_eo_genera_entrada_so_fisico_sin_eo(tmp_path):
    """SO sin su EO (`No. Físico + 1` inexistente) → `SO-<fisico>-SIN-EO` (§8)."""
    _, filas = _leer_filas()
    ruta = _copia(tmp_path / "so_sin_eo.xlsx", _quitar(filas, "EO", FISICO_EO_ALERTA))

    resultado = _pipeline_de(ruta)

    assert resultado["emparejamiento"]["so_sin_pareja"] == [FISICO_SO_ALERTA]
    assert resultado["emparejamiento"]["eo_sin_pareja"] == []
    assert "SO-2999-SIN-EO" in _ids_en_revisar(resultado["cruces"])

    huerfana = _buscar(resultado["cruces"], "SO-2999-SIN-EO")
    assert huerfana["estado_revision"] == REVISAR
    assert huerfana["lineas_eo"] == []
    assert len(huerfana["lineas_so"]) == 1
    assert huerfana["total_eo"] == 0


@pytest.mark.parametrize("fisico_texto", ["E81764", "3686-1"])
def test_caso_fisico_no_numerico_no_lanza_excepcion_y_queda_en_revisar(
    tmp_path, fisico_texto
):
    """`No. Físico` no numérico (`E81764`, `3686-1`) → "Revisar", sin excepción."""
    _, filas = _leer_filas()
    filas_texto = _cambiar(
        filas, "EO", FISICO_EO_SIN_ALERTA, "No. Físico", fisico_texto
    )
    ruta = _copia(tmp_path / f"fisico_{fisico_texto}.xlsx", filas_texto)

    resultado = _pipeline_de(ruta)

    assert resultado["emparejamiento"]["fisicos_no_numericos"] == [fisico_texto]
    # Nunca se compara como texto: la EO no forma par y la SO queda huérfana.
    assert f"EO-{fisico_texto}-SIN-SO" in _ids_en_revisar(resultado["cruces"])
    assert "SO-3999-SIN-EO" in _ids_en_revisar(resultado["cruces"])

    entrada = _buscar(resultado["cruces"], f"EO-{fisico_texto}-SIN-SO")
    assert entrada["estado_revision"] == REVISAR
    assert entrada["lineas_eo"][0]["No. Físico"] == fisico_texto


def test_caso_documento_con_varias_lineas_suma_cantidad_kilos_y_total():
    """Un documento con varias líneas suma Cantidad, Kilos y Total antes de comparar."""
    resultado = _pipeline_de(RUTA_FIXTURE)
    cruce = _buscar(resultado["cruces"], "EO-2000-SO-1999")
    lineas = cruce["lineas_eo"]

    assert len(lineas) == 2
    assert cruce["cantidad_eo"] == sum(linea["Cantidad"] for linea in lineas) == 15.0
    assert cruce["kilos_eo"] == sum(linea["Kilos"] for linea in lineas) == 15.0
    assert cruce["total_eo"] == sum(linea["Total"] for linea in lineas) == 2000.0
    # Con la SUMA el cruce es igual; comparando línea por línea sería "menor".
    assert cruce["total_eo"] == cruce["total_so"]
    assert cruce["costo_eo_mayor"] is False
    assert cruce["estado_revision"] == CORRECTO


def test_caso_total_eo_mayor_al_so_marca_costo_y_semaforo_rojo():
    """`Total` de la EO mayor al de la SO → `costo_eo_mayor` y semáforo rojo."""
    resultado = _pipeline_de(RUTA_FIXTURE)
    cruce = _buscar(resultado["cruces"], "EO-3000-SO-2999")

    assert cruce["total_eo"] > cruce["total_so"]
    assert cruce["costo_eo_mayor"] is True
    assert cruce["diferencia_costo"] == 8000.0
    assert cruce["semaforo"] == ROJO
    assert cruce["etiqueta_semaforo"] == "Rojo"


def test_caso_tipos_distintos_a_eo_so_se_ignoran_sin_error(tmp_path):
    """Los tipos distintos a EO/SO se ignoran: no son error y no se exportan."""
    resultado = _pipeline_de(RUTA_FIXTURE)

    assert resultado["total_eo"] == FILAS_EO_PRUEBA
    assert resultado["total_so"] == FILAS_SO_PRUEBA
    # 10 filas en el archivo, 9 EO/SO: la FPC se descarta (R2).
    assert len(resultado["registros_eo_so"]) == 9
    assert all(
        str(registro["Tipo Doc."]).strip() in ("EO", "SO")
        for registro in resultado["registros_eo_so"]
    )
    # La fila FPC no aparece en ningún cruce ni en el reporte exportable.
    filas_exportadas = construir_filas_exportables(
        resultado["cruces"], resultado["registros_eo_so"]
    )
    assert len(filas_exportadas) == 9
    assert all(fila["Tipo Doc."] != "FPC" for fila in filas_exportadas)


def test_caso_archivo_con_mas_de_una_fecha_procesa_todas_y_empareja_por_fisico(
    tmp_path,
):
    """Con más de una fecha se procesan todas las filas; empareja por `No. Físico`."""
    _, filas = _leer_filas()
    filas_dos_fechas = _cambiar(
        filas, "SO", FISICO_SO_DOS_LINEAS, "Fecha", datetime(2026, 11, 5)
    )
    filas_dos_fechas = _cambiar(
        filas_dos_fechas, "EO", FISICO_EO_ALERTA, "Fecha", datetime(2026, 11, 6)
    )
    ruta = _copia(tmp_path / "dos_fechas.xlsx", filas_dos_fechas)

    resultado = _pipeline_de(ruta)

    fechas = {registro["Fecha"].date() for registro in resultado["registros_eo_so"]}
    assert len(fechas) == 3
    # El emparejamiento no depende de la fecha: mismos 4 cruces y mismas cifras.
    assert len(resultado["cruces"]) == CRUCES_PRUEBA
    assert [c["id_cruce"] for c in resultado["cruces"]] == [
        "EO-2000-SO-1999",
        "EO-3000-SO-2999",
        "EO-4000-SO-3999",
        "EO-5000-SO-4999",
    ]
    assert resultado["cifras"]["diferencia_global"] == DIFERENCIA_GLOBAL_PRUEBA


def test_caso_fisico_duplicado_en_el_mismo_tipo_marca_revisar(tmp_path):
    """Dos documentos distintos con el mismo `No. Físico` del mismo tipo → "Revisar"."""
    _, filas = _leer_filas()
    fila_duplicada = list(_filas_de_tipo(filas, "EO", FISICO_EO_ALERTA)[0])
    fila_duplicada[COLUMNAS.index("No. Documento")] = 700099
    fila_duplicada[COLUMNAS.index("No. Artículo")] = 1006
    fila_duplicada[COLUMNAS.index("Total")] = 1

    ruta = _copia(
        tmp_path / "fisico_duplicado.xlsx", _agregar(filas, fila_duplicada)
    )

    resultado = _pipeline_de(ruta)
    cruce = _buscar(resultado["cruces"], "EO-3000-SO-2999")

    assert cruce["estado_revision"] == REVISAR
    assert "EO-3000-SO-2999" in _ids_en_revisar(resultado["cruces"])
    # Sigue habiendo un solo cruce para ese físico (R3 agrupa), pero marcado.
    assert len(resultado["cruces"]) == CRUCES_PRUEBA
    assert resultado["resumen_revision"]["en_revisar"] == 2


def test_caso_respuesta_agente_fuera_de_contrato_se_descarta_con_ok_false():
    """`parsear_respuesta` descarta JSON inválido, llaves faltantes y tipos malos."""
    no_json = parsear_respuesta("La EO tiene un costo mayor, revisar.")
    assert no_json == {"ok": False, "motivo": "json_invalido", "analisis": {}}

    faltan_llaves = parsear_respuesta(
        '{"resultados": [{"id_cruce": "EO-2000-SO-1999", "costo_eo_mayor": true}]}'
    )
    assert faltan_llaves["ok"] is False
    assert faltan_llaves["motivo"] == "contrato_invalido"
    assert faltan_llaves["analisis"] == {}

    tipo_incorrecto = parsear_respuesta(
        '{"resultados": [{"id_cruce": "EO-2000-SO-1999", '
        '"costo_eo_mayor": "si", "analisis_anomalia": "texto", '
        '"estado_revision": "Correcto"}]}'
    )
    assert tipo_incorrecto["ok"] is False
    assert tipo_incorrecto["motivo"] == "contrato_invalido"

    estado_invalido = parsear_respuesta(
        '{"resultados": [{"id_cruce": "EO-2000-SO-1999", '
        '"costo_eo_mayor": true, "analisis_anomalia": "texto", '
        '"estado_revision": "Aprobado"}]}'
    )
    assert estado_invalido["ok"] is False
    assert estado_invalido["motivo"] == "contrato_invalido"


class _RespuestaFalsa:
    """Respuesta HTTP mínima del proveedor para probar sin salir a la red.

    Solo expone lo que usa `app.services.agente`: `status_code` y `json()`.
    """

    def __init__(self, status_code, contenido):
        self.status_code = status_code
        self._contenido = contenido

    def json(self):
        return {"choices": [{"message": {"content": self._contenido}}]}


def test_caso_consultar_agente_descarta_respuesta_fuera_de_contrato(monkeypatch):
    """El cliente descarta JSON inválido y contrato incompleto sin excepción (§8)."""
    # Llave ficticia de prueba: la petición HTTP está sustituida, no hay red.
    monkeypatch.setenv("OPENROUTER_API_KEY", "llave-ficticia-de-prueba")
    respuestas = iter(
        [
            _RespuestaFalsa(200, "esto no es un JSON"),
            _RespuestaFalsa(200, '{"resultados": []}'),
        ]
    )
    monkeypatch.setattr(
        "app.services.agente.requests.post", lambda *args, **kwargs: next(respuestas)
    )
    resultado = _pipeline_de(RUTA_FIXTURE)

    sin_json = consultar_agente(resultado["cruces"])
    assert sin_json == {"ok": False, "motivo": "json_invalido", "analisis": {}}

    fuera_de_contrato = consultar_agente(resultado["cruces"])
    assert fuera_de_contrato == {
        "ok": False,
        "motivo": "contrato_invalido",
        "analisis": {},
    }

    # Con la respuesta descartada, cada cruce queda en "no indicado".
    aplicar_analisis(resultado["cruces"], fuera_de_contrato)
    assert all(cruce["analisis"] == NO_INDICADO for cruce in resultado["cruces"])


def test_caso_agente_fuera_de_contrato_la_app_queda_no_indicado_sin_romper(
    cliente, monkeypatch
):
    """Si el agente responde fuera de contrato, todo queda "no indicado" y la app sigue."""
    monkeypatch.setattr(
        "app.controllers.resultados.consultar_agente",
        lambda cruces: parsear_respuesta("respuesta del agente sin JSON"),
    )

    respuesta = _subir(cliente, RUTA_FIXTURE)
    assert respuesta.status_code == 302
    ubicacion, pagina = _seguir(cliente, respuesta)

    assert ubicacion.endswith("/resultados")
    assert pagina.status_code == 200
    texto = pagina.get_data(as_text=True)

    # Los 4 cruces muestran "no indicado"; el aviso también lo menciona.
    assert texto.count(NO_INDICADO) >= CRUCES_PRUEBA
    # Las cifras y los estados siguen saliendo del código, no del agente.
    assert "8.000,00" in texto
    assert "7.750,00" in texto
    assert "Revisar" in texto
    assert CORRECTO in texto
    assert NO_INDICADO == "no indicado"


def test_caso_sin_llave_el_agente_no_consulta_y_todo_queda_no_indicado(monkeypatch):
    """Sin llave no se llama al proveedor: `falta_llave` y todo "no indicado"."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    resultado = _pipeline_de(RUTA_FIXTURE)

    respuesta_agente = consultar_agente(resultado["cruces"])
    assert respuesta_agente["ok"] is False
    assert respuesta_agente["motivo"] == "falta_llave"
    assert respuesta_agente["analisis"] == {}

    cruces = aplicar_analisis(resultado["cruces"], respuesta_agente)
    assert len(cruces) == CRUCES_PRUEBA
    assert all(cruce["analisis"] == NO_INDICADO for cruce in cruces)
    # El análisis no cambia las cifras ni los estados calculados (R5, R6).
    assert cruces[0]["costo_eo_mayor"] is False
    assert cruces[0]["estado_revision"] == CORRECTO


def test_caso_el_agente_no_puede_cambiar_costo_ni_estado():
    """El texto del agente se aplica, pero `costo_eo_mayor` y estado no cambian."""
    cruces = [
        {
            "id_cruce": "EO-2000-SO-1999",
            "costo_eo_mayor": False,
            "estado_revision": CORRECTO,
            "diferencia_costo": 0.0,
        }
    ]
    agente = {
        "ok": True,
        "motivo": "",
        "analisis": {"EO-2000-SO-1999": "Sin diferencia de costo."},
    }

    aplicar_analisis(cruces, agente)

    assert cruces[0]["analisis"] == "Sin diferencia de costo."
    assert cruces[0]["costo_eo_mayor"] is False
    assert cruces[0]["estado_revision"] == CORRECTO
    assert cruces[0]["diferencia_costo"] == 0.0


def test_caso_fixture_en_pantalla_muestra_cifras_correctas(cliente, agente_fuera_de_contrato):
    """Subir el archivo de prueba muestra 4 cruces, 1 en Revisar y sus cifras."""
    respuesta = _subir(cliente, RUTA_FIXTURE)

    assert respuesta.status_code == 302
    ubicacion, pagina = _seguir(cliente, respuesta)

    assert ubicacion.endswith("/resultados")
    assert pagina.status_code == 200
    texto = pagina.get_data(as_text=True)

    # Mensaje de carga: 10 filas y 14 columnas.
    assert "10 filas" in texto
    assert "14 columnas" in texto
    # Cifras de control del archivo de prueba (formato de pantalla).
    assert "7.750,00" in texto  # diferencia global
    assert "8.000,00" in texto  # suma solo donde EO > SO
    assert "400,00" in texto  # suma de diferencias unitarias (única cifra 400,00)
    # Un cruce en Revisar y tres correctos.
    assert "Revisar" in texto
    assert CORRECTO in texto


# --- Ningún caso produce error 500 ----------------------------------------

# Casos que deben ser rechazados por R1 (no generan resultados).
CASOS_INVALIDOS = {
    "archivo_vacio",
    "texto_plano",
    "xlsx_corrupto",
    "sin_columna_total",
    "solo_encabezados",
}

CASOS_VALIDOS = {
    "valido",
    "eo_sin_so",
    "so_sin_eo",
    "fisico_no_numerico",
    "fisico_duplicado",
    "dos_fechas",
    "celda_vacia",
    "fila_incompleta",
    "solo_tipos_ignorados",
}


@pytest.fixture(scope="module")
def archivos_casos(tmp_path_factory):
    """Construye en una carpeta temporal un archivo por cada caso límite."""
    carpeta = tmp_path_factory.mktemp("casos_limite_500")
    encabezados, filas = _leer_filas()
    casos = {}

    casos["valido"] = _escribir_xlsx(carpeta / "valido.xlsx", encabezados, filas)

    vacio = carpeta / "archivo_vacio.xlsx"
    vacio.write_bytes(b"")
    casos["archivo_vacio"] = vacio

    plano = carpeta / "texto_plano.txt"
    plano.write_text(
        "Fecha;Bodega;Tipo Doc.\n2026-11-04;400;EO\n", encoding="utf-8"
    )
    casos["texto_plano"] = plano

    corrupto = carpeta / "xlsx_corrupto.xlsx"
    corrupto.write_bytes(b"esto no es un archivo Excel valido")
    casos["xlsx_corrupto"] = corrupto

    indice_total = encabezados.index("Total")
    casos["sin_columna_total"] = _escribir_xlsx(
        carpeta / "sin_columna_total.xlsx",
        [c for c in encabezados if c != "Total"],
        [fila[:indice_total] + fila[indice_total + 1 :] for fila in filas],
    )

    casos["solo_encabezados"] = _escribir_xlsx(
        carpeta / "solo_encabezados.xlsx", encabezados, []
    )

    casos["eo_sin_so"] = _copia(
        carpeta / "eo_sin_so.xlsx", _quitar(filas, "SO", FISICO_SO_DOS_LINEAS)
    )
    casos["so_sin_eo"] = _copia(
        carpeta / "so_sin_eo.xlsx", _quitar(filas, "EO", FISICO_EO_ALERTA)
    )
    casos["fisico_no_numerico"] = _copia(
        carpeta / "fisico_no_numerico.xlsx",
        _cambiar(filas, "EO", FISICO_EO_SIN_ALERTA, "No. Físico", "E81764"),
    )

    duplicada = list(_filas_de_tipo(filas, "EO", FISICO_EO_ALERTA)[0])
    duplicada[COLUMNAS.index("No. Documento")] = 700099
    casos["fisico_duplicado"] = _copia(
        carpeta / "fisico_duplicado.xlsx", _agregar(filas, duplicada)
    )

    casos["dos_fechas"] = _copia(
        carpeta / "dos_fechas.xlsx",
        _cambiar(filas, "SO", FISICO_SO_DOS_LINEAS, "Fecha", datetime(2026, 11, 5)),
    )
    casos["celda_vacia"] = _copia(
        carpeta / "celda_vacia.xlsx",
        _cambiar(filas, "SO", FISICO_SO_DOS_LINEAS, "Costo Uni.", None),
    )
    casos["fila_incompleta"] = _copia(
        carpeta / "fila_incompleta.xlsx", _agregar(filas, _fila_incompleta(9000))
    )
    casos["solo_tipos_ignorados"] = _copia(
        carpeta / "solo_tipos_ignorados.xlsx",
        _filas_de_tipo(filas, "FPC", 6000),
    )

    return casos


@pytest.mark.parametrize(
    "nombre", sorted(CASOS_VALIDOS | CASOS_INVALIDOS)
)
def test_caso_ningun_archivo_produce_error_500(
    nombre, archivos_casos, cliente, agente_fuera_de_contrato
):
    """Cada caso límite sube sin error 500 (solo 200 o 302) y avisa "Revisar"."""
    respuesta = _subir(cliente, archivos_casos[nombre])

    assert respuesta.status_code in (200, 302), (nombre, respuesta.status_code)
    assert respuesta.status_code != 500

    ubicacion, pagina = _seguir(cliente, respuesta)
    assert pagina.status_code in (200, 302), (nombre, pagina.status_code)
    assert pagina.status_code != 500
    texto = pagina.get_data(as_text=True)

    if nombre in CASOS_INVALIDOS:
        # Se rechaza con mensaje en español que contiene "Revisar".
        assert not ubicacion.endswith("/resultados"), nombre
        assert "Revisar" in texto, nombre

        # AGENTS.md §8: no se genera reporte para un archivo rechazado.
        descarga = cliente.get("/descargar")
        assert descarga.status_code == 302, nombre
        pagina_descarga = cliente.get(descarga.headers["Location"])
        assert "Revisar" in pagina_descarga.get_data(as_text=True), nombre
    else:
        # Se acepta y lleva a resultados, sin caerse.
        assert ubicacion.endswith("/resultados"), nombre
        assert "Conciliador EO / SO" in texto, nombre

        # La descarga del reporte tampoco produce 500.
        descarga = cliente.get("/descargar")
        assert descarga.status_code == 200, (nombre, descarga.status_code)
        assert descarga.headers["Content-Type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
