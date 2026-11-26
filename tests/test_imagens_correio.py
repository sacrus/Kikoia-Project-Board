from email.message import EmailMessage

from quadro.correio.html import sanitizar_html
from quadro.correio.servidor import mensagem_de_bytes


def test_imagens_desligadas_ficam_marcadas():
    limpo = sanitizar_html('<p><img src="https://site.org/a.png"></p>', imagens=False)
    assert "[imagem bloqueada]" in limpo
    assert "src=" not in limpo


def test_imagens_ligadas_passam_as_embutidas_e_as_de_sites():
    limpo = sanitizar_html(
        '<img src="cid:logo"><img src="https://site.org/a.png">',
        imagens=True,
        anexos_cid=frozenset({"logo"}),
    )
    assert 'src="kikoia-cid:logo"' in limpo
    assert 'src="https://site.org/a.png"' in limpo


def test_imagem_embutida_em_falta_fica_marcada():
    limpo = sanitizar_html('<img src="cid:nao-existe">', imagens=True, anexos_cid=frozenset())
    assert "[imagem em falta]" in limpo
    assert "src=" not in limpo


def test_anexo_guarda_o_conteudo_para_poder_ser_aberto():
    mensagem = EmailMessage()
    mensagem["From"] = "professor@escola.pt"
    mensagem["To"] = "aluno@exemplo.pt"
    mensagem["Subject"] = "Ficha"
    mensagem.set_content("Segue a ficha.")
    mensagem.add_attachment(b"conteudo da ficha", maintype="application", subtype="octet-stream", filename="ficha.pdf")
    visto = mensagem_de_bytes("1", mensagem.as_bytes()).anexos[0]
    assert visto.nome == "ficha.pdf"
    assert visto.dados == b"conteudo da ficha"
