# Guía de configuración

## Dónde vive la configuración

- Archivo local: `config/config.json` (excluido de git).
- Plantilla versionada: `config.example.json` (sin secretos).
- Variables de entorno: `PARMOVIES_*`.

Precedencia: **variables de entorno > archivo > valores por defecto**.

## Crear el archivo

```powershell
Copy-Item config.example.json config/config.json
```

Luego edita `config/config.json`:

```json
{
  "api_key": "tu_api_key",
  "view_key": "tu_view_key",
  "base_url": "https://vimeus.com",
  "downloads_dir": "",
  "preferred_quality": "best",
  "preferred_audio_language": "es-419",
  "subtitle_mode": "spanish",
  "output_format": "mkv"
}
```

## Variables de entorno

```powershell
$env:PARMOVIES_API_KEY   = "tu_api_key"
$env:PARMOVIES_VIEW_KEY  = "tu_view_key"
```

Las variables tienen prioridad sobre el archivo, lo que resulta útil para no
guardar credenciales en disco.

## Opciones principales

| Clave | Valores | Descripción |
|---|---|---|
| `downloads_dir` | ruta | Vacío = `Descargas/` junto a la aplicación (portable). |
| `preferred_quality` | `best`, `2160`, `1080`, `720`, `480` | Si el valor no existe, se usa la calidad inferior más cercana. |
| `preferred_audio_language` | `es-419`, `es-ES`, `es`, `original` | Orden de preferencia de audio. |
| `subtitle_mode` | `spanish`, `all`, `manual`, `none` | Selección de subtítulos. |
| `output_format` | `mkv`, `mp4` | Contenedor de salida (sin recodificar). |
| `retries` | entero >= 0 | Reintentos por manifiesto y por segmento. |
| `speed_limit_kib` | entero >= 0 | Límite de velocidad en KiB/s (0 = sin límite). |
| `keep_temp_files` | `true`/`false` | Conserva los segmentos temporales. |
| `enable_logs` | `true`/`false` | Activa el registro en `logs/parmovies.log`. |
| `ffmpeg_path` | ruta | Carpeta de FFmpeg/FFprobe. Vacío = `bin/` o PATH. |

## FFmpeg y FFprobe

ParMovies los busca en este orden:

1. `ffmpeg_path` de la configuración.
2. `bin/` junto a la aplicación.
3. El `PATH` del sistema.

Si no puede ejecutarlos, avisará de que no podrá remultiplexar ni verificar.
