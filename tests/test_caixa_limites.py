from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro


def _janela_com_imagem(largura, altura):
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    janela.resize(largura, altura)
    janela.show()
    QApplication.instance().processEvents()
    imagem = QImage(400, 200, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("red"))
    janela.tela.iniciar_imagem(imagem)
    return janela


def _dentro(exterior: QRect, interior: QRect) -> bool:
    return exterior.contains(interior.topLeft()) and exterior.contains(interior.bottomRight())


def test_imagem_e_botoes_ficam_sempre_dentro_da_janela_nos_quatro_cantos():
    janela = _janela_com_imagem(900, 500)
    app = QApplication.instance()
    try:
        caixa = janela.tela._colocacao
        for _ in range(8):
            caixa.redimensionar(1.25)
        area = janela.tela.area_desenho()
        for x, y in [(0.02, 0.02), (0.98, 0.02), (0.02, 0.98), (0.98, 0.98)]:
            caixa.definir_posicao(x, y)
            app.processEvents()
            centro = caixa.rotulo.geometry().center()
            assert area.contains(centro), (x, y)
            assert _dentro(janela.tela.rect(), caixa.geometry()), (x, y)
    finally:
        janela.close()


def test_imagem_pode_ser_aumentada_para_alem_da_area_do_desenho():
    janela = _janela_com_imagem(900, 500)
    try:
        caixa = janela.tela._colocacao
        area = janela.tela.area_desenho()
        for _ in range(6):
            caixa.redimensionar(1.25)
        assert caixa.rotulo.height() > area.height()
        assert caixa.tamanho > 1.0
    finally:
        janela.close()


def test_botoes_ficam_por_baixo_da_imagem_quando_ha_espaco():
    janela = _janela_com_imagem(900, 700)
    try:
        caixa = janela.tela._colocacao
        caixa.definir_posicao(0.5, 0.2)
        QApplication.instance().processEvents()
        assert caixa.y() >= caixa.rotulo.y() + caixa.rotulo.height()
    finally:
        janela.close()


def test_botoes_passam_para_cima_quando_a_imagem_esta_no_fundo():
    janela = _janela_com_imagem(900, 700)
    try:
        caixa = janela.tela._colocacao
        caixa.definir_posicao(0.5, 0.97)
        QApplication.instance().processEvents()
        assert caixa.y() + caixa.height() <= caixa.rotulo.y()
    finally:
        janela.close()


def test_barra_fica_por_cima_da_imagem_mesmo_quando_a_imagem_ocupa_tudo():
    janela = _janela_com_imagem(900, 700)
    try:
        caixa = janela.tela._colocacao
        for _ in range(8):
            caixa.redimensionar(1.25)
        caixa.definir_posicao(0.5, 0.5)
        QApplication.instance().processEvents()
        filhos = janela.tela.children()
        assert filhos.index(caixa) > filhos.index(caixa.rotulo)
    finally:
        janela.close()


def test_confirmacao_usa_o_tamanho_visivel():
    janela = _janela_com_imagem(900, 500)
    try:
        caixa = janela.tela._colocacao
        for _ in range(8):
            caixa.redimensionar(1.25)
        visivel = caixa.tamanho
        janela.tela.confirmar_colocacao()
        assert janela.tela.quadro.camada_base is not None
        assert visivel <= 4.0
    finally:
        janela.close()
