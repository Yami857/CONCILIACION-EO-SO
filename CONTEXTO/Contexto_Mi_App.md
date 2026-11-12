# Documento de contexto: Conciliador EO / SO

> Fuente: `CONTEXTO/DOCUMENTO_DE_CONTEXTO_ConciliadorEO_SO.docx`

DOCUMENTO DE CONTEXTO · ConciliadorEO_SO
Especificación Técnica y Operativa para el Equipo de Desarrollo (OpenCode)
1. Qué es esta app (para quién y qué problema resuelve)
Aplicación web diseñada exclusivamente para Yamileth de los Ángeles Villalobos Castillo con el fin de automatizar el proceso de conciliación de movimientos de inventario (entradas, salidas y subproductos), reduciendo el tiempo operativo de una hora a pocos segundos y detectando anomalías en los costos.
2. El proceso hoy (paso a paso, tiempo que toma, quién lo hace)
- Paso a paso: Se recibe el archivo Excel con los movimientos de inventario. Se revisan visualmente las filas para emparejar los documentos de tipo EO con los SO basándose en su número físico, se calculan las cantidades y costos, y se identifican las diferencias donde el costo de la EO sea mayor que el de la SO.
- Tiempo que toma: Aproximadamente 1 hora de trabajo manual por jornada/lote.
- Quién lo hace: Yamileth de los Ángeles Villalobos Castillo.
3. Datos de entrada
El archivo de entrada contiene los registros detallados de los movimientos de bodega.

**Tabla:**

| Archivo / Dato | Formato | Campos Principales | Ejemplo de Fila |
|---|---|---|---|
| Archivo de Movimientos | Excel (.xlsx / .xls) | Fecha, Bodega, Tipo Doc., Descripción Documento, No. Docu., No. Físico, No. Artículo, Descripción Artículo, Cantidad, Unidad Med., Kilos, Costo Uni., Total, Usuario Ap. | 01/06/2026, Bodega 1, EO, Entrada Operación, 100, 450, ART-01, Producto Base, 10, Kg, 10, 100.00, 1000.00, Yamileth |

4. Reglas de negocio para el código
- R1: El sistema debe permitir cargar un archivo Excel con la estructura de movimientos definida.
- R2: El código debe emparejar automáticamente los registros de tipo EO con los de tipo SO.
- R3: La relación de emparejamiento entre EO y SO se basa en el campo No. Físico, donde el número físico de la EO corresponde al consecutivo de la SO menos un dígito (Ej: EO con No. Físico 450 se empareja con SO de No. Físico 451).
- R4: Si un documento EO o SO no encuentra su pareja correspondiente o presenta datos incompletos/vacíos, el registro debe marcarse explícitamente con la palabra "Revisar".
- R5: El sistema calculará y mostrará las cantidades y los costos totales agrupados por cada cruce.
5. Lo que hace el agente de IA
- Rol: Analista experto en detección de anomalías de costos de inventario y subproductos.
- Qué recibe: Los registros emparejados de EO y SO junto con sus cantidades y costos unitarios/totales.
- Regla estricta: Nunca inventa información. Si un dato no aparece en la entrada, escribe textualmente "no indicado".
Contrato JSON del Agente de IA

**Tabla:**

| Llave (JSON) | Tipo | Qué significa |
|---|---|---|
| id_cruce | String | Identificador único del par EO-SO analizado. |
| costo_eo_mayor | Boolean | true si el costo de la Entrada (EO) es mayor que el de la Salida (SO), de lo contrario false. |
| analisis_anomalia | String | Descripción detallada de la diferencia de costos detectada o "no indicado". |
| estado_revision | String | Etiqueta de control ("Correcto" o "Revisar"). |

6. Qué produce la app (pantallas, tablas, botones, archivos descargables)
- Pantallas: Interfaz web sencilla en español con una tabla resumen interactiva.
- Semáforos: Indicadores visuales en la pantalla para resaltar rápidamente las alertas (costos de EO mayores a SO o registros marcados como "Revisar").
- Botones: Botón para cargar el archivo Excel y botón para exportar el resultado.
- Archivos descargables: Reporte final procesado en formato Excel (.xlsx) que mantiene la estructura original y añade columnas de resultado (Cruce EO-SO, Diferencia de Costo, Análisis IA, Estado de Revisión).
7. Quién decide
Yamileth de los Ángeles Villalobos Castillo es la única responsable de revisar las alertas, interpretar los resultados y tomar la decisión final.
8. Datos de prueba que hay que generar
- movimientos_prueba.xlsx: Un archivo Excel con al menos 6 filas de prueba que contengan columnas como Fecha, Bodega, Tipo Doc. (mezclando "EO" y "SO"), No. Físico (con la relación de consecutivo menos un dígito), No. Artículo, Descripción Artículo, Cantidad, Kilos, Costo Uni. y Total, incluyendo un caso donde el costo de la EO sea notoriamente mayor al de la SO y un caso con datos incompletos para forzar el estado "Revisar".
9. Cifras de control
SUPUESTO: El sistema validará que el total de registros de Entradas (EO) procesados frente a las Salidas (SO) concuerde con los emparejamientos encontrados, y sumará el monto monetario total de las diferencias donde el costo de la EO supere a la SO para mostrar un indicador global de control.
10. Casos límite
- Archivo Excel vacío o con formato incorrecto.
- Celdas obligatorias vacías o filas incompletas.
- Documentos EO sin su contraparte SO correspondiente (o viceversa).
- Costos de EO mayores a SO.
Todos estos escenarios deben ser capturados y señalados con la palabra "Revisar" en la interfaz y en el reporte.
11. Reglas del sistema
- El proyecto se desarrollará en Python con Flask utilizando el patrón MVC, gestionado mediante uv.
- La API Key del agente de IA se almacenará estrictamente en un archivo .env y nunca estará hardcodeada en el código fuente.
- Se incluirá un archivo ejecutable iniciar_app.bat en la raíz del proyecto para encender la aplicación de forma automática y sencilla.
- Las pantallas serán minimalistas, funcionales y redactadas íntegramente en español.
- Queda estrictamente prohibido inventar reglas, columnas o campos que no se encuentren explícitamente definidos en este documento.
12. Supuestos por confirmar
- SUPUESTO 1: La cifra de control global consistirá en la sumatoria de las diferencias monetarias de los costos EO mayores a SO y el conteo total de registros emparejados.
- SUPUESTO 2: El archivo exportado en Excel mantendrá la estructura original de entrada agregando columnas adicionales para el resultado del análisis (Cruce EO-SO, Diferencia de Costo, Análisis IA, Estado de Revisión). [CONFIRMADO]
