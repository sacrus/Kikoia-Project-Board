from quadro import acoes, menu_prefs


def test_jogos_aparece_no_menu_por_omissao(tmp_path):
    assert menu_prefs.ler(tmp_path)["jogos"] is True


def test_preferencia_do_jogos_fica_guardada(tmp_path):
    menu_prefs.guardar({"jogos": False}, tmp_path)
    assert menu_prefs.ler(tmp_path)["jogos"] is False
    menu_prefs.guardar({"jogos": True}, tmp_path)
    assert menu_prefs.ler(tmp_path)["jogos"] is True


def test_jogos_escondido_fica_indisponivel_para_o_teclado():
    estado = acoes.estado("caneta", False, False, False, True, jogos_visivel=False)
    assert estado["jogos"]["disponivel"] is False
    assert acoes.estado("caneta", False, False, False, True)["jogos"]["disponivel"] is True
