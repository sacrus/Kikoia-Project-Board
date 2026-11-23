"""Ícones dos botões do correio. Sempre usados junto ao texto, para o botão continuar legível sem o ícone."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

COR = QColor("#1f2937")
TAMANHO = 32


def _traco(p: QPainter, s: float, espessura: float = 0.08) -> None:
    p.setPen(QPen(COR, s * espessura, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _cheio(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(COR))


def _atualizar(p, s):
    _traco(p, s)
    p.drawArc(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64), 60 * 16, 270 * 16)
    _cheio(p)
    ponta = QPainterPath()
    ponta.moveTo(QPointF(s * 0.78, s * 0.14))
    ponta.lineTo(QPointF(s * 0.86, s * 0.42))
    ponta.lineTo(QPointF(s * 0.6, s * 0.36))
    ponta.closeSubpath()
    p.drawPath(ponta)


def _escrever(p, s):
    _traco(p, s, 0.12)
    p.drawLine(QPointF(s * 0.2, s * 0.8), QPointF(s * 0.74, s * 0.26))
    p.drawLine(QPointF(s * 0.74, s * 0.26), QPointF(s * 0.84, s * 0.36))


def _pessoa(p, s):
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.5, s * 0.32), s * 0.18, s * 0.18)
    p.drawEllipse(QRectF(s * 0.22, s * 0.56, s * 0.56, s * 0.36))


def _engrenagem(p, s):
    _traco(p, s, 0.12)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.2, s * 0.2)
    for i in range(8):
        a = i * math.pi / 4
        p.drawLine(QPointF(s * 0.5 + s * 0.3 * math.cos(a), s * 0.5 + s * 0.3 * math.sin(a)),
                   QPointF(s * 0.5 + s * 0.42 * math.cos(a), s * 0.5 + s * 0.42 * math.sin(a)))


def _lixo(p, s):
    _traco(p, s, 0.07)
    p.drawLine(QPointF(s * 0.18, s * 0.28), QPointF(s * 0.82, s * 0.28))
    p.drawRect(QRectF(s * 0.28, s * 0.36, s * 0.44, s * 0.5))
    p.drawLine(QPointF(s * 0.42, s * 0.18), QPointF(s * 0.58, s * 0.18))


def _seta(p, s, sentido):
    """Seta curva: 'responder' (para a esquerda), 'encaminhar' (para a direita)."""
    _traco(p, s, 0.08)
    if sentido == "esquerda":
        p.drawLine(QPointF(s * 0.2, s * 0.42), QPointF(s * 0.7, s * 0.42))
        p.drawArc(QRectF(s * 0.5, s * 0.42, s * 0.36, s * 0.4), 90 * 16, 180 * 16)
        cabeca = [QPointF(s * 0.2, s * 0.42), QPointF(s * 0.38, s * 0.26), QPointF(s * 0.38, s * 0.58)]
    else:
        p.drawLine(QPointF(s * 0.3, s * 0.42), QPointF(s * 0.8, s * 0.42))
        p.drawArc(QRectF(s * 0.14, s * 0.42, s * 0.36, s * 0.4), -90 * 16, 180 * 16)
        cabeca = [QPointF(s * 0.8, s * 0.42), QPointF(s * 0.62, s * 0.26), QPointF(s * 0.62, s * 0.58)]
    _cheio(p)
    caminho = QPainterPath()
    caminho.moveTo(cabeca[0])
    caminho.lineTo(cabeca[1])
    caminho.lineTo(cabeca[2])
    caminho.closeSubpath()
    p.drawPath(caminho)


def _responder_todos(p, s):
    _seta(p, s, "esquerda")
    _traco(p, s, 0.07)
    p.drawLine(QPointF(s * 0.14, s * 0.7), QPointF(s * 0.6, s * 0.7))


def _folha(p, s):
    _traco(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.22, s * 0.14, s * 0.56, s * 0.72), s * 0.04, s * 0.04)
    for y in (0.36, 0.5, 0.64):
        p.drawLine(QPointF(s * 0.34, s * y), QPointF(s * 0.66, s * y))


def _envelope(p, s):
    _traco(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.24, s * 0.72, s * 0.52), s * 0.03, s * 0.03)
    p.drawLine(QPointF(s * 0.16, s * 0.27), QPointF(s * 0.5, s * 0.56))
    p.drawLine(QPointF(s * 0.84, s * 0.27), QPointF(s * 0.5, s * 0.56))


def _estrela(p, s):
    pontos = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = s * 0.4 if i % 2 == 0 else s * 0.17
        pontos.append(QPointF(s / 2 + r * math.cos(a), s / 2 + r * math.sin(a)))
    caminho = QPainterPath()
    caminho.moveTo(pontos[0])
    for ponto in pontos[1:]:
        caminho.lineTo(ponto)
    caminho.closeSubpath()
    _cheio(p)
    p.drawPath(caminho)


def _pasta(p, s):
    _cheio(p)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.28, s * 0.76, s * 0.5), s * 0.04, s * 0.04)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.2, s * 0.3, s * 0.14), s * 0.03, s * 0.03)


def _lupa(p, s):
    _traco(p, s, 0.09)
    p.drawEllipse(QPointF(s * 0.42, s * 0.42), s * 0.24, s * 0.24)
    p.drawLine(QPointF(s * 0.6, s * 0.6), QPointF(s * 0.84, s * 0.84))


def _aviao(p, s):
    _cheio(p)
    caminho = QPainterPath()
    caminho.moveTo(QPointF(s * 0.12, s * 0.48))
    caminho.lineTo(QPointF(s * 0.88, s * 0.16))
    caminho.lineTo(QPointF(s * 0.6, s * 0.86))
    caminho.lineTo(QPointF(s * 0.46, s * 0.58))
    caminho.closeSubpath()
    p.drawPath(caminho)


def _cruz(p, s):
    _traco(p, s, 0.12)
    p.drawLine(QPointF(s * 0.24, s * 0.24), QPointF(s * 0.76, s * 0.76))
    p.drawLine(QPointF(s * 0.76, s * 0.24), QPointF(s * 0.24, s * 0.76))


def _visto(p, s):
    _traco(p, s, 0.12)
    p.drawLine(QPointF(s * 0.16, s * 0.52), QPointF(s * 0.4, s * 0.76))
    p.drawLine(QPointF(s * 0.4, s * 0.76), QPointF(s * 0.86, s * 0.26))


def _disquete(p, s):
    _cheio(p)
    p.drawRoundedRect(QRectF(s * 0.16, s * 0.16, s * 0.68, s * 0.68), s * 0.06, s * 0.06)
    _traco(p, s, 0.01)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("white")))
    p.drawRect(QRectF(s * 0.3, s * 0.2, s * 0.4, s * 0.2))


def _clipe(p, s):
    _traco(p, s, 0.08)
    caminho = QPainterPath()
    caminho.moveTo(QPointF(s * 0.6, s * 0.3))
    caminho.lineTo(QPointF(s * 0.34, s * 0.58))
    caminho.cubicTo(QPointF(s * 0.26, s * 0.66), QPointF(s * 0.44, s * 0.82), QPointF(s * 0.56, s * 0.7))
    caminho.lineTo(QPointF(s * 0.78, s * 0.46))
    caminho.cubicTo(QPointF(s * 0.9, s * 0.34), QPointF(s * 0.74, s * 0.12), QPointF(s * 0.6, s * 0.26))
    caminho.lineTo(QPointF(s * 0.4, s * 0.48))
    p.drawPath(caminho)


def _imagem(p, s):
    _traco(p, s, 0.07)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.2, s * 0.72, s * 0.6), s * 0.04, s * 0.04)
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.34, s * 0.38), s * 0.07, s * 0.07)
    caminho = QPainterPath()
    caminho.moveTo(QPointF(s * 0.2, s * 0.72))
    caminho.lineTo(QPointF(s * 0.42, s * 0.5))
    caminho.lineTo(QPointF(s * 0.56, s * 0.64))
    caminho.lineTo(QPointF(s * 0.66, s * 0.54))
    caminho.lineTo(QPointF(s * 0.8, s * 0.72))
    caminho.closeSubpath()
    p.drawPath(caminho)


def _mais(p, s):
    _traco(p, s, 0.12)
    p.drawLine(QPointF(s * 0.5, s * 0.22), QPointF(s * 0.5, s * 0.78))
    p.drawLine(QPointF(s * 0.22, s * 0.5), QPointF(s * 0.78, s * 0.5))


def _cadeado(p, s):
    _traco(p, s, 0.08)
    p.drawArc(QRectF(s * 0.3, s * 0.14, s * 0.4, s * 0.4), 0, 180 * 16)
    _cheio(p)
    p.drawRoundedRect(QRectF(s * 0.2, s * 0.44, s * 0.6, s * 0.42), s * 0.05, s * 0.05)


def _altifalante(p, s):
    _cheio(p)
    caminho = QPainterPath()
    caminho.moveTo(QPointF(s * 0.14, s * 0.4))
    caminho.lineTo(QPointF(s * 0.32, s * 0.4))
    caminho.lineTo(QPointF(s * 0.56, s * 0.2))
    caminho.lineTo(QPointF(s * 0.56, s * 0.8))
    caminho.lineTo(QPointF(s * 0.32, s * 0.6))
    caminho.lineTo(QPointF(s * 0.14, s * 0.6))
    caminho.closeSubpath()
    p.drawPath(caminho)
    _traco(p, s, 0.07)
    p.drawArc(QRectF(s * 0.5, s * 0.3, s * 0.36, s * 0.4), -60 * 16, 120 * 16)


def _quadrado(p, s):
    _cheio(p)
    p.drawRoundedRect(QRectF(s * 0.22, s * 0.22, s * 0.56, s * 0.56), s * 0.05, s * 0.05)


DESENHOS = {
    "atualizar": _atualizar, "escrever": _escrever, "pessoa": _pessoa, "configurar": _engrenagem,
    "apagar": _lixo, "responder": lambda p, s: _seta(p, s, "esquerda"),
    "responder_todos": _responder_todos, "encaminhar": lambda p, s: _seta(p, s, "direita"),
    "rascunho": _folha, "lido": _envelope, "estrela": _estrela, "mover": _pasta,
    "pesquisar": _lupa, "enviar": _aviao, "cancelar": _cruz, "guardar": _disquete,
    "anexar": _clipe, "imagem": _imagem, "mais": _mais, "desbloquear": _cadeado,
    "permitir": _visto, "voz": _altifalante, "parar": _quadrado, "fechar": _cruz,
    "remover": lambda p, s: (_traco(p, s, 0.12), p.drawLine(QPointF(s * 0.2, s * 0.5), QPointF(s * 0.8, s * 0.5))),
    "limpar": _cruz,
    "italico": lambda p, s: (_traco(p, s, 0.12), p.drawLine(QPointF(s * 0.5, s * 0.2), QPointF(s * 0.4, s * 0.8)),
                             p.drawLine(QPointF(s * 0.3, s * 0.2), QPointF(s * 0.7, s * 0.2)),
                             p.drawLine(QPointF(s * 0.3, s * 0.8), QPointF(s * 0.5, s * 0.8))),
    "sublinhado": lambda p, s: (_traco(p, s, 0.1), p.drawLine(QPointF(s * 0.5, s * 0.14), QPointF(s * 0.5, s * 0.6)),
                                p.drawArc(QRectF(s * 0.26, s * 0.2, s * 0.48, s * 0.3), 0, 180 * 16),
                                p.drawLine(QPointF(s * 0.2, s * 0.86), QPointF(s * 0.8, s * 0.86))),
    "lista": lambda p, s: (_cheio(p), [p.drawEllipse(QPointF(s * 0.18, s * y), s * 0.05, s * 0.05) for y in (0.3, 0.5, 0.7)],
                           _traco(p, s, 0.08), [p.drawLine(QPointF(s * 0.34, s * y), QPointF(s * 0.84, s * y)) for y in (0.3, 0.5, 0.7)]),
    "negrito": lambda p, s: (_traco(p, s, 0.14), p.drawLine(QPointF(s * 0.3, s * 0.2), QPointF(s * 0.3, s * 0.8)),
                             p.drawArc(QRectF(s * 0.3, s * 0.2, s * 0.4, s * 0.3), 90 * 16, -180 * 16),
                             p.drawArc(QRectF(s * 0.3, s * 0.48, s * 0.4, s * 0.32), 90 * 16, -180 * 16)),
}


def desenhar(nome: str, tamanho: int = TAMANHO) -> QPixmap:
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    p = QPainter(imagem)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    DESENHOS.get(nome, _quadrado)(p, tamanho)
    p.end()
    return QPixmap.fromImage(imagem)
