"""Ferramenta de texto: escreve uma linha de texto na camada de carimbos (pixels).

Como fica em pixels, o desfazer, a borracha de pixels, guardar e abrir funcionam como nos carimbos.
O tamanho é uma fração da altura do quadro, para o texto ter a mesma proporção em qualquer ecrã.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QPixmap

from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro


def escrever(quadro: Quadro, texto: str, x: float, y: float, tamanho: float, cor: str) -> bool:
    """Escreve `texto` com o canto superior esquerdo em (x, y), normalizado. Devolve False se estiver vazio."""
    texto = texto.strip()
    if not texto:
        return False
    imagem = quadro.camada_carimbos
    if imagem is None:
        imagem = QImage(CAMADA_LARGURA, CAMADA_ALTURA, QImage.Format.Format_ARGB32)
        imagem.fill(0)
    fonte = QFont()
    fonte.setPixelSize(max(8, int(tamanho * CAMADA_ALTURA)))
    fonte.setBold(True)
    ascendente = QFontMetrics(fonte).ascent()
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    pintor.setFont(fonte)
    pintor.setPen(QColor(cor))
    pintor.drawText(QPointF(x * CAMADA_LARGURA, y * CAMADA_ALTURA + ascendente), texto)
    pintor.end()
    quadro.camada_carimbos = imagem
    return True


def icone(tamanho: int = 40) -> QPixmap:
    """Cursor de texto (a barra do «I» com serifas), desenhado a branco para a bolha escura."""
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#ffffff"), tamanho * 0.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    pintor.setPen(pen)
    meio = tamanho / 2
    topo, base = tamanho * 0.2, tamanho * 0.8
    pintor.drawLine(QPointF(meio, topo), QPointF(meio, base))
    pintor.drawLine(QPointF(tamanho * 0.3, topo), QPointF(tamanho * 0.7, topo))
    pintor.drawLine(QPointF(tamanho * 0.3, base), QPointF(tamanho * 0.7, base))
    pintor.end()
    return QPixmap.fromImage(imagem)
