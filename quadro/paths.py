"""Localização unificada das pastas de dados do Kikoia e do Quadro Interativo (Windows e Linux).

- Windows: `%LOCALAPPDATA%\\Kikoia` (e `%LOCALAPPDATA%\\Kikoia\\Quadro`)
- Linux: `$XDG_DATA_HOME/Kikoia` ou `~/.local/share/Kikoia` (respeitando `LOCALAPPDATA` se definido em testes)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def pasta_kikoia(base: Path | None = None) -> Path:
    """Pasta partilhada entre o Teclado e o Quadro (`.../Kikoia`)."""
    if base is not None:
        return base
    if sys.platform == "win32":
        raiz = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        raiz = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("XDG_DATA_HOME")
            or str(Path.home() / ".local" / "share")
        )
    return Path(raiz) / "Kikoia"


def pasta_quadro(base: Path | None = None) -> Path:
    """Pasta de dados própria do Quadro Interativo (`.../Kikoia/Quadro`)."""
    if base is not None:
        return base
    return pasta_kikoia() / "Quadro"
