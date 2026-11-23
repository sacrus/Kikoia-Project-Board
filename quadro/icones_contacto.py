"""Ícones dos contactos (sem texto): usados quando um contacto não tem foto.

Desenhados em cor escura sobre fundo claro, para se verem bem em listas e caixas de diálogo.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

COR = QColor("#1f2937")
FUNDO = QColor("#e0e7ff")
TAMANHO_BASE = 96


def _linha(p: QPainter, s: float, espessura: float) -> None:
    p.setPen(QPen(COR, s * espessura, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _cheio(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(COR))


def _pessoa(p: QPainter, s: float) -> None:
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.5, s * 0.34), s * 0.16, s * 0.16)
    p.drawEllipse(QRectF(s * 0.24, s * 0.56, s * 0.52, s * 0.4))


def _estrela(p: QPainter, s: float) -> None:
    pontos = []
    for i in range(10):
        angulo = -math.pi / 2 + i * math.pi / 5
        raio = s * 0.42 if i % 2 == 0 else s * 0.18
        pontos.append(QPointF(s / 2 + raio * math.cos(angulo), s / 2 + raio * math.sin(angulo)))
    caminho = QPainterPath()
    caminho.moveTo(pontos[0])
    for ponto in pontos[1:]:
        caminho.lineTo(ponto)
    caminho.closeSubpath()
    _cheio(p)
    p.drawPath(caminho)


def _coracao(p: QPainter, s: float) -> None:
    caminho = QPainterPath()
    caminho.moveTo(QPointF(s * 0.5, s * 0.84))
    caminho.cubicTo(QPointF(s * 0.05, s * 0.52), QPointF(s * 0.12, s * 0.12), QPointF(s * 0.5, s * 0.34))
    caminho.cubicTo(QPointF(s * 0.88, s * 0.12), QPointF(s * 0.95, s * 0.52), QPointF(s * 0.5, s * 0.84))
    _cheio(p)
    p.drawPath(caminho)


def _sol(p: QPainter, s: float) -> None:
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.2, s * 0.2)
    _linha(p, s, 0.07)
    for i in range(8):
        angulo = i * math.pi / 4
        p.drawLine(
            QPointF(s * 0.5 + s * 0.3 * math.cos(angulo), s * 0.5 + s * 0.3 * math.sin(angulo)),
            QPointF(s * 0.5 + s * 0.44 * math.cos(angulo), s * 0.5 + s * 0.44 * math.sin(angulo)),
        )


def _casa(p: QPainter, s: float) -> None:
    _cheio(p)
    telhado = QPainterPath()
    telhado.moveTo(QPointF(s * 0.1, s * 0.5))
    telhado.lineTo(QPointF(s * 0.5, s * 0.14))
    telhado.lineTo(QPointF(s * 0.9, s * 0.5))
    telhado.closeSubpath()
    p.drawPath(telhado)
    p.drawRect(QRectF(s * 0.22, s * 0.5, s * 0.56, s * 0.36))


def _bola(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.36, s * 0.36)
    p.drawLine(QPointF(s * 0.14, s * 0.5), QPointF(s * 0.86, s * 0.5))
    p.drawLine(QPointF(s * 0.5, s * 0.14), QPointF(s * 0.5, s * 0.86))


def _livro(p: QPainter, s: float) -> None:
    _cheio(p)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.2, s * 0.34, s * 0.6), s * 0.03, s * 0.03)
    p.drawRoundedRect(QRectF(s * 0.52, s * 0.2, s * 0.34, s * 0.6), s * 0.03, s * 0.03)


def _carro(p: QPainter, s: float) -> None:
    _cheio(p)
    p.drawRoundedRect(QRectF(s * 0.08, s * 0.42, s * 0.84, s * 0.26), s * 0.06, s * 0.06)
    p.drawRoundedRect(QRectF(s * 0.26, s * 0.26, s * 0.4, s * 0.2), s * 0.05, s * 0.05)
    p.drawEllipse(QPointF(s * 0.28, s * 0.72), s * 0.09, s * 0.09)
    p.drawEllipse(QPointF(s * 0.72, s * 0.72), s * 0.09, s * 0.09)


def _flor(p: QPainter, s: float) -> None:
    _cheio(p)
    for i in range(5):
        angulo = -math.pi / 2 + i * 2 * math.pi / 5
        p.drawEllipse(QPointF(s * 0.5 + s * 0.2 * math.cos(angulo), s * 0.4 + s * 0.2 * math.sin(angulo)), s * 0.12, s * 0.12)
    p.drawEllipse(QPointF(s * 0.5, s * 0.4), s * 0.1, s * 0.1)
    _linha(p, s, 0.06)
    p.drawLine(QPointF(s * 0.5, s * 0.6), QPointF(s * 0.5, s * 0.9))


def _peixe(p: QPainter, s: float) -> None:
    _cheio(p)
    p.drawEllipse(QRectF(s * 0.14, s * 0.3, s * 0.6, s * 0.4))
    caminho = QPainterPath()
    caminho.moveTo(QPointF(s * 0.72, s * 0.5))
    caminho.lineTo(QPointF(s * 0.92, s * 0.3))
    caminho.lineTo(QPointF(s * 0.92, s * 0.7))
    caminho.closeSubpath()
    p.drawPath(caminho)


DESENHOS = {
    "pessoa": _pessoa,
    "estrela": _estrela,
    "coracao": _coracao,
    "sol": _sol,
    "casa": _casa,
    "bola": _bola,
    "livro": _livro,
    "carro": _carro,
    "flor": _flor,
    "peixe": _peixe,
}


def desenhar(nome: str, tamanho: int = TAMANHO_BASE) -> QPixmap:
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32)
    imagem.fill(FUNDO)
    p = QPainter(imagem)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    DESENHOS.get(nome, _pessoa)(p, tamanho)
    p.end()
    return QPixmap.fromImage(imagem)
