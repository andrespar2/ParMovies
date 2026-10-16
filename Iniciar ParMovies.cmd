@echo off
rem ---------------------------------------------------------------------------
rem  ParMovies - lanzador portable
rem  Ejecuta el ejecutable si existe; si no, arranca desde el codigo fuente.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

if exist "ParMovies.exe" (
    "ParMovies.exe" %*
    goto :fin
)

rem Modo desarrollo: requiere Python y la carpeta src/ del repositorio.
set "PYTHONPATH=%~dp0src"
python -X utf8 -m parmovies %*

:fin
endlocal
