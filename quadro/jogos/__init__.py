"""Jogos educativos nativos integrados diretamente no Quadro Interativo Kikoia."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def abrir_jogo_integrado(modulo: str, parent: QWidget | None = None) -> None:
    """Abre um jogo integrado pelo seu identificador de módulo."""
    if modulo == "caminho_letras":
        from quadro.jogos.caminho_letras import DialogoCaminhoLetras

        dialogo = DialogoCaminhoLetras(parent)
        dialogo.showFullScreen()
        dialogo.exec()
        return
    raise ValueError(f"Jogo integrado desconhecido: {modulo}")
