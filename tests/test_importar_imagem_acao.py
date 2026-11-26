from PySide6.QtWidgets import QApplication

from quadro import acoes
from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro


def test_acao_importar_imagem_esta_no_catalogo_com_icone():
    acao = acoes.acao("importar_imagem")
    assert acao.icone == "imagem"


def test_executar_acao_importar_imagem_chama_a_importacao():
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    chamadas = []
    janela.importar_imagem = lambda: chamadas.append(True)
    try:
        assert janela.executar_acao("importar_imagem")
        assert chamadas == [True]
    finally:
        janela.close()
