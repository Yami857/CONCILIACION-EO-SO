"""Services de la marca "Revisar" (regla R6) y del semáforo (regla R7)."""

from collections import defaultdict
from datetime import date, datetime

from app.services.agrupacion import r4_agrupar_por_cruce
from app.services.carga import COLUMNAS_OBLIGATORIAS

# Etiquetas exactas de R6 / R7 (AGENTS.md §3 R6 y R7).
CORRECTO = "Correcto"
REVISAR = "Revisar"
ROJO = "rojo"
VERDE = "verde"

# Los dos únicos tipos de documento que se procesan (AGENTS.md §2).
TIPO_EO = "EO"
TIPO_SO = "SO"

# Columnas de AGENTS.md §2 que se suman en R4 y que, por lo tanto, no pueden
# venir como texto: `agrupacion._numero` las convertiría en 0 en silencio.
CAMPOS_NUMERICOS = ("Cantidad", "Kilos", "Costo Uni.", "Total")


def _texto(valor):
    """Normaliza una celda de texto a texto sin espacios en los extremos."""
    if valor is None:
        return ""
    return str(valor).strip()


def _vacia(valor):
    """Indica si una celda está vacía (`None` o texto en blanco)."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _tipo(registro):
    """Devuelve el `Tipo Doc.` normalizado de un registro."""
    return _texto(registro.get("Tipo Doc."))


def _fisico_entero(registro):
    """Convierte `No. Físico` a entero; `None` si no es numérico.

    No se compara nunca como texto (AGENTS.md §8): los valores como `E81764`
    o `3686-1` quedan fuera del emparejamiento y van a "Revisar".
    """
    valor = registro.get("No. Físico")
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _etiqueta_fisico(valor):
    """Texto legible del `No. Físico` para el identificador de la entrada.

    Recibe: el valor tal como viene del Excel.
    Devuelve: el texto sin espacios; `"SIN-FISICO"` cuando la celda está vacía.
    """
    texto = _texto(valor)
    return texto if texto else "SIN-FISICO"


def _columnas_vacias(lineas):
    """Indica si alguna línea trae vacía alguna de las 14 columnas obligatorias.

    Recibe: lista de líneas (diccionarios con las 14 columnas de AGENTS.md §2).
    Devuelve: `True` si hay al menos una celda obligatoria vacía.
    """
    for linea in lineas or []:
        for columna in COLUMNAS_OBLIGATORIAS:
            if _vacia(linea.get(columna)):
                return True
    return False


def _es_numero(valor):
    """Indica si una celda de las columnas sumadas es un número real.

    Recibe: el valor tal como viene del Excel.
    Devuelve: `True` solo para `int` o `float` y nunca para `bool` (en Python
    `True` es un `int`); un texto como `"N/A"`, una fecha o `None` dan `False`.
    No se convierte nada: no se acepta texto numérico, porque el archivo real
    trae números y "N/A" en una celda es un dato inválido, no un 0.
    """
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _es_fecha(valor):
    """Indica si una celda `Fecha` trae una fecha utilizable.

    Recibe: el valor tal como viene del Excel.
    Devuelve: `True` para `date`/`datetime` (lo que entrega openpyxl con una
    celda con formato de fecha) y también para el texto que ya trae una fecha
    ISO válida (formato `AAAA-MM-DD`), que es lo que llega cuando la celda está
    guardada como texto. Cualquier otro valor (un número, `"N/A"` o vacío) da
    `False` y marca el cruce para revisión.
    """
    if isinstance(valor, (date, datetime)):
        return True
    if isinstance(valor, str):
        try:
            date.fromisoformat(valor.strip())
        except ValueError:
            return False
        return True
    return False


def _valores_invalidos(lineas):
    """Indica si alguna línea trae un dato de tipo inválido en R6.

    Recibe: las líneas de un cruce (diccionarios con las 14 columnas de
    AGENTS.md §2).
    Devuelve: `True` si en alguna línea `Cantidad`, `Kilos`, `Costo Uni.` o
    `Total` no es numérico, o si `Fecha` no es una fecha. Las celdas vacías no
    cuentan aquí: ya las marca `_columnas_vacias`.
    """
    for linea in lineas or []:
        for columna in CAMPOS_NUMERICOS:
            valor = linea.get(columna)
            if _vacia(valor):
                continue
            if not _es_numero(valor):
                return True
        if not _es_fecha(linea.get("Fecha")):
            return True
    return False


def _fisicos_duplicados(registros_eo_so):
    """Detecta `No. Físico` repetido dentro del mismo tipo de documento.

    Recibe: la lista de registros EO/SO de R2.
    Devuelve: un conjunto de claves `(tipo, fisico)` con más de un
    `No. Documento` distinto. Varias líneas del MISMO documento (caso real de
    5 EO con 2 líneas) no son duplicado y no marcan "Revisar".
    """
    documentos = defaultdict(set)
    for registro in registros_eo_so or []:
        tipo = _tipo(registro)
        if tipo not in (TIPO_EO, TIPO_SO):
            continue
        fisico = _fisico_entero(registro)
        if fisico is None:
            continue
        documentos[(tipo, fisico)].add(_texto(registro.get("No. Documento")))

    return {clave for clave, docs in documentos.items() if len(docs) > 1}


def _requiere_revision(cruce, duplicados):
    """Indica si un cruce debe marcarse "Revisar" (AGENTS.md §3 R6 y §8).

    Recibe: un cruce de R4 + R5 y el conjunto de `(tipo, fisico)` duplicados.
    Devuelve: `True` cuando alguna celda obligatoria de sus líneas está vacía,
    cuando un dato tiene un tipo inválido (`Cantidad`, `Kilos`, `Costo Uni.` o
    `Total` no numéricos, o `Fecha` que no es fecha; si no, R4 los convertiría
    en 0 en silencio) o cuando el `No. Físico` del par está duplicado dentro de
    su tipo.
    """
    lineas = list(cruce.get("lineas_eo") or []) + list(cruce.get("lineas_so") or [])
    if _columnas_vacias(lineas):
        return True
    if _valores_invalidos(lineas):
        return True

    for tipo, campo in ((TIPO_EO, "fisico_eo"), (TIPO_SO, "fisico_so")):
        fisico = cruce.get(campo)
        if fisico is not None and (tipo, fisico) in duplicados:
            return True

    return False


def _entrada_huerfana(tipo, fisico, lineas, id_cruce):
    """Arma la entrada de revisión de un registro que no formó par.

    Recibe: `tipo` ("EO" o "SO"), el `No. Físico`, sus líneas reales y el
    identificador de la entrada.
    Devuelve: un diccionario con la misma forma que un cruce de R4 + R5, con
    las sumas del lado que sí existe (el otro lado queda en 0), sin inventar
    líneas, `costo_eo_mayor = False`, `diferencia_costo = 0` y
    `estado_revision = "Revisar"`.
    """
    par = {
        "id_cruce": id_cruce,
        "fisico_eo": fisico if tipo == TIPO_EO else None,
        "fisico_so": fisico if tipo == TIPO_SO else None,
        "lineas_eo": list(lineas) if tipo == TIPO_EO else [],
        "lineas_so": list(lineas) if tipo == TIPO_SO else [],
    }
    entrada = r4_agrupar_por_cruce([par])[0]

    # R4 toma Bodega y Usuario del documento EO; si el que existe es la SO se
    # toman de sus líneas para no dejar el dato en None.
    primera = list(lineas)[0] if lineas else {}
    if _vacia(entrada.get("bodega")):
        entrada["bodega"] = primera.get("Bodega")
    if _vacia(entrada.get("usuario")):
        entrada["usuario"] = primera.get("Usuario Aplica")

    entrada["costo_eo_mayor"] = False
    entrada["diferencia_costo"] = 0
    entrada["estado_revision"] = REVISAR
    return entrada


def _lineas_por_fisico(registros_eo_so):
    """Agrupa los registros EO/SO por `(tipo, No. Físico entero)`.

    Devuelve: `(lineas, no_numericos)`, donde `lineas` es
    `{(tipo, fisico): [registros...]}` y `no_numericos` es
    `{(tipo, etiqueta): [registros...]}` para los `No. Físico` que no son
    numéricos (AGENTS.md §8).
    """
    lineas = defaultdict(list)
    no_numericos = defaultdict(list)

    for registro in registros_eo_so or []:
        tipo = _tipo(registro)
        if tipo not in (TIPO_EO, TIPO_SO):
            continue
        fisico = _fisico_entero(registro)
        if fisico is None:
            no_numericos[(tipo, _etiqueta_fisico(registro.get("No. Físico")))].append(
                registro
            )
            continue
        lineas[(tipo, fisico)].append(registro)

    return lineas, no_numericos


# Regla R6 — Marca "Revisar" (AGENTS.md §3 R6 y §8 Casos límite)
# Recibe: `cruces` (lista de cruces de R4 + R5), `emparejamiento` (resultado de
#         R3, con `eo_sin_pareja`, `so_sin_pareja` y `fisicos_no_numericos`) y
#         `registros_eo_so` (las filas EO/SO de R2, para recuperar las líneas
#         de los registros que no formaron par).
# Devuelve: una tupla `(cruces, resumen_revision)`:
#   - `cruces`: los mismos cruces, en el mismo orden, más `estado_revision`
#        ("Correcto" o "Revisar"), y al final las entradas de revisión de los
#        registros que no formaron par:
#        `EO-<fisico>-SIN-SO` para cada EO sin pareja,
#        `SO-<fisico>-SIN-EO` para cada SO sin pareja y una entrada por cada
#        `No. Físico` no numérico. Esas entradas llevan
#        `estado_revision = "Revisar"`, `costo_eo_mayor = False` y
#        `diferencia_costo = 0`; los campos del lado inexistente quedan en
#        `None` o `0` y no se inventan líneas.
#   - `resumen_revision`: `{"en_revisar": total Revisar, "correctos": total Correcto}`.
# Se marca "Revisar" cuando una celda de las 14 columnas obligatorias está
# vacía en cualquier línea del cruce, cuando un dato trae un tipo inválido
# (`Cantidad`, `Kilos`, `Costo Uni.` o `Total` no numéricos, o `Fecha` que no es
# fecha), cuando el `No. Físico` no es numérico o cuando el `No. Físico` está
# duplicado dentro del mismo tipo de documento (dos `No. Documento` distintos
# bajo el mismo físico). Si no se cumple nada, el estado es "Correcto".
# "Revisar" no excluye el análisis de costo de R5.
def r6_marcar_revisar(cruces, emparejamiento, registros_eo_so):
    """Marca "Revisar" en los cruces y agrega los registros sin pareja."""
    emparejamiento = emparejamiento or {}
    duplicados = _fisicos_duplicados(registros_eo_so)
    lineas_por_fisico, no_numericos = _lineas_por_fisico(registros_eo_so)

    revisados = []
    for cruce in cruces or []:
        entrada = dict(cruce)
        entrada["estado_revision"] = (
            REVISAR if _requiere_revision(entrada, duplicados) else CORRECTO
        )
        revisados.append(entrada)

    # AGENTS.md §8: EO sin su SO (No. Físico − 1 inexistente) → "Revisar".
    for fisico in sorted(emparejamiento.get("eo_sin_pareja") or []):
        lineas = lineas_por_fisico.get((TIPO_EO, fisico), [])
        revisados.append(
            _entrada_huerfana(
                TIPO_EO, fisico, lineas, f"EO-{fisico}-SIN-SO"
            )
        )

    # AGENTS.md §8: SO sin su EO (No. Físico + 1 inexistente) → "Revisar".
    for fisico in sorted(emparejamiento.get("so_sin_pareja") or []):
        lineas = lineas_por_fisico.get((TIPO_SO, fisico), [])
        revisados.append(
            _entrada_huerfana(
                TIPO_SO, fisico, lineas, f"SO-{fisico}-SIN-EO"
            )
        )

    # AGENTS.md §8: No. Físico no numérico → "Revisar"; nunca se compara como
    # texto y nunca revienta.
    for (tipo, etiqueta) in sorted(no_numericos, key=str):
        lineas = no_numericos[(tipo, etiqueta)]
        sufijo = "SIN-SO" if tipo == TIPO_EO else "SIN-EO"
        revisados.append(
            _entrada_huerfana(tipo, None, lineas, f"{tipo}-{etiqueta}-{sufijo}")
        )

    resumen_revision = {
        "en_revisar": len(
            [c for c in revisados if c.get("estado_revision") == REVISAR]
        ),
        "correctos": len(
            [c for c in revisados if c.get("estado_revision") == CORRECTO]
        ),
    }

    return revisados, resumen_revision


# Regla R7 — Semáforo y etiquetas (AGENTS.md §3 R7)
# Recibe: un cruce de R4 + R5 + R6.
# Devuelve: `"rojo"` si `costo_eo_mayor` es verdadero o si
#         `estado_revision == "Revisar"`; `"verde"` en caso contrario. Deja el
#         resultado en las llaves `semaforo` ("rojo"/"verde") y
#         `etiqueta_semaforo` ("Rojo"/"Verde") del cruce, para que la pantalla
#         muestre el texto además del color.
def r7_estado_semaforo(cruce):
    """Calcula el semáforo de un cruce y lo deja en el propio cruce."""
    rojo = bool(cruce.get("costo_eo_mayor")) or (
        cruce.get("estado_revision") == REVISAR
    )
    semaforo = ROJO if rojo else VERDE

    if isinstance(cruce, dict):
        cruce["semaforo"] = semaforo
        cruce["etiqueta_semaforo"] = "Rojo" if rojo else "Verde"

    return semaforo


# Regla R7 — Semáforo y etiquetas (AGENTS.md §3 R7)
# Recibe: la lista de cruces ya marcados por R6.
# Devuelve: una tupla `(cruces, resumen_semaforo)` con la llave `semaforo` y
#         `etiqueta_semaforo` puestas en cada cruce y con los conteos
#         `{"rojos": n, "verdes": m}`.
def r7_marcar_semaforos(cruces):
    """Agrega el semáforo y sus etiquetas a todos los cruces."""
    rojos = 0
    verdes = 0

    for cruce in cruces or []:
        if r7_estado_semaforo(cruce) == ROJO:
            rojos += 1
        else:
            verdes += 1

    return cruces, {"rojos": rojos, "verdes": verdes}
