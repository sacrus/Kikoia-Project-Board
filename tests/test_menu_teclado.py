import json

from PySide6.QtWidgets import QApplication

from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro
from quadro.ponte import PonteQuadro


def _janela():
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    return janela


def test_teclado_oculta_o_menu_e_volta_a_mostra_lo():
    janela = _janela()
    try:
        janela.controlo_menu_teclado(False)
        assert janela.menu.isHidden()
        janela.controlo_menu_teclado(True)
        assert not janela.menu.isHidden()
    finally:
        janela.close()


def test_menu_volta_sozinho_quando_o_teclado_deixa_de_pedir():
    janela = _janela()
    try:
        janela.controlo_menu_teclado(False)
        janela._ultimo_pedido_teclado -= 10
        janela._verificar_controlo_teclado()
        assert not janela.menu.isHidden()
    finally:
        janela.close()


def test_menu_nao_volta_enquanto_o_teclado_continua_a_pedir():
    janela = _janela()
    try:
        janela.controlo_menu_teclado(False)
        janela._verificar_controlo_teclado()
        assert janela.menu.isHidden()
    finally:
        janela.close()


def test_ocultar_manual_mostra_o_botao_de_restauro_e_o_botao_volta_a_mostrar():
    janela = _janela()
    try:
        janela.ocultar_menu()
        assert janela.menu.isHidden()
        assert not janela._botao_restaurar.isHidden()
        janela._botao_restaurar.click()
        assert not janela.menu.isHidden()
        assert janela._botao_restaurar.isHidden()
    finally:
        janela.close()


def test_pedido_menu_pela_ponte(tmp_path):
    janela = _janela()
    try:
        ponte = PonteQuadro(janela, base=tmp_path)
        resposta = ponte.tratar(json.dumps({"token": ponte.token, "pedido": "menu", "visivel": False}).encode("utf-8"))
        assert resposta["ok"] is True
        assert janela.menu.isHidden()
        assert ponte.tratar(json.dumps({"token": ponte.token, "pedido": "menu", "visivel": "sim"}).encode("utf-8"))["ok"] is False
    finally:
        janela.close()
