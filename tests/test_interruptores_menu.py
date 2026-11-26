from PySide6.QtWidgets import QApplication

from quadro import janela_correio, menu_prefs
from quadro.correio import contas, supervisor
from quadro.janela import JanelaQuadro
from quadro.janela_correio import DialogoCorreio
from quadro.janela_jogos import DialogoJogos
from quadro.modelo import Quadro


def _janela(monkeypatch):
    QApplication.instance() or QApplication([])
    guardadas = {}
    monkeypatch.setattr(menu_prefs, "guardar", lambda valores, *a, **k: guardadas.update(valores))
    monkeypatch.setattr(contas, "guardar_preferencias", lambda valores, *a, **k: guardadas.update(valores))
    monkeypatch.setattr(contas, "preferencias", lambda *a, **k: {**contas.PREFERENCIAS_OMISSAO, **guardadas})
    return JanelaQuadro(Quadro())


def test_interruptor_do_jogos_esconde_a_bolha_no_menu(monkeypatch):
    janela = _janela(monkeypatch)
    try:
        dialogo = DialogoJogos(janela)
        dialogo._menu.setChecked(False)
        assert janela.menu._jogos.isHidden()
        dialogo._menu.setChecked(True)
        assert not janela.menu._jogos.isHidden()
        dialogo.close()
    finally:
        janela.close()


def test_opcoes_de_email_estao_na_configuracao_do_correio_e_guardam(monkeypatch):
    QApplication.instance() or QApplication([])
    guardadas = {}
    monkeypatch.setattr(contas, "guardar_preferencias", lambda valores, *a, **k: guardadas.update(valores))
    monkeypatch.setattr(contas, "preferencias", lambda *a, **k: {**contas.PREFERENCIAS_OMISSAO, **guardadas})
    monkeypatch.setattr(supervisor, "existe", lambda *a, **k: False)
    from quadro.janela_correio import DialogoConfigurar

    dialogo = DialogoConfigurar()
    try:
        dialogo._avisar.setChecked(False)
        dialogo._opcoes["imagens"].setChecked(False)
        assert guardadas["avisar"] is False
        assert guardadas["imagens"] is False
    finally:
        dialogo.close()


def test_com_supervisor_a_opcao_so_muda_com_a_palavra_passe(monkeypatch):
    QApplication.instance() or QApplication([])
    guardadas = {}
    monkeypatch.setattr(contas, "guardar_preferencias", lambda valores, *a, **k: guardadas.update(valores))
    monkeypatch.setattr(contas, "preferencias", lambda *a, **k: {**contas.PREFERENCIAS_OMISSAO, **guardadas})
    monkeypatch.setattr(supervisor, "existe", lambda *a, **k: True)
    monkeypatch.setattr(janela_correio, "verificar_supervisor", lambda pai: False)
    from quadro.janela_correio import DialogoConfigurar

    dialogo = DialogoConfigurar()
    try:
        dialogo._opcoes["html"].setChecked(False)
        assert "html" not in guardadas
        assert dialogo._opcoes["html"].isChecked()
    finally:
        dialogo.close()


def test_interruptor_do_correio_esconde_a_bolha_no_menu(monkeypatch):
    janela = _janela(monkeypatch)
    try:
        dialogo = DialogoCorreio(janela)
        dialogo._menu.setChecked(False)
        assert janela.menu._correio.isHidden()
        dialogo.close()
    finally:
        janela.close()
