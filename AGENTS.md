# AGENTS.md — Conciliador EO / SO

Especificación de trabajo para el equipo de desarrollo (OpenCode).
Fuentes: `CONTEXTO/Contexto_Mi_App.md` y `INSUMOS/MOVIMIENTOS 4-11-26.xlsx`.
En el código y en los ejemplos JSON los números usan el formato del archivo de entrada (punto decimal). En la sección 7 los montos se muestran con separador de miles (`.`) y coma decimal (`,`).

---

## 1. Qué es esta app

Aplicación web en español, de uso exclusivo de **Yamileth de los Ángeles Villalobos Castillo**, que automatiza la conciliación de movimientos de inventario entre documentos **EO** (Entrada por Transformación) y **SO** (Salida por Transformación).

- **Problema:** hoy la conciliación se hace a mano, fila por fila, emparejando EO con SO por su número físico, calculando cantidades y costos y buscando dónde el costo de la EO supera al de la SO.
- **Tiempo actual:** ~1 hora por jornada/lote.
- **Objetivo:** reducir ese tiempo a pocos segundos y detectar automáticamente las anomalías de costo.
- **Alcance:** un archivo Excel por lote (una jornada). En el insumo real todas las filas corresponden a una sola fecha.

Los **subproductos no son un campo ni un tipo de documento aparte**: quedan incluidos dentro de los movimientos EO/SO. No se crea ninguna columna ni regla nueva para ellos.

---

## 2. Datos de entrada

### Archivo real disponible

| Archivo | Formato | Hoja | Filas de datos | Columnas |
|---|---|---|---|---|
| `INSUMOS/MOVIMIENTOS 4-11-26.xlsx` | Excel `.xlsx` | `Movimientos por Tipo Documento ` (tiene un espacio final; usar `trim`) | 4.898 | 14 |

No hay otros archivos en `INSUMOS`. No hay PDF. No hay CSV.

### Campos reales, en orden

| # | Campo | Tipo real | Observaciones del insumo |
|---|---|---|---|
| 1 | `Fecha` | fecha | Un solo día en el archivo: 2026-11-04 |
| 2 | `Bodega` | entero | 29 bodegas, códigos 400–489 |
| 3 | `Tipo Doc.` | texto | 13 valores distintos (ver tabla) |
| 4 | `Descripción Documento` | texto | 1 a 1 con `Tipo Doc.` |
| 5 | `No. Documento` | entero | 1.870 documentos distintos |
| 6 | `No. Físico` | entero | 1.867 valores; 4 filas con texto: `E81764`, `3686-1` (ambas EFP) |
| 7 | `No. Artículo` | entero | 294 artículos distintos |
| 8 | `Descripción Artículo` | texto | 292 descripciones |
| 9 | `Cantidad` | numérico | Sin negativos ni ceros |
| 10 | `Unidad Med.` | texto | Solo `KLG` (4.183 filas) y `UND` (715 filas) |
| 11 | `Kilos` | numérico | En `KLG` siempre igual a `Cantidad`; en `UND` es el peso equivalente |
| 12 | `Costo Uni.` | numérico | 518 valores distintos |
| 13 | `Total` | numérico | Coincide con `Cantidad × Costo Uni.` en 3.387 de 4.898 filas; en el resto la diferencia llega hasta 43 |
| 14 | `Usuario Aplica` | texto | 44 códigos (ej. `CN03`, `GC02`, `PA01`) |

No hay celdas vacías en ninguna de las 4.898 filas.

### Tipos de documento presentes

| `Tipo Doc.` | `Descripción Documento` | Filas | Documentos |
|---|---|---|---|
| `FPC` | FACTURACION CENTRO CARNE | 3.724 | 1.563 |
| `EAC` | ENTRADA  PROD. CENTRO CARNES | 657 | 33 |
| `EFP` | ENTRADA COMPRAS CENTRO CARNES | 260 | 50 |
| **`EO`** | **ENTRADA  TRANSFORMACION** | **94** | **89** |
| **`SO`** | **SALIDA  TRANSFORMACION** | **89** | **89** |
| `EFI` | ENTRADA TOMA F MANUAL CC | 21 | 19 |
| `SPM` | SALIDA PROD.DAÑADO CENTRO CARNES | 13 | 5 |
| `SAF` | SALIDA CENTROS CARNES | 12 | 5 |
| `ET` | ENTRADA  TRASLADO PR | 7 | 6 |
| `ST` | SALIDA  TRASLADO PR | 7 | 6 |
| `SF` | SALIDA TOMA FISICA PR | 6 | 1 |
| `EF` | ENTRADA TOMA FISICA PR | 4 | 1 |
| `DPV` | DEVOLUCION COMPRA CENTRO CARNES | 4 | 3 |

**Solo se procesan `EO` y `SO`.** Los otros 11 tipos se ignoran.

### Nombres de campo: documento vs. archivo real

El documento de contexto abrevia dos nombres. En el código se usan los del archivo:

| Documento de contexto | Campo real |
|---|---|
| `No. Docu.` | `No. Documento` |
| `Usuario Ap.` | `Usuario Aplica` |

También cambian los valores de ejemplo del contexto (`Bodega 1`, `ART-01`, `Producto Base`, `Kg`, `Yamileth`): los reales son códigos numéricos y unidades `KLG`/`UND`. El contexto admite `.xlsx` y `.xls`; el único insumo real es `.xlsx`.

---

## 3. Reglas de negocio (código, sin IA)

Estas reglas se implementan en Python. Ninguna depende del agente de IA.

### R1 — Carga del archivo

Se acepta **únicamente `.xlsx`**. Un archivo `.xls` (o cualquier otro formato) se rechaza con un mensaje en español que contiene la palabra `"Revisar"`.

> **Nota:** el contexto original mencionaba `.xls`; decisión confirmada: queda fuera de alcance.

Leer la primera hoja. La hoja del insumo se llama `Movimientos por Tipo Documento ` y hay que aplicarle `strip()` al nombre. Validar que existan las 14 columnas; si falta alguna, rechazar la carga con un mensaje en español.

### R2 — Filtro de registros

```python
df = df[df["Tipo Doc."].isin(["EO", "SO"])]
```

Se descartan las 4.715 filas de los otros 11 tipos de documento.

### R3 — Emparejamiento EO ↔ SO

```python
from collections import defaultdict

def agrupar(registros, campo="No. Físico"):
    """Un documento puede tener varias líneas: se agrupan por No. Físico."""
    grupos = defaultdict(list)
    for r in registros:
        grupos[int(r[campo])].append(r)
    return grupos

eo_por_fisico = agrupar(df[df["Tipo Doc."] == "EO"])
so_por_fisico = agrupar(df[df["Tipo Doc."] == "SO"])

for fisico_eo, lineas_eo in eo_por_fisico.items():
    # El número físico de la SO es el consecutivo anterior al de la EO.
    lineas_so = so_por_fisico.get(fisico_eo - 1)   # None => "Revisar"
```

Regla confirmada contra el insumo: **`SO.No. Físico = EO.No. Físico − 1`**. Cumple los 89 pares del archivo real (89/89).

> **Corrección al documento de contexto:** su ejemplo dice que la EO 450 se empareja con la SO 451 (`SO = EO + 1`). Eso está invertido respecto del insumo y fue confirmado con la usuaria. La regla vigente es `SO = EO − 1`. No usar `SO = EO + 1`: solo produciría 16 coincidencias falsas.

Datos de apoyo observados en los 89 pares (no son reglas de emparejamiento, solo verificación):

- `EO.No. Documento − SO.No. Documento = 100` en los 89 pares.
- Misma `Bodega` en 89/89 pares y mismo `Usuario Aplica` en 89/89 pares.
- **Los artículos nunca coinciden** entre la EO y su SO (0/89). Por eso el cruce es **documento contra documento**, no artículo contra artículo.

### R4 — Agrupación por cruce

Un cruce = una EO y su SO. Se agrupa por `No. Físico` del documento, sumando todas sus líneas:

```python
cruce = {
    "id_cruce": f"EO-{fisico_eo}-SO-{fisico_eo - 1}",
    "cantidad_eo": suma(lineas_eo["Cantidad"]),
    "cantidad_so": suma(lineas_so["Cantidad"]),
    "kilos_eo":    suma(lineas_eo["Kilos"]),
    "kilos_so":    suma(lineas_so["Kilos"]),
    "total_eo":    suma(lineas_eo["Total"]),
    "total_so":    suma(lineas_so["Total"]),
}
```

En el insumo real, 5 EO tienen 2 líneas; las 89 SO tienen exactamente 1.

### R5 — Detección de anomalía de costo

```python
costo_eo_mayor = total_eo > total_so
diferencia_costo = total_eo - total_so   # solo se reporta si costo_eo_mayor
```

Se compara el **Total del documento** (suma de la columna `Total` de todas sus líneas), no el `Costo Uni.` ni el costo por artículo.

### R6 — Marca `"Revisar"`

Se marca `"Revisar"` cuando:

- la EO no tiene SO con `No. Físico − 1`, o la SO no tiene EO con `No. Físico + 1`;
- `No. Físico` no es numérico;
- algún campo obligatorio está vacío;
- el archivo está vacío o tiene formato incorrecto.

Si no se cumple ninguna, el estado es `"Correcto"`.

`"Revisar"` no excluye el análisis de costo: un cruce puede tener `costo_eo_mayor = true` y a la vez `estado_revision = "Revisar"`.

### R7 — Etiquetas de la interfaz

- Semáforo rojo: `costo_eo_mayor = true` y/o `estado_revision = "Revisar"`.
- Semáforo verde: `estado_revision = "Correcto"`.
- Todo el texto de pantalla, mensajes y encabezados va en español.

---

## 4. Lo que hace el agente de IA

- **Rol:** analista experto en detección de anomalías de costos de inventario y subproductos.
- **Qué recibe:** únicamente los cruces EO–SO ya armados por el código, con sus cantidades y sus costos (unitarios y totales). El agente **no** empareja, **no** filtra y **no** calcula los totales.
- **Qué devuelve:** **un lote** con la forma `{"resultados": [ … ]}`. Cada elemento del arreglo es el resultado de un cruce y conserva las 4 llaves de la tabla de abajo.
- **Regla estricta:** nunca inventa información. Si un dato no aparece en la entrada, escribe textualmente `"no indicado"`.

### Contrato JSON del agente

| Llave | Tipo | Significado |
|---|---|---|
| `id_cruce` | String | Identificador único del par EO-SO analizado |
| `costo_eo_mayor` | Boolean | `true` si el costo de la Entrada (EO) es mayor que el de la Salida (SO); si no, `false` |
| `analisis_anomalia` | String | Descripción detallada de la diferencia de costos detectada, o `"no indicado"` |
| `estado_revision` | String | Etiqueta de control: `"Correcto"` o `"Revisar"` |

### Forma de la respuesta (lote)

```json
{
  "resultados": [
    {
      "id_cruce": "EO-1615096-SO-1615095",
      "costo_eo_mayor": true,
      "analisis_anomalia": "La EO tiene un Total de 23978.17 y la SO de 13383.80; diferencia de 10594.37 a favor de la EO. El Costo Uni. de la EO es 2564.51 y el de la SO 1338.38.",
      "estado_revision": "Correcto"
    }
  ]
}
```

Cada elemento de `resultados` conserva exactamente las 4 llaves de la tabla: `id_cruce`, `costo_eo_mayor`, `analisis_anomalia` y `estado_revision`. Los elementos se emparejan con los cruces por `id_cruce`. Si un elemento no cumple el contrato, se descarta **completo** —no se reutiliza ninguna de sus llaves— y para ese cruce queda `analisis_anomalia = "no indicado"`.

### Ejemplo de un elemento

```json
{
  "id_cruce": "EO-1615096-SO-1615095",
  "costo_eo_mayor": true,
  "analisis_anomalia": "La EO tiene un Total de 23978.17 y la SO de 13383.80; diferencia de 10594.37 a favor de la EO. El Costo Uni. de la EO es 2564.51 y el de la SO 1338.38.",
  "estado_revision": "Correcto"
}
```

El `id_cruce` se compone con los números físicos del par, en el formato `EO-<fisico_eo>-SO-<fisico_so>`. `costo_eo_mayor` y `estado_revision` los calcula el código (R5 y R6); el agente solo redacta `analisis_anomalia` y confirma el contrato. Si el lote no respeta el contrato, se descarta elemento por elemento y cada cruce afectado se registra con `analisis_anomalia = "no indicado"`.

---

## 5. Qué produce la app

- **Pantalla principal:** interfaz web sencilla, minimalista y en español, con una tabla resumen interactiva de los cruces.
- **Semáforos:** indicadores visuales que resaltan los cruces con costo EO mayor al de la SO y los marcados `"Revisar"`.
- **Botones:** uno para cargar el Excel y otro para exportar el resultado.
- **Datos de apoyo en la tabla:** cada fila de cruce muestra también **`Bodega`** y **`Usuario`** (tomados de `Bodega` y `Usuario Aplica` del documento) como contexto, sin convertirlos en reglas de negocio.
- **Filtros de la tabla:** por **texto** (identificador del cruce y descripciones), por **estado** (`Correcto` / `Revisar`) y por **semáforo** (rojo / verde), combinables, sin recargar la página.
- **Detalle por cruce:** al seleccionar una fila se abre el detalle con las **líneas EO y SO** que componen el cruce (artículo, descripción, cantidad, kilos, costo unitario y total de cada línea).
- **Archivo descargable:** reporte Excel `.xlsx` que **conserva la estructura original del archivo de entrada** y añade estas columnas:

| Columna nueva | Contenido |
|---|---|
| `Cruce EO-SO` | Identificador del par (`id_cruce`) |
| `Diferencia de Costo` | `Total EO − Total SO` |
| `Análisis IA` | Texto de `analisis_anomalia` |
| `Estado de Revisión` | `"Correcto"` o `"Revisar"` |

El reporte se entrega en una **hoja nueva llamada `Conciliación EO-SO`**, con las **14 columnas originales en su orden + las 4 nuevas**, y contiene **solo las filas EO/SO** (183 filas con el insumo real: 94 EO + 89 SO).

- **Indicadores de control en pantalla:** las cifras de la sección 7, más estos conteos:
  - líneas EO dentro de cruces: **94**;
  - líneas SO dentro de cruces: **89**;
  - EO con 2 líneas: **5**.

Las filas de tipos de documento distintos a EO/SO no forman cruces y no se exportan.

---

## 6. Quién decide

**Yamileth de los Ángeles Villalobos Castillo** es la única responsable de revisar las alertas, interpretar los resultados y tomar la decisión final. La app calcula, marca y sugiere; no corrige ni aprueba nada por sí sola.

---

## 7. Cifras de control

Calculadas sobre `INSUMOS/MOVIMIENTOS 4-11-26.xlsx` (4.898 filas, fecha 2026-11-04). Sirven para validar la implementación: si el código produce otros números, hay un error.

### Conteos

| Indicador | Valor |
|---|---|
| Filas totales del archivo | 4.898 |
| Filas EO | 94 |
| Filas SO | 89 |
| Líneas EO dentro de cruces | 94 |
| Líneas SO dentro de cruces | 89 |
| **Cruces EO–SO** | **89** |
| EO sin pareja | 0 |
| SO sin pareja | 0 |
| Cruces con `"Revisar"` | 0 |
| EO con 2 líneas | 5 (físicos 1615164, 1615175, 1615241, 1615351, 1615435) |

### Montos

| Indicador | Valor |
|---|---|
| Suma de `Total` de las EO | 1.697.243,98 |
| Suma de `Total` de las SO | 1.424.378,23 |
| **Diferencia global `Total EO − Total SO` (89 cruces)** | **272.865,75** |
| **Suma de diferencias, solo cruces con `Total EO > Total SO` (50 cruces)** | **341.738,47** |
| Suma de diferencias de `Costo Uni.` ponderado por kilos (55 cruces con EO > SO) | 49.829,07 |

### Distribución de los 89 cruces

| Comparación | Cruces |
|---|---|
| `Total EO > Total SO` | 50 |
| `Costo Uni.` ponderado EO > SO | 55 |
| `Costo Uni.` ponderado EO = SO | 17 |
| `Costo Uni.` ponderado EO < SO | 17 |

**Las tres cifras monetarias se muestran en pantalla** (decisión confirmada): diferencia global, suma de diferencias solo donde EO > SO, y suma de diferencias unitarias. La cifra principal de control es la suma de diferencias de `Total` donde `Total EO > Total SO`.

**Regla de cálculo ya implementada:** si el `Kilos` de un cruce es 0, ese cruce se **omite** del cálculo de la suma de diferencias de `Costo Uni.` ponderado por kilos (no se divide por cero). No se altera ninguna de las cifras de las tablas anteriores.

---

## 8. Casos límite

Todos deben capturarse y señalarse con la palabra `"Revisar"` en la interfaz y en el reporte (cuando el archivo permita generar reporte), sin que la app se caiga.

| Caso | Manejo |
|---|---|
| Archivo vacío o con formato incorrecto | Mostrar el mensaje de error en español con la palabra `"Revisar"`; no se genera reporte |
| Faltan columnas obligatorias | Mostrar `"Revisar"` indicando cuál columna falta; no se genera reporte |
| Celdas obligatorias vacías o filas incompletas | `"Revisar"` |
| EO sin su SO (`No. Físico − 1` inexistente) | `"Revisar"` |
| SO sin su EO (`No. Físico + 1` inexistente) | `"Revisar"` |
| `No. Físico` no numérico (en el insumo: `E81764`, `3686-1`, ambas EFP) | `"Revisar"`; nunca convertir a texto para comparar |
| `Cantidad`, `Kilos`, `Costo Uni.` o `Total` no numéricos, o `Fecha` inválida | `"Revisar"`; el valor inválido no se convierte en 0 en silencio |
| Un documento con varias líneas | Sumar `Cantidad`, `Kilos` y `Total` antes de comparar |
| `Total` de la EO mayor al de la SO | `costo_eo_mayor = true`, semáforo rojo |
| Registros de tipos distintos a EO/SO | Se ignoran; no son error |
| Archivo con más de una fecha | Procesar todas las filas; el emparejamiento es por `No. Físico`, no por fecha |
| `No. Físico` duplicado dentro del mismo tipo | `"Revisar"` |
| Respuesta del agente fuera de contrato | Descartarla y usar `"no indicado"` |

---

## 9. Reglas del sistema

- **Stack:** Python + Flask con patrón MVC (controllers, services, templates), gestionado con **uv**. Nunca `pip`.
- **Sin carpeta `app/static`:** la interfaz no usa archivos estáticos externos; el CSS va dentro de `base.html` y el JavaScript nativo dentro de las plantillas.
- **Secretos:** la API Key del agente de IA vive estrictamente en un archivo `.env`; jamás se escribe en el código ni en el repositorio.
- **Arranque:** incluir `iniciar_app.bat` en la raíz del proyecto para encender la app automáticamente.
- **Idioma:** todas las pantallas, mensajes y etiquetas en español; estilo minimalista y funcional.
- **Prohibido inventar** reglas, columnas o campos que no estén definidos en esta especificación o en el contexto.
- **Nunca modificar** los archivos de `INSUMOS`; se leen y se procesan en memoria. `INSUMOS/` **no se versiona** (decisión confirmada): se provee por fuera del repositorio.
- **Cargas subidas:** cada archivo recibido se copia a `instance/` (ignorada por git); al subir uno nuevo se borra la carga anterior y las cargas se purgan a las **24 h**. `INSUMOS` nunca se modifica.
- **Variables de entorno (todas en `.env`):** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` y `SECRET_KEY`; además `CONCILIADOR_INSUMO` para que las pruebas apunten al insumo real cuando no está versionado.
- **Cifras deterministas:** el emparejamiento, los totales y los semáforos los calcula el código. El agente de IA solo redacta el análisis; no altera números ni estados.
- **Datos de prueba (del contexto):** hay que generar `movimientos_prueba.xlsx` con al menos 6 filas, mezclando EO y SO, con la relación `SO = EO − 1`, un caso donde el `Total` de la EO sea notoriamente mayor al de la SO y un caso con datos incompletos que fuerce `"Revisar"`. El archivo se genera en **`tests/fixtures/`**, nunca en `INSUMOS` (que es de solo lectura).
