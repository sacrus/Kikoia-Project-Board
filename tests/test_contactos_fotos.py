import base64

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from quadro import icones_contacto
from quadro.correio import contatos
from quadro.correio.modelo import ErroCorreio


@pytest.fixture
def base(tmp_path):
    return tmp_path


def _foto_pequena():
    imagem = QImage(20, 20, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("green"))
    from PySide6.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "PNG")
    return base64.b64encode(bytes(buffer.data())).decode("ascii")


def test_contacto_guarda_icone_e_foto(base):
    contatos.acrescentar("Mãe", "mae@exemplo.pt", base=base, icone="coracao", foto=_foto_pequena())
    contacto = contatos.carregar(base)[0]
    assert contacto["icone"] == "coracao"
    assert contacto["foto"]


def test_contacto_sem_foto_usa_o_icone_por_omissao(base):
    contatos.acrescentar("Avó", "avo@exemplo.pt", base=base)
    contacto = contatos.carregar(base)[0]
    assert contacto["icone"] == "pessoa"
    assert contacto["foto"] is None


def test_icone_desconhecido_volta_ao_padrao(base):
    contatos.acrescentar("Pai", "pai@exemplo.pt", base=base, icone="inexistente")
    assert contatos.carregar(base)[0]["icone"] == "pessoa"


def test_foto_demasiado_grande_e_recusada(base):
    with pytest.raises(ErroCorreio) as erro:
        contatos.acrescentar("X", "x@exemplo.pt", base=base, foto="A" * (contatos.MAX_FOTO_CHARS + 1))
    assert str(erro.value) == "correio.foto_grande"


def test_todos_os_icones_de_contacto_desenham_uma_imagem_valida():
    QApplication.instance() or QApplication([])
    for nome in contatos.ICONES:
        pixmap = icones_contacto.desenhar(nome, 48)
        assert not pixmap.isNull(), nome
        assert pixmap.width() == 48


def test_escolher_icone_grande_e_guardado_no_contacto(base, monkeypatch):
    from quadro import janela_correio

    monkeypatch.setenv("LOCALAPPDATA", str(base))
    QApplication.instance() or QApplication([])
    dialogo = janela_correio.DialogoContactos()
    try:
        assert set(dialogo._botoes_icones) == set(janela_correio.ROTULOS_ICONES_CONTACTO)
        dialogo._botoes_icones["coracao"].click()
        assert dialogo._icone_escolhido == "coracao"
        dialogo._nome.setText("Avó")
        dialogo._endereco.setText("avo@exemplo.pt")
        dialogo._acrescentar()
        assert contatos.carregar()[0]["icone"] == "coracao"
    finally:
        dialogo.close()


def test_foto_guardada_volta_a_ser_uma_imagem():
    from quadro.janela_correio import imagem_do_contacto

    QApplication.instance() or QApplication([])
    contacto = {"nome": "Mãe", "endereco": "mae@exemplo.pt", "icone": "pessoa", "foto": _foto_pequena()}
    pixmap = imagem_do_contacto(contacto, 40)
    assert not pixmap.isNull()
    assert pixmap.width() == 40
