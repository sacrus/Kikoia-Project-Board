import json

import pytest
from PySide6.QtWidgets import QApplication

from quadro import acoes, carimbos, formas, magia
from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro


def test_identificadores_sao_unicos():
    ids = [a.id for a in acoes.ACOES]
    assert len(ids) == len(set(ids))


def test_todo_o_submenu_aponta_para_um_pai_existente():
    ids = {a.id for a in acoes.ACOES}
    for a in acoes.ACOES:
        if a.pai is not None:
            assert a.pai in ids, a.id


def test_ferramentas_e_figuras_do_catalogo_coincidem_com_o_codigo():
    assert set(acoes.FIGURAS) == set(carimbos.NOMES)
    assert set(acoes.FORMAS) == set(formas.TIPOS)
    assert set(acoes.EFEITOS) == set(magia.EFEITOS)


def test_cada_ferramenta_do_menu_existe_no_janela():
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    try:
        for ferramenta in acoes.FERRAMENTAS:
            janela.menu._escolher_ferramenta(ferramenta)
            assert janela.tela.ferramenta == ferramenta
    finally:
        janela.close()


def test_estado_marca_a_ferramenta_ativa_e_as_acoes_disponiveis():
    e = acoes.estado("borracha", tem_selecao=False, pode_desfazer=True, pode_refazer=False, correio_visivel=False)
    assert e["borracha"]["ativa"] is True
    assert e["caneta"]["ativa"] is False
    assert e["desfazer"]["disponivel"] is True
    assert e["refazer"]["disponivel"] is False
    assert e["apagar_selecao"]["disponivel"] is False


def test_catalogo_exporta_para_json_com_versao():
    dados = json.loads(json.dumps(acoes.catalogo_dados()))
    assert dados["versao"] == acoes.VERSAO_CATALOGO
    assert any(a["id"] == "carimbo.figura.sol" for a in dados["acoes"])


def test_acao_desconhecida_e_recusada():
    with pytest.raises(KeyError):
        acoes.acao("nao-existe")
