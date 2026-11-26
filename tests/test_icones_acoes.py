import base64
import json

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from quadro import acoes, icones_acoes
from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro
from quadro.ponte import PonteQuadro, imagens_dos_icones


def _app():
    return QApplication.instance() or QApplication([])


def test_todo_o_icone_de_acao_tem_imagem():
    _app()
    for acao in acoes.ACOES:
        pixmap = icones_acoes.pixmap_da_acao(acao.icone)
        assert not pixmap.isNull(), acao.id


def test_icone_desconhecido_e_recusado():
    _app()
    try:
        icones_acoes.pixmap_da_acao("nao-existe")
    except KeyError:
        return
    raise AssertionError("devia recusar")


def test_imagens_enviadas_cobrem_as_acoes_e_os_icones_de_navegacao():
    _app()
    enviadas = imagens_dos_icones()
    for acao in acoes.ACOES:
        assert acao.icone in enviadas, acao.id
    for nome in icones_acoes.ICONES_EXTRA:
        assert nome in enviadas, nome


def test_imagens_enviadas_sao_png_validos():
    _app()
    for nome, dados in list(imagens_dos_icones().items())[:5]:
        imagem = QImage()
        assert imagem.loadFromData(QByteArray(base64.b64decode(dados)), "PNG"), nome


def test_catalogo_da_ponte_inclui_as_imagens(tmp_path):
    _app()
    janela = JanelaQuadro(Quadro())
    try:
        ponte = PonteQuadro(janela, base=tmp_path)
        resposta = ponte.tratar(json.dumps({"token": ponte.token, "pedido": "catalogo"}).encode("utf-8"))
        assert resposta["ok"] is True
        assert "carimbo-estrela" in resposta["icones"]
        assert "escolher" in resposta["icones"]
    finally:
        janela.close()
