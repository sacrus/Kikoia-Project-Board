"""Ponto de entrada do executavel do Quadro (usado pelo PyInstaller, ver construir_quadro.ps1)."""

from quadro.__main__ import main

raise SystemExit(main())
