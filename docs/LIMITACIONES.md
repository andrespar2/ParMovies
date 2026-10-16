# Limitaciones reales

ParMovies se construyó sobre comprobaciones reales, no sobre suposiciones. Este
documento recoge las limitaciones verificadas del proyecto.

## Uso autorizado

- ParMovies **solo** debe usarse con contenido al que tengas derecho de acceso.
- **No descifra DRM** ni elude controles de acceso técnicos. Si un manifiesto
  HLS declara cifrado (`#EXT-X-KEY`), la descarga se detiene y se informa al
  usuario.

## Motor de descarga

- El motor es **propio** (basado en `httpx`). Se descartó `yt-dlp` como motor
  principal porque fuerza el encabezado `Sec-Fetch-Mode: navigate`, que el CDN
  rechaza con **HTTP 403**.
- El CDN exige un **User-Agent de navegador** y un **`Referer` de origen**
  (`https://vimeos.net/`). Sin ellos, responde 403.
- La velocidad observada del CDN es modesta (~0.8 MB/s). Los contenidos
  completos pueden ser grandes (películas de ~40 MB a ~440 MB).

## Calidades

- Las calidades mostradas son las **reales** del manifiesto. Por ejemplo, un
  embed puede anunciar "Dual 1080p" y entregar en realidad `888x480` y
  `1336x720`. ParMovies **nunca** simula una resolución superior a la
  disponible: si pides 1080p y no existe, entrega la inmediatamente inferior.
- El HLS observado no incluía audio separado ni DRM.

## FFmpeg y verificación

- Si FFmpeg/FFprobe no están disponibles (por ejemplo, un manifiesto que exige
  elevación, `WinError 740`), ParMovies lo detecta y lo indica: el archivo se
  puede guardar, pero **no se marca como verificado**.
- Un archivo solo se considera correcto si FFprobe confirma una pista de vídeo
  válida. No basta con recibir un HTTP 200.

## Disponibilidad del servicio

- La API de Vimeus está protegida por Cloudflare y rechaza el `User-Agent` por
  defecto de Python (HTTP 403); ParMovies envía uno de navegador.
- Algunos contenidos no tienen servidores asociados o no exponen un manifiesto
  descargable; en ese caso se informa del problema en lugar de fallar en
  silencio (por ejemplo, un anime sin fuentes da un 404 gestionado).
- Si el servicio cambia su estructura, la resolución puede dejar de funcionar
  hasta adaptarla. ParMovies valida la estructura y avisa cuando no la reconoce.
