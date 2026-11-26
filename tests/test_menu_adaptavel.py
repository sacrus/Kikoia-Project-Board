from PySide6.QtWidgets import QApplication

from quadro.janela import TAMANHO_MAX_BOLHA, TAMANHO_MIN_BOLHA, JanelaQuadro
from quadro.modelo import Quadro


def _app():
    return QApplication.instance() or QApplication([])


def _janela(largura: int, altura: int) -> JanelaQuadro:
    janela = JanelaQuadro(Quadro())
    janela.resize(largura, altura)
    janela.show()
    _app().processEvents()
    return janela


def test_menu_cabe_na_altura_de_um_monitor_baixo():
    janela = _janela(800, 400)
    try:
        assert janela.menu.height() <= janela.height()
        assert janela.menu._tamanho >= TAMANHO_MIN_BOLHA
        colunas = {b.geometry().x() for b in janela.menu._botoes}
        assert len(colunas) == 2
    finally:
        janela.close()


def test_menu_fica_numa_coluna_quando_ha_altura():
    janela = _janela(800, 1000)
    try:
        n = len(janela.menu._botoes)
        esperado = min(TAMANHO_MAX_BOLHA, (janela.height() - 16 - (n - 1) * 8) // n)
        assert janela.menu._tamanho == esperado
        colunas = {b.geometry().x() for b in janela.menu._botoes}
        assert len(colunas) == 1
        assert janela.menu.height() <= janela.height()
    finally:
        janela.close()


def test_menu_reajusta_quando_a_janela_muda_de_tamanho():
    janela = _janela(800, 1000)
    try:
        grande = janela.menu._tamanho
        janela.resize(800, 350)
        _app().processEvents()
        assert grande > 0
        assert janela.menu.height() <= janela.height()
    finally:
        janela.close()


def test_todas_as_bolhas_continuam_no_menu():
    janela = _janela(800, 300)
    try:
        assert len(janela.menu._botoes) >= 10
        for botao in janela.menu._botoes:
            assert janela.menu.rect().contains(botao.geometry())
    finally:
        janela.close()


def test_modo_janela_ocupa_80_por_cento_da_area_util_e_acompanha_o_ecra():
    from PySide6.QtGui import QGuiApplication

    _app()
    janela = JanelaQuadro(Quadro())
    janela.modo_janela = True
    janela.show()
    janela.ajustar_a_area_util()
    area = QGuiApplication.primaryScreen().availableGeometry()
    assert abs(janela.width() - int(area.width() * 0.8)) <= 2
    assert abs(janela.height() - int(area.height() * 0.8)) <= 2
    janela.close()
