import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from quadro import jxl
from quadro.modelo import Quadro

precisa_das_ferramentas = pytest.mark.skipif(not jxl.disponivel(), reason="cjxl/djxl não estão na pasta ferramentas")


def _app():
    return QApplication.instance() or QApplication([])


def _imagem_pequena(caminho):
    imagem = QImage(30, 20, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("red"))
    imagem.save(str(caminho), "PNG")
    return imagem


@precisa_das_ferramentas
def test_exportar_gera_um_ficheiro_jpeg_xl(tmp_path):
    _app()
    destino = tmp_path / "desenho.jxl"
    jxl.exportar_jxl(Quadro(), destino, 200, 100)
    dados = destino.read_bytes()
    assert dados[:2] == b"\xff\x0a" or dados[:12] == b"\x00\x00\x00\x0cJXL "


@precisa_das_ferramentas
def test_importar_jxl_devolve_a_imagem_com_o_mesmo_tamanho(tmp_path):
    _app()
    png = tmp_path / "origem.png"
    _imagem_pequena(png)
    ficheiro = tmp_path / "origem.jxl"
    jxl.png_para_jxl(png, ficheiro)
    lida = jxl.abrir_imagem(ficheiro)
    assert not lida.isNull()
    assert (lida.width(), lida.height()) == (30, 20)


def test_sem_ferramentas_a_importacao_avisa_em_vez_de_falhar(tmp_path, monkeypatch):
    _app()
    monkeypatch.setattr(jxl, "ferramenta", lambda nome: None)
    ficheiro = tmp_path / "imagem.jxl"
    ficheiro.write_bytes(b"qualquer coisa")
    assert jxl.abrir_imagem(ficheiro).isNull()


def test_sem_ferramentas_a_exportacao_diz_o_motivo(tmp_path, monkeypatch):
    _app()
    monkeypatch.setattr(jxl, "ferramenta", lambda nome: None)
    with pytest.raises(OSError) as erro:
        jxl.exportar_jxl(Quadro(), tmp_path / "x.jxl", 200, 100)
    assert "ferramentas" in str(erro.value)
