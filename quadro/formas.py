"""Formas: linha, retângulo e elipse, guardadas como riscos (pontos do contorno).

Como são riscos, a varinha, a borracha, o desfazer e a gravação funcionam sem alterações.
As coordenadas são normalizadas; como a conversão para o ecrã é linear em cada eixo, a elipse
continua a ser uma elipse em qualquer proporção de ecrã.
Os botões mostram a forma desenhada (sem texto), porque as crianças podem ainda não ler.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF

TIPOS = ("linha", "retangulo", "elipse", "poligono")
ROTULOS = {"linha": "Linha", "retangulo": "Retângulo", "elipse": "Elipse", "poligono": "Polígono"}
COR_ICONE = "#1f2937"
PONTOS_ELIPSE = 72


def pontos(tipo: str, x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    if tipo == "linha":
        return [(x0, y0), (x1, y1)]
    if tipo == "retangulo":
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    if tipo == "elipse":
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = abs(x1 - x0) / 2, abs(y1 - y0) / 2
        return [
            (cx + rx * math.cos(2 * math.pi * i / PONTOS_ELIPSE), cy + ry * math.sin(2 * math.pi * i / PONTOS_ELIPSE))
            for i in range(PONTOS_ELIPSE + 1)
        ]
    raise ValueError(f"forma desconhecida: {tipo}")


def icone(tipo: str, tamanho: int = 40) -> QPixmap:
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setPen(QPen(QColor(COR_ICONE), tamanho * 0.08, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    margem = tamanho * 0.16
    if tipo == "linha":
        pintor.drawLine(QPointF(margem, tamanho - margem), QPointF(tamanho - margem, margem))
    elif tipo == "retangulo":
        pintor.drawRect(QRectF(margem, tamanho * 0.25, tamanho - 2 * margem, tamanho * 0.5))
    elif tipo == "elipse":
        pintor.drawEllipse(QRectF(margem, tamanho * 0.25, tamanho - 2 * margem, tamanho * 0.5))
    elif tipo == "poligono":
        centro, raio = tamanho / 2, tamanho * 0.36
        vertices = [
            QPointF(centro + raio * math.cos(-math.pi / 2 + i * 2 * math.pi / 5),
                    centro + raio * math.sin(-math.pi / 2 + i * 2 * math.pi / 5))
            for i in range(5)
        ]
        pintor.drawPolygon(QPolygonF(vertices))
    else:
        raise ValueError(f"forma desconhecida: {tipo}")
    pintor.end()
    return QPixmap.fromImage(imagem)
