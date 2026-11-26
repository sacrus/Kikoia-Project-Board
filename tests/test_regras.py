import json
from email.message import EmailMessage

import pytest

from quadro.correio import regras as R
from quadro.correio import servidor, supervisor
from quadro.correio.modelo import ErroCorreio, conta_cpanel
from quadro.correio.servidor import mensagem_de_bytes

PALAVRA = "segredo-1"


@pytest.fixture(autouse=True)
def iteracoes_rapidas(monkeypatch):
    monkeypatch.setattr(supervisor, "ITERACOES", 1000)


@pytest.fixture
def pasta(tmp_path):
    supervisor.definir(PALAVRA, tmp_path)
    return tmp_path


def _mensagem(remetente="desconhecido@lplogic.net", texto="Olá", anexos=(), destinatario="aluno@portugalsat.com"):
    original = EmailMessage()
    original["From"] = remetente
    original["To"] = destinatario
    original["Subject"] = "Assunto"
    original["Date"] = "Mon, 16 Nov 2026 10:00:00 +0000"
    original.set_content(texto)
    for nome, dados in anexos:
        original.add_attachment(dados, maintype="application", subtype="octet-stream", filename=nome)
    return mensagem_de_bytes("1", original.as_bytes())


# --- supervisor -------------------------------------------------------------------


def test_palavra_passe_nao_fica_guardada_em_claro(pasta):
    conteudo = (pasta / supervisor.NOME_FICHEIRO).read_text(encoding="utf-8")
    assert PALAVRA not in conteudo
    assert supervisor.verificar(PALAVRA, pasta)
    assert not supervisor.verificar("errada", pasta)


def test_palavra_passe_curta_e_recusada(tmp_path):
    with pytest.raises(ErroCorreio) as erro:
        supervisor.definir("abc", tmp_path)
    assert str(erro.value) == "supervisor.palavra_curta"


def test_alterar_palavra_passe_exige_a_atual(pasta):
    with pytest.raises(ErroCorreio):
        supervisor.definir("nova-123", pasta, palavra_atual="errada")
    supervisor.definir("nova-123", pasta, palavra_atual=PALAVRA)
    assert supervisor.verificar("nova-123", pasta)
    assert not supervisor.verificar(PALAVRA, pasta)


# --- entradas ---------------------------------------------------------------------


def test_endereco_exato_e_dominio_com_subdominios():
    lista = ["professor@lplogic.net", "escola.pt"]
    assert R.pertence("professor@lplogic.net", lista)
    assert not R.pertence("outro@lplogic.net", lista)
    assert R.pertence("aluno@escola.pt", lista)
    assert R.pertence("aluno@mail.escola.pt", lista)
    assert not R.pertence("aluno@evilescola.pt", lista)
    assert not R.pertence("aluno@escola.pt.evil.net", lista)


def test_entrada_invalida_e_recusada(pasta):
    with pytest.raises(ErroCorreio):
        R.alterar("remetentes", "isto nao e um email", pasta)


# --- ficheiro assinado ------------------------------------------------------------


def test_regras_guardadas_voltam_a_ler_se_integras(pasta):
    R.alterar("remetentes", "Professor@LPLogic.net", pasta)
    regras, integras = R.carregar(pasta)
    assert integras
    assert regras.remetentes == ["professor@lplogic.net"]


def test_ficheiro_alterado_a_mao_bloqueia_tudo(pasta):
    R.alterar("remetentes", "professor@lplogic.net", pasta)
    caminho = R.caminho(pasta)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["corpo"] = dados["corpo"].replace("professor", "intruso")
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    regras, integras = R.carregar(pasta)
    assert not integras
    assert regras.remetentes == []


def test_regras_sem_supervisor_nao_se_guardam(tmp_path):
    with pytest.raises(ErroCorreio) as erro:
        R.guardar(R.Regras(), tmp_path)
    assert str(erro.value) == "supervisor.nao_definido"


def test_alterar_palavra_passe_volta_a_assinar_as_regras(pasta):
    R.alterar("remetentes", "professor@lplogic.net", pasta)
    R.alterar_palavra_passe(PALAVRA, "nova-123", pasta)
    regras, integras = R.carregar(pasta)
    assert integras
    assert regras.remetentes == ["professor@lplogic.net"]


def test_remover_entrada(pasta):
    R.alterar("destinatarios", "professor@lplogic.net", pasta)
    regras = R.remover("destinatarios", "Professor@lplogic.net", pasta)
    assert regras.destinatarios == []


# --- leitura ----------------------------------------------------------------------


def test_remetente_nao_permitido_fica_fechado_e_sem_anexos_permitidos():
    regras = R.Regras(remetentes=["escola.pt"])
    visao = R.ver(regras, _mensagem(remetente="estranho@exemplo.org", anexos=[("ficha.pdf", b"x")]))
    assert not visao.aberta
    assert visao.texto is None
    assert visao.assunto == "Assunto"
    assert not visao.anexos[0].permitido


def test_remetente_permitido_abre_e_anexo_normal_fica_disponivel():
    regras = R.Regras(remetentes=["escola.pt"])
    visao = R.ver(regras, _mensagem(remetente="professor@escola.pt", anexos=[("ficha.pdf", b"x")]))
    assert visao.aberta
    assert "Olá" in visao.texto
    assert visao.anexos[0].permitido


def test_executavel_de_remetente_permitido_abre_com_aviso_e_nao_precisa_de_palavra_passe():
    regras = R.Regras(remetentes=["escola.pt"])
    visao = R.ver(regras, _mensagem(remetente="professor@escola.pt", anexos=[("jogo.exe", b"x")]))
    assert visao.anexos[0].executavel
    assert visao.anexos[0].permitido


def test_anexos_desligados_bloqueiam_tambem_os_executaveis_e_os_outros():
    regras = R.Regras(remetentes=["escola.pt"])
    visao = R.ver(regras, _mensagem(remetente="professor@escola.pt", anexos=[("jogo.exe", b"x"), ("ficha.pdf", b"x")]), anexos_ativos=False)
    assert not any(a.permitido for a in visao.anexos)


def test_desbloqueio_mostra_a_mensagem_de_remetente_bloqueado():
    regras = R.Regras()
    visao = R.ver(regras, _mensagem(), desbloqueada=True)
    assert visao.aberta
    assert "Olá" in visao.texto


def test_ligacoes_so_abrem_em_dominios_aprovados():
    regras = R.Regras(remetentes=["escola.pt"], ligacoes=["escola.pt"])
    texto = "Visita https://www.escola.pt/ficha e https://loja.exemplo.org/promo agora."
    visao = R.ver(regras, _mensagem(remetente="professor@escola.pt", texto=texto))
    assert "https://www.escola.pt/ficha" in visao.texto
    assert "loja.exemplo.org" not in visao.texto
    assert "[ligação bloqueada]" in visao.texto


# --- envio ------------------------------------------------------------------------


def test_envio_para_destinatario_bloqueado_e_recusado(monkeypatch):
    chamadas = []
    monkeypatch.setattr(servidor, "enviar", lambda *a, **k: chamadas.append(a))
    regras = R.Regras(destinatarios=["professor@lplogic.net"])
    conta = conta_cpanel("aluno@portugalsat.com")
    with pytest.raises(ErroCorreio) as erro:
        R.enviar(conta, "x", regras, ["estranho@lplogic.net"], "Olá", "Texto")
    assert str(erro.value) == "correio.destinatarios_bloqueados"
    assert chamadas == []


def test_envio_para_permitido_ou_desbloqueado_chega_ao_servidor(monkeypatch):
    chamadas = []
    monkeypatch.setattr(servidor, "enviar", lambda *a, **k: chamadas.append(a))
    regras = R.Regras(destinatarios=["professor@lplogic.net"])
    conta = conta_cpanel("aluno@portugalsat.com")
    R.enviar(conta, "x", regras, ["professor@lplogic.net"], "Olá", "Texto")
    R.enviar(conta, "x", regras, ["estranho@lplogic.net"], "Olá", "Texto", desbloqueado=True)
    assert len(chamadas) == 2
