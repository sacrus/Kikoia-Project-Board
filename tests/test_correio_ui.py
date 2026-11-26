import sys

import pytest
from PySide6.QtWidgets import QApplication

from quadro.correio import contas, segredos, supervisor, voz
from quadro.correio.modelo import ErroCorreio, conta_cpanel
from quadro.correio.regras import Regras
from quadro.janela import JanelaQuadro
from quadro.janela_correio import DialogoCorreio, DialogoEscrever, texto_erro
from quadro.modelo import Quadro


@pytest.fixture
def dados(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(supervisor, "ITERACOES", 1000)
    return tmp_path


def _app():
    return QApplication.instance() or QApplication([])


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI só existe no Windows")
def test_segredos_ida_e_volta_e_nao_ficam_em_claro():
    cifrado = segredos.cifrar("palavra-passe de teste")
    assert b"palavra-passe" not in cifrado
    assert segredos.decifrar(cifrado) == "palavra-passe de teste"


def test_conta_guardada_sem_palavra_passe_em_claro(dados):
    contas.guardar(conta_cpanel("aluno@portugalsat.com"), "segredo-123")
    conteudo = (contas.pasta() / "contas" / "aluno@portugalsat.com" / "conta.json").read_text(encoding="utf-8")
    assert "segredo-123" not in conteudo
    conta, senha = contas.carregar()
    assert conta.endereco == "aluno@portugalsat.com"
    assert senha == "segredo-123"
    assert conta.imap.porta == 993


def test_apagar_conta_remove_os_dados(dados):
    contas.guardar(conta_cpanel("aluno@portugalsat.com"), "segredo-123")
    contas.apagar()
    assert contas.carregar() is None


def test_preferencias_com_omissao_e_limites(dados):
    assert contas.preferencias()["bolha"] is True
    contas.guardar_preferencias({"bolha": False, "avisar": True, "intervalo_min": 500})
    prefs = contas.preferencias()
    assert prefs["bolha"] is False
    assert prefs["intervalo_min"] == 60


def test_leitura_em_voz_alta_nao_mete_o_texto_na_linha_de_comando():
    comando = " ".join(voz.comando())
    assert "Speak" in comando
    assert "InputEncoding" in comando
    assert "Olá" not in comando


def test_voz_sem_texto_nao_arranca_nada(monkeypatch):
    assert voz.falar("   ") is None
    if sys.platform != "win32":
        monkeypatch.setattr(voz, "comando_linux", lambda idioma=None: None)
        with pytest.raises(ErroCorreio):
            voz.falar("texto")


def test_mensagens_de_erro_conhecidas_sao_traduzidas():
    assert "palavra-passe" in texto_erro(ErroCorreio("correio.autenticacao_falhou"))
    assert texto_erro(ValueError("x")).startswith("Erro inesperado")


def test_dialogo_correio_sem_conta_mostra_a_configuracao(dados):
    _app()
    dialogo = DialogoCorreio()
    try:
        assert "Ainda não há conta" in dialogo._estado.text()
        assert not dialogo._escrever.isEnabled()
        assert dialogo._lista.count() == 0
    finally:
        dialogo.close()


def test_destinatarios_separados_por_virgula_ou_ponto_e_virgula(dados):
    _app()
    escrever = DialogoEscrever(conta_cpanel("aluno@portugalsat.com"), "x", Regras())
    try:
        escrever._para.setText("a@x.pt; b@y.pt, c@z.pt")
        assert escrever._destinatarios() == ["a@x.pt", "b@y.pt", "c@z.pt"]
    finally:
        escrever.close()


def test_bolha_do_correio_respeita_a_preferencia(dados):
    _app()
    contas.guardar_preferencias({"bolha": False, "avisar": False, "intervalo_min": 5})
    janela = JanelaQuadro(Quadro())
    try:
        assert janela.menu._correio.isHidden()
    finally:
        janela.close()


def test_contador_de_nao_lidas_aparece_na_bolha(dados):
    _app()
    janela = JanelaQuadro(Quadro())
    try:
        janela.menu.definir_correio(3)
        assert janela.menu._correio.text() == "✉ 3"
        janela.menu.definir_correio(0)
        assert janela.menu._correio.text() == "✉"
    finally:
        janela.close()


def test_formatacao_imagens_e_anexos_ligados_por_defeito(dados):
    prefs = contas.preferencias(dados)
    assert prefs["html"] is True
    assert prefs["imagens"] is True
    assert prefs["anexos"] is True


def test_sem_supervisao_o_remetente_desconhecido_abre_e_anexo_executavel_fica_disponivel():
    from email.message import EmailMessage

    from quadro.correio import regras as R
    from quadro.correio.servidor import mensagem_de_bytes

    original = EmailMessage()
    original["From"] = "desconhecido@exemplo.org"
    original["To"] = "aluno@portugalsat.com"
    original["Subject"] = "Oi"
    original.set_content("Texto")
    original.add_attachment(b"x", maintype="application", subtype="octet-stream", filename="jogo.exe")
    mensagem = mensagem_de_bytes("1", original.as_bytes())
    visao = R.ver(R.Regras(), mensagem, supervisionado=False)
    assert visao.aberta
    assert visao.texto.strip() == "Texto"
    assert visao.anexos[0].permitido


def test_sem_supervisao_envia_para_qualquer_destinatario(dados, monkeypatch):
    from quadro.correio import regras as R
    from quadro.correio import servidor

    chamadas = []
    monkeypatch.setattr(servidor, "enviar", lambda *a, **k: chamadas.append(a))
    R.enviar(conta_cpanel("aluno@portugalsat.com"), "x", R.Regras(), ["estranho@exemplo.org"], "Oi", "Texto", supervisionado=False)
    assert len(chamadas) == 1


def test_guardar_conta_nao_exige_supervisor(dados):
    contas.guardar(conta_cpanel("aluno@portugalsat.com"), "segredo-123")
    assert not supervisor.existe()


def test_contactos_acrescentar_remover_e_validar(dados):
    from quadro.correio import contatos as contactos

    contactos.acrescentar("Professora", "Professora@Escola.pt")
    contactos.acrescentar("Professora", "professora@escola.pt")
    assert contactos.enderecos() == ["professora@escola.pt"]
    with pytest.raises(ErroCorreio):
        contactos.acrescentar("Mau", "isto nao e um email")
    contactos.remover("professora@escola.pt")
    assert contactos.carregar() == []


def test_completar_substitui_so_o_ultimo_destinatario():
    from quadro.janela_correio import substituir_ultimo_destinatario

    assert substituir_ultimo_destinatario("a@x.pt, b@y", "bruno@y.pt") == "a@x.pt, bruno@y.pt, "
    assert substituir_ultimo_destinatario("ana@", "ana@x.pt") == "ana@x.pt, "


def test_completador_compara_so_o_fragmento_atual():
    _app()
    from quadro.janela_correio import _CompletadorDestinatarios

    completador = _CompletadorDestinatarios()
    assert completador.splitPath("a@x.pt, bru") == ["bru"]


@pytest.mark.skipif(sys.platform != "win32", reason="a leitura em voz alta é só Windows")
def test_nova_leitura_substitui_a_anterior_e_parar_termina_tudo(monkeypatch):
    import subprocess

    from quadro.correio import voz

    monkeypatch.setattr(
        voz, "comando", lambda: [sys.executable, "-c", "import sys,time; sys.stdin.read(); time.sleep(60)"]
    )
    primeira = voz.falar("primeira frase")
    segunda = voz.falar("segunda frase")
    assert primeira.poll() is not None
    assert segunda.poll() is None
    voz.parar()
    assert segunda.poll() is not None
    assert isinstance(segunda, subprocess.Popen)
