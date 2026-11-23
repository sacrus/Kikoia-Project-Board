"""Arranque do Quadro Interativo.

    py -m quadro            ecrã completo: área útil do monitor, sem bordas nem botões de janela
    py -m quadro --janela   o mesmo comportamento numa janela de 80% da área útil (para testes)

Nos dois modos, o quadro acompanha a presença do teclado virtual e da barra de tarefas.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from quadro.janela import JanelaQuadro
from quadro.ponte import PonteQuadro


def main(argumentos: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argumentos is None else argumentos)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    janela = JanelaQuadro()
    janela.modo_janela = "--janela" in argumentos
    janela.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    janela.show()
    janela.ajustar_a_area_util()
    ponte = PonteQuadro(janela)
    janela.ponte = ponte
    if ponte.iniciar():
        app.aboutToQuit.connect(ponte.parar)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
