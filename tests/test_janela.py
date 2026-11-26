from PySide6.QtWidgets import QApplication

from quadro.janela import JanelaQuadro, Menu
from quadro.modelo import Quadro


def _app():
    return QApplication.instance() or QApplication([])


def test_janela_abre_com_o_menu_no_canto():
    _app()
    janela = JanelaQuadro()
    janela.resize(800, 600)
    janela.show()
    assert isinstance(janela.menu, Menu)
    assert janela.menu.pos().x() == 16
    janela.close()


def test_cor_automatica_acompanha_o_fundo():
    _app()
    janela = JanelaQuadro(Quadro())
    tela = janela.tela
    assert tela.cor_ativa() == "#000000"
    janela.quadro.fundo = "#222222"
    assert tela.cor_ativa() == "#ffffff"
    tela.cor_caneta = "#2563eb"
    assert tela.cor_ativa() == "#2563eb"


def test_desenho_e_renderizado_sem_erros():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    traco = janela.quadro.comecar_traco("#000000", 0.01, 0.1, 0.1)
    janela.quadro.acrescentar_ponto(traco, 0.9, 0.9)
    assert not janela.tela.grab().isNull()
    janela.close()


def test_dialogo_definicoes_bento_abre_e_alterna_tema_e_exportar(monkeypatch, tmp_path):
    from quadro import tema_partilhado
    from quadro.janela import DialogoDefinicoes

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _app()
    janela = JanelaQuadro(Quadro())
    dlg = DialogoDefinicoes(janela)
    try:
        assert dlg._painel_exportar.isHidden() is True
        dlg._alternar_exportar()
        assert dlg._painel_exportar.isHidden() is False
        dlg._definir_tema(True)
        assert tema_partilhado.e_escuro() is True
        dlg._definir_fundo("#1e1e1e")
        assert janela.quadro.fundo == "#1e1e1e"
    finally:
        dlg.close()
        janela.close()
