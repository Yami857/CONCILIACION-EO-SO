"""Genera `tests/fixtures/movimientos_prueba.xlsx` para las pruebas de casos límite.

AGENTS.md §9 pide un archivo de prueba con al menos 6 filas, mezclando EO y SO,
con la relación `SO.No. Físico = EO.No. Físico − 1`, un caso donde el `Total` de
la EO sea notoriamente mayor al de la SO y un caso con datos incompletos que
fuerce `"Revisar"`. Ese archivo no existía en `INSUMOS/` y no se crea allí: vive
versionado en `tests/fixtures/`.

Uso:
    uv run python tests/fixtures/generar_movimientos_prueba.py

El archivo se escribe una sola vez y luego se versiona; las pruebas lo LEEN y
nunca lo modifican (las variantes se crean en `tmp_path`).

Contenido (10 filas, 14 columnas reales de AGENTS.md §2):

| Cruce | Filas | Qué prueba |
|---|---|---|
| EO-2000-SO-1999 | 2 EO + 1 SO | EO con 2 líneas, Total EO = Total SO (2000) → Correcto/verde |
| EO-3000-SO-2999 | 1 EO + 1 SO | Total EO 10.000 vs SO 2.000 → alerta y semáforo rojo |
| EO-4000-SO-3999 | 1 EO + 1 SO | Total EO 350 < SO 600 → Correcto/verde sin alerta |
| EO-5000-SO-4999 | 1 EO + 1 SO | `Usuario Aplica` vacío en la EO → "Revisar" |
| (sin cruce) | 1 FPC | Tipo distinto a EO/SO → se ignora, no es error |
"""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

# Las 14 columnas reales, en el orden de AGENTS.md §2. No se agrega ni se
# renombra ninguna.
COLUMNAS = [
    "Fecha",
    "Bodega",
    "Tipo Doc.",
    "Descripción Documento",
    "No. Documento",
    "No. Físico",
    "No. Artículo",
    "Descripción Artículo",
    "Cantidad",
    "Unidad Med.",
    "Kilos",
    "Costo Uni.",
    "Total",
    "Usuario Aplica",
]

# Hoja del insumo real, con su espacio final: R1 debe aplicarle `strip()`.
NOMBRE_HOJA = "Movimientos por Tipo Documento "

FECHA = datetime(2026, 11, 4)

FILAS = [
    # Cruce EO-2000-SO-1999: la EO tiene DOS líneas y suman lo mismo que la SO.
    # Cantidad 10 + 5 = 15, Kilos 10 + 5 = 15, Total 1.000 + 1.000 = 2.000.
    (
        FECHA, 400, "EO", "ENTRADA  TRANSFORMACION", 700001, 2000, 1001,
        "LOMO DE CERDO", 10, "KLG", 10, 100, 1000, "CN03",
    ),
    (
        FECHA, 400, "EO", "ENTRADA  TRANSFORMACION", 700001, 2000, 1002,
        "COSTILLA DE CERDO", 5, "KLG", 5, 200, 1000, "CN03",
    ),
    # SO del cruce anterior: SO.No. Físico = EO.No. Físico − 1 (1999 = 2000 − 1).
    (
        FECHA, 400, "SO", "SALIDA  TRANSFORMACION", 700101, 1999, 2001,
        "CARNE MOLIDA", 15, "KLG", 15, 133.33, 2000, "CN03",
    ),
    # Cruce EO-3000-SO-2999: el Total de la EO es NOTORIAMENTE mayor (10.000 vs 2.000).
    (
        FECHA, 401, "EO", "ENTRADA  TRANSFORMACION", 700002, 3000, 1003,
        "PULPA DE RES", 20, "KLG", 20, 500, 10000, "GC02",
    ),
    (
        FECHA, 401, "SO", "SALIDA  TRANSFORMACION", 700102, 2999, 2002,
        "RECORTE DE RES", 20, "KLG", 20, 100, 2000, "GC02",
    ),
    # Cruce EO-4000-SO-3999: correcto y sin alerta (Total EO 350 < Total SO 600).
    (
        FECHA, 402, "EO", "ENTRADA  TRANSFORMACION", 700003, 4000, 1004,
        "HUESO DE CERDO", 8, "UND", 24, 43.75, 350, "PA01",
    ),
    (
        FECHA, 402, "SO", "SALIDA  TRANSFORMACION", 700103, 3999, 2003,
        "HARINA DE HUESO", 8, "UND", 24, 75, 600, "PA01",
    ),
    # Cruce EO-5000-SO-4999: la EO trae `Usuario Aplica` VACÍO → "Revisar" (R6).
    (
        FECHA, 403, "EO", "ENTRADA  TRANSFORMACION", 700004, 5000, 1005,
        "GRASA DE CERDO", 12, "KLG", 12, 100, 1200, None,
    ),
    (
        FECHA, 403, "SO", "SALIDA  TRANSFORMACION", 700104, 4999, 2004,
        "MANTECA DE CERDO", 12, "KLG", 12, 100, 1200, "CN03",
    ),
    # Tipo distinto a EO/SO: R2 lo descarta y no es error (AGENTS.md §8).
    (
        FECHA, 404, "FPC", "FACTURACION CENTRO CARNE", 800001, 6000, 3001,
        "SERVICIO DE FAENA", 3, "KLG", 3, 10, 30, "CN03",
    ),
]

# Cifras que las pruebas esperan del archivo (se calculan a mano con los datos
# de arriba; NO se toman de la app).
ESPERADO = {
    "filas": len(FILAS),
    "filas_eo": 5,
    "filas_so": 4,
    "cruces": 4,
    "en_revisar": 1,
    "alertas": 1,
    "diferencia_global": 7750.0,
    "suma_diferencias_eo_mayor": 8000.0,
    "suma_diferencias_unitaria": 400.0,
}


def generar(destino):
    """Escribe el `.xlsx` de prueba en `destino` y devuelve la ruta."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = NOMBRE_HOJA
    hoja.append(COLUMNAS)
    for fila in FILAS:
        hoja.append(list(fila))
    libro.save(destino)
    libro.close()
    return Path(destino)


if __name__ == "__main__":
    destino = Path(__file__).resolve().parent / "movimientos_prueba.xlsx"
    generar(destino)
    print(f"Creado: {destino} ({len(FILAS)} filas de datos, {len(COLUMNAS)} columnas)")
