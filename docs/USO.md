# Guía de uso

Esta guía describe los flujos más habituales de ParMovies.

## Inicio

Ejecuta `Iniciar ParMovies.cmd` (paquete portable) o:

```powershell
python -X utf8 -m parmovies
```

La cabecera muestra el estado de FFmpeg y las credenciales enmascaradas.

## 1. Analizar y descargar un enlace

1. Elige **01** en el menú.
2. Pega el enlace de Vimeus **o** el código `<iframe>` completo.
3. ParMovies resuelve el contenido y muestra un resumen: título, tipo,
   resolución real, códecs de vídeo y audio, subtítulos, duración y tamaño
   estimado.
4. Elige la calidad (Enter usa tu preferencia configurada).
5. Elige el modo de subtítulos.
6. Confirma con **S** para iniciar la descarga.

Durante la descarga verás la barra de progreso, los megabytes descargados, la
velocidad y el tiempo restante. Puedes cancelar con **Ctrl+C**.

## 2. Buscar por identificador

Elige **02** e introduce:

- el **tipo** (`movie`, `serie` o `anime`), y
- el **identificador** de TMDb (número) o de IMDb (`tt...`).

Para series y animes se piden temporada y episodio.

## 3. Explorar listados

Las opciones **03**, **04** y **05** muestran los listados de películas, series y
animes de la API. En cada página puedes:

- escribir un **número** para elegir un elemento,
- **n** para la página siguiente, **p** para la anterior,
- **b** para volver.

Al elegir una serie o un anime podrás escoger la temporada y el episodio. La
opción **06** lista directamente los episodios de una serie por su TMDb.

## 4. Historial

La opción **07** muestra tus descargas: título, fecha, tamaño, calidad y estado
(incluida la verificación con FFprobe).

## 5. Configuración

La opción **08** permite editar:

- API Key y View Key,
- carpeta de descargas,
- calidad preferida, idioma de audio y modo de subtítulos,
- formato de salida (mkv/mp4),
- metadatos, reintentos, límite de velocidad, temporales y registros,
- **validar las credenciales** contra Vimeus.

Los cambios se guardan en `config/config.json`.

## Dónde se guardan los archivos

Dentro de la carpeta de descargas:

```text
Descargas/
├─ Peliculas/Titulo (Año)/Titulo (Año) [720p] [ES-LAT].mkv
├─ Series/Nombre/Temporada 01/Nombre - S01E01 [720p].mkv
└─ Anime/Nombre/Temporada 01/Nombre - S01E01.mkv
```

Junto a cada archivo se guardan:

- los subtítulos externos (por ejemplo `.es-419.srt`),
- una ficha `.info.json` con los metadatos y el resultado de la verificación.
