import os
import ssl
import time
from email.message import EmailMessage

import pytest

from quadro.correio import servidor
from quadro.correio.modelo import ErroCorreio, conta_cpanel
from quadro.correio.servidor import ClienteImap, enviar, mensagem_de_bytes

ENDERECO_TESTE = os.environ.get("KIKOIA_TESTE_CORREIO_ENDERECO", "")
SENHA_TESTE = os.environ.get("KIKOIA_TESTE_CORREIO_SENHA", "")
SEM_CREDENCIAIS = pytest.mark.skipif(
    not (ENDERECO_TESTE and SENHA_TESTE),
    reason="defina KIKOIA_TESTE_CORREIO_ENDERECO e KIKOIA_TESTE_CORREIO_SENHA para os testes reais",
)


def test_conta_cpanel_usa_imap_993_e_smtp_465_com_ssl():
    conta = conta_cpanel("Aluno@PortugalSat.com")
    assert conta.endereco == "aluno@portugalsat.com"
    assert conta.utilizador == "aluno@portugalsat.com"
    assert (conta.imap.servidor, conta.imap.porta, conta.imap.ssl) == ("mail.portugalsat.com", 993, True)
    assert (conta.smtp.servidor, conta.smtp.porta, conta.smtp.ssl) == ("mail.portugalsat.com", 465, True)


def test_contexto_exige_certificado_valido():
    contexto = servidor.contexto_seguro()
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.check_hostname is True


def test_mensagem_com_texto_e_anexo():
    original = EmailMessage()
    original["From"] = "Professor <Professor@LPLogic.net>"
    original["To"] = "aluno@portugalsat.com, outro@lplogic.net"
    original["Subject"] = "Trabalho de casa"
    original["Date"] = "Mon, 16 Nov 2026 10:00:00 +0000"
    original.set_content("Entrega até sexta.")
    original.add_attachment(b"%PDF-1.4 teste", maintype="application", subtype="pdf", filename="ficha.pdf")

    mensagem = mensagem_de_bytes("7", original.as_bytes())
    assert mensagem.uid == "7"
    assert mensagem.remetente == "professor@lplogic.net"
    assert mensagem.destinatarios == ("aluno@portugalsat.com", "outro@lplogic.net")
    assert mensagem.assunto == "Trabalho de casa"
    assert "Entrega até sexta." in mensagem.texto
    assert [(a.nome, a.tipo) for a in mensagem.anexos] == [("ficha.pdf", "application/pdf")]


def test_mensagem_so_html_fica_em_texto_sem_scripts():
    original = EmailMessage()
    original["From"] = "loja@exemplo.org"
    original["To"] = "aluno@portugalsat.com"
    original["Subject"] = "Promoção"
    original.set_content("<html><head><style>p{color:red}</style></head>"
                         "<body><script>alert(1)</script><p>Olá</p><p>Clique aqui</p></body></html>",
                         subtype="html")
    mensagem = mensagem_de_bytes("1", original.as_bytes())
    assert "Olá" in mensagem.texto
    assert "Clique aqui" in mensagem.texto
    assert "alert" not in mensagem.texto
    assert "color" not in mensagem.texto


def test_enviar_sem_destinatarios_falha_antes_de_ligar():
    with pytest.raises(ErroCorreio) as erro:
        enviar(conta_cpanel("aluno@portugalsat.com"), "x", [], "a", "b")
    assert str(erro.value) == "correio.sem_destinatarios"


def test_servidor_inexistente_devolve_erro_de_ligacao():
    conta = conta_cpanel("aluno@dominio-que-nao-existe.invalid")
    with pytest.raises(ErroCorreio) as erro:
        with ClienteImap(conta, "x", tempo_limite=5):
            pass
    assert str(erro.value) == "correio.sem_ligacao"


@SEM_CREDENCIAIS
def test_real_listar_caixa_de_entrada():
    conta = conta_cpanel(ENDERECO_TESTE)
    with ClienteImap(conta, SENHA_TESTE) as correio:
        mensagens = correio.listar(limite=5)
        nao_lidas = correio.nao_lidas()
    assert isinstance(mensagens, list)
    assert isinstance(nao_lidas, int) and nao_lidas >= 0


@SEM_CREDENCIAIS
def test_real_enviar_para_a_propria_conta():
    conta = conta_cpanel(ENDERECO_TESTE)
    assunto = f"Teste Kikoia {time.time_ns()}"
    enviar(conta, SENHA_TESTE, [ENDERECO_TESTE], assunto, "Mensagem de teste.")
    fim = time.monotonic() + 60
    assuntos = []
    while time.monotonic() < fim:
        with ClienteImap(conta, SENHA_TESTE) as correio:
            assuntos = [m.assunto for m in correio.listar(limite=20)]
        if assunto in assuntos:
            return
        time.sleep(5)
    pytest.fail(f"mensagem de teste não chegou em 60 s; assuntos vistos: {assuntos[:5]}")
