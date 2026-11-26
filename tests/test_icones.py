from PySide6.QtWidgets import QApplication

from quadro import icones
from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro


def _app():
    return QApplication.instance() or QApplication([])


def test_todos_os_botoes_do_menu_tem_icone_e_nenhum_texto():
    _app()
    janela = JanelaQuadro(Quadro())
    try:
        for botao in janela.menu._botoes:
            assert not botao.icon().isNull(), botao.toolTip()
            if botao is janela.menu._correio:
                continue  # o botão do correio mostra o número de emails por ler, além do ícone
            assert botao.text() == "", botao.toolTip()
    finally:
        janela.close()


def test_icones_escalam_sem_falhar():
    _app()
    for nome in icones.DESENHOS:
        for tamanho in (20, 40, 80):
            assert icones.desenhar(nome, tamanho).width() == tamanho
