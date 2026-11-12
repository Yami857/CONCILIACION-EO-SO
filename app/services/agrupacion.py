"""Service de la agrupación por cruce (regla R4)."""


def _numero(valor):
    """Convierte una celda numérica a `float`; devuelve 0.0 si no es numérica.

    No corrige ni interpreta datos: solo evita que una celda vacía o no
    numérica rompa la suma. Las celdas obligatorias vacías las marca R6
    (AGENTS.md §8), no esta regla.
    """
    if valor is None or isinstance(valor, bool):
        return 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _sumar(lineas, campo):
    """Suma una columna sobre TODAS las líneas de un documento.

    Recibe: `lineas` (lista de filas del documento) y `campo` (nombre de la
    columna, por ejemplo `"Cantidad"`).
    Devuelve: la suma como `float` redondeada a 2 decimales.
    """
    total = 0.0
    for linea in lineas or []:
        total += _numero(linea.get(campo))
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
