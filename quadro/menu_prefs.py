"""Quais das bolhas opcionais aparecem no menu do Quadro («Adicionar ao Menu» nas Definições)."""

from __future__ import annotations

import json
import os
from pathlib import Path

PREFERENCIAS_OMISSAO = {"jogos": True}


def _ficheiro(base: Path | None = None) -> Path:
    from quadro.paths import pasta_quadro

    destino = pasta_quadro(base)
    destino.mkdir(parents=True, exist_ok=True)
    return destino / "menu.json"


def ler(base: Path | None = None) -> dict:
    try:
        dados = json.loads(_ficheiro(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    return {chave: dados[chave] if type(dados.get(chave)) is type(valor) else valor for chave, valor in PREFERENCIAS_OMISSAO.items()}


def guardar(valores: dict, base: Path | None = None) -> None:
    caminho = _ficheiro(base)
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps({**ler(base), **valores}, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, caminho)
