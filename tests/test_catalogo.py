import hashlib
import json
from pathlib import Path

import pytest

from quadro import catalogo
from quadro.catalogo import ErroCatalogo

RAIZ = Path(__file__).resolve().parent.parent / "Resources"
CONTEUDO = b"exe de teste"
SHA = hashlib.sha256(CONTEUDO).hexdigest()


def _base(tmp_path, instalacao=None, **campos):
    base = tmp_path / "Resources"
    pasta = base / "Games" / "demo"
    (pasta / "screenshots").mkdir(parents=True)
    (pasta / "screenshots" / "thumb.png").write_bytes(b"png")
    dados = {
        "id": "demo",
        "nome": "Demo",
        "descricao": "Um jogo de teste.",
        "autores": ["Autor"],
        "copyright": "Copyright 2026 Autor",
        "licenca": "MIT",
        "licenca_url": "https://example.org/licenca",
        "site": "https://example.org",
        "fonte_oficial": "https://example.org/download",
        "screenshots": ["screenshots/thumb.png"],
        "instalacao": instalacao
        if instalacao is not None
        else {
            "windows": {
                "tipo": "executavel",
                "fonte": "https://example.org/demo.exe",
                "ficheiro": "demo.exe",
                "sha256": SHA,
            }
        },
    }
    dados.update(campos)
    (pasta / "game.json").write_text(json.dumps(dados), encoding="utf-8")
    (base / "index.json").write_text(
        json.dumps({"versao": 1, "jogos": [{"id": "demo", "pasta": "Games/demo", "nome": "Demo"}]}),
        encoding="utf-8",
    )
    return base


def _jogo(base):
    resumo = catalogo.carregar_indice(str(base))[0]
    return catalogo.carregar_jogo(resumo, str(base))


def _baixar_de(conteudo):
    def baixar(url, destino, progresso):
        destino.write_bytes(conteudo)

    return baixar


def test_indice_e_jogo_validos(tmp_path):
    jogo = _jogo(_base(tmp_path))
    assert jogo.nome == "Demo"
    assert jogo.instalacao_windows.sha256 == SHA
    assert jogo.screenshots == ["screenshots/thumb.png"]


def test_recursos_do_repositorio_sao_validos():
    resumos = catalogo.carregar_indice(str(RAIZ))
    assert len(resumos) >= 2
    for resumo in resumos:
        catalogo.carregar_jogo(resumo, str(RAIZ))


def test_id_invalido_no_indice_e_recusado(tmp_path):
    base = _base(tmp_path)
    (base / "index.json").write_text(
        json.dumps({"versao": 1, "jogos": [{"id": "../x", "pasta": "Games/demo", "nome": "X"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ErroCatalogo):
        catalogo.carregar_indice(str(base))


def test_pasta_do_indice_que_sai_da_raiz_e_recusada(tmp_path):
    base = _base(tmp_path)
    (base / "index.json").write_text(
        json.dumps({"versao": 1, "jogos": [{"id": "demo", "pasta": "../fora", "nome": "X"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ErroCatalogo):
        catalogo.carregar_indice(str(base))


def test_captura_de_ecra_que_sai_da_pasta_e_recusada(tmp_path):
    with pytest.raises(ErroCatalogo):
        _jogo(_base(tmp_path, screenshots=["../segredo.png"]))


@pytest.mark.parametrize(
    "instalacao",
    [
        {"windows": {"tipo": "executavel", "fonte": "http://example.org/x.exe", "ficheiro": "x.exe", "sha256": SHA}},
        {"windows": {"tipo": "executavel", "fonte": "https://example.org/x.exe", "ficheiro": "x.exe", "sha256": "xyz"}},
        {"windows": {"tipo": "executavel", "fonte": "https://example.org/x.exe", "ficheiro": "../x.exe", "sha256": SHA}},
        {"windows": {"tipo": "script", "fonte": "https://example.org/x.exe", "ficheiro": "x.exe", "sha256": SHA}},
        {"windows": {"tipo": "executavel", "fonte": "https://example.org/x.exe", "ficheiro": "x.exe"}},
    ],
)
def test_instalacao_invalida_e_recusada(tmp_path, instalacao):
    with pytest.raises(ErroCatalogo):
        _jogo(_base(tmp_path, instalacao=instalacao))


def test_transferencia_com_sha_certo_guarda_o_jogo(tmp_path):
    jogo = _jogo(_base(tmp_path))
    pasta = tmp_path / "jogos"
    caminho = catalogo.transferir(jogo, pasta=pasta, baixar=_baixar_de(CONTEUDO))
    assert caminho.read_bytes() == CONTEUDO
    assert catalogo.instalado(jogo, pasta) == caminho


def test_transferencia_com_sha_errado_nao_guarda_nada(tmp_path):
    jogo = _jogo(_base(tmp_path))
    pasta = tmp_path / "jogos"
    with pytest.raises(ErroCatalogo) as erro:
        catalogo.transferir(jogo, pasta=pasta, baixar=_baixar_de(b"outro conteudo"))
    assert str(erro.value) == "catalogo.verificacao_falhou"
    assert catalogo.instalado(jogo, pasta) is None
    assert not (pasta / "demo" / "demo.exe").exists()


def test_jogo_sem_windows_nao_e_transferido(tmp_path):
    jogo = _jogo(_base(tmp_path, instalacao={}))
    with pytest.raises(ErroCatalogo) as erro:
        catalogo.transferir(jogo, pasta=tmp_path / "jogos", baixar=_baixar_de(CONTEUDO))
    assert str(erro.value) == "catalogo.sem_windows"


def test_miniatura_fica_em_cache(tmp_path):
    base = _base(tmp_path)
    jogo = _jogo(base)
    cache = tmp_path / "cache"
    caminho = catalogo.miniatura(jogo, cache, base=str(base))
    assert caminho.read_bytes() == b"png"
    (base / "Games" / "demo" / "screenshots" / "thumb.png").unlink()
    assert catalogo.miniatura(jogo, cache, base=str(base)) == caminho


def test_controlos_validos_e_sinonimos(tmp_path):
    jogo = _jogo(
        _base(
            tmp_path,
            controlos={
                "toque": "obrigatorio",
                "caneta": "aconselhado",
                "rato": "suportado",
            },
        )
    )
    assert jogo.controlos == {
        "toque": "necessario",
        "caneta": "aconselhado",
        "rato": "suportado",
    }


@pytest.mark.parametrize(
    "controlos",
    [
        "rato",
        {"comando": "aconselhado"},
        {"rato": "opcional"},
    ],
)
def test_controlos_invalidos_sao_recusados(tmp_path, controlos):
    with pytest.raises(ErroCatalogo):
        _jogo(_base(tmp_path, controlos=controlos))
