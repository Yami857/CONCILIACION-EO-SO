# Conciliador EO / SO

Aplicación web en español que concilia los movimientos de inventario **EO** (entrada por
transformación) con sus **SO** (salida por transformación), calcula las diferencias de costo
y arma el reporte en Excel.

Regla de emparejamiento: **`SO.No. Físico = EO.No. Físico − 1`**.
Solo se procesan los documentos `EO` y `SO`; los demás tipos se ignoran.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (gestiona Python y las dependencias; no se usa `pip`)
- Windows, macOS o Linux

## Arranque local

```bash
iniciar_app.bat      # Windows: enciende la app y abre el navegador
```

o bien:

```bash
uv run python wsgi.py
```

La app queda en <http://127.0.0.1:5000>.

## Variables de entorno

Se leen de `.env` (nunca se versiona) o del entorno del sistema. Ver `.env.example`.

| Variable | Uso |
|---|---|
| `OPENROUTER_API_KEY` | Llave del agente de IA. Sin llave la app funciona y el análisis dice `no indicado`. |
| `OPENROUTER_MODEL` | Modelo de OpenRouter (por defecto `google/gemma-4-31b-it:free`). |
| `SECRET_KEY` | Clave de las sesiones de Flask. |
| `APP_USUARIO` | Usuario del ingreso (opcional; tiene prioridad sobre el respaldo). |
| `APP_CLAVE` | Contraseña del ingreso (opcional; tiene prioridad sobre el respaldo). |
| `CONCILIADOR_INSUMO` | Ruta al Excel real para las pruebas (opcional). |

## Acceso

La app pide usuario y contraseña antes de mostrar cualquier pantalla; no hay base de
datos de usuarios. Hay dos formas de entrar, en este orden:

1. **Variables del entorno** `APP_USUARIO` y `APP_CLAVE`. Si las dos están definidas,
   tienen prioridad.
2. **Credencial de respaldo definitiva**: usuario `admon@montecillos.com` y una clave
   guardada solo como huella PBKDF2 dentro de `app/controllers/acceso.py` (nunca en texto
   plano). Funciona siempre, aunque Render deje las variables vacías al redesplegar.

Por eso el formulario ya no muestra el aviso de «acceso no configurado»: siempre hay una
forma válida de entrar. Si las variables están definidas pero la clave es distinta, se
prueba el respaldo automáticamente.

- En local las variables van en `.env` (nunca se versiona). En Render, si se quieren usar,
  van en **Environment** → **Add Environment Variable**; no son necesarias.
- Para cambiar la clave de respaldo hay que regenerar `SAL_RESPALDO` y `HASH_RESPALDO`
  con `hashlib.pbkdf2_hmac` y subir el cambio; la clave nueva se entrega solo a la usuaria.
- Al entrar, la pantalla principal muestra el email en la cabecera y el enlace
  **Salir**, que cierra la sesión.

## Pruebas

```bash
uv run pytest -q
```

Sin el insumo real, las pruebas que lo necesitan se omiten (`skip`) en lugar de fallar.

## Datos

`INSUMOS/` no se versiona: contiene datos reales de la empresa y se provee por fuera del
repositorio. Los archivos que se suben por la web se guardan en `instance/` (ignorada por git)
y se borran a las 24 horas.

## Despliegue en Render

El repositorio incluye `render.yaml` (Blueprint), `.python-version` (Python 3.12) y
`gunicorn` como servidor de producción.

### Opción A — Blueprint (recomendado)

1. Entra a <https://dashboard.render.com> → **New** → **Blueprint**.
2. Conecta el repositorio `Yami857/CONCILIACION-EO-SO` y la rama `main`.
3. Render lee `render.yaml` y muestra el servicio `conciliacion-eo-so`.
4. Cuando pida el valor de `OPENROUTER_API_KEY`, pega tu llave (o déjala vacía: la app
   funciona igual y el análisis aparece como «no indicado»).
5. **Apply** y espera el primer despliegue.

### Opción B — Web Service manual

| Campo | Valor |
|---|---|
| Language | `Python 3` |
| Branch | `main` |
| Build Command | `uv sync --frozen --no-dev` |
| Start Command | `uv run --frozen --no-dev gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 180 --access-logfile - --error-logfile -` |
| Health Check Path | `/` |
| Plan | `Free` |

Y en **Environment**:

| Variable | Valor |
|---|---|
| `SECRET_KEY` | Generar uno: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `OPENROUTER_API_KEY` | Tu llave de OpenRouter (opcional) |
| `OPENROUTER_MODEL` | `google/gemma-4-31b-it:free` |
| `APP_USUARIO` | Opcional: email del ingreso (si se define, tiene prioridad) |
| `APP_CLAVE` | Opcional: contraseña del ingreso (si se define, tiene prioridad) |

### Notas de producción

- Un solo **proceso** de gunicorn con 8 hilos: el plan Free tiene 512 MB de memoria y así
  no se duplica el Excel en memoria al procesarlo.
- El **timeout de gunicorn se sube a 180 s** porque el análisis de IA de los 89 cruces
  puede tardar más que los 30 s por defecto.
- En Render el disco es **efímero**: los archivos subidos se pierden al redesplegar o
  reiniciar el servicio. Basta con volver a subir el Excel.
- En el **plan Free** el servicio se duerme tras 15 minutos sin uso; la primera petición
  puede tardar ~50 s en despertar.
- `SECRET_KEY` debe estar definida: si falta, cada proceso genera una clave distinta y las
  sesiones se pierden entre peticiones.
- Las cookies de sesión se marcan `Secure` automáticamente cuando la app corre en Render
  (variable `RENDER` que Render define sola).
