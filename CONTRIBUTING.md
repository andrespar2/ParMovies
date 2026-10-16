# Guía de contribución

¡Gracias por tu interés en ParMovies! Este documento describe cómo preparar el
entorno, el estilo de código y el flujo de trabajo del proyecto.

## Requisitos

- Windows 10/11.
- Python 3.10 o superior.
- Git.

## Preparar el entorno

```powershell
git clone https://github.com/andrespar2/ParMovies.git
cd ParMovies
python -m pip install -e ".[test,build]"
$env:PYTHONPATH = "src"
```

## Ejecutar las pruebas

```powershell
$env:PYTHONPATH = "src"
python -X utf8 -m pytest
```

Todas las pruebas deben pasar antes de abrir un *pull request*. Las pruebas usan
`pythonpath=src` (configurado en `pyproject.toml`).

### Verificación de integración (opcional)

Requiere credenciales válidas y conexión. Descarga un fragmento real, lo
remultiplexa con FFmpeg y lo verifica con FFprobe:

```powershell
python -X utf8 scripts/integration_check.py 264420 8
```

## Estilo de código

- **Idioma**: el código, los comentarios, los mensajes de error, la interfaz y
  los *commits* se escriben en **español**.
- Sigue el estilo del código existente (nombres, estructura y formato).
- Mantén un diseño claro y tolerante a fallos: las funciones no deben lanzar
  excepciones inesperadas ante datos ausentes o inválidos.
- **Nunca** registres ni imprimas credenciales completas: usa
  `parmovies.security.redaction`.
- Añade o actualiza pruebas para cada cambio de comportamiento.

## Commits

Se usa [Conventional Commits](https://www.conventionalcommits.org/es/):

```text
feat:     nueva funcionalidad
fix:      corrección de errores
docs:     documentación
test:     pruebas
style:    formato, interfaz, sin cambio de comportamiento
refactor: reestructuración sin cambio de comportamiento
chore:    tareas de mantenimiento
```

Ejemplos:

- `feat: agregar seleccion de audio preferido`
- `fix: corregir redaccion del view_key en el historial`
- `docs: describir la instalacion portable`

Haz *commits* pequeños y atómicos, cada uno con su descripción clara en español.

## Pull requests

1. Crea una rama descriptiva (`feature/...`, `fix/...`).
2. Asegúrate de que `pytest` pasa en verde.
3. Actualiza `CHANGELOG.md` si el cambio es visible para el usuario.
4. Describe el cambio, su motivación y cómo lo probaste.

## Contenido autorizado

Las contribuciones deben respetar el propósito del proyecto: **solo contenido
autorizado**. No se aceptarán cambios que eludan DRM o controles de acceso
técnicos, ni que faciliten el acceso a contenido no autorizado.
