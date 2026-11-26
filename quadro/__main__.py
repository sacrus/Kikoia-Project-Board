"""Arranque do Quadro Interativo.

    py -m quadro            ecrã completo: área útil do monitor, sem bordas nem botões de janela
    py -m quadro --janela   o mesmo comportamento numa janela de 80% da área útil (para testes)

Nos dois modos, o quadro acompanha a presença do teclado virtual e da barra de tarefas.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from quadro import idiomas
from quadro.janela import JanelaQuadro
from quadro.ponte import PonteQuadro

_APP_USER_MODEL_ID = "Kikoia.Quadro"


def _escolher_plataforma_grafica() -> None:
    """No Linux sob Wayland com XWayland disponível, usa `xcb` por omissão.

    Isto permite que o Quadro respeite a área reservada pelo Teclado Kikoia (`_NET_WM_STRUT_PARTIAL`),
    posicione janelas/diálogos com `setGeometry` e seja detetado em foco pelo Teclado.
    """
    if not sys.platform.startswith("linux") or "QT_QPA_PLATFORM" in os.environ or not os.environ.get("DISPLAY"):
        return
    for biblioteca in ("libxcb-cursor.so.0", "libxcb-icccm.so.4", "libxcb-keysyms.so.1"):
        try:
            ctypes.CDLL(biblioteca)
        except OSError:
            return
    os.environ["QT_QPA_PLATFORM"] = "xcb"


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


def _instalar_icone_janelas_windows(app: QApplication, caminho_ico: Path | None) -> QObject | None:
    """Garante o ícone Kikoia (WM_SETICON 64-bit) em TODAS as janelas e diálogos no Windows."""
    if sys.platform != "win32" or caminho_ico is None or not caminho_ico.is_file():
        return None
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.LoadImageW.argtypes = (
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.SendMessageW.restype = ctypes.c_ssize_t
        set_class_long = getattr(user32, "SetClassLongPtrW", user32.SetClassLongW)
        set_class_long.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
        set_class_long.restype = ctypes.c_ssize_t

        IMAGE_ICON, LR_LOADFROMFILE = 1, 0x0010
        WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1
        GCLP_HICON, GCLP_HICONSM = -14, -34
        caminho = str(caminho_ico.resolve())
        hicon_big = user32.LoadImageW(None, caminho, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
        hicon_small = user32.LoadImageW(None, caminho, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        if not hicon_big and not hicon_small:
            return None
    except Exception:
        return None

    def _aplicar(widget: QWidget) -> None:
        try:
            if not widget.isWindow():
                return
            wh = widget.windowHandle()
            if wh is None:
                return
            hwnd = int(wh.winId())
            if not hwnd:
                return
            if hicon_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                set_class_long(hwnd, GCLP_HICON, hicon_big)
            if hicon_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                set_class_long(hwnd, GCLP_HICONSM, hicon_small)
        except Exception:
            pass

    class _FiltroIcone(QObject):
        def eventFilter(self, obj: QObject, evento: QEvent) -> bool:  # noqa: N802
            if isinstance(obj, QWidget) and obj.isWindow() and evento.type() == QEvent.Type.Show:
                QTimer.singleShot(0, lambda w=obj: _aplicar(w))
                QTimer.singleShot(80, lambda w=obj: _aplicar(w))
            return super().eventFilter(obj, evento)

    filtro = _FiltroIcone(app)
    app.installEventFilter(filtro)
    return filtro


def main(argumentos: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argumentos is None else argumentos)
    _escolher_plataforma_grafica()
    idiomas.carregar_partilhado()
    caminho_ico = _caminho_icone("ico")
    caminho_png = _caminho_icone("png")
    _registar_identidade_windows(caminho_ico)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Kikoia - Quadro Interativo")
    if hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName("kikoia-quadro")
    icone = QIcon()
    if caminho_ico is not None:
        icone.addFile(str(caminho_ico))
    if caminho_png is not None:
        icone.addFile(str(caminho_png))
    if not icone.isNull():
        app.setWindowIcon(icone)
    _filtro_icone = _instalar_icone_janelas_windows(app, caminho_ico)

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
