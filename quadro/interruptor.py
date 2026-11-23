"""Interruptor On/Off discreto usado pelas janelas do Quadro (ex.: «Adicionar ao Menu»)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QPushButton


class _InterruptorDiscreto(QPushButton):
    """Botao On/Off compacto com deslizador estilo iOS/Android."""

    def __init__(self, texto: str, marcado: bool) -> None:
        super().__init__(texto)
        self.setCheckable(True)
        self.setChecked(marcado)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self._cor_texto = QColor("#E2E8F0")
        self.toggled.connect(lambda _=False: self.update())

    def definir_cor_texto(self, cor: str) -> None:
        self._cor_texto = QColor(cor)
        self.update()

    def _fonte(self) -> QFont:
        f = QFont(self.font())
        f.setPixelSize(12)
        f.setWeight(QFont.Weight.Medium)
        return f

    def sizeHint(self) -> QSize:  # noqa: N802
        largura = QFontMetrics(self._fonte()).horizontalAdvance(self.text()) + 52
        return QSize(max(largura, 110), 28)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            pintor.setOpacity(0.45)

        h = float(self.height())
        w = float(self.width())
        cy = h / 2.0
        ligado = self.isChecked()

        # Deslizador compacto a direita (36x20)
        tw, th = 36.0, 20.0
        trilho = QRectF(w - tw - 2.0, cy - th / 2.0, tw, th)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor("#22C55E") if ligado else QColor(148, 163, 184, 175))
        pintor.drawRoundedRect(trilho, th / 2.0, th / 2.0)

        # Bola deslizante branca
        bola = 14.0
        bx = trilho.right() - bola - 3.0 if ligado else trilho.left() + 3.0
        pintor.setBrush(QColor("#FFFFFF"))
        pintor.drawEllipse(QRectF(bx, cy - bola / 2.0, bola, bola))

        # Texto discreto a esquerda
        pintor.setFont(self._fonte())
        pintor.setPen(self._cor_texto)
        pintor.drawText(
            QRectF(2.0, 0.0, trilho.left() - 10.0, h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )
        pintor.end()


def interruptor(texto: str, marcado: bool) -> QPushButton:
    """Interruptor On/Off compacto e discreto: verde quando ligado, cinzento quando desligado."""
    return _InterruptorDiscreto(texto, marcado)
