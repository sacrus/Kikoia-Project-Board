"""Lista de contactos do correio. É só uma comodidade para escrever: não concede permissões de envio."""

from __future__ import annotations

import json
import re
from pathlib import Path

from quadro.correio import contas
from quadro.correio.modelo import ErroCorreio

NOME_FICHEIRO = "contactos.json"
_ENDERECO = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")


def caminho(base: Path | None = None) -> Path:
    return contas.pasta(base) / NOME_FICHEIRO


ICONES = ("pessoa", "estrela", "coracao", "sol", "casa", "bola", "livro", "carro", "flor", "peixe")
MAX_FOTO_CHARS = 120_000  # ~90 KB de imagem: fotos pequenas, para o ficheiro de contactos não crescer


def carregar(base: Path | None = None) -> list[dict]:
    try:
        dados = json.loads(caminho(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(dados, list):
        return []
    validos = []
    for item in dados:
        if isinstance(item, dict) and isinstance(item.get("endereco"), str) and _ENDERECO.fullmatch(item["endereco"]):
            validos.append({
                "nome": str(item.get("nome") or item["endereco"]),
                "endereco": item["endereco"],
                "icone": item["icone"] if item.get("icone") in ICONES else "pessoa",
                "foto": item.get("foto") if isinstance(item.get("foto"), str) else None,
            })
    return sorted(validos, key=lambda c: c["nome"].lower())


def enderecos(base: Path | None = None) -> list[str]:
    return [c["endereco"] for c in carregar(base)]


def _gravar(lista: list[dict], base: Path | None) -> None:
    destino = caminho(base)
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(json.dumps(lista, ensure_ascii=False), encoding="utf-8")
    temporario.replace(destino)


def acrescentar(nome: str, endereco: str, base: Path | None = None, icone: str = "pessoa", foto: str | None = None) -> list[dict]:
    """Acrescenta ou atualiza um contacto. A foto (PNG em base64, pequena) é opcional; sem ela usa-se o ícone."""
    endereco = endereco.strip().lower()
    if not _ENDERECO.fullmatch(endereco):
        raise ErroCorreio("correio.entrada_invalida")
    if foto is not None and len(foto) > MAX_FOTO_CHARS:
        raise ErroCorreio("correio.foto_grande")
    atuais = [c for c in carregar(base) if c["endereco"] != endereco]
    atuais.append({
        "nome": nome.strip() or endereco,
        "endereco": endereco,
        "icone": icone if icone in ICONES else "pessoa",
        "foto": foto,
    })
    atuais.sort(key=lambda c: c["nome"].lower())
    _gravar(atuais, base)
    return atuais


def remover(endereco: str, base: Path | None = None) -> list[dict]:
    atuais = [c for c in carregar(base) if c["endereco"] != endereco.strip().lower()]
    _gravar(atuais, base)
    return atuais
