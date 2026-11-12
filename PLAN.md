# PLAN.md — Conciliador EO / SO

Plan de entregas para este proyecto. Fuente de verdad: `AGENTS.md`, `CONTEXTO/Contexto_Mi_App.md` e `INSUMOS/MOVIMIENTOS 4-11-26.xlsx`.
Fecha del plan: 2026-11-04. Estado: **aprobado y ejecutado (2026-11-04)**.

---

## 1. RESUMEN

1. Construimos una app web local en Flask (MVC, con uv) que concilia movimientos de inventario **EO** (entrada por transformación) con **SO** (salida por transformación).
2. Entra un Excel con 14 columnas de movimientos de bodega; del archivo real solo se procesan las 183 filas EO/SO (94 EO + 89 SO).
3. El código empareja por `SO.No. Físico = EO.No. Físico − 1`, agrupa cada par y compara el `Total` del documento.
4. El agente de IA recibe cada cruce ya calculado y devuelve un JSON de 4 llaves (`id_cruce`, `costo_eo_mayor`, `analisis_anomalia`, `estado_revision`); nunca calcula cifras y nunca inventa datos.
5. Sale una pantalla con contadores, semáforos y tabla filtrable, más un `.xlsx` con la estructura original y 4 columnas de resultado.

---

## 2. LO QUE ENCONTRÉ

### En `contexto`

- `DOCUMENTO_DE_CONTEXTO_ConciliadorEO_SO.docx` (40 KB): especificación en 12 secciones. Ya convertido a `Contexto_Mi_App.md` (6.263 B), con las 2 tablas completas y sin imágenes.
- Define: problema, proceso manual de ~1 hora, campos de entrada, reglas R1–R5, rol del agente, contrato JSON, pantallas, responsable, cifras de control y reglas del sistema.
- Trae dos **SUPUESTOS**: el 1 (cifra de control global) quedó confirmado por la usuaria; el 2 (estructura del export) ya estaba marcado `[CONFIRMADO]`.

### En `insumos`

- Un solo archivo: `MOVIMIENTOS 4-11-26.xlsx` (387.486 B), hoja `Movimientos por Tipo Documento ` (con espacio final), **4.898 filas × 14 columnas**, todas del 2026-11-04, sin celdas vacías.
- 13 tipos de documento; los relevantes son **EO (94 filas / 89 documentos)** y **SO (89 filas / 89 documentos)**. FPC sola concentra 3.724 filas.
- 29 bodegas, 44 usuarios, 294 artículos. `No. Físico` trae 4 valores de texto (`E81764`, `3686-1`), ambos en EFP.
- 5 EO tienen 2 líneas; las 89 SO tienen 1.
- **No hay PDF, ni CSV, ni Word en `insumos`**, así que no hay nada escaneado que leer.

### Coincidencias con `AGENTS.md`

| Punto | ¿Coincide? |
|---|---|
| 14 columnas de entrada | Sí, con dos nombres corregidos (`No. Documento`, `Usuario Aplica`) |
| Solo EO y SO | Sí, decisión confirmada |
| `SO.No. Físico = EO.No. Físico − 1` | Sí: 89/89 pares |
| 89 cruces, 0 sin pareja, 0 en `Revisar` | Sí |
| Cifras de control (50 alertas, 341.738,47 / 272.865,75 / 49.829,07) | Sí, recalculadas sobre el archivo |
| Contrato JSON de 4 llaves | Sí, definido en `AGENTS.md` §4 |

### Lo que falta o no cuadra

1. **El documento original invierte la regla R3.** Su ejemplo dice EO 450 ↔ SO 451; los datos y `AGENTS.md` dicen `SO = EO − 1`. Si alguien implementa el ejemplo, solo acertaría 16 pares falsos. Ya está corregido en `AGENTS.md`; el plan usa la regla corregida.
2. **`movimientos_prueba.xlsx` no existe.** `AGENTS.md` §9 lo pide para pruebas; hay que generarlo dentro de `tests/`.
3. **No se define la moneda** de los montos. No se mostrará símbolo hasta que la usuaria lo confirme.
4. **No se define el nombre de la variable de entorno** de la llave ni el proveedor/modelo del agente.
5. **No se define** si el export lleva las 183 filas EO/SO o las 4.898 originales.
6. **No se define** si el análisis de IA va por cruce (89 llamadas) o en lote.
7. **"Subproductos"** no tiene campo ni tipo de documento: queda confirmado que no aplica y no se crea nada nuevo.

---

## 3. ENTREGAS POR SUBAGENTE

Orden de ejecución: 18 entregas pequeñas. `@backend` 7, `@frontend` 5, `@tester` 4, `@revisor` 2.
Cada entrega se construye y se verifica en pocos minutos; ninguna avanza sin que la anterior esté en verde.

| N° | Responsable | Qué debe entregar | Archivos que crea o modifica | Qué recibe de la entrega anterior | Cómo se verifica en pantalla |
|---|---|---|---|---|---|
| 1 | `@backend` | B1 — Esqueleto MVC con uv, `create_app()`, ruta raíz, `wsgi.py` e `iniciar_app.bat` que abre el navegador | `pyproject.toml`, `app/__init__.py`, `app/controllers/__init__.py`, `app/controllers/main.py`, `app/services/__init__.py`, `wsgi.py`, `iniciar_app.bat` | Nada: es la primera entrega | Doble clic en `iniciar_app.bat` → se abre `http://127.0.0.1:5000` con el título "Conciliador EO / SO" y sin error 500 |
| 2 | `@frontend` | F1 — `base.html` con el CSS base y `inicio.html` con el formulario de carga | `app/templates/base.html`, `app/templates/inicio.html` | La ruta `/` y el nombre de la app de B1 | Abrir `/` → formulario "Cargar archivo de movimientos", botón "Analizar" en español, sin estilos rotos |
| 3 | `@backend` | B2 — **R1**: leer la hoja con `strip`, validar las 14 columnas y responder resumen o error en español | `app/services/carga.py`, `app/controllers/carga.py`, `app/__init__.py` | El formulario POST de F1 | Subir `MOVIMIENTOS 4-11-26.xlsx` → "4.898 filas y 14 columnas cargadas"; subir un `.txt` → mensaje con la palabra "Revisar" |
| 4 | `@backend` | B3 — **R2** filtro EO/SO + **R3** emparejamiento `SO = EO − 1`, agrupando líneas por `No. Físico` | `app/services/filtro.py`, `app/services/emparejamiento.py`, `app/controllers/resultados.py` | Los 4.898 registros ya validados de B2 | Tras cargar → "183 registros EO/SO · 89 cruces · 0 sin pareja" |
| 5 | `@tester` | T1 — `conftest.py` con pythonpath + pruebas de R1, R2 y R3 contra el archivo real | `tests/conftest.py`, `tests/test_r1_carga.py`, `tests/test_r2_filtro.py`, `tests/test_r3_emparejamiento.py` | Código de B2 y B3 | `uv run pytest -q` → 3 archivos en verde, 0 fallos |
| 6 | `@backend` | B4 — **R4** agrupación por cruce + **R5** `costo_eo_mayor` por `Total` del documento y su diferencia | `app/services/agrupacion.py`, `app/services/costos.py`, `app/controllers/resultados.py` | Los 89 cruces de B3 | Tras cargar → "50 cruces con EO > SO · diferencia 341.738,47 · global 272.865,75" |
| 7 | `@backend` | B5 — **R6** marca `"Revisar"` + **R7** semáforo y etiquetas | `app/services/revision.py`, `app/controllers/resultados.py` | Cruces y costos de B4 | Con el archivo real → "0 cruces en Revisar"; con una EO borrada → ese cruce pasa a "Revisar" |
| 8 | `@tester` | T2 — Pruebas de R4, R5, R6, R7 y de las cifras de control | `tests/test_r4_agrupacion.py`, `tests/test_r5_costos.py`, `tests/test_r6_revisar.py`, `tests/test_cifras_control.py` | Código de B4 y B5 | `uv run pytest -q` → verde, incluidas 89 / 50 / 341.738,47 / 272.865,75 / 49.829,07 |
| 9 | `@backend` | B6 — Agente de IA: cliente, llave desde `.env`, contrato JSON de 4 llaves y descarte a `"no indicado"` | `app/services/agente.py`, `app/controllers/resultados.py`, `.env` (sin versionar), `pyproject.toml` | Los cruces calculados de B5 y el contrato de `AGENTS.md` §4 | Cargar el archivo → cada cruce muestra su análisis; con la llave vacía → "no indicado" y la app sigue funcionando |
| 10 | `@backend` | B7 — Exportación `.xlsx` con la estructura original + `Cruce EO-SO`, `Diferencia de Costo`, `Análisis IA`, `Estado de Revisión` | `app/services/exportacion.py`, `app/controllers/descarga.py` | Cruces + análisis de B6 | Botón "Descargar" → `.xlsx` con 183 filas y 18 columnas (14 + 4) |
| 11 | `@tester` | T3 — Casos límite + `movimientos_prueba.xlsx` generado dentro de `tests/` | `tests/test_casos_limite.py`, `tests/fixtures/movimientos_prueba.xlsx` | Código de B6 y B7 | `uv run pytest -q` → todos los casos en verde y ningún error 500 |
| 12 | `@frontend` | F2 — `resultados.html`: contadores grandes con las tres cifras y los semáforos | `app/templates/resultados.html` | Datos de B5 y B6 | Abrir `/resultados` → tarjetas grandes con 272.865,75 · 341.738,47 · 49.829,07, más 89 cruces y 50 alertas |
| 13 | `@frontend` | F3 — Tabla de cruces con filtro por texto y por estado, sin recargar (JS nativo) | `app/templates/_tabla.html`, `app/templates/resultados.html` | Contadores de F2 | Escribir "Revisar" en el filtro → 0 filas; borrarlo → vuelven las 89 |
| 14 | `@frontend` | F4 — Detalle por registro en panel/modal: líneas EO y SO, cantidades, kilos, costos y análisis | `app/templates/_tabla.html`, `app/templates/resultados.html` | Tabla de F3 y análisis de B6 | Clic en una fila → panel con EO 1615096 / SO 1615095, sus artículos, 23.978,17 vs 13.383,80 y el texto del análisis |
| 15 | `@frontend` | F5 — Estilo final: jerarquía, legibilidad, estados vacíos y mensajes de error | `app/templates/base.html`, `app/templates/inicio.html`, `app/templates/resultados.html` | Pantallas de F1–F4 | Recorrer `/` y `/resultados` → todo legible y en español, sin desbordes; con archivo inválido se ve "Revisar" |
| 16 | `@tester` | T4 — `VALIDACION.md` con esperado vs obtenido de cada cifra y cada caso límite | `tests/VALIDACION.md` | Resultados de T1, T2 y T3 | Abrir `tests/VALIDACION.md` → tabla con las 5 cifras y "0 diferencias" |
| 17 | `@revisor` | R1 — Seguridad: llaves en código, `.env`, `.gitignore`, datos sensibles y archivos que no deben subirse | Ninguno (reporte en el chat) | Todo el código de B1–B7 y F1–F5 | Leer el reporte: `.env` fuera de git, 0 llaves hardcodeadas, `.gitignore` cubre `.env`, `.venv`, `__pycache__` |
| 18 | `@revisor` | R2 — Coherencia con `AGENTS.md`: R1–R7, columnas, cifras y contrato JSON implementados; nada de más | Ninguno (reporte en el chat) | Entregas 1–17 | Leer el reporte: 0 hallazgos de prioridad alta y cada regla R1–R7 con archivo y línea |

> Nota: `VALIDACION.md` vive en `tests/` porque el permiso de edición de `@tester` se limita a esa carpeta.

---

## 4. PUNTOS DE CONTROL

`@tester` interviene en las entregas **5, 8, 11 y 16**. Estos son los puntos donde la usuaria debe mirar la pantalla y comparar con `AGENTS.md`:

| Punto | Después de la entrega | Quién valida | Qué debo ver exactamente |
|---|---|---|---|
| C1 | 3 — R1 | `@backend` (manual) | "4.898 filas y 14 columnas cargadas" |
| C2 | 4 — R2 + R3 | `@backend` (manual) | "183 registros EO/SO · 89 cruces · 0 sin pareja" |
| C3 | 5 — T1 | `@tester` | `pytest` en verde; si falla, no se avanza a B4 |
| C4 | 6 — R4 + R5 | `@backend` (manual) | 50 cruces con EO > SO · **341.738,47** · global **272.865,75** · unitaria **49.829,07** |
| C5 | 7 — R6 + R7 | `@backend` (manual) | "0 cruces en Revisar" con el archivo real; "1 en Revisar" al borrar una EO |
| C6 | 8 — T2 | `@tester` | `pytest` en verde con las 5 cifras exactas |
| C7 | 9 — B6 | `@backend` (manual) | 89 análisis redactados, o "no indicado" si la llave falla |
| C8 | 10 — B7 | `@backend` (manual) | Excel descargado con 183 filas y 18 columnas |
| C9 | 11 — T3 | `@tester` | `pytest` en verde con todos los casos límite |
| C10 | 12 — F2 | Usuaria | Las tres tarjetas grandes con 272.865,75 · 341.738,47 · 49.829,07 y 89 / 50 |
| C11 | 13 — F3 | Usuaria | Filtro "Revisar" → 0 filas; sin filtro → 89 filas |
| C12 | 14 — F4 | Usuaria | Detalle del cruce EO 1615096 / SO 1615095 con 23.978,17 vs 13.383,80 |
| C13 | 16 — T4 | `@tester` | `VALIDACION.md` con "0 diferencias" |
| C14 | 18 — Revisor | `@revisor` | Reporte con 0 hallazgos de prioridad alta |

**Regla de bloqueo:** si un punto de control no cuadra, se detiene la cadena y se corrige la entrega anterior. No se continúa "para arreglarlo después".

---

## 5. RIESGOS

| Riesgo | Prob. | Quién responde | Qué hace |
|---|---|---|---|
| Archivo vacío, corrupto o con columnas faltantes | Media | `@backend` + `@tester` | R1 rechaza con mensaje en español y la palabra "Revisar"; no genera reporte. Prueba en T1 |
| `No. Físico` no numérico (`E81764`, `3686-1`) | Alta | `@backend` | Se convierte con `try/except`; si falla, ese registro va a "Revisar". Nunca comparar como texto |
| EO sin SO o SO sin EO | Media | `@backend` | `"Revisar"`; el conteo de "sin pareja" se muestra en pantalla |
| EO con 2 líneas (5 casos reales) | Alta | `@backend` | Agrupar por `No. Físico` y sumar `Cantidad`, `Kilos` y `Total` antes de comparar |
| `Total` no coincide con `Cantidad × Costo Uni.` (hasta 43) | Alta | `@backend` | Usar la columna `Total` tal como viene; **no recalcular** ni "corregir" |
| Archivo con más de una fecha | Baja | `@backend` | Procesar todo; el emparejamiento es por `No. Físico`, no por fecha |
| Alguien sube PDF o imagen escaneada | Media | `@backend` | Rechazar con "formato no soportado: solo .xlsx". No hay OCR y no se implementa |
| Excel bloqueado por estar abierto | Media | `@backend` | Trabajar sobre la copia que llega por el formulario; si falla, mensaje "cierre el archivo e intente de nuevo" |
| Respuesta del agente que no es JSON o le faltan llaves | Alta | `@backend` | `try/except` + validación de las 4 llaves; se descarta y se usa `"no indicado"`. El estado y el costo los pone el código |
| El agente inventa cifras en el texto | Media | `@backend` + `@tester` | El prompt solo redacta sobre datos recibidos; las cifras de la pantalla salen del código, no del texto del agente |
| Límite de la llave gratis (429, timeout) | Alta | `@backend` | Un reintento con espera corta; si vuelve a fallar, `"no indicado"`. La descarga nunca se bloquea |
| 89 llamadas al agente tardan demasiado | Media | `@backend` | Procesar en lotes pequeños con indicador de avance y caché por `id_cruce` |
| Codificación de tildes en Windows/Excel | Media | `@backend` | UTF-8 en archivos y respuestas; `strip()` al nombre de la hoja |
| Se implementa la R3 invertida del documento original | Media | `@tester` | Prueba explícita: 89/89 pares con `SO = EO − 1`; con `+1` debe fallar |
| Datos reales de la empresa visibles en el repositorio | Media | `@revisor` | Revisión de `.gitignore` y de archivos versionados; reporte con prioridad alta |

---

## 6. PREGUNTAS PARA MÍ

Necesito que confirmes esto antes de que `@backend` empiece:

1. **Llave del agente:** ¿nombre exacto de la variable en `.env` y qué proveedor/modelo uso? No está en `AGENTS.md`.
2. **Moneda:** ¿los montos son colones? ¿Muestro el símbolo o solo el número?
3. **Export:** ¿el `.xlsx` lleva solo las 183 filas EO/SO o las 4.898 originales con las columnas nuevas?
4. **Análisis de IA:** ¿una llamada por cruce (89) o una sola llamada por lote? Con llave gratis, 89 llamadas pueden tardar o dar 429.
5. **Si el agente falla:** ¿la app muestra "no indicado" y permite exportar, o bloquea la descarga hasta tener análisis?
6. **Acceso:** ¿la app es solo local para Yamileth, o necesita login/usuarios?
7. **Historial:** ¿cada carga es independiente o hay que guardar los lotes anteriores?
8. **`.xls`:** el documento dice `.xlsx / .xls`, pero el único insumo es `.xlsx`. ¿Soporto ambos o solo `.xlsx`?
9. **Detalle por registro:** ¿panel/modal en la misma pantalla (mi propuesta) o página aparte?
10. **`"Revisar"`:** ¿impide exportar ese cruce o solo lo marca y se exporta igual?

---

**Alcance de este archivo:** solo se creó `PLAN.md`. No se tocó ningún otro archivo. La cadena de entregas no empieza hasta que apruebes la tabla de la sección 3 y respondas las preguntas de la sección 6.
