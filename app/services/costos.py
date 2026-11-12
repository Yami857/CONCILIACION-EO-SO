"""Service de la detección de anomalía de costo (regla R5)."""

from decimal import Decimal, InvalidOperation, localcontext

# Precisión interna para dividir Total / Kilos sin perder centavos. El
# redondeo de salida se hace al final, a 2 decimales.
_PRECISION = 28


def _decimal(valor):
    """Convierte un número ya sumado a `Decimal` exacto; 0 si no es numérico."""
    if valor is None or isinstance(valor, bool):
        return Decimal("0")
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _redondear(valor):
    """Redondea un `Decimal` a 2 decimales y lo devuelve como `float`."""
    return float(valor.quantize(Decimal("0.01")))


def _comparar_unitario(cruce):
    """Compara el Costo Uni. ponderado por kilos de la EO contra el de la SO.

    Recibe: un cruce de R4 (con `total_eo`, `total_so`, `kilos_eo`, `kilos_so`).
    Devuelve: `1` si el unitario de la EO es mayor, `0` si es igual, `-1` si es
    menor, y `None` si algún `Kilos` es 0 (no se divide: se omite del cálculo).
    La comparación se hace con productos cruzados exactos
    (`total_eo × kilos_so` contra `total_so × kilos_eo`), sin dividir, para no
    introducir diferencias de redondeo.
    """
    kilos_eo = _decimal(cruce.get("kilos_eo"))
    kilos_so = _decimal(cruce.get("kilos_so"))
    if kilos_eo == 0 or kilos_so == 0:
        # AGENTS.md: si Kilos es 0 no se divide; el cruce se omite del cálculo.
        return None

    izquierda = _decimal(cruce.get("total_eo")) * kilos_so
    derecha = _decimal(cruce.get("total_so")) * kilos_eo
    if izquierda > derecha:
        return 1
    if izquierda < derecha:
        return -1
    return 0


# Regla R5 — Detección de anomalía de costo (AGENTS.md §3 R5 y §7)
# Recibe: `cruces`, la lista de cruces de R4 (`r4_agrupar_por_cruce`).
# Devuelve: una tupla `(cruces_con_costo, cifras)`:
#   - `cruces_con_costo`: los mismos cruces, en el mismo orden, más
#        `costo_eo_mayor` (booleano: `total_eo > total_so`) y
#        `diferencia_costo` (`total_eo - total_so`, solo tiene sentido cuando
#        `costo_eo_mayor` es verdadero).
#   - `cifras`: las cifras de control de AGENTS.md §7 y los conteos:
#        `diferencia_global`, `suma_diferencias_eo_mayor`,
#        `suma_diferencias_unitaria`, `cruces_total`, `cruces_eo_mayor`,
#        `cruces_total_mayor`, `cruces_unitario_mayor`,
#        `cruces_unitario_igual` y `cruces_unitario_menor`.
# Se compara el **Total del documento** (suma de la columna `Total` de todas
# sus líneas), NO el `Costo Uni.` ni el costo por artículo, y el `Total` se usa
# tal como viene en el archivo: no se recalcula (AGENTS.md §5 y PLAN.md §5).
def r5_detectar_costo_mayor(cruces):
    """Marca `costo_eo_mayor` por Total del documento y calcula las cifras."""
    cruces_con_costo = []
    cruces_total_mayor = 0
    cruces_unitario_mayor = 0
    cruces_unitario_igual = 0
    cruces_unitario_menor = 0

    with localcontext() as contexto:
        contexto.prec = _PRECISION

        diferencia_global = Decimal("0")
        suma_diferencias_eo_mayor = Decimal("0")
        suma_diferencias_unitaria = Decimal("0")

        for cruce in cruces or []:
            total_eo = _decimal(cruce.get("total_eo"))
            total_so = _decimal(cruce.get("total_so"))

            # R5: comparación del Total del documento, no del Costo Uni.
            diferencia = total_eo - total_so
            costo_eo_mayor = total_eo > total_so

            cruce_con_costo = dict(cruce)
            cruce_con_costo["costo_eo_mayor"] = costo_eo_mayor
            cruce_con_costo["diferencia_costo"] = _redondear(diferencia)
            cruces_con_costo.append(cruce_con_costo)

            diferencia_global += diferencia
            if costo_eo_mayor:
                # Solo se reporta cuando el Total de la EO es mayor (R5).
                cruces_total_mayor += 1
                suma_diferencias_eo_mayor += diferencia

            comparacion = _comparar_unitario(cruce)
            if comparacion == 1:
                cruces_unitario_mayor += 1
                # Diferencia de Costo Uni. ponderado por kilos (AGENTS.md §7).
                kilos_eo = _decimal(cruce.get("kilos_eo"))
                kilos_so = _decimal(cruce.get("kilos_so"))
                suma_diferencias_unitaria += (total_eo / kilos_eo) - (
                    total_so / kilos_so
                )
            elif comparacion == 0:
                cruces_unitario_igual += 1
            elif comparacion == -1:
                cruces_unitario_menor += 1
            # `None`: Kilos 0, el cruce se omite del cálculo unitario.

        cifras = {
            # Las tres cifras monetarias de AGENTS.md §7, a 2 decimales.
            "diferencia_global": _redondear(diferencia_global),
            "suma_diferencias_eo_mayor": _redondear(suma_diferencias_eo_mayor),
            "suma_diferencias_unitaria": _redondear(suma_diferencias_unitaria),
            # Conteos.
            "cruces_total": len(cruces_con_costo),
            "cruces_eo_mayor": cruces_total_mayor,
            "cruces_total_mayor": cruces_total_mayor,
            "cruces_unitario_mayor": cruces_unitario_mayor,
            "cruces_unitario_igual": cruces_unitario_igual,
            "cruces_unitario_menor": cruces_unitario_menor,
        }

    return cruces_con_costo, cifras
