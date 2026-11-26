import base64
import hashlib
import json
import sys
import threading
import urllib.parse
import urllib.request

import pytest

from quadro.correio import contas, oauth, supervisor
from quadro.correio.modelo import ErroCorreio


def _b64(dados: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(dados).encode("utf-8")).rstrip(b"=").decode("ascii")


def _id_token(dados: dict) -> str:
    return f"{_b64({'alg': 'none'})}.{_b64(dados)}.assinatura"


def test_pkce_desafio_e_o_sha256_do_verificador():
    verificador, desafio = oauth.gerar_pkce()
    esperado = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    assert desafio == esperado
    assert 43 <= len(verificador) <= 128


def test_url_de_entrada_pede_pkce_e_os_ambitos_certos(monkeypatch):
    monkeypatch.setitem(oauth.PROVEDORES["google"], "cliente", "id-google")
    url = oauth.url_autorizacao("google", "http://127.0.0.1:5000/", "desafio", "estado-1")
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert query["code_challenge"] == ["desafio"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] == ["estado-1"]
    assert query["client_id"] == ["id-google"]
    assert "https://mail.google.com/" in query["scope"][0]
    assert query["access_type"] == ["offline"]


def test_xoauth2_tem_o_formato_sasl_esperado():
    assert oauth.xoauth2("aluno@escola.pt", "token") == "user=aluno@escola.pt\x01auth=Bearer token\x01\x01"


def test_email_sai_do_id_token():
    assert oauth.email_do_id_token(_id_token({"email": "Aluno@Escola.PT"})) == "aluno@escola.pt"
    assert oauth.email_do_id_token(_id_token({"preferred_username": "prof@escola.pt"})) == "prof@escola.pt"
    assert oauth.email_do_id_token("lixo") == ""


def test_renovar_devolve_o_token_de_acesso(monkeypatch):
    monkeypatch.setattr(oauth, "_pedido_token", lambda url, campos: {"access_token": "acesso", "refresh_token": "nova"})
    assert oauth.renovar("microsoft", "antiga") == ("acesso", "nova")


def test_renovar_sem_token_de_acesso_falha(monkeypatch):
    monkeypatch.setattr(oauth, "_pedido_token", lambda url, campos: {})
    with pytest.raises(ErroCorreio):
        oauth.renovar("google", "antiga")


def _navegador_que_confirma(estado_errado: bool):
    def abrir(url: str) -> bool:
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        redirect = query["redirect_uri"][0]
        estado = "errado" if estado_errado else query["state"][0]

        def responder():
            urllib.request.urlopen(f"{redirect}?code=codigo-1&state={estado}", timeout=5).read()

        threading.Thread(target=responder, daemon=True).start()
        return True

    return abrir


def test_entrar_troca_o_codigo_e_devolve_o_email_e_a_renovacao(monkeypatch):
    monkeypatch.setitem(oauth.PROVEDORES["google"], "cliente", "id-google")
    monkeypatch.setattr(oauth, "secreto", lambda provedor: None)
    monkeypatch.setattr(oauth.webbrowser, "open", _navegador_que_confirma(False))
    pedidos = []

    def pedido(url, campos):
        pedidos.append(campos)
        return {
            "scope": "https://mail.google.com/ openid email",
            "refresh_token": "renovacao-1",
            "id_token": _id_token({"email": "aluno@gmail.com"}),
        }

    monkeypatch.setattr(oauth, "_pedido_token", pedido)
    assert oauth.entrar("google") == ("aluno@gmail.com", "renovacao-1")
    assert pedidos[0]["grant_type"] == "authorization_code"
    assert pedidos[0]["code"] == "codigo-1"
    assert pedidos[0]["code_verifier"]


def test_entrar_sem_permissao_de_correio_avisa_em_vez_de_guardar(monkeypatch):
    monkeypatch.setitem(oauth.PROVEDORES["google"], "cliente", "id-google")
    monkeypatch.setattr(oauth, "secreto", lambda provedor: None)
    monkeypatch.setattr(oauth.webbrowser, "open", _navegador_que_confirma(False))
    monkeypatch.setattr(
        oauth,
        "_pedido_token",
        lambda url, campos: {
            "scope": "https://www.googleapis.com/auth/userinfo.email openid",
            "refresh_token": "renovacao-1",
            "id_token": _id_token({"email": "aluno@gmail.com"}),
        },
    )
    with pytest.raises(ErroCorreio) as erro:
        oauth.entrar("google")
    assert str(erro.value) == "correio.oauth_sem_correio"


def test_entrar_com_estado_trocado_e_recusada(monkeypatch):
    monkeypatch.setitem(oauth.PROVEDORES["google"], "cliente", "id-google")
    monkeypatch.setattr(oauth.webbrowser, "open", _navegador_que_confirma(True))
    with pytest.raises(ErroCorreio) as erro:
        oauth.entrar("google")
    assert str(erro.value) == "correio.oauth_cancelado"


def test_entrar_sem_aplicacao_registada_avisa(monkeypatch):
    monkeypatch.setitem(oauth.PROVEDORES["microsoft"], "cliente", "")
    with pytest.raises(ErroCorreio) as erro:
        oauth.entrar("microsoft")
    assert str(erro.value) == "correio.oauth_nao_configurado"


@pytest.fixture
def dados(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(supervisor, "ITERACOES", 1000)
    return tmp_path


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI só existe no Windows")
def test_conta_oauth_guarda_so_a_renovacao_e_renova_ao_abrir(dados, monkeypatch):
    conta = oauth.conta_do_provedor("google", "aluno@gmail.com")
    contas.guardar(conta, "renovacao-1")
    conteudo = (contas.pasta() / "contas" / "aluno@gmail.com" / "conta.json").read_text(encoding="utf-8")
    assert "renovacao-1" not in conteudo
    monkeypatch.setattr(oauth, "renovar", lambda provedor, renovacao: ("acesso-novo", "renovacao-2"))
    carregada, token = contas.carregar(endereco="aluno@gmail.com")
    assert carregada.metodo == "google"
    assert token == "acesso-novo"
    monkeypatch.setattr(oauth, "renovar", lambda provedor, renovacao: ("acesso-3", renovacao))
    assert contas.carregar(endereco="aluno@gmail.com")[1] == "acesso-3"


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI só existe no Windows")
def test_conta_oauth_com_renovacao_recusada_nao_deixa_entrar(dados, monkeypatch):
    contas.guardar(oauth.conta_do_provedor("microsoft", "prof@escola.pt"), "renovacao-1")

    def recusada(provedor, renovacao):
        raise ErroCorreio("correio.oauth_expirou")

    monkeypatch.setattr(oauth, "renovar", recusada)
    _, token = contas.carregar(endereco="prof@escola.pt")
    assert token == ""
