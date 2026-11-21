"""Ponte do Quadro: deixa o teclado virtual e a app Android ler o menu e executar ações.

- Liga-se só em 127.0.0.1 (não é acessível pela rede).
- Cada pedido é uma linha JSON com o token gravado em `ponte.json` (na pasta do utilizador).
  Sem o token, o pedido é recusado.
- Pedidos:
    {"token": ..., "pedido": "catalogo"}          -> catálogo, versão e estado atual
    {"token": ..., "pedido": "estado"}            -> estado atual
    {"token": ..., "pedido": "acao", "id": "..."} -> executa a ação do catálogo
- As ações são executadas na thread da janela, como os cliques do utilizador.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
from pathlib import Path

import base64

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject
from PySide6.QtNetwork import QHostAddress, QTcpServer

from quadro import acoes, icones_acoes

VERSAO_PONTE = 1
LIMITE_LINHA = 4096
NOME_FICHEIRO = "ponte.json"
TAMANHO_ICONE_ENVIADO = 64


def imagens_dos_icones() -> dict[str, str]:
    """PNG (em base64) de cada ícone usado pelo catálogo. O teclado mostra estas imagens nas teclas."""
    resultado: dict[str, str] = {}
    for nome in icones_acoes.nomes_necessarios([a.icone for a in acoes.ACOES]):
        try:
            pixmap = icones_acoes.pixmap_da_acao(nome, TAMANHO_ICONE_ENVIADO)
        except KeyError:
            continue
        armazenamento = QByteArray()
        buffer = QBuffer(armazenamento)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        resultado[nome] = base64.b64encode(bytes(armazenamento)).decode("ascii")
    return resultado


def pasta(base: Path | None = None) -> Path:
    if base is not None:
        return base
    raiz = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(raiz) / "Kikoia" / "Quadro"


def _erro(codigo: str) -> dict:
    return {"ok": False, "erro": codigo}


class PonteQuadro(QObject):
    def __init__(self, janela, base: Path | None = None) -> None:
        super().__init__(janela)
        self._janela = janela
        self._base = base
        self._token = secrets.token_hex(16)
        self._servidor = QTcpServer(self)
        self._buffers: dict = {}

    @property
    def token(self) -> str:
        return self._token

    def iniciar(self) -> bool:
        if not self._servidor.listen(QHostAddress.SpecialAddress.LocalHost, 0):
            return False
        self._servidor.newConnection.connect(self._nova_ligacao)
        self._gravar_ficheiro()
        return True

    def parar(self) -> None:
        self._servidor.close()
        (pasta(self._base) / NOME_FICHEIRO).unlink(missing_ok=True)

    def _gravar_ficheiro(self) -> None:
        destino = pasta(self._base)
        destino.mkdir(parents=True, exist_ok=True)
        temporario = destino / (NOME_FICHEIRO + ".tmp")
        temporario.write_text(
            json.dumps({"porta": self._servidor.serverPort(), "token": self._token, "versao": VERSAO_PONTE, "pid": os.getpid()}),
            encoding="utf-8",
        )
        os.replace(temporario, destino / NOME_FICHEIRO)

    # --- ligação -------------------------------------------------------------------

    def _nova_ligacao(self) -> None:
        ligacao = self._servidor.nextPendingConnection()
        self._buffers[ligacao] = b""
        ligacao.readyRead.connect(lambda l=ligacao: self._ler(l))
        ligacao.disconnected.connect(lambda l=ligacao: self._buffers.pop(l, None))

    def _ler(self, ligacao) -> None:
        dados = self._buffers.get(ligacao, b"") + bytes(ligacao.readAll())
        while b"\n" in dados:
            linha, dados = dados.split(b"\n", 1)
            resposta = self.tratar(linha)
            ligacao.write((json.dumps(resposta, ensure_ascii=False) + "\n").encode("utf-8"))
        if len(dados) > LIMITE_LINHA:
            ligacao.disconnectFromHost()
            dados = b""
        self._buffers[ligacao] = dados

    # --- pedidos -------------------------------------------------------------------

    def tratar(self, linha: bytes) -> dict:
        if len(linha) > LIMITE_LINHA:
            return _erro("pedido_demasiado_grande")
        try:
            pedido = json.loads(linha.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _erro("pedido_invalido")
        if not isinstance(pedido, dict):
            return _erro("pedido_invalido")
        token = pedido.get("token")
        if not isinstance(token, str) or not hmac.compare_digest(token, self._token):
            return _erro("nao_autorizado")
        tipo = pedido.get("pedido")
        if tipo == "catalogo":
            imagens = imagens_dos_icones()
            return {
                "ok": True,
                "versao": VERSAO_PONTE,
                "catalogo": acoes.catalogo_dados(),
                "icones": imagens,
                "coloridos": sorted(n for n in imagens if icones_acoes.e_colorido(n)),
                "estado": self.estado(),
            }
        if tipo == "estado":
            return {"ok": True, "estado": self.estado()}
        if tipo == "menu":
            visivel = pedido.get("visivel")
            if not isinstance(visivel, bool):
                return _erro("visivel_invalido")
            self._janela.controlo_menu_teclado(visivel)
            return {"ok": True, "estado": self.estado()}
        if tipo == "acao":
            identificador = pedido.get("id")
            if not isinstance(identificador, str):
                return _erro("acao_invalida")
            try:
                executada = self._janela.executar_acao(identificador)
            except KeyError:
                return _erro("acao_desconhecida")
            return {"ok": bool(executada), "estado": self.estado()}
        return _erro("pedido_desconhecido")

    def estado(self) -> dict:
        janela = self._janela
        return acoes.estado(
            ferramenta=janela.tela.ferramenta,
            tem_selecao=bool(janela.tela.selecao),
            pode_desfazer=janela.quadro.pode_desfazer(),
            pode_refazer=janela.quadro.pode_refazer(),
            correio_visivel=not janela.menu._correio.isHidden(),
            jogos_visivel=not janela.menu._jogos.isHidden(),
        )
