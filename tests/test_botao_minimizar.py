from PySide6.QtWidgets import QApplication

from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro


def _janela():
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    return janela


def test_botao_minimizar_fica_no_canto_superior_direito():
    janela = _janela()
    try:
        botao = janela._botao_minimizar
        assert botao.geometry().right() == janela.width() - 16 - 1
        assert botao.geometry().top() == 16
    finally:
        janela.close()


def test_botao_minimizar_minimiza_a_janela():
    janela = _janela()
    try:
        janela._botao_minimizar.click()
        assert janela.isMinimized()
    finally:
        janela.close()
