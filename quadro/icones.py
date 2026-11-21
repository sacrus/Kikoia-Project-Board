"""Ícones desenhados do menu do Quadro.

Todos são desenhados (não são símbolos de texto), por isso ficam nítidos em qualquer tamanho de bolha
e não dependem da fonte instalada no computador. Desenhados em branco, para o fundo escuro das bolhas.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

from quadro import borracha, textos

TAMANHO_BASE = 64
BRANCO = QColor("#ffffff")


def _linha(pintor: QPainter, s: float, espessura: float) -> None:
    pintor.setPen(QPen(BRANCO, s * espessura, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    pintor.setBrush(Qt.BrushStyle.NoBrush)


def _cheio(pintor: QPainter) -> None:
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QBrush(BRANCO))


def _estrela(pintor: QPainter, cx: float, cy: float, r: float) -> None:
    pontos = []
    for i in range(8):
        angulo = -math.pi / 2 + i * math.pi / 4
        raio = r if i % 2 == 0 else r * 0.3
        pontos.append(QPointF(cx + raio * math.cos(angulo), cy + raio * math.sin(angulo)))
    caminho = QPainterPath()
    caminho.moveTo(pontos[0])
    for p in pontos[1:]:
        caminho.lineTo(p)
    caminho.closeSubpath()
    _cheio(pintor)
    pintor.drawPath(caminho)


def _caneta(p: QPainter, s: float) -> None:
    _linha(p, s, 0.17)
    p.drawLine(QPointF(s * 0.22, s * 0.78), QPointF(s * 0.72, s * 0.28))
    _linha(p, s, 0.06)
    p.drawLine(QPointF(s * 0.22, s * 0.78), QPointF(s * 0.12, s * 0.9))


def _varinha(p: QPainter, s: float) -> None:
    _linha(p, s, 0.1)
    p.drawLine(QPointF(s * 0.25, s * 0.75), QPointF(s * 0.58, s * 0.42))
    _estrela(p, s * 0.7, s * 0.3, s * 0.2)
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.5, s * 0.18), s * 0.05, s * 0.05)


def _balde(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    caminho = QPainterPath()
    caminho.moveTo(s * 0.22, s * 0.38)
    caminho.lineTo(s * 0.3, s * 0.82)
    caminho.lineTo(s * 0.62, s * 0.82)
    caminho.lineTo(s * 0.7, s * 0.38)
    caminho.closeSubpath()
    p.drawPath(caminho)
    p.drawArc(QRectF(s * 0.22, s * 0.16, s * 0.48, s * 0.44), 0, 180 * 16)
    _cheio(p)
    gota = QPainterPath()
    gota.moveTo(s * 0.82, s * 0.5)
    gota.quadTo(s * 0.9, s * 0.66, s * 0.82, s * 0.74)
    gota.quadTo(s * 0.74, s * 0.66, s * 0.82, s * 0.5)
    p.drawPath(gota)


def _carimbo(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawEllipse(QPointF(s * 0.5, s * 0.3), s * 0.13, s * 0.13)
    p.drawRect(QRectF(s * 0.2, s * 0.5, s * 0.6, s * 0.2))
    p.drawLine(QPointF(s * 0.18, s * 0.82), QPointF(s * 0.82, s * 0.82))


def _magia(p: QPainter, s: float) -> None:
    _estrela(p, s * 0.42, s * 0.56, s * 0.3)
    _estrela(p, s * 0.76, s * 0.24, s * 0.14)


def _forma(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawRect(QRectF(s * 0.14, s * 0.22, s * 0.4, s * 0.4))
    p.drawEllipse(QRectF(s * 0.44, s * 0.44, s * 0.42, s * 0.42))


def _cor(p: QPainter, s: float) -> None:
    _linha(p, s, 0.06)
    p.drawEllipse(QRectF(s * 0.12, s * 0.12, s * 0.76, s * 0.76))
    _cheio(p)
    for x, y in ((0.36, 0.36), (0.62, 0.34), (0.5, 0.64)):
        p.drawEllipse(QPointF(s * x, s * y), s * 0.08, s * 0.08)


def _seta_volta(p: QPainter, s: float, espelho: bool) -> None:
    def x(v: float) -> float:
        return s - v if espelho else v

    _linha(p, s, 0.09)
    caminho = QPainterPath()
    caminho.moveTo(x(s * 0.25), s * 0.66)
    caminho.cubicTo(QPointF(x(s * 0.3), s * 0.24), QPointF(x(s * 0.8), s * 0.22), QPointF(x(s * 0.8), s * 0.58))
    p.drawPath(caminho)
    p.drawLine(QPointF(x(s * 0.25), s * 0.66), QPointF(x(s * 0.44), s * 0.5))
    p.drawLine(QPointF(x(s * 0.25), s * 0.66), QPointF(x(s * 0.44), s * 0.82))


def _apagar(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawLine(QPointF(s * 0.22, s * 0.3), QPointF(s * 0.78, s * 0.3))
    caminho = QPainterPath()
    caminho.moveTo(s * 0.4, s * 0.3)
    caminho.lineTo(s * 0.4, s * 0.2)
    caminho.lineTo(s * 0.6, s * 0.2)
    caminho.lineTo(s * 0.6, s * 0.3)
    p.drawPath(caminho)
    caminho = QPainterPath()
    caminho.moveTo(s * 0.3, s * 0.3)
    caminho.lineTo(s * 0.34, s * 0.84)
    caminho.lineTo(s * 0.66, s * 0.84)
    caminho.lineTo(s * 0.7, s * 0.3)
    p.drawPath(caminho)


def _jogos(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.32, s * 0.76, s * 0.4), s * 0.16, s * 0.16)
    p.drawLine(QPointF(s * 0.3, s * 0.45), QPointF(s * 0.3, s * 0.63))
    p.drawLine(QPointF(s * 0.21, s * 0.54), QPointF(s * 0.39, s * 0.54))
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.66, s * 0.47), s * 0.05, s * 0.05)
    p.drawEllipse(QPointF(s * 0.76, s * 0.6), s * 0.05, s * 0.05)


def _correio(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.25, s * 0.72, s * 0.5), s * 0.05, s * 0.05)
    p.drawLine(QPointF(s * 0.14, s * 0.25), QPointF(s * 0.5, s * 0.55))
    p.drawLine(QPointF(s * 0.86, s * 0.25), QPointF(s * 0.5, s * 0.55))


def _definicoes(p: QPainter, s: float) -> None:
    _linha(p, s, 0.1)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.2, s * 0.2)
    _linha(p, s, 0.16)
    for i in range(8):
        angulo = i * math.pi / 4
        p.drawLine(
            QPointF(s * 0.5 + s * 0.27 * math.cos(angulo), s * 0.5 + s * 0.27 * math.sin(angulo)),
            QPointF(s * 0.5 + s * 0.39 * math.cos(angulo), s * 0.5 + s * 0.39 * math.sin(angulo)),
        )


def _ocultar(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawEllipse(QRectF(s * 0.12, s * 0.3, s * 0.76, s * 0.4))
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.1, s * 0.1)
    _linha(p, s, 0.08)
    p.drawLine(QPointF(s * 0.18, s * 0.86), QPointF(s * 0.82, s * 0.14))


def _escolher(p: QPainter, s: float) -> None:
    _linha(p, s, 0.12)
    caminho = QPainterPath()
    caminho.moveTo(s * 0.2, s * 0.52)
    caminho.lineTo(s * 0.42, s * 0.74)
    caminho.lineTo(s * 0.8, s * 0.3)
    p.drawPath(caminho)


def _voltar(p: QPainter, s: float) -> None:
    _linha(p, s, 0.1)
    p.drawLine(QPointF(s * 0.82, s * 0.5), QPointF(s * 0.22, s * 0.5))
    p.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.44, s * 0.28))
    p.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.44, s * 0.72))


def _teclado(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.1, s * 0.27, s * 0.8, s * 0.46), s * 0.06, s * 0.06)
    _cheio(p)
    for linha in (0.4, 0.55):
        for coluna in range(4):
            p.drawEllipse(QPointF(s * (0.22 + coluna * 0.18), s * linha), s * 0.03, s * 0.03)
    p.drawEllipse(QPointF(s * 0.5, s * 0.67), s * 0.1, s * 0.035)


def _quadro(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.16, s * 0.76, s * 0.68), s * 0.04, s * 0.04)
    caminho = QPainterPath()
    caminho.moveTo(s * 0.2, s * 0.72)
    caminho.lineTo(s * 0.42, s * 0.42)
    caminho.lineTo(s * 0.56, s * 0.6)
    caminho.lineTo(s * 0.66, s * 0.5)
    caminho.lineTo(s * 0.8, s * 0.72)
    p.drawPath(caminho)
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.68, s * 0.3), s * 0.06, s * 0.06)


def _imagem(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.18, s * 0.72, s * 0.64), s * 0.05, s * 0.05)
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.34, s * 0.4), s * 0.07, s * 0.07)
    caminho = QPainterPath()
    caminho.moveTo(QPointF(s * 0.2, s * 0.74))
    caminho.lineTo(QPointF(s * 0.42, s * 0.5))
    caminho.lineTo(QPointF(s * 0.55, s * 0.62))
    caminho.lineTo(QPointF(s * 0.66, s * 0.5))
    caminho.lineTo(QPointF(s * 0.8, s * 0.74))
    caminho.closeSubpath()
    p.drawPath(caminho)


def _minimizar(p: QPainter, s: float) -> None:
    _linha(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.18, s * 0.72, s * 0.56), s * 0.05, s * 0.05)
    _linha(p, s, 0.1)
    p.drawLine(QPointF(s * 0.3, s * 0.86), QPointF(s * 0.7, s * 0.86))


def _menu(p: QPainter, s: float) -> None:
    _cheio(p)
    for x, y in ((0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)):
        p.drawEllipse(QPointF(s * x, s * y), s * 0.14, s * 0.14)


DESENHOS = {
    "minimizar": _minimizar,
    "imagem": _imagem,
    "menu": _menu,
    "escolher": _escolher,
    "voltar": _voltar,
    "teclado": _teclado,
    "quadro": _quadro,
    "caneta": _caneta,
    "varinha": _varinha,
    "balde": _balde,
    "carimbo": _carimbo,
    "magia": _magia,
    "forma": _forma,
    "cor": _cor,
    "desfazer": lambda p, s: _seta_volta(p, s, False),
    "refazer": lambda p, s: _seta_volta(p, s, True),
    "apagar": _apagar,
    "jogos": _jogos,
    "correio": _correio,
    "definicoes": _definicoes,
    "ocultar": _ocultar,
}
ESPECIAIS = {
    "borracha": lambda t: borracha.icone(t),
    "borracha_riscos": lambda t: borracha.icone(t, riscos=True),
    "texto": textos.icone,
}


def desenhar(nome: str, tamanho: int = TAMANHO_BASE) -> QPixmap:
    """Ícone pelo nome. Desenha-se à resolução base e escala-se, para as linhas ficarem nítidas."""
    if nome in ESPECIAIS:
        return ESPECIAIS[nome](tamanho)
    if nome not in DESENHOS:
        raise KeyError(f"ícone desconhecido: {nome}")
    imagem = QImage(TAMANHO_BASE, TAMANHO_BASE, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    DESENHOS[nome](pintor, TAMANHO_BASE)
    pintor.end()
    return QPixmap.fromImage(imagem).scaled(tamanho, tamanho, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
