from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from quadro import janela as janela_modulo
from quadro.desenho import exportar_png, exportar_svg
from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro


def _app():
    return QApplication.instance() or QApplication([])


def _quadro_com_traco(fundo="#fff8dc"):
    quadro = Quadro(fundo)
    traco = quadro.comecar_traco("#e11d48", 0.02, 0.1, 0.5)
    quadro.acrescentar_ponto(traco, 0.9, 0.5)
    return quadro


def test_png_tem_as_dimensoes_e_o_fundo(tmp_path):
    _app()
    caminho = tmp_path / "desenho.png"
    exportar_png(_quadro_com_traco(), caminho, 640, 360)
    imagem = QImage(str(caminho))
    assert (imagem.width(), imagem.height()) == (640, 360)
    assert imagem.pixelColor(0, 0).name() == "#fff8dc"


def test_png_mostra_o_traco(tmp_path):
    _app()
    caminho = tmp_path / "desenho.png"
    exportar_png(_quadro_com_traco(), caminho, 640, 360)
    imagem = QImage(str(caminho))
    assert imagem.pixelColor(320, 180).name() == "#e11d48"


def test_svg_contem_o_traco(tmp_path):
    _app()
    caminho = tmp_path / "desenho.svg"
    exportar_svg(_quadro_com_traco(), caminho, 640, 360)
    conteudo = caminho.read_text(encoding="utf-8")
    assert "<svg" in conteudo
    assert "<path" in conteudo
    assert "#e11d48" in conteudo


def test_gravar_e_abrir_pela_janela(tmp_path, monkeypatch):
    _app()
    caminho = tmp_path / "meu-desenho"
    monkeypatch.setattr(janela_modulo.QFileDialog, "getSaveFileName", lambda *a, **k: (str(caminho), ""))
    janela = JanelaQuadro(_quadro_com_traco("#e8f4ea"))
    janela.gravar()
    assert (tmp_path / "meu-desenho.kquadro").is_file()

    janela2 = JanelaQuadro(Quadro())
    monkeypatch.setattr(
        janela_modulo.QFileDialog,
        "getOpenFileName",
        lambda *a, **k: (str(tmp_path / "meu-desenho.kquadro"), ""),
    )
    janela2.abrir()
    assert janela2.quadro.fundo == "#e8f4ea"
    assert len(janela2.quadro.tracos) == 1


def test_abrir_ficheiro_invalido_nao_altera_o_desenho(tmp_path, monkeypatch):
    _app()
    ficheiro = tmp_path / "mau.kquadro"
    ficheiro.write_text("{\"formato\": \"outro\"}", encoding="utf-8")
    monkeypatch.setattr(janela_modulo.QFileDialog, "getOpenFileName", lambda *a, **k: (str(ficheiro), ""))
    monkeypatch.setattr(janela_modulo.QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    avisos = []
    monkeypatch.setattr(janela_modulo.QMessageBox, "warning", lambda *a, **k: avisos.append(a))
    janela = JanelaQuadro(_quadro_com_traco("#fff8dc"))
    janela.abrir()
    assert janela.quadro.fundo == "#fff8dc"
    assert len(avisos) == 1


def test_substituir_desenho_pede_confirmacao(tmp_path, monkeypatch):
    _app()
    ficheiro = tmp_path / "outro.kquadro"
    Quadro("#e8f4ea").guardar(ficheiro)
    monkeypatch.setattr(janela_modulo.QFileDialog, "getOpenFileName", lambda *a, **k: (str(ficheiro), ""))
    monkeypatch.setattr(janela_modulo.QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    janela = JanelaQuadro(_quadro_com_traco("#fff8dc"))
    janela.abrir()
    assert janela.quadro.fundo == "#fff8dc"
