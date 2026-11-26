from email.message import EmailMessage

from quadro.correio import composicao
from quadro.correio.modelo import Anexo, Mensagem
from quadro.correio.servidor import ClienteImap, _criterio_pesquisa, mensagem_de_bytes


def _mensagem(**campos):
    base = dict(
        uid="1",
        remetente="prof@escola.pt",
        destinatarios=("aluno@escola.pt",),
        assunto="Ficha",
        data="Mon, 16 Nov 2026 10:00:00 +0000",
        texto="Segue a ficha.\nBom trabalho.",
        anexos=(Anexo("ficha.pdf", "application/pdf", 3, b"abc"),),
        cc=("colega@escola.pt",),
    )
    base.update(campos)
    return Mensagem(**base)


def test_responder_vai_so_ao_remetente_e_cita_o_texto():
    rascunho = composicao.responder(_mensagem(), "aluno@escola.pt")
    assert rascunho.para == ("prof@escola.pt",)
    assert rascunho.cc == ()
    assert rascunho.assunto == "Re: Ficha"
    assert "> Segue a ficha." in rascunho.texto
    assert "prof@escola.pt escreveu" in rascunho.texto


def test_responder_a_todos_inclui_os_outros_e_exclui_o_proprio():
    mensagem = _mensagem(destinatarios=("aluno@escola.pt", "outro@escola.pt"), cc=("colega@escola.pt",))
    rascunho = composicao.responder(mensagem, "aluno@escola.pt", todos=True)
    assert rascunho.para == ("prof@escola.pt",)
    assert rascunho.cc == ("outro@escola.pt", "colega@escola.pt")


def test_assunto_nao_repete_o_prefixo():
    assert composicao.responder(_mensagem(assunto="Re: Ficha"), "a@x.pt").assunto == "Re: Ficha"
    assert composicao.encaminhar(_mensagem(assunto="Fwd: Ficha")).assunto == "Fwd: Ficha"


def test_encaminhar_leva_o_texto_e_os_anexos():
    rascunho = composicao.encaminhar(_mensagem())
    assert rascunho.para == ()
    assert rascunho.assunto == "Fwd: Ficha"
    assert "Mensagem encaminhada" in rascunho.texto
    assert rascunho.anexos[0].nome == "ficha.pdf"


def test_editar_rascunho_repoe_destinatarios_e_texto():
    rascunho = composicao.editar(_mensagem(assunto="Rascunho", texto="Ainda a escrever"))
    assert rascunho.para == ("aluno@escola.pt",)
    assert rascunho.cc == ("colega@escola.pt",)
    assert rascunho.texto == "Ainda a escrever"


def test_pesquisa_ignora_acentos_e_maiusculas():
    assert _criterio_pesquisa("Reunião") == ["TEXT", '"Reuniao"']
    assert _criterio_pesquisa("   ") == ["ALL"]


def _mensagem_bruta(uid_flags: bytes) -> bytes:
    mensagem = EmailMessage()
    mensagem["From"] = "prof@escola.pt"
    mensagem["To"] = "aluno@escola.pt"
    mensagem["Subject"] = "Teste"
    mensagem.set_content("Olá")
    return mensagem.as_bytes()


class _Ligacao:
    def __init__(self, bruta=None):
        self.comandos = []
        self.bruta = bruta

    def select(self, pasta, readonly=True):
        self.comandos.append(("select", pasta, readonly))
        return "OK", [b"1"]

    def uid(self, *argumentos):
        self.comandos.append(("uid",) + argumentos)
        if argumentos[0] == "FETCH":
            return "OK", [(b'1 (UID 5 FLAGS (\\Seen \\Flagged) BODY[] {10}', self.bruta), b")"]
        return "OK", [b"1"]

    def expunge(self):
        self.comandos.append(("expunge",))
        return "OK", []

    def list(self):
        return "OK", [b'(\\HasNoChildren \\Drafts) "." "INBOX.Drafts"']

    def status(self, pasta, criterio):
        return "OK", [f'{pasta} (UNSEEN 0)'.encode("utf-8")]

    def append(self, pasta, flags, data, mensagem):
        self.comandos.append(("append", pasta, flags, mensagem[:4]))
        return "OK", [b"done"]


def _cliente(bruta=None):
    cliente = ClienteImap(None, "x")
    cliente._ligacao = _Ligacao(bruta)
    return cliente


def test_obter_le_as_bandeiras_de_lida_e_estrela():
    cliente = _cliente(_mensagem_bruta(b""))
    mensagem = cliente.obter("5")
    assert mensagem.lida is True
    assert mensagem.marcada is True


def test_marcar_como_nao_lida_retira_o_visto():
    cliente = _cliente()
    cliente.marcar("5", "INBOX", lida=False)
    assert ("uid", "STORE", "5", "-FLAGS", "(\\Seen)") in cliente._ligacao.comandos


def test_mover_copia_marca_como_apagada_e_expurga():
    cliente = _cliente()
    cliente.mover("5", "INBOX", "INBOX.Spam")
    assert cliente._ligacao.comandos == [
        ("select", "INBOX", False),
        ("uid", "COPY", "5", "INBOX.Spam"),
        ("uid", "STORE", "5", "+FLAGS", "(\\Deleted)"),
        ("expunge",),
    ]


def test_janela_de_escrever_abre_preenchida_com_a_resposta():
    from PySide6.QtWidgets import QApplication

    from quadro.correio.modelo import conta_cpanel
    from quadro.correio.regras import Regras
    from quadro.janela_correio import DialogoEscrever

    QApplication.instance() or QApplication([])
    rascunho = composicao.responder(_mensagem(), "aluno@escola.pt", todos=True)
    dialogo = DialogoEscrever(conta_cpanel("aluno@portugalsat.com"), "x", Regras(), None, rascunho)
    try:
        assert dialogo._para.text() == "prof@escola.pt"
        assert dialogo._assunto.text() == "Re: Ficha"
        assert "> Segue a ficha." in dialogo._texto.toPlainText()
    finally:
        dialogo.close()


def test_escolha_de_remetente_tem_as_contas_e_por_omissao_a_ativa():
    from PySide6.QtWidgets import QApplication

    from quadro.correio.modelo import conta_cpanel
    from quadro.correio.regras import Regras
    from quadro.janela_correio import DialogoEscrever

    QApplication.instance() or QApplication([])
    ativa = conta_cpanel("b@portugalsat.com")
    dialogo = DialogoEscrever(ativa, "x", Regras(), None, None, enderecos=["a@portugalsat.com", "b@portugalsat.com"])
    try:
        assert [dialogo._de.itemText(i) for i in range(dialogo._de.count())] == ["a@portugalsat.com", "b@portugalsat.com"]
        assert dialogo._de.currentText() == "b@portugalsat.com"
    finally:
        dialogo.close()


def test_rascunho_vai_para_a_pasta_de_rascunhos_com_a_marca_de_rascunho():
    cliente = _cliente()
    cliente.guardar_em_pasta("rascunhos", b"Subject: x\r\n\r\nola", "(\\Draft \\Seen)")
    assert ("append", "INBOX.Drafts", "(\\Draft \\Seen)", b"Subj") in cliente._ligacao.comandos
