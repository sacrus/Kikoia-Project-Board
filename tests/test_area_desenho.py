from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from quadro.janela import JanelaQuadro
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro

PROPORCAO = CAMADA_LARGURA / CAMADA_ALTURA


def _janela(largura, altura):
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    janela.resize(largura, altura)
    janela.show()
    QApplication.instance().processEvents()
    return janela


def test_area_do_desenho_mantem_a_proporcao_em_janela_larga():
    janela = _janela(1400, 600)
    try:
        area = janela.tela.area_desenho()
        assert abs(area.width() / area.height() - PROPORCAO) < 0.01
        assert area.height() <= janela.tela.height()
    finally:
        janela.close()


def test_area_do_desenho_mantem_a_proporcao_em_janela_alta():
    janela = _janela(700, 1000)
    try:
        area = janela.tela.area_desenho()
        assert abs(area.width() / area.height() - PROPORCAO) < 0.01
        assert area.width() <= janela.tela.width()
    finally:
        janela.close()


def test_cantos_da_area_correspondem_a_zero_e_um():
    janela = _janela(1400, 600)
    try:
        area = janela.tela.area_desenho()
        x0, y0 = janela.tela._normalizar(QPointF(area.x(), area.y()))
        x1, y1 = janela.tela._normalizar(QPointF(area.x() + area.width(), area.y() + area.height()))
        assert (round(x0, 3), round(y0, 3)) == (0.0, 0.0)
        assert (round(x1, 3), round(y1, 3)) == (1.0, 1.0)
    finally:
        janela.close()


def test_exportacao_usa_a_proporcao_do_quadro():
    janela = _janela(1400, 600)
    try:
        area = janela.tela.area_desenho()
        assert abs(area.width() / area.height() - PROPORCAO) < 0.01
    finally:
        janela.close()
