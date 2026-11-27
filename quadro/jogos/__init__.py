"""Jogos educativos nativos integrados diretamente no Quadro Interativo Kikoia."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def abrir_jogo_integrado(modulo: str, parent: QWidget | None = None) -> None:
    """Abre um jogo integrado pelo seu identificador de módulo ocupando toda a área útil."""
    if modulo == "caminho_letras":
        from quadro.jogos.caminho_letras import DialogoCaminhoLetras

        dialogo = DialogoCaminhoLetras(parent)
    elif modulo == "dedos_musicais":
        from quadro.jogos.dedos_musicais import DialogoDedosMusicais

        dialogo = DialogoDedosMusicais(parent)
    elif modulo == "labirintos":
        from quadro.jogos.labirintos import DialogoLabirintos

        dialogo = DialogoLabirintos(parent)
    else:
        raise ValueError(f"Jogo integrado desconhecido: {modulo}")

    try:
        dialogo.iniciar_ecra_completo()
        dialogo.exec()
    finally:
        if hasattr(dialogo, "_parar_jogo"):
            dialogo._parar_jogo()
        dialogo.deleteLater()
