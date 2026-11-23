"""Botão On/Off usado pelas janelas do Quadro (ex.: «Adicionar ao Menu»)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


def interruptor(texto: str, marcado: bool) -> QPushButton:
    """Botão On/Off pequeno (como os do teclado): verde quando ligado, cinzento quando desligado."""
    botao = QPushButton(texto)
    botao.setCheckable(True)
    botao.setChecked(marcado)
    botao.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    botao.setStyleSheet(
        "QPushButton { background: #9E9E9E; color: white; border: none; border-radius: 10px;"
        " padding: 6px 14px; font-size: 15px; }"
        " QPushButton:checked { background: #43A047; }"
    )
    return botao
