"""Utilidad compartida de normalización de texto (sin regla de negocio nueva).

Antes esta misma función estaba copiada en `carga.py`, `filtro.py`,
`emparejamiento.py`, `revision.py` y `exportacion.py`. Aquí vive una sola vez y
los módulos la importan como `_texto` para no cambiar sus llamadas internas.
No implementa ninguna regla R1–R7: solo quita los espacios de los extremos.
"""


def texto(valor):
    """Normaliza una celda a texto sin espacios en los extremos.

    Recibe: el valor de una celda (cualquier tipo, incluido `None`).
    Devuelve: `""` cuando el valor es `None`; en cualquier otro caso,
    `str(valor).strip()`.
    """
    return "" if valor is None else str(valor).strip()
