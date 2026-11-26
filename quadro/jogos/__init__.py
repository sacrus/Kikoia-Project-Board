"""Jogos educativos nativos integrados diretamente no Quadro Interativo Kikoia."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def abrir_jogo_integrado(modulo: str, parent: QWidget | None = None) -> None:
    """Abre um jogo integrado pelo seu identificador de módulo ocupando toda a área útil."""
    if modulo == "caminho_letras":
        from quadro.jogos.caminho_letras import DialogoCaminhoLetras

        dialogo = DialogoCaminhoLetras(parent)
        dialogo.iniciar_ecra_completo()
        dialogo.exec()
        return
    if modulo == "dedos_musicais":
        from quadro.jogos.dedos_musicais import DialogoDedosMusicais

        dialogo = DialogoDedosMusicais(parent)
        dialogo.iniciar_ecra_completo()
        dialogo.exec()
        return
    raise ValueError(f"Jogo integrado desconhecido: {modulo}")
