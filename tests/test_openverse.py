import json
import sys

import pytest
from PySide6.QtWidgets import QApplication

from quadro import janela as janela_modulo
from quadro import openverse, segredos_app
from quadro.correio import oauth
from quadro.correio import supervisor as supervisor_correio
from quadro.janela_imagens import DialogoPesquisaImagens
from quadro.modelo import Quadro

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI só existe no Windows")


@pytest.fixture(autouse=True)
def token_limpo(monkeypatch):
    monkeypatch.setitem(openverse._token, "valor", None)
    monkeypatch.setitem(openverse._token, "expira", 0.0)


@windows_only
def test_credenciais_lidas_do_ficheiro_cifrado(tmp_path):
    segredos_app.gravar({"openverse_client_id": "abc", "openverse_client_secret": "segredo-real"}, tmp_path)
    assert openverse.credenciais(tmp_path) == ("abc", "segredo-real")


@windows_only
def test_sem_segredo_nao_ha_credenciais(tmp_path):
    segredos_app.gravar({"openverse_client_id": "abc"}, tmp_path)
    assert openverse.credenciais(tmp_path) is None


def test_sem_ficheiro_nao_ha_credenciais(tmp_path):
    assert openverse.credenciais(tmp_path) is None


@windows_only
def test_ficheiro_cifrado_nao_contem_o_segredo_em_claro(tmp_path):
    segredos_app.gravar({"openverse_client_secret": "segredo-visivel-123"}, tmp_path)
    assert b"segredo-visivel-123" not in (tmp_path / segredos_app.NOME_FICHEIRO).read_bytes()


@windows_only
def test_migracao_passa_os_ficheiros_antigos_para_o_cifrado_e_apaga_os_originais(tmp_path):
    antigo = {"client_id": "abc", "client_secret": "segredo-antigo"}
    (tmp_path / segredos_app.LEGADO_OPENVERSE).write_text(json.dumps(antigo), encoding="utf-8")
    (tmp_path / segredos_app.LEGADO_GOOGLE).write_text(json.dumps({"secreto": "google-antigo"}), encoding="utf-8")
    migrados = segredos_app.migrar(tmp_path)
    assert set(migrados) == {"openverse_client_id", "openverse_client_secret", "google_client_secret"}
    assert openverse.credenciais(tmp_path) == ("abc", "segredo-antigo")
    assert not (tmp_path / segredos_app.LEGADO_OPENVERSE).exists()
    assert not (tmp_path / segredos_app.LEGADO_GOOGLE).exists()


def test_codigo_nao_traz_identificadores_nem_segredos():
    assert oauth.CLIENTE_GOOGLE == ""
    assert oauth.CLIENTE_MICROSOFT == ""


def test_chave_desconhecida_e_recusada(tmp_path):
    with pytest.raises(KeyError):
        segredos_app.gravar({"chave_inventada": "x"}, tmp_path)


def test_token_e_reutilizado_enquanto_for_valido(monkeypatch):
    pedidos = []

    def pedido(url, dados=None, cabecalhos=None):
        pedidos.append(url)
        return {"access_token": "token-1", "expires_in": 43200}

    monkeypatch.setattr(openverse, "_pedido", pedido)
    assert openverse.token(("abc", "s")) == "token-1"
    assert openverse.token(("abc", "s")) == "token-1"
    assert len(pedidos) == 1


def test_pesquisa_devolve_autor_licenca_e_origem(monkeypatch):
    monkeypatch.setattr(openverse, "token", lambda credencial: "token-1")
    monkeypatch.setattr(openverse, "_pedido", lambda url, dados=None, cabecalhos=None: {
        "results": [{
            "id": "9", "title": "Gato", "creator": "Ana", "license": "by-nc-nd", "license_version": "2.0",
            "url": "https://ex.org/gato.jpg", "thumbnail": "https://ex.org/t.jpg",
            "foreign_landing_url": "https://ex.org/pagina",
        }]
    })
    resultado = openverse.pesquisar("gato", ("abc", "s"))
    assert len(resultado) == 1
    assert resultado[0].autor == "Ana"
    assert resultado[0].licenca == "BY-NC-ND 2.0"
    assert resultado[0].pagina == "https://ex.org/pagina"


def test_pesquisa_vazia_nao_faz_pedidos(monkeypatch):
    monkeypatch.setattr(openverse, "_pedido", lambda *a, **k: pytest.fail("não devia pedir nada"))
    assert openverse.pesquisar("   ", ("abc", "s")) == []


def test_imagem_demasiado_grande_e_recusada(monkeypatch):
    class Resposta:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, n):
            return b"x" * n

    monkeypatch.setattr(openverse.urllib.request, "urlopen", lambda *a, **k: Resposta())
    with pytest.raises(openverse.ErroOpenverse) as erro:
        openverse.descarregar("https://ex.org/g.jpg", limite=10)
    assert str(erro.value) == "openverse.imagem_grande"


def test_sem_credenciais_a_janela_nao_abre_a_pesquisa(monkeypatch):
    QApplication.instance() or QApplication([])
    abertos = []
    monkeypatch.setattr(openverse, "credenciais", lambda *a, **k: None)
    monkeypatch.setattr(janela_modulo.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(janela_modulo, "DialogoPesquisaImagens", lambda *a, **k: abertos.append(a))
    janela = janela_modulo.JanelaQuadro(Quadro())
    try:
        janela.pesquisar_imagens()
        assert abertos == []
    finally:
        janela.close()


def test_com_supervisor_so_abre_com_a_palavra_passe(monkeypatch):
    QApplication.instance() or QApplication([])
    abertos = []
    monkeypatch.setattr(openverse, "credenciais", lambda *a, **k: ("abc", "s"))
    monkeypatch.setattr(supervisor_correio, "existe", lambda *a, **k: True)
    monkeypatch.setattr(janela_modulo, "verificar_supervisor", lambda pai: False)
    monkeypatch.setattr(janela_modulo, "DialogoPesquisaImagens", lambda *a, **k: abertos.append(a))
    janela = janela_modulo.JanelaQuadro(Quadro())
    try:
        janela.pesquisar_imagens()
        assert abertos == []
    finally:
        janela.close()


def test_pagina_seguinte_pede_a_pagina_certa_e_devolve_o_total(monkeypatch):
    pedidos = []

    def pedido(url, dados=None, cabecalhos=None):
        pedidos.append(url)
        return {"page_count": 7, "results": []}

    monkeypatch.setattr(openverse, "token", lambda credencial: "token-1")
    monkeypatch.setattr(openverse, "_pedido", pedido)
    resultados, total = openverse.pesquisar_pagina("cão", ("abc", "s"), pagina=3)
    assert total == 7
    assert "page=3" in pedidos[0]


def test_resultados_sem_miniatura_nao_entram_na_lista(monkeypatch):
    monkeypatch.setattr(openverse, "token", lambda credencial: "token-1")
    monkeypatch.setattr(openverse, "_pedido", lambda url, dados=None, cabecalhos=None: {
        "page_count": 1,
        "results": [
            {"id": "1", "title": "Com imagem", "creator": "A", "license": "by", "license_version": "4.0",
             "url": "https://ex.org/1.jpg", "thumbnail": "https://ex.org/t1.jpg", "foreign_landing_url": ""},
            {"id": "2", "title": "Só texto", "creator": "B", "license": "by", "license_version": "4.0",
             "url": "https://ex.org/2.jpg", "thumbnail": None, "foreign_landing_url": ""},
        ],
    })
    resultados, _ = openverse.pesquisar_pagina("cão", ("abc", "s"))
    assert [r.titulo for r in resultados] == ["Com imagem"]


def test_dialogo_de_pesquisa_mostra_o_campo_e_o_botao_de_usar():
    QApplication.instance() or QApplication([])
    dialogo = DialogoPesquisaImagens(None, ("abc", "s"), lambda imagem, origem: None)
    try:
        assert not dialogo._usar.isEnabled()
        assert dialogo._campo.placeholderText()
    finally:
        dialogo.close()
