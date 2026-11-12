"""Service del emparejamiento EO ↔ SO (regla R3)."""

from collections import defaultdict


def _texto(valor):
    """Normaliza el valor de `Tipo Doc.` a texto sin espacios en los extremos."""
    if valor is None:
        return ""
    return str(valor).strip()


def _fisico_numerico(registro):
    """Convierte `No. Físico` a entero.

    Devuelve `(entero, None)` si se pudo convertir y `(None, valor_original)`
    si no. Nunca revienta: el insumo real trae valores de texto como `E81764`
    y `3686-1` en el tipo EFP (AGENTS.md §2 y §8).
    """
    valor = registro.get("No. Físico")
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, valor
    try:
        return int(valor), None
    except (TypeError, ValueError):
        # Se guarda el valor tal cual llegó, sin convertirlo a texto para
        # comparar (AGENTS.md §8: "nunca convertir a texto para comparar").
        return None, valor


def _agrupar(registros):
    """Agrupa los registros de un mismo tipo por `No. Físico`.

    Devuelve `(grupos, no_numericos)`: `grupos` es un diccionario
    `{fisico: [lineas...]}` con TODAS las líneas de cada documento, y
    `no_numericos` la lista de valores de `No. Físico` que no se pudieron
    convertir a entero.
    """
    grupos = defaultdict(list)
    no_numericos = []

    for registro in registros:
        fisico, invalido = _fisico_numerico(registro)
        if fisico is None:
            no_numericos.append(invalido)
            continue
        grupos[fisico].append(registro)

    return grupos, no_numericos


# Regla R3 — Emparejamiento EO ↔ SO (AGENTS.md §3 R3)
# Recibe: `registros_eo_so`, la lista de filas EO y SO que devuelve R2.
# Devuelve: un diccionario con
#         `pares`: lista de diccionarios, uno por cruce, con las llaves
#             `fisico_eo`, `fisico_so`, `id_cruce`, `lineas_eo` y `lineas_so`;
#         `eo_sin_pareja`: lista de `No. Físico` (enteros) de EO sin SO;
#         `so_sin_pareja`: lista de `No. Físico` (enteros) de SO sin EO;
#         `fisicos_no_numericos`: lista de valores de `No. Físico` que no son
#             numéricos (no forman pareja y van a "Revisar" en R6).
# Agrupa TODAS las líneas de cada documento por `No. Físico` (en el insumo
# real hay 5 EO con 2 líneas) y empareja con la regla confirmada
# `SO.No. Físico = EO.No. Físico − 1`. La regla `SO = EO + 1` del documento de
# contexto está invertida y NO se usa (AGENTS.md §3 R3).
def r3_emparejar(registros_eo_so):
    """Empareja cada EO con la SO de `No. Físico − 1`."""
    eo = [r for r in registros_eo_so or [] if _texto(r.get("Tipo Doc.")) == "EO"]
    so = [r for r in registros_eo_so or [] if _texto(r.get("Tipo Doc.")) == "SO"]

    eo_por_fisico, fisicos_no_numericos = _agrupar(eo)
    so_por_fisico, no_numericos_so = _agrupar(so)
    fisicos_no_numericos.extend(no_numericos_so)

    pares = []
    eo_sin_pareja = []

    for fisico_eo in sorted(eo_por_fisico):
        lineas_eo = eo_por_fisico[fisico_eo]
        fisico_so = fisico_eo - 1
        lineas_so = so_por_fisico.get(fisico_so)

        if not lineas_so:
            # AGENTS.md §8: EO sin su SO (No. Físico − 1 inexistente).
            eo_sin_pareja.append(fisico_eo)
            continue

        pares.append(
            {
                "fisico_eo": fisico_eo,
                "fisico_so": fisico_so,
                "id_cruce": f"EO-{fisico_eo}-SO-{fisico_so}",
                "lineas_eo": lineas_eo,
                "lineas_so": lineas_so,
            }
        )

    fisicos_so_emparejados = {fisico_eo - 1 for fisico_eo in eo_por_fisico}
    so_sin_pareja = [
        fisico_so
        for fisico_so in sorted(so_por_fisico)
        if fisico_so not in fisicos_so_emparejados
    ]

    return {
        "pares": pares,
        "eo_sin_pareja": eo_sin_pareja,
        "so_sin_pareja": so_sin_pareja,
        "fisicos_no_numericos": fisicos_no_numericos,
    }
