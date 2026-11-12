"""Service del agente de IA: cliente OpenRouter y contrato JSON (AGENTS.md §4).

El agente **no** empareja, **no** filtra y **no** calcula cifras: recibe los
cruces EO–SO ya armados y solo redacta el `analisis_anomalia` de cada uno. El
`costo_eo_mayor` y el `estado_revision` siempre los manda el código (R5 y R6).

La llave se lee de `OPENROUTER_API_KEY` en el entorno (nunca se escribe en el
código) y no se registra en logs, ni se devuelve al navegador, ni se incluye en
ningún mensaje de error.
"""

import json
import os
import time

import requests

# Proveedor y modelo confirmados por la usuaria para la entrega B6.
URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
VARIABLE_LLAVE = "OPENROUTER_API_KEY"
VARIABLE_MODELO = "OPENROUTER_MODEL"
MODELO_POR_DEFECTO = "google/gemma-4-31b-it:free"

# Texto exacto que exige AGENTS.md §4 cuando un dato no aparece en la entrada.
NO_INDICADO = "no indicado"

# Parámetros de la única llamada por lote.
TEMPERATURA = 0.2
MAX_TOKENS = 8000
SEGUNDOS_ESPERA = 90
SEGUNDOS_REINTENTO = 2

# Contrato JSON del agente (AGENTS.md §4): 4 llaves por cruce.
LLAVES_CONTRATO = (
    "id_cruce",
    "costo_eo_mayor",
    "analisis_anomalia",
    "estado_revision",
)
ESTADOS_VALIDOS = ("Correcto", "Revisar")

# Textos en español de cada motivo de falla, sin secretos ni datos internos.
MOTIVOS_ES = {
    "falta_llave": "no se configuró la llave del agente en el archivo .env",
    "sin_cruces": "no hay cruces para analizar",
    "cupo_agotado": "el proveedor del agente rechazó la petición por límite de uso",
    "tiempo_agotado": "el proveedor del agente no respondió a tiempo",
    "error_red": "no se pudo conectar con el proveedor del agente",
    "error_proveedor": "el proveedor del agente devolvió un error",
    "respuesta_vacia": "el proveedor del agente no devolvió contenido",
    "json_invalido": "la respuesta del agente no es un JSON válido",
    "contrato_invalido": "la respuesta del agente no cumple el contrato de 4 llaves",
}

PROMPT_SISTEMA = (
    "Eres un analista experto en detección de anomalías de costos de inventario "
    "y subproductos. Recibes cruces EO (Entrada por Transformación) y SO "
    "(Salida por Transformación) que el sistema ya emparejó, agrupó y calculó: "
    "tú no emparejas, no filtras y no recalculas ninguna cifra.\n"
    "Regla estricta: nunca inventes información. Si un dato no aparece en la "
    'entrada, escribe textualmente "no indicado".\n'
    "Responde SOLO con un objeto JSON, sin explicaciones ni texto adicional, "
    'con esta forma exacta: {"resultados": [{"id_cruce": "...", '
    '"costo_eo_mayor": true, "analisis_anomalia": "...", '
    '"estado_revision": "Correcto"}]}.\n'
    "Devuelve un objeto por cada cruce recibido y conserva su id_cruce. En "
    "costo_eo_mayor y estado_revision repite el valor que viene en la entrada. "
    "En analisis_anomalia describe la diferencia de costos detectada en un "
    "máximo de 2 frases y solo con las cifras recibidas."
)


def _numero(valor):
    """Convierte una celda numérica a `float`; 0.0 si no es numérica."""
    if valor is None or isinstance(valor, bool):
        return 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


# Agente de IA — entrada del contrato (AGENTS.md §4)
# Recibe: `cruces`, la lista de cruces ya calculados por R4, R5 y R6.
# Devuelve: una lista de diccionarios compactos, uno por cruce, con
#         `id_cruce`, `fisico_eo`, `fisico_so`, `cantidad_eo`, `cantidad_so`,
#         `kilos_eo`, `kilos_so`, `total_eo`, `total_so`, `costo_unitario_eo`,
#         `costo_unitario_so`, `diferencia_costo`, `costo_eo_mayor` y
#         `estado_revision`.
# Los costos unitarios son `Total / Kilos` a 2 decimales y valen `null` cuando
# los kilos son 0. No se agrega ningún dato que no venga de los cruces.
# Privacidad (corrección de seguridad R1): `bodega` y `usuario` NO se envían al
# proveedor del agente; el resto del contrato no cambia.
def armar_payload_cruces(cruces):
    """Arma la lista compacta de cruces que recibe el agente."""
    payload = []
    for cruce in cruces or []:
        total_eo = _numero(cruce.get("total_eo"))
        total_so = _numero(cruce.get("total_so"))
        kilos_eo = _numero(cruce.get("kilos_eo"))
        kilos_so = _numero(cruce.get("kilos_so"))

        payload.append(
            {
                "id_cruce": cruce.get("id_cruce"),
                "fisico_eo": cruce.get("fisico_eo"),
                "fisico_so": cruce.get("fisico_so"),
                "cantidad_eo": _numero(cruce.get("cantidad_eo")),
                "cantidad_so": _numero(cruce.get("cantidad_so")),
                "kilos_eo": kilos_eo,
                "kilos_so": kilos_so,
                "total_eo": total_eo,
                "total_so": total_so,
                "costo_unitario_eo": _costo_unitario(total_eo, kilos_eo),
                "costo_unitario_so": _costo_unitario(total_so, kilos_so),
                "diferencia_costo": _numero(cruce.get("diferencia_costo")),
                "costo_eo_mayor": bool(cruce.get("costo_eo_mayor")),
                "estado_revision": cruce.get("estado_revision"),
            }
        )
    return payload


def _costo_unitario(total, kilos):
    """Calcula el costo unitario ponderado por kilos (Total / Kilos).

    Recibe: `total` (Total del documento) y `kilos` (Kilos sumados del documento).
    Devuelve: el cociente redondeado a 2 decimales, o `None` cuando `kilos` es 0
    (no se divide por cero y el agente recibe `null`).
    """
    if kilos == 0:
        return None
    return round(total / kilos, 2)


def _extraer_json(texto):
    """Convierte el texto del agente en un objeto JSON, con tolerancia a cercas.

    Recibe: el `content` devuelto por el proveedor (texto libre).
    Devuelve: el objeto JSON ya parseado, o `None` si no hay JSON válido. Se
    toleran los bloques de código ```json ... ``` con que algunos modelos
    envuelven la respuesta; cualquier otro texto alrededor se descarta.
    """
    if not isinstance(texto, str):
        return None

    limpio = texto.strip()
    if limpio.startswith("```"):
        # Se quita la cerca de apertura (``` o ```json) y la de cierre.
        lineas = limpio.splitlines()[1:]
        if lineas and lineas[-1].strip().startswith("```"):
            lineas = lineas[:-1]
        limpio = "\n".join(lineas).strip()

    try:
        return json.loads(limpio)
    except (TypeError, ValueError):
        return None


# Agente de IA — contrato JSON de 4 llaves (AGENTS.md §4)
# Recibe: `datos`, el objeto JSON devuelto por el agente.
# Devuelve: `{id_cruce: analisis_anomalia}` si la respuesta cumple el contrato,
#         o `None` si no lo cumple.
# Para aceptarla se exige: la lista `resultados`, y en cada item las 4 llaves
# (`id_cruce`, `costo_eo_mayor`, `analisis_anomalia`, `estado_revision`) con sus
# tipos correctos, `estado_revision` en {"Correcto", "Revisar"} y
# `analisis_anomalia` como texto no vacío. Si algo no cuadra, la respuesta
# completa se descarta (AGENTS.md §8: "no indicado").
def validar_contrato(datos):
    """Valida el contrato del agente y devuelve el análisis por `id_cruce`."""
    if not isinstance(datos, dict):
        return None

    resultados = datos.get("resultados")
    if not isinstance(resultados, list) or not resultados:
        return None

    analisis = {}
    for item in resultados:
        if not isinstance(item, dict):
            return None
        if any(llave not in item for llave in LLAVES_CONTRATO):
            return None

        id_cruce = item.get("id_cruce")
        if not isinstance(id_cruce, str) or not id_cruce.strip():
            return None

        if not isinstance(item.get("costo_eo_mayor"), bool):
            return None

        estado = item.get("estado_revision")
        if not isinstance(estado, str) or estado.strip() not in ESTADOS_VALIDOS:
            return None

        texto = item.get("analisis_anomalia")
        if not isinstance(texto, str) or not texto.strip():
            return None

        analisis[id_cruce.strip()] = texto.strip()

    return analisis


# Agente de IA — descarte a "no indicado" (AGENTS.md §4 y §8)
# Recibe: `texto`, la respuesta cruda del agente.
# Devuelve: `{"ok": True, "motivo": "", "analisis": {id_cruce: texto}}` si la
#         respuesta cumple el contrato, o
#         `{"ok": False, "motivo": "json_invalido"|"contrato_invalido",
#           "analisis": {}}` si se descarta.
def parsear_respuesta(texto):
    """Parsea y valida la respuesta del agente; la descarta si no cumple."""
    datos = _extraer_json(texto)
    if datos is None:
        return {"ok": False, "motivo": "json_invalido", "analisis": {}}

    analisis = validar_contrato(datos)
    if analisis is None:
        return {"ok": False, "motivo": "contrato_invalido", "analisis": {}}

    return {"ok": True, "motivo": "", "analisis": analisis}


def _contenido(respuesta):
    """Extrae el texto del mensaje del agente desde la respuesta HTTP."""
    datos = respuesta.json()
    if not isinstance(datos, dict):
        return None
    elecciones = datos.get("choices")
    if not isinstance(elecciones, list) or not elecciones:
        return None
    mensaje = elecciones[0].get("message") if isinstance(elecciones[0], dict) else None
    if not isinstance(mensaje, dict):
        return None
    contenido = mensaje.get("content")
    return contenido if isinstance(contenido, str) else None


def _peticion(llave, modelo, mensaje_usuario):
    """Hace la petición al proveedor, con un único reintento si hay 429 o 5xx.

    Recibe: la llave (solo se usa en la cabecera), el modelo y el mensaje.
    Devuelve: el objeto `requests.Response`. No registra la llave ni el
    contenido del mensaje en ningún log.
    """
    cabeceras = {
        "Authorization": f"Bearer {llave}",
        "Content-Type": "application/json",
    }
    cuerpo = {
        "model": modelo,
        "temperature": TEMPERATURA,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": mensaje_usuario},
        ],
    }

    respuesta = requests.post(
        URL_OPENROUTER, headers=cabeceras, json=cuerpo, timeout=SEGUNDOS_ESPERA
    )

    # Reintento único: solo por límite de uso (429) o error del servidor (5xx).
    if respuesta.status_code == 429 or 500 <= respuesta.status_code < 600:
        time.sleep(SEGUNDOS_REINTENTO)
        respuesta = requests.post(
            URL_OPENROUTER, headers=cabeceras, json=cuerpo, timeout=SEGUNDOS_ESPERA
        )

    return respuesta


# Agente de IA — una sola llamada por lote (AGENTS.md §4)
# Recibe: `cruces`, la lista completa de cruces EO–SO de la carga.
# Devuelve: `{"ok": True, "motivo": "", "analisis": {id_cruce: texto}}` cuando
#         el agente responde y cumple el contrato, o
#         `{"ok": False, "motivo": "<clave de MOTIVOS_ES>", "analisis": {}}`
#         cuando falta la llave, se agota el cupo, hay timeout, falla la red o
#         la respuesta no respeta el contrato.
# Nunca lanza una excepción hacia el controller: la app sigue funcionando y
# permite exportar con `analisis_anomalia = "no indicado"`. La llave se lee del
# entorno y nunca se registra ni se devuelve.
def consultar_agente(cruces):
    """Consulta al agente una sola vez por lote y devuelve su análisis."""
    cruces = list(cruces or [])
    if not cruces:
        return {"ok": False, "motivo": "sin_cruces", "analisis": {}}

    llave = os.environ.get(VARIABLE_LLAVE, "").strip()
    if not llave:
        # Sin llave no se hace ninguna petición.
        return {"ok": False, "motivo": "falta_llave", "analisis": {}}

    modelo = os.environ.get(VARIABLE_MODELO, "").strip() or MODELO_POR_DEFECTO
    mensaje_usuario = json.dumps(
        {"cruces": armar_payload_cruces(cruces)}, ensure_ascii=False
    )

    try:
        respuesta = _peticion(llave, modelo, mensaje_usuario)
    except requests.Timeout:
        return {"ok": False, "motivo": "tiempo_agotado", "analisis": {}}
    except requests.RequestException:
        return {"ok": False, "motivo": "error_red", "analisis": {}}

    if respuesta.status_code == 429:
        return {"ok": False, "motivo": "cupo_agotado", "analisis": {}}
    if respuesta.status_code >= 400:
        return {"ok": False, "motivo": "error_proveedor", "analisis": {}}

    try:
        contenido = _contenido(respuesta)
    except ValueError:
        contenido = None
    if contenido is None:
        return {"ok": False, "motivo": "respuesta_vacia", "analisis": {}}

    return parsear_respuesta(contenido)


# Agente de IA — las cifras y el estado mandan desde el código (AGENTS.md §4)
# Recibe: `cruces` y el resultado de `consultar_agente`.
# Devuelve: los mismos cruces con la llave `analisis` puesta: el texto del
#         agente cuando existe para ese `id_cruce` y `"no indicado"` cuando
#         falta. NO toca `costo_eo_mayor`, `diferencia_costo` ni
#         `estado_revision`: esos valores los calcula el código (R5 y R6) y la
#         respuesta del agente no los puede cambiar.
def aplicar_analisis(cruces, resultado):
    """Asigna el análisis del agente a cada cruce, con respaldo "no indicado"."""
    analisis = (resultado or {}).get("analisis") or {}

    for cruce in cruces or []:
        texto = analisis.get(cruce.get("id_cruce"))
        if isinstance(texto, str) and texto.strip():
            cruce["analisis"] = texto.strip()
        else:
            cruce["analisis"] = NO_INDICADO

    return cruces


# Agente de IA — texto del aviso en pantalla (AGENTS.md §4)
# Recibe: la clave de motivo que devuelve `consultar_agente`.
# Devuelve: un texto corto en español, sin secretos, para el aviso discreto de
#         la pantalla de resultados.
def texto_motivo(motivo):
    """Traduce la clave del motivo a un texto corto en español."""
    return MOTIVOS_ES.get(motivo, "el análisis del agente no está disponible")
