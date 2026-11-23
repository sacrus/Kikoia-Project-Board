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
    """Lapis/caneta diagonal bem reconhecivel: corpo, ponta afiada e topo."""
    p.save()
    p.translate(s * 0.5, s * 0.5)
    p.rotate(-45)
    # Corpo da caneta
    _linha(p, s, 0.065)
    p.drawRoundedRect(QRectF(-s * 0.24, -s * 0.11, s * 0.52, s * 0.22), s * 0.04, s * 0.04)
    # Separador do topo (borracha/tampa)
    p.drawLine(QPointF(s * 0.17, -s * 0.11), QPointF(s * 0.17, s * 0.11))
    # Ponta triangular
    ponta = QPainterPath()
    ponta.moveTo(-s * 0.24, -s * 0.11)
    ponta.lineTo(-s * 0.42, 0.0)
    ponta.lineTo(-s * 0.24, s * 0.11)
    p.drawPath(ponta)
    # Bico cheio
    _cheio(p)
    bico = QPainterPath()
    bico.moveTo(-s * 0.34, -s * 0.05)
    bico.lineTo(-s * 0.44, 0.0)
    bico.lineTo(-s * 0.34, s * 0.05)
    bico.closeSubpath()
    p.drawPath(bico)
    p.restore()


def _varinha(p: QPainter, s: float) -> None:
    """Varinha de selecao: haste diagonal com estrela e pontos de selecao."""
    _linha(p, s, 0.085)
    p.drawLine(QPointF(s * 0.18, s * 0.82), QPointF(s * 0.58, s * 0.42))
    _estrela(p, s * 0.7, s * 0.3, s * 0.22)
    _cheio(p)
    for x, y, r in ((0.44, 0.2, 0.048), (0.82, 0.54, 0.045), (0.28, 0.42, 0.038)):
        p.drawEllipse(QPointF(s * x, s * y), s * r, s * r)


def _balde(p: QPainter, s: float) -> None:
    """Balde de tinta inclinado a verter uma gota bem visivel."""
    p.save()
    p.translate(s * 0.44, s * 0.48)
    p.rotate(-35)
    _linha(p, s, 0.07)
    # Corpo do balde
    p.drawRoundedRect(QRectF(-s * 0.24, -s * 0.22, s * 0.46, s * 0.48), s * 0.07, s * 0.07)
    # Asa no topo
    p.drawArc(QRectF(-s * 0.18, -s * 0.38, s * 0.34, s * 0.32), 0, 180 * 16)
    # Nivel de tinta cheio na metade inferior
    _cheio(p)
    p.drawRoundedRect(QRectF(-s * 0.2, s * 0.02, s * 0.38, s * 0.2), s * 0.04, s * 0.04)
    p.restore()
    # Gota grande a cair a direita
    _cheio(p)
    gota = QPainterPath()
    gota.moveTo(s * 0.8, s * 0.44)
    gota.cubicTo(QPointF(s * 0.92, s * 0.64), QPointF(s * 0.9, s * 0.82), QPointF(s * 0.8, s * 0.82))
    gota.cubicTo(QPointF(s * 0.7, s * 0.82), QPointF(s * 0.68, s * 0.64), QPointF(s * 0.8, s * 0.44))
    gota.closeSubpath()
    p.drawPath(gota)


def _carimbo(p: QPainter, s: float) -> None:
    """Carimbo classico: pega arredondada, pescoco fino, base larga e almofada."""
    _linha(p, s, 0.065)
    # Pega e corpo do carimbo (contorno limpo)
    pega = QPainterPath()
    pega.moveTo(s * 0.38, s * 0.52)
    pega.cubicTo(QPointF(s * 0.42, s * 0.42), QPointF(s * 0.34, s * 0.36), QPointF(s * 0.34, s * 0.26))
    pega.cubicTo(QPointF(s * 0.34, s * 0.14), QPointF(s * 0.66, s * 0.14), QPointF(s * 0.66, s * 0.26))
    pega.cubicTo(QPointF(s * 0.66, s * 0.36), QPointF(s * 0.58, s * 0.42), QPointF(s * 0.62, s * 0.52))
    p.drawPath(pega)
    # Base do carimbo
    p.drawRoundedRect(QRectF(s * 0.18, s * 0.52, s * 0.64, s * 0.18), s * 0.06, s * 0.06)
    # Linha da almofada / marca em baixo
    _cheio(p)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.78, s * 0.72, s * 0.09), s * 0.04, s * 0.04)


def _magia(p: QPainter, s: float) -> None:
    """Pincel magico: tres brilhos de estrelas bem distintos e luminosos."""
    _estrela(p, s * 0.38, s * 0.58, s * 0.28)
    _estrela(p, s * 0.74, s * 0.26, s * 0.18)
    _estrela(p, s * 0.76, s * 0.7, s * 0.12)


def _forma(p: QPainter, s: float) -> None:
    """Formas geometricas: triangulo, quadrado e circulo bem organizados."""
    _linha(p, s, 0.065)
    # Triangulo no topo esquerdo
    tri = QPainterPath()
    tri.moveTo(s * 0.34, s * 0.14)
    tri.lineTo(s * 0.54, s * 0.48)
    tri.lineTo(s * 0.14, s * 0.48)
    tri.closeSubpath()
    p.drawPath(tri)
    # Circulo a direita
    p.drawEllipse(QRectF(s * 0.54, s * 0.48, s * 0.34, s * 0.34))
    # Quadrado em baixo a esquerda
    p.drawRoundedRect(QRectF(s * 0.16, s * 0.56, s * 0.3, s * 0.28), s * 0.04, s * 0.04)


def _cor(p: QPainter, s: float) -> None:
    """Paleta de artista com furo para o polegar e 4 tintas."""
    _linha(p, s, 0.065)
    p.drawEllipse(QRectF(s * 0.12, s * 0.14, s * 0.76, s * 0.72))
    # Furo do polegar
    p.drawEllipse(QPointF(s * 0.66, s * 0.64), s * 0.085, s * 0.085)
    # Pingos de tinta
    _cheio(p)
    for x, y in ((0.34, 0.36), (0.52, 0.28), (0.68, 0.38), (0.34, 0.58)):
        p.drawEllipse(QPointF(s * x, s * y), s * 0.068, s * 0.068)


def _seta_volta(p: QPainter, s: float, espelho: bool) -> None:
    def x(v: float) -> float:
        return s - v if espelho else v

    _linha(p, s, 0.085)
    caminho = QPainterPath()
    caminho.moveTo(x(s * 0.22), s * 0.48)
    caminho.cubicTo(QPointF(x(s * 0.34), s * 0.22), QPointF(x(s * 0.8), s * 0.26), QPointF(x(s * 0.78), s * 0.64))
    caminho.cubicTo(QPointF(x(s * 0.77), s * 0.78), QPointF(x(s * 0.62), s * 0.82), QPointF(x(s * 0.5), s * 0.8))
    p.drawPath(caminho)
    # Ponta de seta nitida
    p.drawLine(QPointF(x(s * 0.22), s * 0.48), QPointF(x(s * 0.24), s * 0.24))
    p.drawLine(QPointF(x(s * 0.22), s * 0.48), QPointF(x(s * 0.46), s * 0.48))


def _apagar(p: QPainter, s: float) -> None:
    """Caixote do lixo nitido com tampa e duas riscas verticais."""
    _linha(p, s, 0.068)
    p.drawLine(QPointF(s * 0.18, s * 0.28), QPointF(s * 0.82, s * 0.28))
    p.drawRoundedRect(QRectF(s * 0.38, s * 0.16, s * 0.24, s * 0.12), s * 0.03, s * 0.03)
    caminho = QPainterPath()
    caminho.moveTo(s * 0.26, s * 0.28)
    caminho.lineTo(s * 0.32, s * 0.84)
    caminho.lineTo(s * 0.68, s * 0.84)
    caminho.lineTo(s * 0.74, s * 0.28)
    p.drawPath(caminho)
    _linha(p, s, 0.055)
    p.drawLine(QPointF(s * 0.43, s * 0.42), QPointF(s * 0.45, s * 0.72))
    p.drawLine(QPointF(s * 0.57, s * 0.42), QPointF(s * 0.55, s * 0.72))


def _jogos(p: QPainter, s: float) -> None:
    _linha(p, s, 0.068)
    p.drawRoundedRect(QRectF(s * 0.12, s * 0.3, s * 0.76, s * 0.42), s * 0.18, s * 0.18)
    p.drawLine(QPointF(s * 0.3, s * 0.42), QPointF(s * 0.3, s * 0.6))
    p.drawLine(QPointF(s * 0.21, s * 0.51), QPointF(s * 0.39, s * 0.51))
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.65, s * 0.46), s * 0.052, s * 0.052)
    p.drawEllipse(QPointF(s * 0.76, s * 0.57), s * 0.052, s * 0.052)


def _correio(p: QPainter, s: float) -> None:
    _linha(p, s, 0.068)
    p.drawRoundedRect(QRectF(s * 0.14, s * 0.24, s * 0.72, s * 0.52), s * 0.07, s * 0.07)
    p.drawLine(QPointF(s * 0.16, s * 0.27), QPointF(s * 0.5, s * 0.54))
    p.drawLine(QPointF(s * 0.84, s * 0.27), QPointF(s * 0.5, s * 0.54))


def _definicoes(p: QPainter, s: float) -> None:
    """Roda dentada nitida de 8 dentes com furo central."""
    centro = s / 2.0
    r_ext, r_dente, r_furo = s * 0.42, s * 0.31, s * 0.14
    caminho = QPainterPath()
    caminho.setFillRule(Qt.FillRule.OddEvenFill)
    primeiro = True
    for dente in range(8):
        ang = 2 * math.pi * dente / 8
        for desl, r in ((-0.17, r_dente), (-0.09, r_ext), (0.09, r_ext), (0.17, r_dente)):
            a = ang + desl
            pt = QPointF(centro + r * math.cos(a), centro + r * math.sin(a))
            if primeiro:
                caminho.moveTo(pt)
                primeiro = False
            else:
                caminho.lineTo(pt)
    caminho.closeSubpath()
    caminho.addEllipse(QPointF(centro, centro), r_furo, r_furo)
    _cheio(p)
    p.drawPath(caminho)


def _ocultar(p: QPainter, s: float) -> None:
    """Olho em forma de amendoa com traco diagonal."""
    _linha(p, s, 0.068)
    olho = QPainterPath()
    olho.moveTo(s * 0.12, s * 0.5)
    olho.quadTo(QPointF(s * 0.5, s * 0.18), QPointF(s * 0.88, s * 0.5))
    olho.quadTo(QPointF(s * 0.5, s * 0.82), QPointF(s * 0.12, s * 0.5))
    p.drawPath(olho)
    _cheio(p)
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), s * 0.11, s * 0.11)
    _linha(p, s, 0.08)
    p.drawLine(QPointF(s * 0.18, s * 0.84), QPointF(s * 0.82, s * 0.16))


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


def _lupa_comum(p: QPainter, s: float) -> None:
    p.setPen(QPen(BRANCO, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(s * 0.42, s * 0.42), s * 0.24, s * 0.24)
    p.drawLine(QPointF(s * 0.6, s * 0.6), QPointF(s * 0.84, s * 0.84))


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
    "pesquisar": lambda p, s: _lupa_comum(p, s),
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
