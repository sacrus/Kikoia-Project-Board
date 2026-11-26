from email.message import EmailMessage

import pytest

from quadro.correio import servidor
from quadro.correio.modelo import ErroCorreio, conta_cpanel
from quadro.correio.servidor import ClientePop3, cliente_de


def _bruta(assunto: str, remetente: str) -> list[bytes]:
    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = "aluno@escola.pt"
    mensagem["Subject"] = assunto
    mensagem.set_content("Corpo de " + assunto)
    return mensagem.as_bytes().splitlines()


MENSAGENS = {1: _bruta("Primeira", "prof@escola.pt"), 2: _bruta("Segunda", "colega@escola.pt")}


class _Pop3Falso:
    def __init__(self):
        self.comandos = []

    def user(self, utilizador):
        self.comandos.append(("user", utilizador))

    def pass_(self, palavra):
        self.comandos.append(("pass", palavra))

    def uidl(self):
        return b"+OK", [b"1 uid-a", b"2 uid-b"], 0

    def retr(self, numero):
        self.comandos.append(("retr", numero))
        return b"+OK", MENSAGENS[numero], 0

    def dele(self, numero):
        self.comandos.append(("dele", numero))
        return b"+OK"

    def quit(self):
        self.comandos.append(("quit",))
        return b"+OK"


@pytest.fixture
def servidor_falso(monkeypatch):
    instancia = _Pop3Falso()
    monkeypatch.setattr(servidor.poplib, "POP3_SSL", lambda *a, **k: instancia)
    return instancia


def _conta_pop3():
    return conta_cpanel("aluno@escola.pt", protocolo="pop3")


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="DPAPI só existe no Windows")
def test_protocolo_pop3_fica_guardado_na_conta():
    from quadro.correio import contas

    contas.guardar(_conta_pop3(), "segredo")
    carregada, senha = contas.carregar(endereco="aluno@escola.pt")
    assert carregada.protocolo == "pop3"
    assert carregada.imap.porta == 995
    assert senha == "segredo"


def test_conta_pop3_usa_a_porta_995():
    assert _conta_pop3().imap.porta == 995
    assert conta_cpanel("aluno@escola.pt").imap.porta == 993


def test_cliente_de_escolhe_pop3_quando_a_conta_o_pede():
    assert isinstance(cliente_de(_conta_pop3(), "x"), ClientePop3)


def test_login_com_utilizador_e_palavra_passe(servidor_falso):
    with ClientePop3(_conta_pop3(), "segredo") as correio:
        correio.listar_pastas()
    assert ("user", "aluno@escola.pt") in servidor_falso.comandos
    assert ("pass", "segredo") in servidor_falso.comandos


def test_lista_as_mensagens_mais_recentes_primeiro(servidor_falso):
    with ClientePop3(_conta_pop3(), "x") as correio:
        mensagens = correio.listar(limite=10)
    assert [m.assunto for m in mensagens] == ["Segunda", "Primeira"]
    assert [m.uid for m in mensagens] == ["uid-b", "uid-a"]


def test_apagar_marca_para_apagar_e_confirma_ao_sair(servidor_falso):
    with ClientePop3(_conta_pop3(), "x") as correio:
        correio.listar()
        correio.apagar("uid-b", "INBOX", None)
    assert ("dele", 2) in servidor_falso.comandos
    assert servidor_falso.comandos[-1] == ("quit",)


def test_operacoes_sem_equivalente_no_pop3_avisam(servidor_falso):
    with ClientePop3(_conta_pop3(), "x") as correio:
        with pytest.raises(ErroCorreio) as marcar:
            correio.marcar("uid-a", "INBOX", lida=False)
        assert str(marcar.value) == "correio.pop3_sem_marcas"
        with pytest.raises(ErroCorreio) as enviados:
            correio.guardar_em_enviados(b"x")
        assert str(enviados.value) == "correio.pop3_sem_enviados"


def test_pesquisa_no_pop3_filtra_por_assunto(servidor_falso):
    with ClientePop3(_conta_pop3(), "x") as correio:
        encontradas = correio.listar(termo="primeira")
    assert [m.assunto for m in encontradas] == ["Primeira"]


def test_nao_lidas_no_pop3_sao_zero_porque_o_servidor_nao_guarda_o_estado(servidor_falso):
    with ClientePop3(_conta_pop3(), "x") as correio:
        assert correio.nao_lidas() == 0
