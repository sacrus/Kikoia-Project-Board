from quadro.correio.html import sanitizar_html


def test_font_size_zero_passa_a_um_pixel():
    limpo = sanitizar_html('<p style="font-size:0px">oculto</p>')
    assert "font-size:1px" in limpo
    assert "font-size:0" not in limpo


def test_font_size_zero_com_espacos_e_maiusculas():
    limpo = sanitizar_html('<div style="FONT-SIZE: 0 ; color:red">x</div>')
    assert "1px" in limpo
    assert "0 " not in limpo.split("1px")[0][-3:]


def test_atalho_font_com_zero_tambem_fica_com_um_pixel():
    limpo = sanitizar_html('<p style="font:0px Arial">x</p>')
    assert "font:1px" in limpo


def test_tamanho_de_etiqueta_font_zero_passa_a_um():
    assert 'size="1"' in sanitizar_html('<font size="0">x</font>')


def test_tamanhos_normais_ficam_iguais():
    assert "font-size:12px" in sanitizar_html('<p style="font-size:12px">x</p>')
    assert "font-size:0.5px" in sanitizar_html('<p style="font-size:0.5px">x</p>')
