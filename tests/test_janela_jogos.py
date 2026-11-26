import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from quadro import catalogo
from quadro.janela_jogos import DialogoJogos

RAIZ = Path(__file__).resolve().parent.parent / "Resources"


def _esperar(app, condicao, limite=10.0):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        app.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_dialogo_lista_os_jogos_e_mostra_os_creditos(monkeypatch, tmp_path):
    monkeypatch.setenv(catalogo.VARIAVEL_RECURSOS, str(RAIZ))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    dialogo = DialogoJogos()
    try:
        assert _esperar(app, lambda: dialogo._lista.count() >= 41)
        assert _esperar(app, lambda: dialogo._jogo is not None)
        assert dialogo._jogo.nome == "GCompris"
        assert "Timothée Giet" in dialogo._texto.text()
        assert "AGPL-3.0" in dialogo._texto.text()
        assert "Como jogar:" in dialogo._texto.text()
        assert "Rato / Touchpad" in dialogo._texto.text()
        assert not dialogo._cartoes[0]._caixa_controlos.isHidden()
        assert dialogo._cartoes[0]._layout_controlos.count() == 4
    finally:
        dialogo.close()


def test_gcompris_instalado_mostra_iniciar_jogo(monkeypatch, tmp_path):
    monkeypatch.setenv(catalogo.VARIAVEL_RECURSOS, str(RAIZ))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    exe = tmp_path / "GCompris-Qt" / "bin" / "GCompris.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(catalogo, "executavel_instalado", lambda jogo, *a, **k: exe if jogo.id == "gcompris" else None)
    app = QApplication.instance() or QApplication([])
    dialogo = DialogoJogos()
    try:
        assert _esperar(app, lambda: dialogo._lista.count() >= 41)
        assert _esperar(app, lambda: dialogo._cartoes[0].jogo is not None)
        assert dialogo._cartoes[0].botao_principal.text() == "Iniciar jogo"
        # Clicar no segundo cartao expande-o e recolhe o primeiro
        dialogo._alternar_cartao(dialogo._cartoes[1])
        assert dialogo._cartoes[1]._expandido is True
        assert dialogo._cartoes[0]._expandido is False
    finally:
        dialogo.close()


def test_filtros_de_tipo_categoria_e_controlos(monkeypatch, tmp_path):
    monkeypatch.setenv(catalogo.VARIAVEL_RECURSOS, str(RAIZ))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    dialogo = DialogoJogos()
    try:
        assert _esperar(app, lambda: dialogo._lista.count() >= 42)
        assert _esperar(app, lambda: all(c.jogo is not None for c in dialogo._cartoes))

        # Filtrar por controlo "caneta" -> apenas Caminho das Letras
        idx_caneta = dialogo._filtro_controlos.findData("caneta")
        dialogo._filtro_controlos.setCurrentIndex(idx_caneta)
        visiveis = [c.jogo.id for c in dialogo._cartoes if not c.isHidden()]
        assert visiveis == ["kikoia-caminho-letras"]

        # Limpar e filtrar por tipo "integrado" -> ambos os jogos nativos Kikoia
        dialogo._limpar_filtros()
        idx_int = dialogo._filtro_tipo.findData("integrado")
        dialogo._filtro_tipo.setCurrentIndex(idx_int)
        visiveis = [c.jogo.id for c in dialogo._cartoes if not c.isHidden()]
        assert visiveis == ["kikoia-caminho-letras", "kikoia-dedos-musicais"]

        # Limpar e filtrar por categoria "Educativo" -> GCompris
        dialogo._limpar_filtros()
        idx_edu = dialogo._filtro_categoria.findData("Educativo")
        assert idx_edu > 0
        dialogo._filtro_categoria.setCurrentIndex(idx_edu)
        visiveis = [c.jogo.id for c in dialogo._cartoes if not c.isHidden()]
        assert visiveis == ["gcompris"]

        # Limpar volta a mostrar todos os 42 jogos
        dialogo._limpar_filtros()
        assert sum(1 for c in dialogo._cartoes if not c.isHidden()) >= 42
    finally:
        dialogo.close()
