import math

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from quadro import formas
from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro


def _app():
    return QApplication.instance() or QApplication([])


def test_linha_tem_dois_pontos():
    assert formas.pontos("linha", 0.1, 0.2, 0.5, 0.6) == [(0.1, 0.2), (0.5, 0.6)]


def test_retangulo_fecha_o_contorno():
    contorno = formas.pontos("retangulo", 0.2, 0.2, 0.6, 0.4)
    assert contorno[0] == contorno[-1]
    assert len(set(contorno)) == 4


def test_elipse_fica_sobre_a_elipse_pedida():
    cx, cy, rx, ry = 0.5, 0.5, 0.2, 0.1
    contorno = formas.pontos("elipse", cx - rx, cy - ry, cx + rx, cy + ry)
    for x, y in contorno:
        assert math.isclose(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2, 1.0, abs_tol=1e-9)


def test_forma_desconhecida_e_recusada():
    import pytest

    with pytest.raises(ValueError):
        formas.pontos("estrela-estranha", 0, 0, 1, 1)


def test_soltar_o_rato_cria_um_risco_que_se_desfaz():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    tela = janela.tela
    tela.ferramenta = "forma"
    tela.forma = "retangulo"
    QTest.mousePress(tela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, tela.rect().topLeft() + _ponto(tela, 0.2, 0.2))
    tela._forma = (0.2, 0.2, 0.6, 0.4)
    QTest.mouseRelease(tela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, tela.rect().topLeft() + _ponto(tela, 0.6, 0.4))
    assert len(janela.quadro.tracos) == 1
    assert len(janela.quadro.tracos[0].pontos) == 5
    janela.desfazer()
    assert janela.quadro.tracos == []
    janela.close()


def _ponto(tela, x, y):
    from PySide6.QtCore import QPoint

    return QPoint(int(x * tela.width()), int(y * tela.height()))
