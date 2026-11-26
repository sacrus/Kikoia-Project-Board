from email.message import EmailMessage

import pytest

from quadro.correio import regras as R
from quadro.correio import servidor
from quadro.correio.modelo import Anexo, conta_cpanel
from quadro.correio.servidor import mensagem_de_bytes, montar_mensagem


def _partes_com_nome(mensagem):
    return [p.get_filename() for p in mensagem.iter_attachments()]


def test_mensagem_tem_cc_anexos_e_imagem_embutida_mas_nao_bcc():
    html = '<p><img src="cid:img1"></p>'
    mensagem = montar_mensagem(
        "a@escola.pt",
        ["b@escola.pt"],
        "Ficha",
        "Texto",
        html=html,
        cc=["c@escola.pt"],
        cco=["d@escola.pt"],
        anexos=(Anexo("ficha.pdf", "application/pdf", 3, b"abc"),),
        imagens=(Anexo("img1", "image/png", 3, b"\x89PN", "img1"),),
    )
    assert mensagem["Cc"] == "c@escola.pt"
    assert mensagem["Bcc"] is None
    assert "ficha.pdf" in _partes_com_nome(mensagem)
    assert any(p.get("Content-ID") == "<img1>" for p in mensagem.walk())


def test_copia_para_enviados_leva_o_bcc():
    copia = montar_mensagem("a@escola.pt", ["b@escola.pt"], "Ficha", "Texto", cco=["d@escola.pt"], com_bcc=True)
    assert copia["Bcc"] == "d@escola.pt"


def test_mensagem_recebida_le_cc_e_bcc_dos_cabecalhos():
    original = EmailMessage()
    original["From"] = "prof@escola.pt"
    original["To"] = "aluno@escola.pt"
    original["Cc"] = "colega@escola.pt"
    original["Bcc"] = "oculto@escola.pt"
    original["Subject"] = "Teste"
    original.set_content("Olá")
    lida = mensagem_de_bytes("1", original.as_bytes())
    assert lida.destinatarios == ("aluno@escola.pt",)
    assert lida.cc == ("colega@escola.pt",)
    assert lida.cco == ("oculto@escola.pt",)


class _SmtpFalso:
    registos: list = []

    def __init__(self, host, porta, context=None, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def login(self, utilizador, palavra):
        pass

    def send_message(self, mensagem, from_addr=None, to_addrs=None):
        _SmtpFalso.registos.append((mensagem, to_addrs))
        return {}


def test_envio_entrega_a_todos_mas_a_mensagem_nao_mostra_o_bcc(monkeypatch):
    _SmtpFalso.registos = []
    monkeypatch.setattr(servidor.smtplib, "SMTP_SSL", _SmtpFalso)
    conta = conta_cpanel("a@escola.pt")
    copia = servidor.enviar(
        conta,
        "x",
        ["b@escola.pt"],
        "Oi",
        "Texto",
        cc=["c@escola.pt"],
        cco=["d@escola.pt"],
    )
    mensagem, destinatarios = _SmtpFalso.registos[0]
    assert set(destinatarios) == {"b@escola.pt", "c@escola.pt", "d@escola.pt"}
    assert mensagem["Bcc"] is None
    assert copia["Bcc"] == "d@escola.pt"


def test_bcc_de_destinatario_fora_da_lista_permitida_e_bloqueado_com_supervisao():
    regras = R.Regras(destinatarios=["colega@escola.pt"])
    with pytest.raises(Exception) as erro:
        R.enviar(conta_cpanel("a@escola.pt"), "x", regras, ["colega@escola.pt"], "Oi", "Texto", cco=["fora@exemplo.org"])
    assert str(erro.value) == "correio.destinatarios_bloqueados"
