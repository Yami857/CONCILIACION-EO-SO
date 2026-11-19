"""Service de la agrupación por cruce (regla R4)."""


def _es_numero(valor):
    """Indica si una celda puede sumarse sin inventar un cero.

    Recibe: el valor tal como viene del Excel.
    Devuelve: `True` para números reales (no booleanos) y para texto convertible
    a número; `False` para celdas vacías, booleanos y texto no numérico
    (`"N/A"`, por ejemplo). Las celdas inválidas las marca R6 como "Revisar"
    (AGENTS.md §8); esta regla solo decide si entran en la suma.
    """
    if valor is None or isinstance(valor, bool):
        return False
    try:
        float(valor)
        return True
    except (TypeError, ValueError):
        return False


def _numero(valor):
    """Convierte una celda ya validada por `_es_numero` a `float`.

    Recibe: un valor numérico (o texto numérico).
    Devuelve: el `float` correspondiente. No se llama con celdas vacías ni con
    texto no numérico: ésas se ignoran en `_sumar` para no fingir un 0.
    """
    return float(valor)


def _sumar(lineas, campo):
    """Suma una columna sobre las celdas numéricas de todas las líneas.

    Recibe: `lineas` (lista de filas del documento) y `campo` (nombre de la
    columna, por ejemplo `"Cantidad"`).
    Devuelve: la suma como `float` redondeada a 2 decimales, contando SOLO las
    celdas numéricas. Las celdas vacías o no numéricas se ignoran (no suman 0.0)
    para que la cifra no finja un cero: R6 marca el cruce como "Revisar"
    (AGENTS.md §8) y esta regla no corrige ni interpreta datos. Con el insumo
    real, donde todo es numérico, el resultado es idéntico al de antes.
    """
    total = 0.0
    for linea in lineas or []:
        valor = linea.get(campo)
        if _es_numero(valor):
            total += _numero(valor)
    return round(total, 2)


# Regla R4 — Agrupación por cruce (AGENTS.md §3 R4)
# Recibe: `pares`, la lista de pares EO–SO que devuelve R3
#         (`r3_emparejar(...)["pares"]`), cada uno con su `id_cruce`,
#         `fisico_eo`, `fisico_so`, `lineas_eo` y `lineas_so`.
# Devuelve: una lista de diccionarios, uno por cruce, con `id_cruce`,
#         `fisico_eo`, `fisico_so`, `bodega`, `usuario`, las líneas de cada
#         documento (`lineas_eo`, `lineas_so`) y las sumas `cantidad_eo`,
#         `cantidad_so`, `kilos_eo`, `kilos_so`, `total_eo`, `total_so`.
# Un cruce = una EO y su SO. Se suman TODAS las líneas de cada documento
# (en el insumo real 5 EO tienen 2 líneas; las 89 SO tienen 1) antes de
# comparar. `bodega` y `usuario` salen del documento EO, tal como indica R4.
# No compara costos (eso es R5) ni marca estados (eso es R6).
def r4_agrupar_por_cruce(pares):
    """Agrupa cada par EO–SO y suma sus líneas en un solo cruce."""
    cruces = []

    for par in pares or []:
        lineas_eo = par.get("lineas_eo") or []
        lineas_so = par.get("lineas_so") or []
        # Bodega y Usuario Aplica salen del documento EO (AGENTS.md §3 R4).
        primera_eo = lineas_eo[0] if lineas_eo else {}

        cruces.append(
            {
                "id_cruce": par.get("id_cruce"),
                "fisico_eo": par.get("fisico_eo"),
                "fisico_so": par.get("fisico_so"),
                "bodega": primera_eo.get("Bodega"),
                "usuario": primera_eo.get("Usuario Aplica"),
                "lineas_eo": lineas_eo,
                "lineas_so": lineas_so,
                "cantidad_eo": _sumar(lineas_eo, "Cantidad"),
                "cantidad_so": _sumar(lineas_so, "Cantidad"),
                "kilos_eo": _sumar(lineas_eo, "Kilos"),
                "kilos_so": _sumar(lineas_so, "Kilos"),
                "total_eo": _sumar(lineas_eo, "Total"),
                "total_so": _sumar(lineas_so, "Total"),
            }
        )

    return cruces
