"""Segredos e identificadores das APIs (Google, Microsoft, Openverse), guardados cifrados neste computador.

Ficheiro: %LOCALAPPDATA%\\Kikoia\\Quadro\\segredos.bin, cifrado com a proteção do Windows (DPAPI),
ligado à conta do utilizador. Nada disto existe no código fonte nem no repositório: a versão pública
traz estes campos em branco, e cada instalação preenche os seus.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from quadro.correio import segredos

NOME_FICHEIRO = "segredos.bin"
CHAVES = (
    "google_client_id",
    "google_client_secret",
    "microsoft_client_id",
    "openverse_client_id",
    "openverse_client_secret",
)
# Ficheiros em texto simples de versões anteriores; são migrados e apagados no primeiro uso.
LEGADO_GOOGLE = "oauth_google.json"
LEGADO_OPENVERSE = "openverse.json"


def pasta(base: Path | None = None) -> Path:
    from quadro.paths import pasta_quadro

    destino = pasta_quadro(base)
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def ler(base: Path | None = None) -> dict[str, str]:
    """Todos os valores guardados. Sem ficheiro, ou se não for possível decifrar, devolve vazio."""
    caminho = pasta(base) / NOME_FICHEIRO
    try:
        cifrado = caminho.read_bytes()
    except OSError:
        return {}
    try:
        dados = json.loads(segredos.decifrar(cifrado))
    except Exception:
        return {}
    if not isinstance(dados, dict):
        return {}
    return {chave: valor for chave, valor in dados.items() if chave in CHAVES and isinstance(valor, str)}


def _ler_embutidos() -> dict[str, str]:
    """Lê chaves embutidas apenas em builds oficiais (módulo opcional, fora do Git)."""
    try:
        from quadro import _segredos_embutidos  # type: ignore[attr-defined]

        dados = _segredos_embutidos.ler()
    except Exception:
        return {}
    if not isinstance(dados, dict):
        return {}
    return {chave: valor.strip() for chave, valor in dados.items() if chave in CHAVES and isinstance(valor, str) and valor.strip()}


def obter(chave: str, base: Path | None = None) -> str | None:
    if chave not in CHAVES:
        raise KeyError(chave)
    valor = ler(base).get(chave, "").strip()
    if valor:
        return valor
    if base is None:
        embutido = _ler_embutidos().get(chave, "").strip()
        if embutido:
            return embutido
    return None


def gravar(valores: dict[str, str], base: Path | None = None) -> None:
    """Acrescenta ou altera valores, sem apagar os outros. Só aceita as chaves conhecidas."""
    desconhecidas = set(valores) - set(CHAVES)
    if desconhecidas:
        raise KeyError(sorted(desconhecidas)[0])
    atuais = ler(base)
    atuais.update({chave: valor.strip() for chave, valor in valores.items() if valor and valor.strip()})
    destino = pasta(base) / NOME_FICHEIRO
    temporario = destino.with_suffix(".tmp")
    temporario.write_bytes(segredos.cifrar(json.dumps(atuais, ensure_ascii=False)))
    os.replace(temporario, destino)


def migrar(base: Path | None = None) -> list[str]:
    """Passa os ficheiros em texto simples para o ficheiro cifrado e apaga-os. Devolve o que foi migrado."""
    origem = pasta(base)
    migrado: dict[str, str] = {}
    for nome, mapa in (
        (LEGADO_GOOGLE, {"secreto": "google_client_secret"}),
        (LEGADO_OPENVERSE, {"client_id": "openverse_client_id", "client_secret": "openverse_client_secret"}),
    ):
        caminho = origem / nome
        if not caminho.is_file():
            continue
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        for campo, chave in mapa.items():
            valor = dados.get(campo) if isinstance(dados, dict) else None
            if isinstance(valor, str) and valor.strip() and "COLA_AQUI" not in valor:
                migrado[chave] = valor
    if not migrado:
        return []
    gravar(migrado, base)
    for nome in (LEGADO_GOOGLE, LEGADO_OPENVERSE):
        (origem / nome).unlink(missing_ok=True)
    return sorted(migrado)
