from quadro.correio import ordenacao
from quadro.correio.modelo import Mensagem
from quadro.correio.servidor import ClienteImap


def _m(uid, remetente, assunto, data, lida=True):
    return Mensagem(uid=uid, remetente=remetente, destinatarios=(), assunto=assunto, data=data, texto="", lida=lida)


MENSAGENS = [
    _m("1", "b@x.pt", "Zebra", "Mon, 16 Nov 2026 10:00:00 +0000"),
    _m("2", "a@x.pt", "Ficha", "Tue, 17 Nov 2026 10:00:00 +0000", lida=False),
    _m("3", "c@x.pt", "Aviso", "Sun, 15 Nov 2026 10:00:00 +0000"),
]


def _uids(mensagens):
    return [m.uid for m in mensagens]


def test_mais_recentes_primeiro_e_mais_antigas_primeiro():
    assert _uids(ordenacao.ordenar(MENSAGENS, "recentes")) == ["2", "1", "3"]
    assert _uids(ordenacao.ordenar(MENSAGENS, "antigas")) == ["3", "1", "2"]


def test_ordem_por_remetente_e_por_assunto():
    assert _uids(ordenacao.ordenar(MENSAGENS, "remetente")) == ["2", "1", "3"]
    assert _uids(ordenacao.ordenar(MENSAGENS, "assunto")) == ["3", "2", "1"]


def test_por_ler_primeiro():
    assert _uids(ordenacao.ordenar(MENSAGENS, "nao_lidas"))[0] == "2"


def test_data_invalida_nao_rebenta_a_ordenacao():
    estranha = _m("9", "d@x.pt", "Sem data", "isto não é uma data")
    assert _uids(ordenacao.ordenar([estranha] + MENSAGENS, "antigas"))[0] == "9"


class _Ligacao:
    def list(self):
        return "OK", [b'(\\HasNoChildren) "." "INBOX"', b'(\\HasNoChildren \\Drafts) "." "INBOX.Drafts"']

    def status(self, pasta, criterio):
        contagem = {"INBOX": 4, "INBOX.Drafts": 0}[pasta.strip('"')]
        return "OK", [f'"{pasta}" (UNSEEN {contagem})'.encode("utf-8")]


def test_pastas_trazem_o_numero_de_nao_lidas():
    cliente = ClienteImap(None, "x")
    cliente._ligacao = _Ligacao()
    pastas = {p.nome: p.nao_lidas for p in cliente.listar_pastas()}
    assert pastas == {"INBOX": 4, "INBOX.Drafts": 0}


def test_email_novo_leva_a_assinatura(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from quadro import janela_correio
    from quadro.correio.modelo import conta_cpanel
    from quadro.correio.regras import Regras

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(janela_correio.contas, "preferencias", lambda *a, **k: {"assinatura": "Luís Patrício"})
    dialogo = janela_correio.DialogoEscrever(conta_cpanel("a@portugalsat.com"), "x", Regras(), None, None)
    try:
        assert "-- \nLuís Patrício" in dialogo._texto.toPlainText()
    finally:
        dialogo.close()
