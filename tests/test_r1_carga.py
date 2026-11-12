"""Pruebas de la regla R1 — Carga y validación del archivo.

Fuente: AGENTS.md §2 (campos, hoja real), §3 R1, §7 (4.898 filas, 14 columnas)
y §8 (archivo vacío, formato incorrecto, columnas faltantes).

Las pruebas usan el archivo real de `INSUMOS/` a través de la copia temporal
del fixture `ruta_insumo`; los archivos inválidos se construyen en `tmp_path`.
"""

from openpyxl import Workbook

from app.services.carga import COLUMNAS_OBLIGATORIAS, r1_cargar_movimientos

# Valores de control de AGENTS.md §2 y §7 para el insumo real.
FILAS_REALES = 4898
COLUMNAS_REALES = 14
HOJA_REAL = "Movimientos por Tipo Documento"  # nombre con strip()


def _crear_xlsx(ruta, encabezados, filas=()):
    """Crea un .xlsx mínimo en `ruta` con los encabezados y filas indicados."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Movimientos por Tipo Documento "
    hoja.append(list(encabezados))
    for fila in filas:
        hoja.append(list(fila))
    libro.save(ruta)
    libro.close()
    return ruta


def _fila_ejemplo():
    """Una fila de datos completa, en el orden de las 14 columnas."""
    return (
        "2026-11-04",
        400,
        "EO",
        "ENTRADA  TRANSFORMACION",
        1,
        1615096,
        12345,
        "ARTICULO DE PRUEBA",
        10,
        "KLG",
        10,
        100,
        1000,
        "CN03",
    )


# --- Insumo real -----------------------------------------------------------


def test_r1_archivo_real_carga_4898_filas_y_14_columnas(registros):
    """El insumo real da ok=True, 4.898 filas y 14 columnas (AGENTS.md §7)."""
    assert registros["ok"] is True, registros["mensaje"]
    assert registros["filas"] == FILAS_REALES
    assert registros["columnas"] == COLUMNAS_REALES
    assert len(registros["registros"]) == FILAS_REALES
    assert len(registros["encabezados"]) == COLUMNAS_REALES


def test_r1_nombre_de_hoja_queda_sin_el_espacio_final(registros):
    """La hoja real se llama «Movimientos por Tipo Documento » y se recorta."""
    assert registros["hoja"] == HOJA_REAL
    assert not registros["hoja"].endswith(" ")
    assert registros["hoja"] == registros["hoja"].strip()


def test_r1_mensaje_de_exito_muestra_4898_filas(registros):
    """El mensaje de pantalla informa las 4.898 filas cargadas."""
    assert "4.898 filas" in registros["mensaje"]
    assert "14 columnas" in registros["mensaje"]


def test_r1_carga_por_formulario_avisa_4898_filas(cliente, ruta_insumo):
    """La ruta `/cargar` acepta el Excel real y deja el aviso de 4.898 filas."""
    with open(ruta_insumo, "rb") as archivo:
        respuesta = cliente.post(
            "/cargar",
            data={"archivo": (archivo, ruta_insumo.name)},
            content_type="multipart/form-data",
        )

    # El archivo válido se acepta y lleva a la pantalla de resultados.
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/resultados")

    # El aviso en español que verá la usuaria informa las 4.898 filas.
    with cliente.session_transaction() as sesion:
        avisos = sesion.get("_flashes") or []
    textos = [texto for _, texto in avisos]
    assert any("4.898 filas" in texto for texto in textos), textos
    assert any("14 columnas" in texto for texto in textos), textos


# --- Casos límite de R1 (AGENTS.md §8) -------------------------------------


def test_r1_falta_columna_obligatoria_responde_revisar_con_el_nombre(tmp_path):
    """Si falta una columna, ok=False y el mensaje nombra la columna que falta."""
    encabezados = [c for c in COLUMNAS_OBLIGATORIAS if c != "Kilos"]
    # «Kilos» es la columna 11 de 14 (índice 10): se quita también de la fila.
    fila_sin_kilos = _fila_ejemplo()[:10] + _fila_ejemplo()[11:]
    assert len(encabezados) == 13
    ruta = _crear_xlsx(tmp_path / "sin_kilos.xlsx", encabezados, [fila_sin_kilos])

    resultado = r1_cargar_movimientos(ruta)

    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]
    assert "Kilos" in resultado["mensaje"]
    assert resultado["registros"] == []


def test_r1_archivo_txt_rechazado_con_revisar(tmp_path):
    """Un `.txt` no es un Excel `.xlsx`: ok=False y mensaje con «Revisar»."""
    ruta = tmp_path / "movimientos.txt"
    ruta.write_text(
        "Fecha;Bodega;Tipo Doc.\n2026-11-04;400;EO\n", encoding="utf-8"
    )

    resultado = r1_cargar_movimientos(ruta)

    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]


def test_r1_archivo_vacio_revisar(tmp_path):
    """Un archivo de 0 bytes: ok=False y mensaje con «Revisar»."""
    ruta = tmp_path / "vacio.xlsx"
    ruta.write_bytes(b"")

    resultado = r1_cargar_movimientos(ruta)

    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]
    assert resultado["filas"] == 0


def test_r1_xlsx_sin_filas_de_datos_revisar(tmp_path):
    """Un `.xlsx` con encabezados y sin filas de datos: ok=False con «Revisar»."""
    ruta = _crear_xlsx(tmp_path / "solo_encabezados.xlsx", COLUMNAS_OBLIGATORIAS)

    resultado = r1_cargar_movimientos(ruta)

    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]


def test_r1_xlsx_corrupto_no_lanza_excepcion(tmp_path):
    """Un `.xlsx` dañado no debe provocar una excepción: responde «Revisar»."""
    ruta = tmp_path / "corrupto.xlsx"
    ruta.write_bytes(b"esto no es un archivo Excel valido")

    resultado = r1_cargar_movimientos(ruta)

    assert isinstance(resultado, dict)
    assert resultado["ok"] is False
    assert "Revisar" in resultado["mensaje"]
