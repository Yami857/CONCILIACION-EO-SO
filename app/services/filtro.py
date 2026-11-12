"""Service del filtro de registros EO / SO (regla R2)."""

# Los únicos dos tipos de documento que se procesan (AGENTS.md §2).
TIPOS_EO_SO = ("EO", "SO")


def _texto(valor):
    """Normaliza el valor de `Tipo Doc.` a texto sin espacios en los extremos."""
    if valor is None:
        return ""
    return str(valor).strip()


# Regla R2 — Filtro de registros (AGENTS.md §3 R2)
# Recibe: `registros`, lista de diccionarios con las 14 columnas tal como los
#         entrega R1 (`r1_cargar_movimientos`), sin filtrar.
# Devuelve: una tupla `(registros_eo_so, total_eo, total_so)` donde
#         `registros_eo_so` conserva el orden del archivo y solo contiene las
#         filas con `Tipo Doc.` igual a "EO" o "SO"; `total_eo` y `total_so`
#         son el conteo de FILAS de cada tipo (no de documentos).
# Descarta los otros 11 tipos de documento del insumo (4.715 filas) sin
# marcarlos como error. No empareja ni suma líneas: eso es R3 y R4.
def r2_filtrar_eo_so(registros):
    """Deja solo las filas EO y SO; las demás se ignoran."""
    registros_eo_so = []
    total_eo = 0
    total_so = 0

    for registro in registros or []:
        tipo = _texto(registro.get("Tipo Doc."))
        if tipo == "EO":
            total_eo += 1
        elif tipo == "SO":
            total_so += 1
        else:
            # AGENTS.md §8: tipos distintos a EO/SO se ignoran; no son error.
            continue
        registros_eo_so.append(registro)

    return registros_eo_so, total_eo, total_so
