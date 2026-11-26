from email.message import EmailMessage

from quadro.correio import regras as R
from quadro.correio.html import sanitizar_html
from quadro.correio.servidor import mensagem_de_bytes


def _mensagem_html(html: str, remetente: str = "professor@escola.pt"):
    original = EmailMessage()
    original["From"] = remetente
    original["To"] = "aluno@portugalsat.com"
    original["Subject"] = "Ficha"
    original.set_content("Versão de texto")
    original.add_alternative(html, subtype="html")
    return mensagem_de_bytes("1", original.as_bytes())


def test_scripts_e_estilos_sao_removidos_com_o_conteudo():
    limpo = sanitizar_html("<p>Olá<script>alert('x')</script></p><style>p{color:red}</style>")
    assert "Olá" in limpo
    assert "alert" not in limpo
    assert "color:red" not in limpo


def test_imagens_remotas_nunca_ficam_ligadas():
    limpo = sanitizar_html('<p>Veja <img src="https://rastreio.exemplo.org/p.gif"></p>')
    assert "src=" not in limpo
    assert "rastreio" not in limpo
    assert "[imagem bloqueada]" in limpo


def test_atributos_de_eventos_e_estilos_com_url_sao_removidos():
    limpo = sanitizar_html('<p onclick="x()" style="background:url(http://a.org/x.png)">Texto</p>')
    assert "onclick" not in limpo
    assert "url(" not in limpo
    assert "Texto" in limpo


def test_formatacao_basica_e_mantida():
    limpo = sanitizar_html("<p><b>Negrito</b> e <i>itálico</i></p><ul><li>Item</li></ul>")
    assert "<b>Negrito</b>" in limpo
    assert "<i>itálico</i>" in limpo
    assert "<li>Item</li>" in limpo


def test_ligacao_so_fica_ativa_em_dominios_permitidos():
    html = '<a href="https://www.escola.pt/ficha">ficha</a> <a href="https://loja.org/x">promo</a>'
    limpo = sanitizar_html(html, lambda dominio: dominio.endswith("escola.pt"))
    assert 'href="https://www.escola.pt/ficha"' in limpo
    assert "loja.org" not in limpo
    assert "promo" in limpo


def test_sem_filtro_de_ligacoes_todas_ficam_ativas():
    limpo = sanitizar_html('<a href="https://loja.org/x">promo</a>')
    assert "https://loja.org/x" in limpo


def test_javascript_em_ligacao_e_removido():
    limpo = sanitizar_html('<a href="javascript:alert(1)">clique</a>')
    assert "javascript" not in limpo
    assert "clique" in limpo


def test_html_so_aparece_quando_a_preferencia_esta_ligada():
    mensagem = _mensagem_html("<p><b>Ficha</b></p>")
    desligado = R.ver(R.Regras(remetentes=["escola.pt"]), mensagem, html_ativo=False)
    ligado = R.ver(R.Regras(remetentes=["escola.pt"]), mensagem, html_ativo=True)
    assert desligado.html is None
    assert ligado.html is not None and "<b>Ficha</b>" in ligado.html
    assert ligado.texto is not None and "Versão de texto" in ligado.texto


def test_html_nao_mostra_mensagem_bloqueada():
    mensagem = _mensagem_html("<p>Segredo</p>", remetente="estranho@exemplo.org")
    visao = R.ver(R.Regras(), mensagem, html_ativo=True)
    assert not visao.aberta
    assert visao.html is None


def test_mensagem_com_formatacao_leva_texto_e_html():
    from quadro.correio.servidor import montar_mensagem

    mensagem = montar_mensagem("aluno@portugalsat.com", ["professor@escola.pt"], "Ficha", "Olá", "<p><b>Olá</b></p>")
    tipos = [parte.get_content_type() for parte in mensagem.walk() if not parte.is_multipart()]
    assert "text/plain" in tipos and "text/html" in tipos
    assert mensagem.get_body(("plain",)).get_content().strip() == "Olá"


def test_mensagem_sem_formatacao_e_so_texto():
    from quadro.correio.servidor import montar_mensagem

    mensagem = montar_mensagem("aluno@portugalsat.com", ["professor@escola.pt"], "Ficha", "Olá")
    assert not mensagem.is_multipart()


def test_html_do_editor_perde_cabecalho_e_meta():
    html_do_editor = (
        '<!DOCTYPE HTML><html><head><meta name="qrichtext" content="1" />'
        "<style>p, li { white-space: pre-wrap; }</style></head>"
        '<body><p style="margin:0"><b>Olá</b></p></body></html>'
    )
    limpo = sanitizar_html(html_do_editor, None)
    assert "<b>Olá</b>" in limpo
    assert "<meta" not in limpo
    assert "white-space" not in limpo
