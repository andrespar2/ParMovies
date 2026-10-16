# ParMovies

**ParMovies** es un descargador multimedia portable para Windows con interfaz de
terminal *Black Modern AMOLED*. Analiza enlaces de Vimeus de forma autorizada,
detecta las calidades reales disponibles, prioriza el audio en español
latinoamericano, descarga los subtítulos y los metadatos, y **verifica cada
archivo con FFprobe**.

Desarrollado por **andrespar2** y **doc_osomanuel**.

---

## Características

- **Portable**: no requiere instalación. Se ejecuta desde cualquier carpeta,
  disco externo o unidad USB.
- **Interfaz AMOLED**: menú numérico claro, sin colores saturados, con barra de
  progreso, velocidad y tiempo restante.
- **Análisis real**: resuelve la cadena completa (`/e/<tipo>` -> embeds ->
  reproductor -> `master.m3u8`) y muestra la resolución y los códecs reales
  (por ejemplo `1336x720`, `H.264`, `AAC`).
- **Preferencia de audio**: es-419 (latino) > es-ES (castellano) > español
  genérico > original > otros.
- **Subtítulos**: modo solo español, todos, manual o ninguno. Convierte VTT a
  SRT automáticamente.
- **Verificación con FFprobe**: un archivo solo se marca como correcto si FFprobe
  confirma que contiene una pista de vídeo válida.
- **Historial** de descargas, **organización** automática por categorías y
  **ficha `.info.json`** junto a cada archivo.
- **Credenciales protegidas**: nunca se escriben en los registros, en el
  historial ni en los archivos versionados.

## Requisitos

- **Windows 10/11** (64 bits).
- **FFmpeg + FFprobe**: se incluyen en el ZIP portable dentro de `bin/`. Si no
  están, ParMovies avisa de que no podrá remultiplexar ni verificar (nunca
  finge una verificación que no ha ocurrido).
- Conexión a Internet y credenciales válidas de la API de Vimeus
  (*API Key* y *View Key*).

## Instalación (portable)

1. Descarga `ParMovies-v1.0.0-portable.zip` desde
   [Releases](https://github.com/andrespar2/ParMovies/releases).
2. Descomprime **toda** la carpeta donde quieras (por ejemplo, una unidad USB).
3. Edita `config/config.json` con tus credenciales, o ejecuta la aplicación y
   usa la opción **08 - Configuracion**.
4. Haz doble clic en **`Iniciar ParMovies.cmd`**.

Estructura del paquete portable:

```text
ParMovies/
├─ ParMovies.exe
├─ Iniciar ParMovies.cmd
├─ bin/
│  ├─ ffmpeg.exe
│  └─ ffprobe.exe
├─ config/
│  └─ config.json          (tus credenciales; no se comparte)
├─ Descargas/              (aquí se guardan los contenidos)
└─ logs/
   └─ parmovies.log
```

## Instalación desde el código (desarrollo)

```powershell
git clone https://github.com/andrespar2/ParMovies.git
cd ParMovies
python -m pip install -e ".[test]"
$env:PYTHONPATH = "src"
python -X utf8 -m parmovies
```

## Configuración

La configuración se resuelve con esta precedencia:

1. **Variables de entorno** `PARMOVIES_*` (la más alta).
2. **`config/config.json`** (archivo local, excluido de git).
3. Valores por defecto.

Copia `config.example.json` a `config/config.json` y rellena `api_key` y
`view_key`. También puedes usar variables de entorno:

```powershell
$env:PARMOVIES_API_KEY = "tu_api_key"
$env:PARMOVIES_VIEW_KEY = "tu_view_key"
```

| Clave | Variable de entorno | Por defecto |
|---|---|---|
| `api_key` | `PARMOVIES_API_KEY` | *(vacío)* |
| `view_key` | `PARMOVIES_VIEW_KEY` | *(vacío)* |
| `base_url` | `PARMOVIES_BASE_URL` | `https://vimeus.com` |
| `downloads_dir` | `PARMOVIES_DOWNLOADS_DIR` | `Descargas/` (portable) |
| `preferred_quality` | `PARMOVIES_PREFERRED_QUALITY` | `best` |
| `preferred_audio_language` | `PARMOVIES_PREFERRED_AUDIO_LANGUAGE` | `es-419` |
| `subtitle_mode` | `PARMOVIES_SUBTITLE_MODE` | `spanish` |
| `output_format` | `PARMOVIES_OUTPUT_FORMAT` | `mkv` |
| `retries` | `PARMOVIES_RETRIES` | `3` |
| `speed_limit_kib` | `PARMOVIES_SPEED_LIMIT_KIB` | `0` (sin límite) |
| `keep_temp_files` | `PARMOVIES_KEEP_TEMP_FILES` | `false` |
| `enable_logs` | `PARMOVIES_ENABLE_LOGS` | `true` |
| `ffmpeg_path` | `PARMOVIES_FFMPEG_PATH` | *(auto: `bin/` o PATH)* |

> **Nunca** compartas `config/config.json`: contiene tus credenciales. Solo se
> versiona `config.example.json`, que va sin secretos.

## Uso

### Interfaz interactiva

```powershell
python -X utf8 -m parmovies
```

Menú principal:

| Opción | Acción |
|---|---|
| `01` | Analizar y descargar un enlace de Vimeus (URL o `<iframe>`) |
| `02` | Buscar por identificador (TMDb / IMDb) |
| `03` | Explorar películas |
| `04` | Explorar series |
| `05` | Explorar animes |
| `06` | Explorar episodios de una serie |
| `07` | Mis descargas (historial) |
| `08` | Configuración |
| `09` | Acerca de ParMovies |
| `00` | Salir |

### Línea de comandos

```powershell
python -X utf8 -m parmovies "https://vimeus.com/e/movie?tmdb=264420"
python -X utf8 -m parmovies --help
python -X utf8 -m parmovies --version
```

## Contenido autorizado y limitaciones reales

- ParMovies **solo** debe usarse con contenido al que tengas derecho de acceso.
- **No descifra DRM ni elude ningún control de acceso técnico**. Si un manifiesto
  declara cifrado, la descarga se detiene y se informa al usuario.
- El motor de descarga es propio (basado en `httpx`), porque clientes genéricos
  que fuerzan `Sec-Fetch-Mode: navigate` son rechazados (HTTP 403) por el CDN.
- Las resoluciones que muestra la aplicación son las **reales** del manifiesto;
  no se simula ninguna calidad superior a la disponible.
- Si FFmpeg/FFprobe no están disponibles, el archivo se puede guardar, pero se
  indicará que **no se pudo verificar**.

Consulta [`docs/LIMITACIONES.md`](docs/LIMITACIONES.md) para más detalle.

## Privacidad de credenciales

- `api_key` y `view_key` nunca se imprimen completas (se enmascaran).
- Los registros, el historial y las URLs se pasan por una capa de redacción que
  sustituye `view_key`, `api_key`, `token` y `hash` por `********`.
- `config/config.json`, `Descargas/`, `logs/` y los binarios de `bin/` están
  excluidos de git mediante `.gitignore`.

## Desarrollo

```powershell
# Pruebas
$env:PYTHONPATH = "src"
python -X utf8 -m pytest

# Verificación real de la cadena completa (descarga, remux y FFprobe)
python -X utf8 scripts/integration_check.py 264420 8
```

Consulta [`CONTRIBUTING.md`](CONTRIBUTING.md) para las pautas de contribución.

## Licencia

MIT. Ver [`LICENSE`](LICENSE).

Créditos: **andrespar2** y **doc_osomanuel**.
