# VALIDACION.md — Conciliador EO / SO

Validación de la entrega **T4** del `PLAN.md`: contraste de las **cifras de control** (`AGENTS.md` §7) y de los **casos límite** (`AGENTS.md` §8) contra lo que devuelve realmente la aplicación.

| Dato | Contenido |
|---|---|
| Proyecto | Conciliador EO / SO (Flask + MVC, gestionado con `uv`) |
| Fecha de la validación | 4 de noviembre de 2026 (2026-11-04) |
| Archivo usado | `INSUMOS/MOVIMIENTOS 4-11-26.xlsx` (4.898 filas, 14 columnas, hoja `Movimientos por Tipo Documento `) |
| Archivo de prueba complementario | `tests/fixtures/movimientos_prueba.xlsx` (10 filas, 14 columnas) |
| Comando ejecutado | `uv run pytest -q` |
| Resultado de pytest | **129 pruebas aprobadas, 0 fallidas** (7,41 s). Salida completa en `tests/_salida_pytest_acceso.txt` (la corrida histórica de T4, con 116 pruebas, quedó en `tests/_salida_pytest_t4.txt`) |
| Acceso (login) | Todas las rutas exigen sesión (`APP_USUARIO` / `APP_CLAVE` del entorno). Las 116 pruebas anteriores ahora usan un cliente con sesión iniciada y se agregaron 13 pruebas de acceso en `tests/test_acceso.py` |
| Método de obtención | Los valores se leyeron de la app real: `POST /cargar` + `GET /resultados` con el cliente de Flask, y del HTML renderizado (tarjetas, contadores y semáforos), además de los services R1–R7 |
| Responsable de la validación | `@tester` (entrega 16) |
| Alteraciones al código de la app | Ninguna (no se modificó `app/`, `wsgi.py`, `iniciar_app.bat` ni las pruebas existentes) |

---

## a. Cifras de control (`AGENTS.md` §7)

Moneda no definida en `AGENTS.md`: los montos se muestran sin símbolo. Formato español (miles con `.`, decimales con `,`) y tolerancia de comparación de **0,005** (medio centavo).

### Conteos

| Indicador | Esperado (§7) | Obtenido | Diferencia | Estado |
|---|---|---|---|---|
| Filas totales del archivo | 4.898 | 4.898 | 0 | OK |
| Filas EO | 94 | 94 | 0 | OK |
| Filas SO | 89 | 89 | 0 | OK |
| Registros EO/SO (94 + 89) | 183 | 183 | 0 | OK |
| Filas de otros tipos descartadas (R2) | 4.715 | 4.715 | 0 | OK |
| Líneas EO dentro de cruces | 94 | 94 | 0 | OK |
| Líneas SO dentro de cruces | 89 | 89 | 0 | OK |
| **Cruces EO–SO** | **89** | **89** | 0 | OK |
| EO sin pareja | 0 | 0 | 0 | OK |
| SO sin pareja | 0 | 0 | 0 | OK |
| Cruces con `"Revisar"` | 0 | 0 | 0 | OK |
| Cruces correctos | 89 | 89 | 0 | OK |
| EO con 2 líneas | 5 | 5 | 0 | OK |
| Físicos de las EO con 2 líneas | 1615164, 1615175, 1615241, 1615351, 1615435 | 1615164, 1615175, 1615241, 1615351, 1615435 | 0 | OK |
| Alertas de costo (`Total EO > Total SO`) | 50 | 50 | 0 | OK |
| `Costo Uni.` ponderado EO > SO | 55 | 55 | 0 | OK |
| `Costo Uni.` ponderado EO = SO | 17 | 17 | 0 | OK |
| `Costo Uni.` ponderado EO < SO | 17 | 17 | 0 | OK |
| Semáforo rojo | 50 | 50 | 0 | OK |
| Semáforo verde | 39 | 39 | 0 | OK |

### Montos

| Indicador | Esperado (§7) | Obtenido | Diferencia | Estado |
|---|---|---|---|---|
| Suma de `Total` de las EO | 1.697.243,98 | 1.697.243,98 | 0,00 | OK |
| Suma de `Total` de las SO | 1.424.378,23 | 1.424.378,23 | 0,00 | OK |
| **Diferencia global `Total EO − Total SO` (89 cruces)** | **272.865,75** | **272.865,75** | 0,00 | OK |
| **Suma de diferencias, solo cruces con `Total EO > Total SO` (50 cruces)** | **341.738,47** | **341.738,47** | 0,00 | OK |
| Suma de diferencias de `Costo Uni.` ponderado por kilos (55 cruces) | 49.829,07 | 49.829,07 | 0,00 | OK |

Comprobaciones cruzadas adicionales (todas en verde):

- La diferencia global coincide con la suma de `diferencia_costo` de los 89 cruces: 272.865,75.
- La suma de 341.738,47 se obtiene **solo** de los 50 cruces con alerta y todas sus diferencias son positivas.
- 55 + 17 + 17 = 89 cruces.
- Orden de magnitud de §7 respetado: 341.738,47 > 272.865,75 > 49.829,07.

### Valores tal como aparecen en pantalla

Los mismos números, ya formateados por la plantilla `resultados.html`:

| Zona de la pantalla | Lo que debe mostrar | Lo que muestra |
|---|---|---|
| Tarjeta "Diferencia global EO − SO" | 272.865,75 | 272.865,75 |
| Tarjeta principal "Diferencias donde la EO supera a la SO" | 341.738,47 | 341.738,47 |
| Tarjeta "Diferencias de costo unitario" | 49.829,07 | 49.829,07 |
| Contadores | 183 · 89 · 50 · 0 · 89 · 89 · 0 | 183 · 89 · 50 · 0 · 89 · 89 · 0 |
| Semáforos | 50 rojos / 39 verdes | 50 rojos / 39 verdes |
| Filas de la tabla de cruces | 89 | 89 |

Los siete contadores, en orden de la pantalla: **Registros EO/SO** 183 · **Cruces** 89 · **Alertas de costo** 50 · **En revisar** 0 · **Correctos** 89 · **Entradas en la tabla** 89 · **Sin pareja** 0.

---

## b. Casos límite (`AGENTS.md` §8)

| # | Caso (§8) | Resultado esperado | Resultado obtenido | Prueba que lo demuestra | Estado |
|---|---|---|---|---|---|
| 1 | Archivo vacío | Mensaje en español con `"Revisar"`; no se genera reporte | `ok=False`, mensaje contiene "Revisar", `registros=[]`, `filas=0`; sin excepción y sin 500 | `test_r1_archivo_vacio_revisar`, `test_caso_archivo_vacio_responde_ok_false_con_revisar_sin_excepcion` | OK |
| 2 | `.xlsx` solo con encabezados (sin filas de datos) | `"Revisar"` | `ok=False` con "Revisar" | `test_r1_xlsx_sin_filas_de_datos_revisar`, `test_caso_xlsx_solo_con_encabezados_responde_revisar` | OK |
| 3 | Formato incorrecto (`.txt` y `.xlsx` corrupto) | `"Revisar"`; no se genera reporte | Mensaje que exige `.xlsx`; la descarga redirige con "Revisar"; sin excepción | `test_r1_archivo_txt_rechazado_con_revisar`, `test_r1_xlsx_corrupto_no_lanza_excepcion`, `test_caso_formato_incorrecto_txt_responde_revisar`, `test_caso_ningun_archivo_produce_error_500[texto_plano]`, `test_caso_ningun_archivo_produce_error_500[xlsx_corrupto]` | OK |
| 4 | Faltan columnas obligatorias | `"Revisar"` indicando cuál columna falta; no se genera reporte | `ok=False`; el mensaje nombra `Total`; `registros=[]` | `test_r1_falta_columna_obligatoria_responde_revisar_con_el_nombre`, `test_caso_faltan_columnas_el_mensaje_nombra_la_columna_que_falta`, `test_caso_ningun_archivo_produce_error_500[sin_columna_total]` | OK |
| 5 | Celdas obligatorias vacías o filas incompletas | `"Revisar"` | El cruce afectado pasa a `"Revisar"` (y solo ese); el resto del archivo se sigue procesando | `test_caso_celda_obligatoria_vacia_marca_el_cruce_en_revisar`, `test_caso_fila_incompleta_genera_entrada_en_revisar`, `test_r6_linea_con_campo_obligatorio_vacio_marca_el_cruce_en_revisar`, `test_r6_campo_obligatorio_vacio_en_la_eo_tambien_marca_revisar` | OK |
| 6 | EO sin su SO (`No. Físico − 1` inexistente) | `"Revisar"` | Entrada `EO-<fisico>-SIN-SO` en `"Revisar"`, conserva sus líneas, `total_so = 0`, no inventa la SO | `test_caso_eo_sin_so_genera_entrada_eo_fisico_sin_so`, `test_r6_eo_sin_so_genera_exactamente_una_entrada_eo_fisico_sin_so` | OK |
| 7 | SO sin su EO (`No. Físico + 1` inexistente) | `"Revisar"` | Entrada `SO-<fisico>-SIN-EO` en `"Revisar"`, `total_eo = 0` | `test_caso_so_sin_eo_genera_entrada_so_fisico_sin_eo`, `test_r6_so_sin_eo_genera_exactamente_una_entrada_so_fisico_sin_eo` | OK |
| 8 | `No. Físico` no numérico (`E81764`, `3686-1`) | `"Revisar"`; nunca comparar como texto; sin excepción | Ambas etiquetas quedan en `"Revisar"`; la EO no forma par y la SO queda huérfana; sin excepción | `test_caso_fisico_no_numerico_no_lanza_excepcion_y_queda_en_revisar[E81764]`, `[...][3686-1]`, `test_r3_no_numerico_no_lanza_excepcion`, `test_r6_fisico_no_numerico_no_lanza_excepcion_y_queda_en_revisar` | OK |
| 9 | Un documento con varias líneas | Sumar `Cantidad`, `Kilos` y `Total` antes de comparar | Las 5 EO reales con 2 líneas suman sus dos líneas; caso de prueba: 2 líneas EO suman 15 / 15 / 2.000,00 y el cruce resulta `Correcto` (comparar línea por línea daría "menor") | `test_r4_los_5_fisicos_con_dos_lineas_eo_suman_sus_dos_lineas`, `test_r4_cada_cruce_suma_todas_las_lineas_de_sus_documentos`, `test_caso_documento_con_varias_lineas_suma_cantidad_kilos_y_total`, `test_control_todos_los_registros_eo_so_estan_dentro_de_un_cruce` | OK |
| 10 | `Total` de la EO mayor al de la SO | `costo_eo_mayor = true`, semáforo rojo | 50 cruces con alerta y 50 rojos; ejemplo real `EO-1615096-SO-1615095`: 23.978,17 vs 13.383,80 → diferencia 10.594,37, `Correcto`, rojo | `test_caso_total_eo_mayor_al_so_marca_costo_y_semaforo_rojo`, `test_r5_hay_89_cruces_y_50_con_total_eo_mayor`, `test_r7_archivo_real_50_rojos_y_39_verdes` | OK |
| 11 | Registros de tipos distintos a EO/SO | Se ignoran; no son error | 4.715 filas descartadas; el reporte exporta solo las 183 EO/SO (ninguna `FPC`) | `test_r2_descarta_las_4715_filas_de_otros_tipos`, `test_r2_solo_conserva_tipos_eo_y_so`, `test_caso_tipos_distintos_a_eo_so_se_ignoran_sin_error` | OK |
| 12 | Archivo con más de una fecha | Procesar todas las filas; emparejar por `No. Físico`, no por fecha | Con 3 fechas distintas se procesan todas y se obtienen los mismos cruces e idénticas cifras | `test_caso_archivo_con_mas_de_una_fecha_procesa_todas_y_empareja_por_fisico` | OK |
| 13 | `No. Físico` duplicado dentro del mismo tipo | `"Revisar"` | El cruce con el físico repetido pasa a `"Revisar"` (sigue habiendo un solo cruce); varias líneas del **mismo** documento no se consideran duplicado | `test_caso_fisico_duplicado_en_el_mismo_tipo_marca_revisar`, `test_r6_fisico_duplicado_en_el_mismo_tipo_marca_revisar`, `test_r6_varias_lineas_del_mismo_documento_no_es_duplicado`, `test_r3_ningun_fisico_duplicado_dentro_del_mismo_tipo` | OK |
| 14 | Respuesta del agente fuera de contrato | Descartarla y usar `"no indicado"` | `ok=False` con motivo `json_invalido` o `contrato_invalido`, `analisis={}`; los 89 cruces quedan en `"no indicado"`; las cifras y los estados **no cambian** | `test_caso_respuesta_agente_fuera_de_contrato_se_descarta_con_ok_false`, `test_caso_consultar_agente_descarta_respuesta_fuera_de_contrato`, `test_caso_agente_fuera_de_contrato_la_app_queda_no_indicado_sin_romper`, `test_caso_el_agente_no_puede_cambiar_costo_ni_estado` | OK |
| 15 | Sin `OPENROUTER_API_KEY` en `.env` | No se llama al proveedor; todo `"no indicado"`; la app sigue funcionando | Motivo `falta_llave`, 0 peticiones de red, los 89 cruces en `"no indicado"`, aviso en pantalla, cifras intactas | `test_caso_sin_llave_el_agente_no_consulta_y_todo_queda_no_indicado` + verificación manual descrita en la sección e | OK |
| 16 | Ningún caso produce error 500 | Solo respuestas 200/302; `"Revisar"` donde corresponde; sin excepciones | 14 variantes (9 válidas y 5 inválidas) sin 500; en las válidas la descarga responde 200 con `Content-Type` de Excel; en las inválidas redirige con "Revisar" | `test_caso_ningun_archivo_produce_error_500[...]` (14 parametrizaciones) | OK |
| 17 | `Cantidad`, `Kilos`, `Costo Uni.` o `Total` no numéricos, o `Fecha` inválida | `"Revisar"`; el valor inválido no se convierte en 0 en silencio | Los cinco campos se validan con el dato crudo de la línea: `Total`, `Cantidad`, `Costo Uni.` y `Kilos` de texto y `Fecha` inválida dejan el cruce en `"Revisar"`; `"Revisar"` no anula `costo_eo_mayor` (sigue `true`) ni el semáforo rojo; solo se marca el cruce que trae el dato inválido | `test_r6_total_no_numerico_marca_revisar`, `test_r6_cantidad_no_numerica_marca_revisar`, `test_r6_costo_unitario_no_numerico_marca_revisar_sin_anular_el_costo`, `test_r6_kilos_no_numerico_marca_revisar_sin_anular_el_costo`, `test_r6_fecha_invalida_marca_revisar[N/A]`, `[...][31/02/2026]`, `[...][20261104]`, `test_r6_valores_invalidos_solo_afectan_al_cruce_que_los_trae` | OK |
| 18 | Acceso: sin sesión, cualquier pantalla (no es un caso de §8; es la regla de acceso del login) | 302 a `/login`; no se ve la conciliación ni se descarga el reporte | `/`, `/resultados`, `/descargar` y `POST /cargar` responden 302 con `Location` = `/login` y no se crea sesión | `test_acceso_sin_sesion_la_pantalla_principal_redirige_a_login`, `test_acceso_sin_sesion_toda_ruta_protegida_redirige_a_login[GET/POST ...]` (4 parametrizaciones) | OK |
| 19 | Acceso: ingreso con credenciales | Con usuario y clave correctos entra a `/`; con cualquiera incorrecta se queda en `/login` con «Usuario o contraseña incorrectos» y sin sesión; sin `APP_USUARIO`/`APP_CLAVE` avisa «El acceso no está configurado en el servidor.»; `/salir` cierra la sesión; la cabecera muestra el email y «Salir» solo con sesión | Todo lo anterior se cumple: 302 a `/` con credenciales buenas y luego `GET /` 200; 200 con el mensaje exacto y `GET /` 302 cuando la clave o el usuario no coinciden; 200 con el aviso de servidor sin configurar y sin sesión; `/salir` → 302 a `/login` y después `/` → 302 (también sin sesión, sin error) | `test_acceso_login_muestra_usuario_contrasena_y_boton_entrar`, `test_acceso_login_con_clave_incorrecta_no_entra_y_avisa`, `test_acceso_login_con_usuario_incorrecto_no_entra_y_avisa`, `test_acceso_login_con_credenciales_correctas_entra_a_la_pantalla_principal`, `test_acceso_sin_variables_el_login_avisa_que_no_esta_configurado`, `test_acceso_salir_con_sesion_cierra_la_sesion`, `test_acceso_salir_sin_sesion_redirige_a_login_sin_fallar`, `test_acceso_la_cabecera_muestra_usuario_y_salir_solo_con_sesion` | OK |

---

## c. Diferencias encontradas

**0 diferencias.**

Las 25 cifras de control de `AGENTS.md` §7 y los 19 casos verificados (17 de §8 más los 2 del acceso) coinciden exactamente con lo que devuelve la aplicación sobre `INSUMOS/MOVIMIENTOS 4-11-26.xlsx`. No se cambió ningún esperado, ninguna tolerancia ni ningún dato de entrada para que las pruebas pasaran, y no se usó `skip` ni `xfail`.

---

## d. Notas y limitaciones

1. **Solo se admite `.xlsx`.** Es una decisión confirmada: el único insumo real es `.xlsx`. Un `.xls`, un `.txt`, un PDF o una imagen escaneada se rechazan con el mensaje en español que contiene `"Revisar"` y no generan reporte (no hay OCR ni conversión).
2. **El análisis de IA requiere `OPENROUTER_API_KEY` en `.env`.** Sin llave, la app no hace ninguna petición al proveedor: muestra el aviso "Análisis IA no disponible: no se configuró la llave del agente en el archivo .env. Se muestra «no indicado»." y los 89 cruces quedan con `analisis_anomalia = "no indicado"`. En esta validación no había llave configurada, así que ese fue el comportamiento observado (89 de 89 cruces en "no indicado"). El modelo se puede fijar con `OPENROUTER_MODEL`; el valor por defecto es del código.
3. **El agente nunca altera cifras.** `costo_eo_mayor`, `diferencia_costo` y `estado_revision` los calcula el código (R5 y R6); está probado que un análisis del agente no los cambia. Aun con la IA caída, las tres cifras monetarias y los semáforos son los de §7.
4. **Los `No. Físico` de texto del insumo no generan `"Revisar"` en el archivo real.** Los valores `E81764` y `3686-1` pertenecen a documentos `EFP`, que R2 descarta antes del emparejamiento; por eso el insumo real da 0 `No. Físico` no numéricos dentro de EO/SO. El caso límite sí se verifica con archivos de prueba donde esos valores se ponen en una EO o SO.
5. **El reporte exportado no tiene prueba automatizada propia.** La suite no incluye un archivo de pruebas dedicado a la exportación; en esta validación se comprobó a mano sobre el insumo real: `GET /descargar` responde 200 con `Content-Type` de `.xlsx`, **183 filas y 18 columnas** (14 originales + `Cruce EO-SO`, `Diferencia de Costo`, `Análisis IA`, `Estado de Revisión`). Queda como limitación de cobertura de la suite, no como diferencia de comportamiento.
6. **No se muestra símbolo de moneda** porque `AGENTS.md` no define la moneda. La pantalla lo dice de forma explícita: "Montos sin símbolo de moneda".
7. **Los montos se comparan con tolerancia de 0,005** (medio centavo) porque se manejan 2 decimales. Todas las cifras cuadran además exactas, sin necesidad de la tolerancia.
8. **Tildes en la consola de Windows.** Al ejecutar `pytest` desde PowerShell algunos acentos se ven mal en la consola (codificación de la terminal); el HTML de la app, los mensajes y los archivos son UTF-8 y en pantalla se ven correctos. No es un defecto de la app.
9. **`/resultados` recalcula todo en cada visita** (R1 a R7) sobre la copia del Excel guardada en `instance/subidas`; no guarda resultados entre visitas. Es coherente con el alcance de "un archivo por lote".
10. **El archivo de prueba vive en `tests/`**, no en `INSUMOS/` (esa carpeta es de solo lectura y no contiene `movimientos_prueba.xlsx`). Tiene 10 filas, 14 columnas, mezcla EO/SO con `SO = EO − 1`, un cruce con `Total` de la EO muy superior al de la SO y un cruce con dato incompleto que fuerza `"Revisar"`.
11. **`INSUMOS/` no se versiona** (está en `.gitignore`), así que un clon del repositorio no trae `MOVIMIENTOS 4-11-26.xlsx`. Para reproducir las cifras de control hay que definir la variable de entorno `CONCILIADOR_INSUMO` con la ruta al `.xlsx`, o colocar `MOVIMIENTOS 4-11-26.xlsx` en `INSUMOS/` en la raíz del proyecto. `tests/conftest.py` resuelve la ruta en ese orden; si el archivo no existe, las pruebas que dependen del insumo real (las de cifras de control entre ellas) se **omiten** con el mensaje "Falta el insumo real: defina CONCILIADOR_INSUMO o coloque MOVIMIENTOS 4-11-26.xlsx en INSUMOS/ (no se versiona).". La omisión es solo por ausencia de ese dato externo, no para esconder fallos: con el archivo presente corren las 129 pruebas y cualquier diferencia con `AGENTS.md` falla. Las pruebas que usan `tests/fixtures/movimientos_prueba.xlsx` (los 41 de `test_casos_limite.py`) y las del acceso (los 13 de `test_acceso.py`) corren siempre. En esta máquina, con el archivo real presente, el resultado sigue siendo **129 aprobadas, 0 omitidas, 0 fallidas**.
12. **Acceso con usuario y contraseña.** Desde que se agregó el login, todas las rutas exigen sesión y redirigen a `/login` (302) si no la hay. Las credenciales se leen de `APP_USUARIO` y `APP_CLAVE` del entorno (`.env`), nunca del código. `tests/conftest.py` fija esas dos variables con valores de prueba (`prueba@montecillos.com` / `clave-de-prueba-2026`) antes de crear la app, así que la suite no depende del `.env` local, y entrega el fixture `cliente` **con sesión iniciada**: las 116 pruebas anteriores siguen comprobando exactamente lo mismo y ya no reciben el 302 a `/login`. El caso «servidor sin configurar» se prueba con el fixture `cliente_sin_credenciales`, que borra esas variables solo durante esa prueba.

---

## e. Cómo reproducir

### Con la suite de pruebas

```bash
uv run pytest -q
```

Resultado esperado (y observado el 2026-11-11, con el login ya integrado):

```
........................................................................ [ 55%]
.........................................................                [100%]
129 passed in 7.41s
```

- 129 pruebas: `test_acceso.py` 13 · `test_r1_carga.py` 9 · `test_r2_filtro.py` 4 · `test_r3_emparejamiento.py` 6 · `test_r4_agrupacion.py` 10 · `test_r5_costos.py` 9 · `test_r6_revisar.py` 24 · `test_cifras_control.py` 13 · `test_casos_limite.py` 41.
- Cualquier `F` o `E` en esa salida es un hallazgo: no se debe ajustar el esperado ni el dato de entrada.
- La salida completa de esta validación está guardada en `tests/_salida_pytest_acceso.txt` (la corrida anterior a la del login, con 116 pruebas, está en `tests/_salida_pytest_t4.txt`).

Para ver solo las cifras de control:

```bash
uv run pytest -q tests/test_cifras_control.py
```

Para ver solo el acceso:

```bash
uv run pytest -q tests/test_acceso.py
```

### En pantalla

1. Doble clic en `iniciar_app.bat` en la raíz del proyecto. Se abre el navegador en `http://127.0.0.1:5000`; como no hay sesión, la app muestra la pantalla **Ingresar** (o redirige a `http://127.0.0.1:5000/login`) con el título **"Conciliador EO / SO"**, sin error 500.
2. Escribir en **Usuario** y **Contraseña** los valores de `APP_USUARIO` y `APP_CLAVE` del `.env` y pulsar **"Entrar"**: se abre la pantalla principal y en la cabecera, a la derecha, aparecen el email y el enlace **"Salir"**. Con una clave equivocada se queda en `/login` con el mensaje **"Usuario o contraseña incorrectos"**.
3. En "Cargar archivo de movimientos", seleccionar `INSUMOS/MOVIMIENTOS 4-11-26.xlsx` y pulsar **"Analizar"**.
4. Debe aparecer el mensaje **"4.898 filas y 14 columnas cargadas desde la hoja «Movimientos por Tipo Documento»."**
5. En **"Cifras de control"** deben verse las tres tarjetas: **272.865,75** (diferencia global), **341.738,47** (cifra principal, diferencias donde la EO supera a la SO) y **49.829,07** (diferencias de costo unitario).
6. En **"Contadores del archivo"**: **183** registros EO/SO (94 EO y 89 SO), **89** cruces, **50** alertas de costo, **0** en revisar, **89** correctos, **89** entradas y **0** sin pareja.
7. En **"Semáforos"**: **50 rojos / 39 verdes**.
8. En la tabla de cruces: **89 filas**. Al escribir `Revisar` en el filtro de estado deben quedar **0 filas**; al borrarlo vuelven las 89.
9. Clic en la fila del cruce **EO-1615096-SO-1615095**: el detalle debe mostrar Total EO **23.978,17**, Total SO **13.383,80** y diferencia **10.594,37** (semáforo rojo, estado `Correcto`).
10. Botón **"Descargar reporte"**: se obtiene un `.xlsx` con **183 filas y 18 columnas** (las 14 originales más `Cruce EO-SO`, `Diferencia de Costo`, `Análisis IA` y `Estado de Revisión`).
11. Sin `OPENROUTER_API_KEY` en `.env`, arriba de las cifras se ve la banda de aviso "Análisis IA no disponible… Se muestra «no indicado»" y la columna de análisis dice `no indicado` en todos los cruces, **sin que cambien las cifras ni los semáforos**.
12. Clic en **"Salir"**: vuelve a la pantalla de ingreso y, al entrar de nuevo a `http://127.0.0.1:5000/`, la app pide las credenciales otra vez.

---

## Resumen

- Archivo de este reporte: `tests/VALIDACION.md`
- Pruebas ejecutadas: **129** · aprobadas: **129** · fallidas: **0** (`uv run pytest -q`, 7,41 s)
- Cifras de control verificadas: **25 de 25 OK**
- Casos verificados: **19 de 19 OK** (17 de `AGENTS.md` §8 + 2 del acceso)
- **0 diferencias**
