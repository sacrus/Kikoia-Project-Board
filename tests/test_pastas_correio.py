from quadro.correio.servidor import ClienteImap, Pasta, _nome_imap, _pasta_de_linha


def test_pasta_de_spam_e_identificada_pela_marca_do_servidor():
    assert _pasta_de_linha('(\\HasNoChildren \\Junk) "." "INBOX.Spam"') == Pasta("INBOX.Spam", "spam")


def test_pasta_do_lixo_e_identificada_pela_marca_do_servidor():
    assert _pasta_de_linha('(\\HasNoChildren \\Trash) "." "INBOX.Trash"') == Pasta("INBOX.Trash", "lixo")


def test_pasta_do_lixo_sem_marca_e_reconhecida_pelo_nome():
    assert _pasta_de_linha('(\\HasNoChildren) "." "INBOX.Lixo"') == Pasta("INBOX.Lixo", "lixo")


def test_caixa_de_entrada_e_pasta_normal():
    assert _pasta_de_linha('(\\HasNoChildren) "." INBOX') == Pasta("INBOX", None)


def test_pasta_nao_selecionavel_e_ignorada():
    assert _pasta_de_linha('(\\Noselect) "." "INBOX.Pastas"') is None


def test_nome_com_espacos_fica_entre_aspas():
    assert _nome_imap("INBOX.Lixo eletrónico") == '"INBOX.Lixo eletrónico"'
    assert _nome_imap("INBOX.Spam") == "INBOX.Spam"


class _Ligacao:
    def __init__(self):
        self.comandos = []

    def select(self, pasta, readonly=True):
        self.comandos.append(("select", pasta, readonly))
        return "OK", [b"1"]

    def uid(self, *argumentos):
        self.comandos.append(("uid",) + argumentos)
        return "OK", [b"1"]

    def expunge(self):
        self.comandos.append(("expunge",))
        return "OK", []


def _cliente_falso():
    cliente = ClienteImap(None, "x")
    cliente._ligacao = _Ligacao()
    return cliente


def test_apagar_move_para_o_lixo_e_expurga():
    cliente = _cliente_falso()
    cliente.apagar("7", "INBOX", "INBOX.Trash")
    assert cliente._ligacao.comandos == [
        ("select", "INBOX", False),
        ("uid", "COPY", "7", "INBOX.Trash"),
        ("uid", "STORE", "7", "+FLAGS", "(\\Deleted)"),
        ("expunge",),
    ]


def test_apagar_no_lixo_apaga_de_vez_sem_copiar():
    cliente = _cliente_falso()
    cliente.apagar("7", "INBOX.Trash", "INBOX.Trash")
    assert not any(c[:2] == ("uid", "COPY") for c in cliente._ligacao.comandos)
    assert ("uid", "STORE", "7", "+FLAGS", "(\\Deleted)") in cliente._ligacao.comandos
