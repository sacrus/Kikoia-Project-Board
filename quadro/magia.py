"""Pincel mágico: efeitos aplicados ao que está por baixo do pincel (desfocar, tingir, pixelizar).

O efeito é guardado numa camada própria por cima de tudo. As cores lidas vêm do desenho tal como estava
no início do gesto, por isso um traço não lê o efeito que ele próprio acabou de criar.
"""

from __future__ import annotations

from array import array

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPixmap

from quadro.camadas import _composto, _valores
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro

EFEITOS = ("desfocar", "tingir", "pixelizar")
ROTULOS = {"desfocar": "Desfocar", "tingir": "Tingir", "pixelizar": "Pixelizar"}
FORCA_TINGIR = 0.35


def _pack(r: int, g: int, b: int) -> int:
    return 0xFF000000 | (r << 16) | (g << 8) | b


class Pincel:
    def __init__(self, quadro: Quadro, efeito: str, cor: str) -> None:
        if efeito not in EFEITOS:
            raise ValueError(f"efeito desconhecido: {efeito}")
        self._quadro = quadro
        self._efeito = efeito
        self._origem = _valores(_composto(quadro))
        self._destino = array("I")
        if quadro.camada_efeitos is not None:
            self._destino.frombytes(_valores(quadro.camada_efeitos).tobytes())
        else:
            self._destino.frombytes(bytes(CAMADA_LARGURA * CAMADA_ALTURA * 4))
        tinta = QColor(cor)
        self._tinta = (tinta.red(), tinta.green(), tinta.blue())

    def aplicar(self, x: float, y: float, raio: float) -> None:
        """Aplica o efeito num disco de raio `raio` (fração da altura) centrado em (x, y), normalizado."""
        largura, altura = CAMADA_LARGURA, CAMADA_ALTURA
        cx, cy = x * largura, y * altura
        r = raio * altura
        r2 = r * r
        x0, x1 = max(0, int(cx - r)), min(largura - 1, int(cx + r))
        y0, y1 = max(0, int(cy - r)), min(altura - 1, int(cy + r))
        bloco = max(4, int(r / 2))
        for py in range(y0, y1 + 1):
            dy = py - cy
            for px in range(x0, x1 + 1):
                dx = px - cx
                if dx * dx + dy * dy <= r2:
                    self._destino[py * largura + px] = self._pixel(px, py, bloco)
        dados = self._destino.tobytes()
        self._quadro.camada_efeitos = QImage(dados, largura, altura, largura * 4, QImage.Format.Format_ARGB32).copy()

    def _pixel(self, px: int, py: int, bloco: int) -> int:
        largura, altura = CAMADA_LARGURA, CAMADA_ALTURA
        origem = self._origem
        if self._efeito == "desfocar":
            soma_r = soma_g = soma_b = n = 0
            for vy in range(max(0, py - 1), min(altura, py + 2)):
                for vx in range(max(0, px - 1), min(largura, px + 2)):
                    cor = origem[vy * largura + vx]
                    soma_r += (cor >> 16) & 255
                    soma_g += (cor >> 8) & 255
                    soma_b += cor & 255
                    n += 1
            return _pack(soma_r // n, soma_g // n, soma_b // n)
        if self._efeito == "tingir":
            cor = origem[py * largura + px]
            tr, tg, tb = self._tinta
            r = int(((cor >> 16) & 255) * (1 - FORCA_TINGIR) + tr * FORCA_TINGIR)
            g = int(((cor >> 8) & 255) * (1 - FORCA_TINGIR) + tg * FORCA_TINGIR)
            b = int((cor & 255) * (1 - FORCA_TINGIR) + tb * FORCA_TINGIR)
            return _pack(r, g, b)
        bx = px - px % bloco
        by = py - py % bloco
        return origem[by * largura + bx] | 0xFF000000


def icone(efeito: str, tamanho: int = 40) -> QPixmap:
    """Ícone sem texto, que mostra o efeito: desfocar (bolhas suaves), tingir (cores a misturar), pixelizar (blocos)."""
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setPen(Qt.PenStyle.NoPen)
    s = tamanho
    if efeito == "desfocar":
        for raio, alfa in ((0.42, 60), (0.32, 110), (0.2, 200)):
            pintor.setBrush(QBrush(QColor(31, 41, 55, alfa)))
            pintor.drawEllipse(QPointF(s / 2, s / 2), s * raio, s * raio)
    elif efeito == "tingir":
        pintor.setBrush(QBrush(QColor(239, 68, 68, 200)))
        pintor.drawEllipse(QRectF(s * 0.12, s * 0.2, s * 0.56, s * 0.56))
        pintor.setBrush(QBrush(QColor(37, 99, 235, 200)))
        pintor.drawEllipse(QRectF(s * 0.32, s * 0.2, s * 0.56, s * 0.56))
    elif efeito == "pixelizar":
        cinzentos = (60, 120, 180, 230)
        bloco = s / 4
        for i in range(3):
            for j in range(3):
                tom = cinzentos[(i + j) % len(cinzentos)]
                pintor.setBrush(QBrush(QColor(tom, tom, tom)))
                pintor.drawRect(QRectF(s * 0.1 + i * bloco, s * 0.1 + j * bloco, bloco, bloco))
    else:
        raise ValueError(f"efeito desconhecido: {efeito}")
    pintor.end()
    return QPixmap.fromImage(imagem)
