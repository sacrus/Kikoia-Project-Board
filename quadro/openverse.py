"""Pesquisa de imagens no Openverse (openverse.org).

As credenciais ficam cifradas neste computador (quadro/segredos_app.py), fora do repositório.
Cada imagem traz autor, licença e ligação à origem, que a interface tem de mostrar.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from quadro import segredos_app

BASE = "https://api.openverse.org/v1/"
TEMPO_LIMITE_S = 15
LIMITE_MINIATURA_BYTES = 300 * 1024
LIMITE_IMAGEM_BYTES = 10 * 1024 * 1024
NOME_FICHEIRO = "openverse.json"

_token: dict = {"valor": None, "expira": 0.0}

MENSAGENS = {
    "openverse.nao_configurado": "A pesquisa de imagens ainda não está configurada neste computador.",
    "openverse.sem_ligacao": "Não foi possível ligar ao Openverse. Verifique a ligação à internet.",
    "openverse.recusado": "O Openverse recusou o pedido. Tente outra vez mais tarde.",
    "openverse.sem_token": "Não foi possível obter autorização do Openverse.",
    "openverse.imagem_grande": "Esta imagem é demasiado grande para o Quadro.",
}


class ErroOpenverse(RuntimeError):
    """A mensagem é uma chave de MENSAGENS."""


@dataclass(frozen=True)
class Imagem:
    id: str
    titulo: str
    autor: str
    licenca: str
    url: str
    miniatura: str
    pagina: str


def pasta(base: Path | None = None) -> Path:
    if base is not None:
        return base
    raiz = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(raiz) / "Kikoia" / "Quadro"


def credenciais(base: Path | None = None) -> tuple[str, str] | None:
    """O par identificador/segredo guardado cifrado neste computador (ver segredos_app). Senão None."""
    identificador = segredos_app.obter("openverse_client_id", base)
    segredo = segredos_app.obter("openverse_client_secret", base)
    if identificador and segredo:
        return identificador, segredo
    return None


AGENTE = "KikoiaQuadro/1.0 (+https://github.com/sacrus/Kikoia-Project-Board)"


def _pedido(url: str, dados: dict | None = None, cabecalhos: dict | None = None) -> dict:
    corpo = urllib.parse.urlencode(dados).encode("utf-8") if dados is not None else None
    pedido = urllib.request.Request(url, data=corpo, headers={"User-Agent": AGENTE, **(cabecalhos or {})})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE_S) as resposta:
            resultado = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        raise ErroOpenverse("openverse.recusado") from erro
    except (OSError, ValueError) as erro:
        raise ErroOpenverse("openverse.sem_ligacao") from erro
    if not isinstance(resultado, dict):
        raise ErroOpenverse("openverse.recusado")
    return resultado


def token(credencial: tuple[str, str]) -> str:
    """Token de acesso, reutilizado enquanto for válido (o Openverse dá cerca de 12 horas)."""
    agora = time.time()
    if _token["valor"] and agora < _token["expira"] - 60:
        return _token["valor"]
    identificador, segredo = credencial
    dados = _pedido(
        BASE + "auth_tokens/token/",
        {"grant_type": "client_credentials", "client_id": identificador, "client_secret": segredo},
    )
    valor = dados.get("access_token")
    if not isinstance(valor, str) or not valor:
        raise ErroOpenverse("openverse.sem_token")
    _token.update(valor=valor, expira=agora + int(dados.get("expires_in", 3600)))
    return valor


def pesquisar(termo: str, credencial: tuple[str, str], limite: int = 20) -> list[Imagem]:
    return pesquisar_pagina(termo, credencial, pagina=1, limite=limite)[0]


def pesquisar_pagina(termo: str, credencial: tuple[str, str], pagina: int = 1, limite: int = 20) -> tuple[list[Imagem], int]:
    """Uma página de resultados e o total de páginas. Só entram resultados com miniatura,
    porque sem ela a lista mostraria um texto sem imagem."""
    termo = termo.strip()
    if not termo:
        return [], 0
    consulta = urllib.parse.urlencode({"q": termo, "page_size": max(1, min(limite, 20)), "page": max(1, pagina)})
    dados = _pedido(BASE + "images/?" + consulta, cabecalhos={"Authorization": "Bearer " + token(credencial)})
    try:
        total = int(dados.get("page_count") or 0)
    except (TypeError, ValueError):
        total = 0
    resultados = []
    for item in dados.get("results", []):
        if not isinstance(item, dict) or not item.get("url") or not item.get("thumbnail"):
            continue
        licenca = f"{item.get('license', '')} {item.get('license_version', '')}".strip().upper()
        resultados.append(
            Imagem(
                id=str(item.get("id", "")),
                titulo=str(item.get("title") or "Sem título"),
                autor=str(item.get("creator") or "Autor desconhecido"),
                licenca=licenca or "licença não indicada",
                url=str(item["url"]),
                miniatura=str(item.get("thumbnail") or ""),
                pagina=str(item.get("foreign_landing_url") or ""),
            )
        )
    return resultados, total


def descarregar(url: str, limite: int = LIMITE_IMAGEM_BYTES) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE_S) as resposta:
            dados = resposta.read(limite + 1)
    except (OSError, ValueError) as erro:
        raise ErroOpenverse("openverse.sem_ligacao") from erro
    if len(dados) > limite:
        raise ErroOpenverse("openverse.imagem_grande")
    return dados


def mensagem(erro: BaseException) -> str:
    return MENSAGENS.get(str(erro), "Ocorreu um erro na pesquisa de imagens.")
