# Changelog

Todos los cambios relevantes de ParMovies se documentan en este archivo.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [1.0.0] - 2026-10-15

### Añadido

- **Interfaz Black Modern AMOLED** con logotipo ASCII propio, menú numérico,
  pantalla de análisis, barra de progreso con velocidad y tiempo restante, e
  historial de descargas.
- **Cliente de la API de Vimeus** (`X-API-Key`) con listados de películas,
  series, animes y episodios, paginación y mensajes de error en español.
- **Analizador de enlaces**: acepta URLs y código `<iframe>`, valida el dominio
  (prevención de SSRF) e identifica tipos `movie`, `serie`, `anime` y `episode`.
- **Resolución completa de medios**: página de embed -> JSON `embeds` ->
  reproductor externo -> desofuscación del JavaScript empaquetado ->
  manifiesto `master.m3u8` y pistas de subtítulos VTT.
- **Selección inteligente**: calidad máxima real disponible, audio
  es-419 > es-ES > español > original, y subtítulos español / todos / manual /
  ninguno (con conversión VTT a SRT).
- **Motor de descarga propio** (HLS y enlaces directos) basado en `httpx`, con
  reanudación, reintentos, cancelación segura y control opcional de velocidad.
- **Integración segura con FFmpeg/FFprobe**: remultiplexado sin recodificar y
  **verificación real** del resultado con FFprobe.
- **Organización automática** de archivos, ficha `.info.json` y **historial**
  persistente.
- **Seguridad de credenciales**: enmascarado y redacción de `api_key`,
  `view_key`, `token` y `hash` en registros, historial y URLs.
- **Configuración portable** por archivo (`config/config.json`) y variables de
  entorno (`PARMOVIES_*`).
- **Suite de pruebas** (86 pruebas) y **script de verificación de integración**
  con descarga, remux y comprobación con FFprobe.

[1.0.0]: https://github.com/andrespar2/ParMovies/releases/tag/v1.0.0
