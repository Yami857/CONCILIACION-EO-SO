"""Service de la exportación del reporte Excel (AGENTS.md §5 "Qué produce la app").

El reporte conserva las 14 columnas originales, en su orden, y agrega al final
las 4 columnas nuevas: `Cruce EO-SO`, `Diferencia de Costo`, `Análisis IA` y
`Estado de Revisión`. Solo lleva las filas EO y SO (183 en el insumo real); las
filas de los otros 11 tipos de documento no forman cruces y no se exportan.

Los montos van sin símbolo de moneda (decisión confirmada por la usuaria) y el
Excel no lleva colores de semáforo: los semáforos son de la pantalla (R7).
"""

import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app.services.carga import COLUMNAS_OBLIGATORIAS

# Las 4 columnas nuevas, con el nombre exacto de AGENTS.md §5.
COLUMNA_CRUCE = "Cruce EO-SO"
COLUMNA_DIFERENCIA = "Diferencia de Costo"
COLUMNA_ANALISIS = "Análisis IA"
COLUMNA_ESTADO = "Estado de Revisión"

COLUMNAS_RESULTADO = (
    COLUMNA_CRUCE,
    COLUMNA_DIFERENCIA,
    COLUMNA_ANALISIS,
    COLUMNA_ESTADO,
)

# Las 18 columnas del reporte: 14 originales en su orden + 4 de resultado.
COLUMNAS_SALIDA = COLUMNAS_OBLIGATORIAS + COLUMNAS_RESULTADO

# Textos exactos que exige AGENTS.md §4 y §5.
NO_INDICADO = "no indicado"
REVISAR = "Revisar"

# Únicos tipos de documento que se procesan (AGENTS.md §2).
TIPOS_EO_SO = ("EO", "SO")

# Marca del identificador de las entradas que no formaron par (R6).
MARCA_SIN_PAREJA = "-SIN-"

# Formato numérico de la columna `Diferencia de Costo` (2 decimales, sin
# símbolo de moneda).
FORMATO_DIFERENCIA = "0.00"

# Límites de los anchos de columna del reporte.
ANCHO_MINIMO = 10
ANCHO_MAXIMO = 45


def _texto(valor):
    """Normaliza una celda de texto a texto sin espacios en los extremos."""
    if valor is None:
        return ""
    return str(valor).strip()


def _fisico_clave(valor):
    """Devuelve la clave comparable de un `No. Físico`.

    Recibe: el valor de la celda `No. Físico` (entero, decimal o texto).
    Devuelve: el entero cuando es numérico y el texto sin espacios cuando no lo
    es (`"E81764"`, `"3686-1"`). Nunca convierte un número a texto para
    comparar (AGENTS.md §8).
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return "SIN-FISICO"
    try:
        return int(valor)
    except (TypeError, ValueError):
        return _texto(valor)


def _clave_linea(linea):
    """Arma la clave `(Tipo Doc., No. Físico)` de una línea del archivo.

    Recibe: una fila de las 14 columnas originales.
    Devuelve: la tupla que identifica a qué documento pertenece la línea, para
    saber a qué cruce va asociada.
    """
    return (_texto(linea.get("Tipo Doc.")), _fisico_clave(linea.get("No. Físico")))


def _id_sin_pareja(tipo, etiqueta):
    """Arma el identificador de una entrada que no formó par (R6).

    Recibe: el tipo de documento ("EO" o "SO") y el texto del `No. Físico`.
    Devuelve: `EO-<fisico>-SIN-SO` o `SO-<fisico>-SIN-EO`, en el mismo formato
    que usa R6 para las entradas de "Revisar".
    """
    sufijo = "SIN-SO" if tipo == "EO" else "SIN-EO"
    return f"{tipo}-{etiqueta}-{sufijo}"


def _es_sin_pareja(cruce):
    """Indica si un cruce es una entrada que no formó par (R6).

    Recibe: un cruce de R4 + R5 + R6.
    Devuelve: `True` cuando el identificador trae la marca `-SIN-`, es decir,
    cuando no existe el documento del otro lado.
    """
    return MARCA_SIN_PAREJA in _texto(cruce.get("id_cruce"))


# Salida — Reporte Excel (AGENTS.md §5)
# Recibe: `cruces`, la lista de cruces ya calculados por R4, R5, R6 y con el
#         `analisis` del agente (B6), y `registros`, las filas EO/SO que devuelve
#         R2 (`r2_filtrar_eo_so`), en el orden original del archivo.
# Devuelve: una lista de diccionarios, uno por LÍNEA del archivo (no por cruce),
#         en el orden original, con las 14 columnas originales en su orden y las
#         4 columnas nuevas al final:
#           - `Cruce EO-SO`: el `id_cruce` del par al que pertenece la línea.
#           - `Diferencia de Costo`: la del cruce (`Total EO − Total SO`);
#             vacía (`None`) cuando la entrada no formó par.
#           - `Análisis IA`: el `analisis_anomalia` del agente o `"no indicado"`.
#           - `Estado de Revisión`: `"Correcto"` o `"Revisar"`.
#         Solo se incluyen filas EO y SO; los otros 11 tipos no se exportan.
#         Cada línea de un cruce (las 5 EO con 2 líneas del insumo real) lleva
#         los mismos valores del cruce. Los tipos de las celdas se conservan:
#         fecha como fecha, número como número y texto como texto.
#         Las entradas sin pareja (si existieran) se exportan con su id
#         `...-SIN-...`, la diferencia vacía y estado "Revisar".
def construir_filas_exportables(cruces, registros):
    """Arma las filas del reporte: 14 columnas originales + 4 de resultado."""
    # Índice de qué cruce corresponde a cada línea, tomando el `Tipo Doc.` y el
    # `No. Físico` de la propia línea (R3 agrupa todas las líneas del documento
    # en un solo cruce, así que la clave no se repite entre cruces).
    indice = {}
    for cruce in cruces or []:
        lineas = list(cruce.get("lineas_eo") or []) + list(cruce.get("lineas_so") or [])
        for linea in lineas:
            indice[_clave_linea(linea)] = cruce

    filas = []
    for registro in registros or []:
        tipo = _texto(registro.get("Tipo Doc."))
        if tipo not in TIPOS_EO_SO:
            # AGENTS.md §5: los otros 11 tipos de documento no se exportan.
            continue

        fila = {columna: registro.get(columna) for columna in COLUMNAS_OBLIGATORIAS}
        cruce = indice.get(_clave_linea(registro))

        etiqueta = _texto(registro.get("No. Físico")) or "SIN-FISICO"
        fila[COLUMNA_CRUCE] = (
            _texto(cruce.get("id_cruce")) if cruce is not None else _id_sin_pareja(tipo, etiqueta)
        )

        if cruce is None or _es_sin_pareja(cruce):
            # Entrada sin pareja (R6): no hay Total del otro lado que restar.
            fila[COLUMNA_DIFERENCIA] = None
            fila[COLUMNA_ANALISIS] = NO_INDICADO
            fila[COLUMNA_ESTADO] = REVISAR
        else:
            fila[COLUMNA_DIFERENCIA] = cruce.get("diferencia_costo")
            fila[COLUMNA_ANALISIS] = (
                _texto(cruce.get("analisis")) or NO_INDICADO
            )
            fila[COLUMNA_ESTADO] = _texto(cruce.get("estado_revision")) or REVISAR

        filas.append(fila)

    return filas


def _texto_celda(valor):
    """Devuelve el texto de una celda para medir el ancho de la columna."""
    if isinstance(valor, datetime):
        return valor.isoformat(sep=" ")
    if isinstance(valor, (date, time)):
        return valor.isoformat()
    return "" if valor is None else str(valor)


def _ancho(columna, filas):
    """Calcula un ancho razonable para una columna del reporte.

    Recibe: el nombre de la columna y las filas a escribir.
    Devuelve: el ancho en caracteres, con un mínimo de 10 y un máximo de 45.
    """
    largo = len(columna)
    for fila in filas:
        largo = max(largo, len(_texto_celda(fila.get(columna))))
    return max(ANCHO_MINIMO, min(ANCHO_MAXIMO, largo + 2))


# Salida — Reporte Excel (AGENTS.md §5)
# Recibe: `filas`, la lista que devuelve `construir_filas_exportables`, y
#         `destino`, la ruta del `.xlsx` a escribir o un flujo binario.
# Devuelve: el `.xlsx` escrito, con la fila 1 de encabezados en negrita,
#         congelada, con autofiltro, anchos razonables y la columna
#         `Diferencia de Costo` con formato numérico de 2 decimales. No lleva
#         colores de semáforo (R7 es de la pantalla) ni símbolo de moneda.
def generar_xlsx(filas, destino):
    """Escribe el reporte `.xlsx` con openpyxl."""
    filas = list(filas or [])

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Conciliación EO-SO"

    hoja.append(list(COLUMNAS_SALIDA))
    for celda in hoja[1]:
        celda.font = Font(bold=True)

    for fila in filas:
        hoja.append([fila.get(columna) for columna in COLUMNAS_SALIDA])

    # Encabezado fijo al desplazarse y filtros en todas las columnas.
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions

    for indice, columna in enumerate(COLUMNAS_SALIDA, start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = _ancho(columna, filas)

    # `Diferencia de Costo`: número con 2 decimales, sin símbolo de moneda.
    columna_diferencia = COLUMNAS_SALIDA.index(COLUMNA_DIFERENCIA) + 1
    for numero_fila in range(2, hoja.max_row + 1):
        hoja.cell(row=numero_fila, column=columna_diferencia).number_format = (
            FORMATO_DIFERENCIA
        )

    libro.save(destino)
    return destino


def _valor_a_json(valor):
    """Convierte un valor de celda a algo que JSON pueda guardar.

    Recibe: el valor de una celda del reporte.
    Devuelve: el mismo valor si JSON lo admite, o un objeto
    `{"__tipo__": ..., "valor": ...}` cuando es fecha, hora o `Decimal`, para
    poder devolverle su tipo original al leer la caché.
    """
    if isinstance(valor, datetime):
        return {"__tipo__": "fecha_hora", "valor": valor.isoformat()}
    if isinstance(valor, date):
        return {"__tipo__": "fecha", "valor": valor.isoformat()}
    if isinstance(valor, time):
        return {"__tipo__": "hora", "valor": valor.isoformat()}
    if isinstance(valor, Decimal):
        return {"__tipo__": "decimal", "valor": str(valor)}
    return valor


def _valor_desde_json(valor):
    """Devuelve su tipo original a un valor leído de la caché en JSON."""
    if isinstance(valor, dict) and "__tipo__" in valor:
        tipo = valor.get("__tipo__")
        texto = valor.get("valor")
        try:
            if tipo == "fecha_hora":
                return datetime.fromisoformat(texto)
            if tipo == "fecha":
                return date.fromisoformat(texto)
            if tipo == "hora":
                return time.fromisoformat(texto)
            if tipo == "decimal":
                return Decimal(str(texto))
        except (TypeError, ValueError):
            return texto
    return valor


# Salida — Reporte Excel (AGENTS.md §5): una sola llamada a la IA por carga
# Recibe: `filas`, la lista de `construir_filas_exportables`, y `destino`, la
#         ruta del archivo `.json` de caché.
# Devuelve: la ruta escrita. Guarda las filas ya armadas (con el análisis que
#         redactó el agente) para que la descarga NO vuelva a llamar a la IA:
#         solo lee esta caché y escribe el `.xlsx`.
def guardar_filas_exportables(filas, destino):
    """Guarda las filas exportables en un JSON de caché."""
    ruta = Path(destino)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    datos = {
        "columnas": list(COLUMNAS_SALIDA),
        "filas": [
            {columna: _valor_a_json(fila.get(columna)) for columna in COLUMNAS_SALIDA}
            for fila in filas or []
        ],
    }
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return ruta


# Salida — Reporte Excel (AGENTS.md §5): la descarga no llama a la IA
# Recibe: la ruta del JSON de caché que dejó `/resultados`.
# Devuelve: la lista de filas exportables, con sus tipos originales (fecha como
#         fecha, número como número, texto como texto).
def leer_filas_exportables(ruta):
    """Lee las filas exportables guardadas en la caché de `/resultados`."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    filas = []
    for fila in datos.get("filas") or []:
        filas.append(
            {
                columna: _valor_desde_json(fila.get(columna))
                for columna in COLUMNAS_SALIDA
            }
        )
    return filas
