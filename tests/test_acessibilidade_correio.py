from PySide6.QtWidgets import QApplication, QPushButton

from quadro import icones_correio
from quadro.correio.modelo import conta_cpanel
from quadro.correio.regras import Regras
from quadro.janela_correio import DialogoEscrever, botao_com_icone


def _app():
    return QApplication.instance() or QApplication([])


def test_todos_os_icones_do_correio_desenham_imagem_valida():
    _app()
    for nome in icones_correio.DESENHOS:
        pixmap = icones_correio.desenhar(nome, 32)
        assert not pixmap.isNull(), nome


def test_botao_do_correio_tem_icone_e_texto():
    _app()
    botao = botao_com_icone("Responder", "responder")
    assert botao.text() == "Responder"
    assert not botao.icon().isNull()


def test_botoes_de_escrever_tem_icone_e_texto():
    _app()
    dialogo = DialogoEscrever(conta_cpanel("a@portugalsat.com"), "x", Regras(), None, None)
    try:
        for botao in dialogo.findChildren(QPushButton):
            if botao.text():
                assert not botao.icon().isNull(), botao.text()
    finally:
        dialogo.close()
