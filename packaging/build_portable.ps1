# Ensambla el paquete portable de ParMovies y genera el ZIP de la release.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File packaging/build_portable.ps1
#   powershell -ExecutionPolicy Bypass -File packaging/build_portable.ps1 -Version 1.0.0
#
# Requiere: Python con PyInstaller instalado (pip install -e ".[build]").

param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Write-Host "==> ParMovies v$Version - empaquetado portable" -ForegroundColor Cyan
Write-Host "    Raiz del proyecto: $Root"

Push-Location $Root
try {
    # 1) Compilar el ejecutable con PyInstaller.
    Write-Host "==> Compilando ParMovies.exe con PyInstaller..." -ForegroundColor Cyan
    python -m PyInstaller `
        --noconfirm --clean `
        --distpath "$Root\dist" `
        --workpath "$Root\build\pyinstaller" `
        "$Root\packaging\parmovies.spec"
    if (-not (Test-Path "$Root\dist\ParMovies.exe")) {
        throw "No se genero dist\ParMovies.exe"
    }

    # 2) Preparar la carpeta de staging.
    $Stage = "$Root\build\portable\ParMovies"
    if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
    New-Item -ItemType Directory -Path $Stage -Force | Out-Null
    New-Item -ItemType Directory -Path "$Stage\config" -Force | Out-Null
    New-Item -ItemType Directory -Path "$Stage\Descargas" -Force | Out-Null
    New-Item -ItemType Directory -Path "$Stage\logs" -Force | Out-Null
    New-Item -ItemType Directory -Path "$Stage\bin" -Force | Out-Null

    Copy-Item "$Root\dist\ParMovies.exe"    $Stage
    Copy-Item "$Root\Iniciar ParMovies.cmd" $Stage
    Copy-Item "$Root\README.md"             $Stage
    Copy-Item "$Root\LICENSE"               $Stage
    Copy-Item "$Root\config.example.json"   "$Stage\config\config.example.json"

    # FFmpeg/FFprobe locales (si estan presentes en bin/).
    foreach ($tool in @("ffmpeg.exe", "ffprobe.exe")) {
        if (Test-Path "$Root\bin\$tool") {
            Copy-Item "$Root\bin\$tool" "$Stage\bin\$tool"
            Write-Host "    Incluido bin\$tool"
        } else {
            Write-Warning "No se encontro bin\$tool; el paquete quedara sin verificacion FFprobe."
        }
    }

    # 3) Crear el ZIP de la release.
    $ReleaseDir = "$Root\release"
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
    $Zip = "$ReleaseDir\ParMovies-v$Version-portable.zip"
    if (Test-Path $Zip) { Remove-Item $Zip -Force }
    Compress-Archive -Path $Stage -DestinationPath $Zip -Force

    $sizeMb = [math]::Round((Get-Item $Zip).Length / 1MB, 2)
    Write-Host "==> Listo: $Zip ($sizeMb MB)" -ForegroundColor Green
}
finally {
    Pop-Location
}
