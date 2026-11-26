# -*- mode: python ; coding: utf-8 -*-
"""Especificação PyInstaller para empacotar o Kikoia Quadro Interativo no Linux."""

from pathlib import Path

RAIZ = Path(SPECPATH).resolve().parent.parent

dados = [
    (str(RAIZ / "data"), "data"),
    (str(RAIZ / "Resources"), "Resources"),
]

a = Analysis(
    [str(RAIZ / "tools" / "empacotar" / "quadro_principal.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=dados,
    hiddenimports=[
        "PySide6.QtPdf",
        "PySide6.QtSvg",
        "PySide6.QtPrintSupport",
        "PySide6.QtNetwork",
        "cryptography.fernet",
    ] + (["quadro._segredos_embutidos"] if (RAIZ / "quadro" / "_segredos_embutidos.py").is_file() else []),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KikoiaQuadro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KikoiaQuadro",
)
