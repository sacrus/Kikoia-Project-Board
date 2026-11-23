"""Arranque do Quadro Interativo.

    py -m quadro            ecrã completo: área útil do monitor, sem bordas nem botões de janela
    py -m quadro --janela   o mesmo comportamento numa janela de 80% da área útil (para testes)

Nos dois modos, o quadro acompanha a presença do teclado virtual e da barra de tarefas.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from quadro.janela import JanelaQuadro
from quadro.ponte import PonteQuadro

_APP_USER_MODEL_ID = "Kikoia.Quadro"


def _caminho_icone(extensao: str) -> Path | None:
    """Procura o ícone oficial do Kikoia junto ao projeto ou ao executável empacotado."""
    bases = [Path(__file__).resolve().parent.parent]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases.insert(0, Path(meipass))
        bases.insert(0, Path(sys.executable).resolve().parent)
    for base in bases:
        for rel in (
            Path("Resources") / "Images" / f"kikoia.{extensao}",
            Path("data") / "icone" / f"kikoia.{extensao}",
            Path(f"kikoia.{extensao}"),
        ):
            cand = base / rel
            if cand.is_file():
                return cand
    return None


def _registar_identidade_windows(caminho_ico: Path | None) -> None:
    """Define AppUserModelID próprio para o Windows não agrupar com python.exe na barra de tarefas."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except Exception:
        pass
    if caminho_ico is None:
        return
    try:
        import winreg

        chave_caminho = rf"Software\Classes\AppUserModelId\{_APP_USER_MODEL_ID}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chave_caminho) as chave:
            winreg.SetValueEx(chave, "DisplayName", 0, winreg.REG_SZ, "Kikoia — Quadro Interativo")
            winreg.SetValueEx(chave, "IconUri", 0, winreg.REG_SZ, str(caminho_ico))
    except Exception:
        pass


def _aplicar_icone_janela_windows(janela: QWidget, caminho_ico: Path | None) -> None:
    """Força o ícone HICON (small + big) via Win32 WM_SETICON para aparecer sempre na barra de tarefas."""
    if sys.platform != "win32" or caminho_ico is None:
        return
    try:
        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        hwnd = int(janela.winId())
        caminho = str(caminho_ico)
        hicon_big = user32.LoadImageW(None, caminho, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
        hicon_small = user32.LoadImageW(None, caminho, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        if hicon_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
        if hicon_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    except Exception:
        pass


def main(argumentos: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argumentos is None else argumentos)
    caminho_ico = _caminho_icone("ico")
    caminho_png = _caminho_icone("png")
    _registar_identidade_windows(caminho_ico)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    icone = QIcon()
    if caminho_ico is not None:
        icone.addFile(str(caminho_ico))
    if caminho_png is not None:
        icone.addFile(str(caminho_png))
    if not icone.isNull():
        app.setWindowIcon(icone)

    janela = JanelaQuadro()
    if not icone.isNull():
        janela.setWindowIcon(icone)
    janela.modo_janela = "--janela" in argumentos
    janela.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    janela.show()
    _aplicar_icone_janela_windows(janela, caminho_ico)
    janela.ajustar_a_area_util()

    ponte = PonteQuadro(janela)
    janela.ponte = ponte
    if ponte.iniciar():
        app.aboutToQuit.connect(ponte.parar)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
