"""Carimbos: figuras simples desenhadas pelo próprio Quadro, colocadas com um toque.

Cada carimbo é uma função de desenho escrita de raiz. Os carimbos ficam numa camada de pixels
por cima dos riscos, por isso desfazer, guardar e abrir funcionam como nas outras camadas.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QPolygonF

from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro

NOMES = ("estrela", "coracao", "sol", "flor", "casa", "arvore", "peixe", "sorriso", "nuvem")
ROTULOS = {
    "estrela": "Estrela",
    "coracao": "Coração",
    "sol": "Sol",
    "flor": "Flor",
    "casa": "Casa",
    "arvore": "Árvore",
    "peixe": "Peixe",
    "sorriso": "Sorriso",
    "nuvem": "Nuvem",
}


def _circulo(pintor: QPainter, x: float, y: float, raio: float) -> None:
    pintor.drawEllipse(QPointF(x, y), raio, raio)


def desenhar_forma(pintor: QPainter, nome: str, cx: float, cy: float, r: float, cor: QColor) -> None:
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QBrush(cor))
    if nome == "estrela":
        pontos = []
        for i in range(10):
            angulo = -math.pi / 2 + i * math.pi / 5
            raio = r if i % 2 == 0 else r * 0.45
            pontos.append(QPointF(cx + raio * math.cos(angulo), cy + raio * math.sin(angulo)))
        pintor.drawPolygon(QPolygonF(pontos))
    elif nome == "coracao":
        _circulo(pintor, cx - r * 0.5, cy - r * 0.25, r * 0.55)
        _circulo(pintor, cx + r * 0.5, cy - r * 0.25, r * 0.55)
        pintor.drawPolygon(
            QPolygonF([QPointF(cx - r * 0.98, cy - r * 0.1), QPointF(cx + r * 0.98, cy - r * 0.1), QPointF(cx, cy + r)])
        )
    elif nome == "sol":
        _circulo(pintor, cx, cy, r * 0.5)
        pintor.setPen(QPen(cor, r * 0.14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i in range(8):
            angulo = i * math.pi / 4
            pintor.drawLine(
                QPointF(cx + r * 0.7 * math.cos(angulo), cy + r * 0.7 * math.sin(angulo)),
                QPointF(cx + r * math.cos(angulo), cy + r * math.sin(angulo)),
            )
    elif nome == "flor":
        for i in range(6):
            angulo = i * math.pi / 3
            _circulo(pintor, cx + r * 0.5 * math.cos(angulo), cy + r * 0.5 * math.sin(angulo), r * 0.35)
        pintor.setBrush(QBrush(QColor("#fde047")))
        _circulo(pintor, cx, cy, r * 0.3)
    elif nome == "casa":
        pintor.drawRect(QRectF(cx - r * 0.7, cy - r * 0.1, r * 1.4, r * 0.9))
        pintor.drawPolygon(QPolygonF([QPointF(cx - r * 0.9, cy - r * 0.1), QPointF(cx + r * 0.9, cy - r * 0.1), QPointF(cx, cy - r * 0.9)]))
    elif nome == "arvore":
        pintor.setBrush(QBrush(QColor("#92400e")))
        pintor.drawRect(QRectF(cx - r * 0.15, cy + r * 0.2, r * 0.3, r * 0.8))
        pintor.setBrush(QBrush(cor))
        _circulo(pintor, cx, cy - r * 0.25, r * 0.7)
    elif nome == "peixe":
        pintor.drawEllipse(QRectF(cx - r * 0.8, cy - r * 0.45, r * 1.5, r * 0.9))
        pintor.drawPolygon(QPolygonF([QPointF(cx + r * 0.6, cy), QPointF(cx + r * 1.1, cy - r * 0.4), QPointF(cx + r * 1.1, cy + r * 0.4)]))
    elif nome == "sorriso":
        _circulo(pintor, cx, cy, r)
        escuro = QColor("#1f2937")
        pintor.setBrush(QBrush(escuro))
        _circulo(pintor, cx - r * 0.35, cy - r * 0.25, r * 0.12)
        _circulo(pintor, cx + r * 0.35, cy - r * 0.25, r * 0.12)
        pintor.setPen(QPen(escuro, r * 0.12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        pintor.drawArc(QRectF(cx - r * 0.5, cy - r * 0.2, r, r * 0.9), 200 * 16, 140 * 16)
    elif nome == "nuvem":
        _circulo(pintor, cx - r * 0.4, cy, r * 0.45)
        _circulo(pintor, cx, cy - r * 0.2, r * 0.55)
        _circulo(pintor, cx + r * 0.45, cy, r * 0.45)
        pintor.drawRect(QRectF(cx - r * 0.85, cy, r * 1.7, r * 0.45))


def tracar(quadro: Quadro, nome: str, x: float, y: float, tamanho: float, cor: str) -> None:
    """Coloca um carimbo no centro (x, y), normalizado. `tamanho` é o diâmetro, em fração da altura."""
    imagem = quadro.camada_carimbos
    if imagem is None:
        imagem = QImage(CAMADA_LARGURA, CAMADA_ALTURA, QImage.Format.Format_ARGB32)
        imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    desenhar_forma(pintor, nome, x * CAMADA_LARGURA, y * CAMADA_ALTURA, tamanho * CAMADA_ALTURA / 2, QColor(cor))
    pintor.end()
    quadro.camada_carimbos = imagem


def previa(nome: str, cor: str, lado: int) -> QPixmap:
    """Carimbo com o mesmo desenho de `tracar`, para ver onde fica antes de o colocar."""
    imagem = QImage(lado, lado, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    desenhar_forma(pintor, nome, lado / 2, lado / 2, lado / 2, QColor(cor))
    pintor.end()
    return QPixmap.fromImage(imagem)


def icone(nome: str, tamanho: int = 40) -> QPixmap:
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    desenhar_forma(pintor, nome, tamanho / 2, tamanho / 2, tamanho * 0.4, QColor("#1f2937"))
    pintor.end()
    return QPixmap.fromImage(imagem)
