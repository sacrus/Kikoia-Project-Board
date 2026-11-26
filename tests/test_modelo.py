import json

import pytest

from quadro.modelo import (
    BRANCO,
    FORMATO,
    VERSAO_FORMATO,
    ErroQuadro,
    Quadro,
    cor_caneta_automatica,
)


@pytest.mark.parametrize(
    "fundo, caneta",
    [
        ("#ffffff", "#000000"),
        ("#fff8dc", "#000000"),
        ("#dbeafe", "#000000"),
        ("#222222", "#ffffff"),
        ("#000000", "#ffffff"),
        ("#2563eb", "#ffffff"),
    ],
)
def test_caneta_automatica_segue_a_luminancia_do_fundo(fundo, caneta):
    assert cor_caneta_automatica(fundo) == caneta


def test_traco_acumula_pontos():
    quadro = Quadro()
    traco = quadro.comecar_traco("#000000", 0.01, 0.1, 0.1)
    quadro.acrescentar_ponto(traco, 0.2, 0.3)
    assert quadro.tracos == [traco]
    assert traco.pontos == [(0.1, 0.1), (0.2, 0.3)]


def test_borracha_remove_so_os_tracos_perto():
    quadro = Quadro()
    perto = quadro.comecar_traco("#000000", 0.01, 0.5, 0.5)
    quadro.comecar_traco("#000000", 0.01, 0.9, 0.9)
    assert quadro.apagar_perto(0.5, 0.5, 0.05) == 1
    assert perto not in quadro.tracos
    assert len(quadro.tracos) == 1


def test_borracha_usa_a_proporcao_do_ecra():
    quadro = Quadro()
    quadro.comecar_traco("#000000", 0.01, 0.5, 0.5)
    # Num ecrã 2:1, 0.1 de largura (normalizada) equivale a 0.2 de altura: fora do raio de 0.15.
    assert quadro.apagar_perto(0.6, 0.5, 0.15, proporcao=2.0) == 0
    assert quadro.apagar_perto(0.6, 0.5, 0.15, proporcao=1.0) == 1


def test_guardar_e_carregar_mantem_o_desenho(tmp_path):
    quadro = Quadro("#e8f4ea")
    traco = quadro.comecar_traco("#e11d48", 0.02, 0.25, 0.5)
    quadro.acrescentar_ponto(traco, 0.75, 0.5)
    ficheiro = tmp_path / "desenho.json"
    quadro.guardar(ficheiro)

    lido = Quadro.carregar(ficheiro)
    assert lido.fundo == "#e8f4ea"
    assert lido.tracos == quadro.tracos


def test_ficheiro_tem_formato_e_versao(tmp_path):
    ficheiro = tmp_path / "d.json"
    Quadro().guardar(ficheiro)
    dados = json.loads(ficheiro.read_text(encoding="utf-8"))
    assert dados["formato"] == FORMATO
    assert dados["versao"] == VERSAO_FORMATO
    assert dados["fundo"] == BRANCO


@pytest.mark.parametrize(
    "dados",
    [
        [],
        {"formato": "outro", "versao": 1, "fundo": "#ffffff", "tracos": []},
        {"formato": FORMATO, "versao": 99, "fundo": "#ffffff", "tracos": []},
        {"formato": FORMATO, "versao": 1, "fundo": "vermelho", "tracos": []},
        {"formato": FORMATO, "versao": 1, "fundo": "#ffffff", "tracos": "x"},
        {"formato": FORMATO, "versao": 1, "fundo": "#ffffff", "tracos": [
            {"cor": "#000000", "espessura": 0, "pontos": [[0.1, 0.1]]}]},
        {"formato": FORMATO, "versao": 1, "fundo": "#ffffff", "tracos": [
            {"cor": "#000000", "espessura": 0.01, "pontos": [[1.5, 0.1]]}]},
        {"formato": FORMATO, "versao": 1, "fundo": "#ffffff", "tracos": [
            {"cor": "#000000", "espessura": 0.01, "pontos": []}]},
        {"formato": FORMATO, "versao": 1, "fundo": "#ffffff", "tracos": [
            {"cor": "#000000", "espessura": True, "pontos": [[0.1, 0.1]]}]},
    ],
)
def test_ficheiro_invalido_e_recusado(dados):
    with pytest.raises(ErroQuadro):
        Quadro.de_dados(dados)


def test_ficheiro_ilegivel_e_recusado(tmp_path):
    ficheiro = tmp_path / "partido.json"
    ficheiro.write_text("{nao e json", encoding="utf-8")
    with pytest.raises(ErroQuadro):
        Quadro.carregar(ficheiro)
