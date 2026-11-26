"""Sistema de idiomas do Quadro Interativo (pt-PT, en, es, fr) com sincronização com o Teclado Kikoia.

Os catálogos ficam em `data/idiomas/<codigo>.json`. Se uma chave faltar num idioma,
usa automaticamente `pt-PT`. O idioma escolhido é guardado em
`%LOCALAPPDATA%\\Kikoia\\idioma_partilhado.json` (Windows) / `~/.local/share/Kikoia/idioma_partilhado.json` (Linux)
para se manter sincronizado entre o Quadro e o Teclado.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

IDIOMA_PADRAO = "pt-PT"
IDIOMAS = {
    "pt-PT": "Português (Portugal)",
    "en": "English",
    "es": "Español",
    "fr": "Français",
}

_NOME_FICHEIRO = "idioma_partilhado.json"
_catalogos: dict[str, dict[str, str]] = {}
_atual = IDIOMA_PADRAO


def _pasta_idiomas() -> Path:
    bases = [Path(__file__).resolve().parent.parent]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases.insert(0, Path(meipass))
        bases.insert(0, Path(sys.executable).resolve().parent)
    for base in bases:
        cand = base / "data" / "idiomas"
        if cand.is_dir():
            return cand
    return bases[0] / "data" / "idiomas"


def caminho_partilhado(base: Path | None = None) -> Path:
    from quadro.paths import pasta_kikoia

    return pasta_kikoia(base) / _NOME_FICHEIRO


def idioma_valido(codigo: object) -> str:
    return codigo if isinstance(codigo, str) and codigo in IDIOMAS else IDIOMA_PADRAO


def ler_partilhado(base: Path | None = None) -> dict | None:
    ficheiro = caminho_partilhado(base)
    try:
        dados = json.loads(ficheiro.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict) or dados.get("idioma") not in IDIOMAS:
        return None
    return {
        "idioma": dados["idioma"],
        "atualizado_em": float(dados.get("atualizado_em", 0.0)),
    }


def guardar_partilhado(codigo: str, base: Path | None = None) -> float:
    codigo = idioma_valido(codigo)
    destino = caminho_partilhado(base)
    destino.parent.mkdir(parents=True, exist_ok=True)
    agora = time.time()
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"idioma": codigo, "atualizado_em": agora}, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, destino)
    return agora


def carregar_partilhado(base: Path | None = None) -> str:
    """Atualiza o idioma ativo a partir do ficheiro partilhado (se existir)."""
    global _atual
    dados = ler_partilhado(base)
    if dados is not None:
        _atual = idioma_valido(dados["idioma"])
    return _atual


def definir(codigo: object, guardar: bool = True, base: Path | None = None) -> str:
    global _atual
    _atual = idioma_valido(codigo)
    if guardar:
        try:
            guardar_partilhado(_atual, base)
        except OSError:
            pass
    return _atual


def atual() -> str:
    return _atual


def _carregar(codigo: str) -> dict[str, str]:
    if codigo not in _catalogos:
        caminho = _pasta_idiomas() / f"{codigo}.json"
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            dados = {}
        _catalogos[codigo] = {k: v for k, v in dados.items() if isinstance(v, str)}
    return _catalogos[codigo]


def t(chave: str, **valores: object) -> str:
    """Devolve o texto traduzido no idioma atual (com fallback para pt-PT)."""
    texto = _carregar(_atual).get(chave)
    if texto is None:
        texto = _carregar(IDIOMA_PADRAO).get(chave, chave)
    return texto.format(**valores) if valores else texto
