from PySide6.QtWidgets import QApplication

from quadro import acoes, icones
from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro


def test_pesquisa_de_imagens_esta_no_catalogo_com_icone():
    acao = acoes.acao("pesquisar_imagens")
    assert acao.nome == "Pesquisar imagens"
    assert not icones.desenhar("pesquisar").isNull()


def test_executar_a_acao_abre_a_pesquisa(monkeypatch):
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    chamadas = []
    janela.pesquisar_imagens = lambda: chamadas.append(True)
    try:
        assert janela.executar_acao("pesquisar_imagens")
        assert chamadas == [True]
    finally:
        janela.close()


def test_menu_tem_bolha_de_pesquisa_com_icone_e_clique_abre_a_pesquisa(monkeypatch):
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    chamadas = []
    janela.pesquisar_imagens = lambda: chamadas.append(True)
    try:
        bolhas = [b for b in janela.menu._botoes if b.toolTip() == "Pesquisar imagens"]
        assert len(bolhas) == 1
        assert not bolhas[0].icon().isNull()
        bolhas[0].click()
        assert chamadas == [True]
    finally:
        janela.close()
