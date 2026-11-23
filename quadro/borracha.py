"""Ícones das borrachas: uma borracha de escola (corpo cor de tijolo com uma ponta azul).

- borracha: a borracha sozinha (apaga riscos e pixels).
- borracha de riscos: a borracha pequena com um traço por baixo (apaga só os riscos).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

LARANJA = QColor("#d9542b")
AZUL = QColor("#2563eb")
BRANCO = QColor("#ffffff")


def _borracha(pintor: QPainter, cx: float, cy: float, escala: float, s: float) -> None:
    comprimento = s * 0.42 * escala
    altura = s * 0.22 * escala
    pintor.save()
    pintor.translate(cx, cy)
    pintor.rotate(-35)
    corpo = QPainterPath()
    corpo.addRoundedRect(QRectF(-comprimento, -altura, 2 * comprimento, 2 * altura), altura * 0.35, altura * 0.35)
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QBrush(LARANJA))
    pintor.drawPath(corpo)
    pintor.save()
    pintor.setClipPath(corpo)
    pintor.setBrush(QBrush(AZUL))
    pintor.drawRect(QRectF(comprimento * 0.42, -altura, comprimento, 2 * altura))
    pintor.restore()
    pintor.setPen(QPen(BRANCO, s * 0.035))
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    pintor.drawPath(corpo)
    pintor.drawLine(QPointF(comprimento * 0.42, -altura), QPointF(comprimento * 0.42, altura))
    pintor.restore()


def _riscos(pintor: QPainter, s: float) -> None:
    pintor.setPen(QPen(BRANCO, s * 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    caminho = QPainterPath()
    caminho.moveTo(s * 0.1, s * 0.86)
    for i in range(3):
        x0 = s * (0.1 + i * 0.2)
        caminho.quadTo(QPointF(x0 + s * 0.1, s * 0.7), QPointF(x0 + s * 0.2, s * 0.86))
    pintor.drawPath(caminho)


def icone(tamanho: int = 40, riscos: bool = False) -> QPixmap:
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = tamanho
    if riscos:
        _borracha(pintor, s * 0.56, s * 0.4, 0.72, s)
        _riscos(pintor, s)
    else:
        _borracha(pintor, s * 0.5, s * 0.5, 1.0, s)
    pintor.end()
    return QPixmap.fromImage(imagem)
