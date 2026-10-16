# -*- mode: python ; coding: utf-8 -*-
"""Especificacion de PyInstaller para el ejecutable portable de ParMovies.

Genera un unico ``ParMovies.exe`` (modo consola) a partir de
``packaging/entry.py``. Las dependencias (rich, httpx) se detectan
automaticamente; se excluyen modulos innecesarios para reducir el tamano.
"""

import os

SPEC_DIR = os.path.dirname(os.path.abspath(SPECPATH))
ROOT = os.path.dirname(SPEC_DIR)

a = Analysis(
    [os.path.join(SPEC_DIR, "entry.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "PyInstaller", "setuptools", "pip"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ParMovies",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
