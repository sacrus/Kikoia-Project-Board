"""Palavra-passe de supervisor. Guardada só como hash PBKDF2, num ficheiro partilhado com o teclado."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

from quadro.correio.modelo import ErroCorreio

ITERACOES = 310_000
TAMANHO_MINIMO = 6
NOME_FICHEIRO = "supervisor.json"


def pasta_dados(base: Path | None = None) -> Path:
    if base is not None:
        return base
    raiz = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    pasta = Path(raiz) / "Kikoia"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho(pasta: Path | None = None) -> Path:
    return pasta_dados(pasta) / NOME_FICHEIRO


def _derivar(palavra: str, sal: bytes, iteracoes: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", palavra.encode("utf-8"), sal, iteracoes)


def _ler(pasta: Path | None) -> dict | None:
    try:
        dados = json.loads(caminho(pasta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def existe(pasta: Path | None = None) -> bool:
    return caminho(pasta).is_file()


def apagar(pasta: Path | None = None) -> None:
    caminho(pasta).unlink(missing_ok=True)


def verificar(palavra: str, pasta: Path | None = None) -> bool:
    dados = _ler(pasta)
    if dados is None:
        return False
    try:
        sal = bytes.fromhex(dados["sal"])
        esperado = bytes.fromhex(dados["hash"])
        iteracoes = int(dados["iteracoes"])
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(_derivar(palavra, sal, iteracoes), esperado)


def definir(palavra: str, pasta: Path | None = None, palavra_atual: str | None = None) -> None:
    """Cria a palavra-passe ou, se já existir, altera-a (exige a atual)."""
    if len(palavra) < TAMANHO_MINIMO:
        raise ErroCorreio("supervisor.palavra_curta")
    if existe(pasta) and not verificar(palavra_atual or "", pasta):
        raise ErroCorreio("supervisor.palavra_incorreta")
    sal = secrets.token_bytes(16)
    dados = {
        "versao": 1,
        "iteracoes": ITERACOES,
        "sal": sal.hex(),
        "hash": _derivar(palavra, sal, ITERACOES).hex(),
    }
    destino = caminho(pasta)
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados), encoding="utf-8")
    os.replace(temporario, destino)


def chave_integridade(pasta: Path | None = None) -> bytes | None:
    """Chave usada para assinar o ficheiro de regras. Muda sempre que a palavra-passe muda."""
    dados = _ler(pasta)
    if dados is None:
        return None
    try:
        return bytes.fromhex(dados["hash"])
    except (KeyError, TypeError, ValueError):
        return None
