import shutil
import sys

import pytest

from quadro.correio import contas, supervisor
from quadro.correio.modelo import conta_cpanel

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI só existe no Windows")


@pytest.fixture
def dados(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(supervisor, "ITERACOES", 1000)
    return tmp_path


def test_varias_contas_ficam_guardadas_e_cada_uma_tem_a_sua_palavra_passe(dados):
    contas.guardar(conta_cpanel("b@portugalsat.com"), "segredo-b")
    contas.guardar(conta_cpanel("a@portugalsat.com"), "segredo-a")
    assert contas.listar_enderecos() == ["a@portugalsat.com", "b@portugalsat.com"]
    conta, senha = contas.carregar(endereco="b@portugalsat.com")
    assert conta.endereco == "b@portugalsat.com"
    assert senha == "segredo-b"


def test_apagar_uma_conta_nao_apaga_as_outras(dados):
    contas.guardar(conta_cpanel("a@portugalsat.com"), "segredo-a")
    contas.guardar(conta_cpanel("b@portugalsat.com"), "segredo-b")
    contas.apagar(endereco="a@portugalsat.com")
    assert contas.listar_enderecos() == ["b@portugalsat.com"]
    assert contas.carregar(endereco="a@portugalsat.com") is None


def test_conta_da_versao_anterior_passa_para_a_pasta_de_contas(dados):
    contas.guardar(conta_cpanel("antiga@portugalsat.com"), "segredo")
    pasta = contas.pasta()
    destino = pasta / "contas" / "antiga@portugalsat.com"
    shutil.move(str(destino / "conta.json"), str(pasta / "conta.json"))
    shutil.move(str(destino / "senha.bin"), str(pasta / "senha.bin"))
    destino.rmdir()
    assert contas.listar_enderecos() == ["antiga@portugalsat.com"]
    assert not (pasta / "conta.json").exists()
    conta, senha = contas.carregar()
    assert senha == "segredo"
