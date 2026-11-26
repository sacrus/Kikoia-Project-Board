from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from quadro import acoes, carimbos
from quadro.janela import JanelaQuadro
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro


def _app():
    return QApplication.instance() or QApplication([])


def _janela():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    return janela


def _alfa(imagem, x, y):
    return imagem.pixelColor(int(x * CAMADA_LARGURA), int(y * CAMADA_ALTURA)).alpha()


def _clique(tela, x, y):
    ponto = QPoint(int(x * tela.width()), int(y * tela.height()))
    QTest.mouseClick(tela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)


def test_borracha_de_riscos_nao_apaga_pixels():
    janela = _janela()
    try:
        tela = janela.tela
        carimbos.tracar(janela.quadro, "sol", 0.5, 0.5, 0.2, "#f59e0b")
        traco = janela.quadro.comecar_traco("#000000", 0.02, 0.5, 0.45)
        janela.quadro.acrescentar_ponto(traco, 0.5, 0.55)
        tela.ferramenta = "borracha_riscos"
        tela._registado = False
        tela._apagar(0.5, 0.5)
        assert janela.quadro.tracos == []
        assert _alfa(janela.quadro.camada_carimbos, 0.5, 0.5) > 0
    finally:
        janela.close()


def test_borracha_completa_apaga_riscos_e_pixels():
    janela = _janela()
    try:
        tela = janela.tela
        carimbos.tracar(janela.quadro, "sol", 0.5, 0.5, 0.2, "#f59e0b")
        tela.ferramenta = "borracha"
        tela._registado = False
        tela._apagar(0.5, 0.5)
        assert _alfa(janela.quadro.camada_carimbos, 0.5, 0.5) == 0
    finally:
        janela.close()


def test_poligono_fecha_ao_tocar_no_primeiro_ponto():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "forma"
        tela.forma = "poligono"
        for x, y in ((0.2, 0.2), (0.8, 0.2), (0.5, 0.8)):
            _clique(tela, x, y)
        assert janela.quadro.tracos == []
        _clique(tela, 0.2, 0.2)
        assert len(janela.quadro.tracos) == 1
        pontos = janela.quadro.tracos[0].pontos
        assert pontos[0] == pontos[-1]
        assert len(pontos) == 4
    finally:
        janela.close()


def test_poligono_aberto_termina_com_duplo_clique_e_desfaz():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "forma"
        tela.forma = "poligono"
        _clique(tela, 0.2, 0.2)
        _clique(tela, 0.8, 0.2)
        QTest.mouseDClick(tela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                          QPoint(int(0.8 * tela.width()), int(0.2 * tela.height())))
        assert len(janela.quadro.tracos) == 1
        assert len(janela.quadro.tracos[0].pontos) == 2
        janela.desfazer()
        assert janela.quadro.tracos == []
    finally:
        janela.close()


def test_botao_direito_cancela_o_poligono_em_curso():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "forma"
        tela.forma = "poligono"
        _clique(tela, 0.2, 0.2)
        QTest.mouseClick(tela, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, QPoint(10, 10))
        assert tela._poligono is None
        assert janela.quadro.tracos == []
    finally:
        janela.close()


def test_catalogo_inclui_borracha_de_riscos_e_poligono():
    assert "borracha_riscos" in acoes.FERRAMENTAS
    assert "poligono" in acoes.FORMAS
    assert acoes.acao("borracha_riscos.tamanho.2").pai == "borracha_riscos"


def test_executar_acao_da_borracha_de_riscos_e_do_poligono():
    janela = _janela()
    try:
        assert janela.executar_acao("borracha_riscos")
        assert janela.tela.ferramenta == "borracha_riscos"
        assert janela.executar_acao("forma.poligono")
        assert janela.tela.forma == "poligono"
    finally:
        janela.close()
