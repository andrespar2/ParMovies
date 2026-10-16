"""Punto de entrada para el empaquetado con PyInstaller.

No anade logica: reutiliza el mismo punto de entrada que ``python -m parmovies``
para que el ejecutable portable se comporte igual que la version de desarrollo.
"""

from __future__ import annotations

from parmovies.cli.app import main

if __name__ == "__main__":
    raise SystemExit(main())
