import json
import time

from PySide6.QtNetwork import QTcpSocket
from PySide6.QtWidgets import QApplication

from quadro.janela import CARIMBO_TAMANHOS, CORES_ACAO, ESPESSURAS_CANETA, JanelaQuadro
from quadro.modelo import Quadro
from quadro.ponte import PonteQuadro


def _app():
    return QApplication.instance() or QApplication([])


def _ponte(tmp_path):
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    ponte = PonteQuadro(janela, base=tmp_path)
    return janela, ponte


def _pedido(ponte, **campos):
    return ponte.tratar(json.dumps({"token": ponte.token, **campos}).encode("utf-8"))


def test_pedido_sem_token_e_recusado(tmp_path):
    janela, ponte = _ponte(tmp_path)
    try:
        assert ponte.tratar(b'{"pedido": "catalogo"}') == {"ok": False, "erro": "nao_autorizado"}
        assert ponte.tratar(b'{"token": "errado", "pedido": "catalogo"}')["erro"] == "nao_autorizado"
    finally:
        janela.close()


def test_catalogo_e_estado_com_token(tmp_path):
    janela, ponte = _ponte(tmp_path)
    try:
        resposta = _pedido(ponte, pedido="catalogo")
        assert resposta["ok"] is True
        assert any(a["id"] == "carimbo.figura.sol" for a in resposta["catalogo"]["acoes"])
        assert resposta["estado"]["caneta"]["ativa"] is True
    finally:
        janela.close()


def test_acao_de_ferramenta_muda_a_ferramenta(tmp_path):
    janela, ponte = _ponte(tmp_path)
    try:
        resposta = _pedido(ponte, pedido="acao", id="balde")
        assert resposta["ok"] is True
        assert janela.tela.ferramenta == "balde"
        assert resposta["estado"]["balde"]["ativa"] is True
    finally:
        janela.close()


def test_acoes_de_figura_forma_e_tamanho(tmp_path):
    janela, ponte = _ponte(tmp_path)
    try:
        _pedido(ponte, pedido="acao", id="carimbo.figura.sol")
        assert janela.tela.carimbo == "sol"
        assert janela.tela.ferramenta == "carimbo"
        _pedido(ponte, pedido="acao", id="carimbo.tamanho.3")
        assert janela.tela.tamanho_carimbo == CARIMBO_TAMANHOS[2]
        _pedido(ponte, pedido="acao", id="caneta.tamanho.3")
        assert janela.tela.espessura == ESPESSURAS_CANETA[2]
        _pedido(ponte, pedido="acao", id="forma.elipse")
        assert janela.tela.forma == "elipse"
    finally:
        janela.close()


def test_acao_de_cor_define_a_cor_da_caneta(tmp_path):
    janela, ponte = _ponte(tmp_path)
    try:
        _pedido(ponte, pedido="acao", id="cor.azul")
        assert janela.tela.cor_caneta == CORES_ACAO["azul"]
        _pedido(ponte, pedido="acao", id="cor.automatica")
        assert janela.tela.cor_caneta is None
    finally:
        janela.close()


def test_desfazer_pela_ponte(tmp_path):
    janela, ponte = _ponte(tmp_path)
    try:
        janela.quadro.registar()
        janela.quadro.comecar_traco("#000000", 0.01, 0.1, 0.1)
        resposta = _pedido(ponte, pedido="acao", id="desfazer")
        assert janela.quadro.tracos == []
        assert resposta["estado"]["refazer"]["disponivel"] is True
    finally:
        janela.close()


def test_acao_desconhecida_e_pedido_invalido(tmp_path):
    janela, ponte = _ponte(tmp_path)
    try:
        assert _pedido(ponte, pedido="acao", id="nao-existe")["erro"] == "acao_desconhecida"
        assert _pedido(ponte, pedido="acao")["erro"] == "acao_invalida"
        assert _pedido(ponte, pedido="inventado")["erro"] == "pedido_desconhecido"
        assert ponte.tratar(b"isto nao e json")["erro"] == "pedido_invalido"
    finally:
        janela.close()


def test_ligacao_tcp_real_e_ficheiro_com_porta(tmp_path):
    janela, ponte = _ponte(tmp_path)
    try:
        assert ponte.iniciar()
        dados = json.loads((tmp_path / "ponte.json").read_text(encoding="utf-8"))
        assert dados["token"] == ponte.token
        cliente = QTcpSocket()
        cliente.connectToHost("127.0.0.1", dados["porta"])
        assert _esperar(lambda: cliente.state().name == "ConnectedState")
        pedido = {"token": dados["token"], "pedido": "acao", "id": "borracha"}
        cliente.write((json.dumps(pedido) + "\n").encode("utf-8"))
        recebidos = bytearray()
        assert _esperar(lambda: (recebidos.extend(bytes(cliente.readAll())) or b"\n" in recebidos))
        resposta = json.loads(bytes(recebidos).split(b"\n")[0])
        assert resposta["ok"] is True
        assert janela.tela.ferramenta == "borracha"
        cliente.disconnectFromHost()
        ponte.parar()
        assert not (tmp_path / "ponte.json").exists()
    finally:
        janela.close()


def _esperar(condicao, limite=5.0):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        QApplication.processEvents()
        if condicao():
            return True
        time.sleep(0.01)
    return False

