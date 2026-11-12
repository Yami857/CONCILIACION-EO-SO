"""Service de carga y validación del archivo de movimientos (regla R1)."""

import os
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

# Las 14 columnas obligatorias, en el orden y con la ortografía exacta de
# AGENTS.md §2 ("Campos reales, en orden"). No se agrega ni se renombra ninguna.
COLUMNAS_OBLIGATORIAS = (
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
)


def _formato_miles(numero):
    """Devuelve un entero con separador de miles con punto (ej. 4.898)."""
    return f"{numero:,}".replace(",", ".")


def _texto(valor):
    """Normaliza un encabezado: texto sin espacios en los extremos."""
    if valor is None:
        return ""
    return str(valor).strip()


def _respuesta_error(mensaje):
    """Estructura de respuesta con `ok = False` y el mensaje en español."""
    return {
        "ok": False,
        "mensaje": mensaje,
        "hoja": None,
        "filas": 0,
        "columnas": 0,
        "encabezados": [],
        "registros": [],
    }


def _resolver_archivo(archivo):
    """Separa nombre y fuente de lectura de un FileStorage o de una ruta.

    Devuelve (nombre, fuente, error). Cuando `error` no es None, no hay nada
    que leer y el mensaje ya viene listo en español.
    """
    # Archivo subido por el formulario (werkzeug FileStorage): tiene nombre y
    # un flujo de bytes en memoria o en un archivo temporal.
    if hasattr(archivo, "filename") and hasattr(archivo, "stream"):
        nombre = (archivo.filename or "").strip()
        if not nombre:
            return None, None, "Revisar: no se recibió ningún archivo. Seleccione el Excel de movimientos (.xlsx) e intente de nuevo."
        flujo = archivo.stream
        flujo.seek(0, os.SEEK_END)
        tamano = flujo.tell()
        flujo.seek(0)
        if tamano == 0:
            return None, None, f'Revisar: el archivo «{nombre}» está vacío. Seleccione el Excel de movimientos (.xlsx) e intente de nuevo.'
        return nombre, flujo, None

    # Ruta en disco (cadena o Path).
    if archivo is None:
        return None, None, "Revisar: no se recibió ningún archivo. Seleccione el Excel de movimientos (.xlsx) e intente de nuevo."
    ruta = Path(archivo)
    if not ruta.is_file():
        return None, None, f'Revisar: no se encontró el archivo «{ruta.name}». Verifique la ruta e intente de nuevo.'
    if ruta.stat().st_size == 0:
        return None, None, f'Revisar: el archivo «{ruta.name}» está vacío. Seleccione el Excel de movimientos (.xlsx) e intente de nuevo.'
    return ruta.name, ruta, None


def _sin_datos(valor):
    """Indica si una celda está vacía (None o texto en blanco)."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


# Regla R1 — Carga y validación del archivo
# Recibe: `archivo`, el Excel subido por el formulario (FileStorage) o una
#         ruta a un archivo en disco.
# Devuelve: un diccionario con `ok`, `mensaje` (español), `hoja` (nombre con
#         `strip()`), `filas` (filas con algún dato), `columnas`, `encabezados`
#         y `registros` (lista de diccionarios con las 14 columnas, fila por
#         fila, sin filtrar ni emparejar).
# Implementa AGENTS.md §3 R1 y §2: se lee la primera hoja, se valida la
# existencia de las 14 columnas y se rechaza con un mensaje en español cuando
# falta alguna o el archivo no se puede leer. No implementa R2–R7.
def r1_cargar_movimientos(archivo):
    """Lee y valida el Excel de movimientos; no filtra ni empareja."""
    nombre, fuente, error = _resolver_archivo(archivo)
    if error:
        return _respuesta_error(error)

    # Solo `.xlsx`: `.xls` y cualquier otro formato se rechazan sin intentar
    # leerlos (AGENTS.md §2: el único insumo real es `.xlsx`).
    if not nombre.lower().endswith(".xlsx"):
        return _respuesta_error(
            f'Revisar: el archivo «{nombre}» no es un Excel .xlsx. '
            "Por ahora solo se admite el formato .xlsx."
        )

    libro = None
    try:
        libro = load_workbook(fuente, read_only=True, data_only=True)
        if not libro.worksheets:
            return _respuesta_error(
                f'Revisar: el archivo «{nombre}» no tiene ninguna hoja con movimientos.'
            )

        # R1: primera hoja, con `strip()` en el nombre (el insumo real se llama
        # "Movimientos por Tipo Documento " y trae un espacio al final).
        hoja = libro.worksheets[0]
        nombre_hoja = _texto(hoja.title)

        filas = hoja.iter_rows(values_only=True)
        try:
            fila_encabezado = next(filas)
        except StopIteration:
            return _respuesta_error(
                f'Revisar: el archivo «{nombre}» no tiene fila de encabezado. '
                "Debe traer las 14 columnas de movimientos."
            )

        encabezados = [_texto(valor) for valor in fila_encabezado]
        faltantes = [columna for columna in COLUMNAS_OBLIGATORIAS if columna not in encabezados]
        if faltantes:
            detalle = ", ".join(f"«{columna}»" for columna in faltantes)
            return _respuesta_error(
                f"Revisar: al archivo «{nombre}» le faltan columnas obligatorias: "
                f"{detalle}. El archivo debe traer las 14 columnas de movimientos."
            )

        # Posición de cada columna obligatoria en la fila de encabezado, para
        # leer por nombre y no depender del orden físico de las columnas.
        posiciones = {
            columna: encabezados.index(columna) for columna in COLUMNAS_OBLIGATORIAS
        }

        registros = []
        for fila in filas:
            valores = [
                fila[posiciones[columna]] if posiciones[columna] < len(fila) else None
                for columna in COLUMNAS_OBLIGATORIAS
            ]
            # Solo cuentan las filas con algún dato: las filas totalmente
            # vacías del Excel se ignoran.
            if all(_sin_datos(valor) for valor in valores):
                continue
            registros.append(dict(zip(COLUMNAS_OBLIGATORIAS, valores)))

        if not registros:
            return _respuesta_error(
                f'Revisar: el archivo «{nombre}» no tiene filas de datos debajo '
                "del encabezado."
            )

        # Cantidad de columnas realmente presentes en el encabezado.
        columnas = len([encabezado for encabezado in encabezados if encabezado])

        return {
            "ok": True,
            "mensaje": (
                f"{_formato_miles(len(registros))} filas y "
                f"{len(COLUMNAS_OBLIGATORIAS)} columnas cargadas desde la hoja "
                f"«{nombre_hoja}»."
            ),
            "hoja": nombre_hoja,
            "filas": len(registros),
            "columnas": columnas,
            "encabezados": encabezados,
            "registros": registros,
        }
    except (InvalidFileException, BadZipFile, KeyError, OSError, ValueError):
        return _respuesta_error(
            f'Revisar: no se pudo leer «{nombre}» como Excel .xlsx. '
            "Verifique que el archivo no esté dañado ni abierto en Excel e intente de nuevo."
        )
    except Exception:
        # R6/§8: la app nunca se cae; el caso se reporta con la palabra "Revisar".
        return _respuesta_error(
            f'Revisar: ocurrió un problema al leer «{nombre}». '
            "Verifique el archivo e intente de nuevo."
        )
    finally:
        if libro is not None:
            libro.close()
