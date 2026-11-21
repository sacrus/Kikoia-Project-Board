"""Resolve o nome do ícone de cada ação do catálogo (quadro/acoes.py) para uma imagem.

É aqui que vivem as regras de nomes (ex.: "carimbo-sol" -> o carimbo do sol). O teclado recebe as
imagens já prontas, pela ponte, e não precisa de conhecer estes nomes.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap

from quadro import carimbos, formas, icones, magia

CORES_ACAO = {
    "preto": "#000000",
    "vermelho": "#e11d48",
    "azul": "#2563eb",
    "verde": "#16a34a",
    "laranja": "#f59e0b",
    "roxo": "#7c3aed",
    "branco": "#ffffff",
}
# Tamanho do ponto de cada opção de tamanho, em fração do ícone.
FRACAO_TAMANHO = {"1": 0.16, "2": 0.26, "3": 0.38, "4": 0.5}
TAMANHO_BASE = 64
ICONES_EXTRA = ("escolher", "voltar", "teclado", "quadro")


def _tela(tamanho: int) -> tuple[QImage, QPainter]:
    imagem = QImage(tamanho, tamanho, QImage.Format.Format_ARGB32)
    imagem.fill(0)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    return imagem, pintor


def _pixmap(imagem: QImage, tamanho: int) -> QPixmap:
    return QPixmap.fromImage(imagem).scaled(tamanho, tamanho, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def _tamanho(numero: str, tamanho: int) -> QPixmap:
    imagem, pintor = _tela(TAMANHO_BASE)
    raio = TAMANHO_BASE * FRACAO_TAMANHO[numero] / 2
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QBrush(QColor("#ffffff")))
    pintor.drawEllipse(QPointF(TAMANHO_BASE / 2, TAMANHO_BASE / 2), raio, raio)
    pintor.end()
    return _pixmap(imagem, tamanho)


def _cor(nome: str, tamanho: int) -> QPixmap:
    imagem, pintor = _tela(TAMANHO_BASE)
    centro = TAMANHO_BASE / 2
    pintor.setPen(QPen(QColor("#ffffff"), TAMANHO_BASE * 0.06))
    if nome == "automatica":
        pintor.setBrush(QBrush(QColor("#000000")))
        pintor.drawEllipse(QRectF(TAMANHO_BASE * 0.12, TAMANHO_BASE * 0.12, TAMANHO_BASE * 0.76, TAMANHO_BASE * 0.76))
        pintor.setBrush(QBrush(QColor("#ffffff")))
        pintor.drawChord(QRectF(TAMANHO_BASE * 0.12, TAMANHO_BASE * 0.12, TAMANHO_BASE * 0.76, TAMANHO_BASE * 0.76), 90 * 16, 180 * 16)
    else:
        pintor.setBrush(QBrush(QColor(CORES_ACAO[nome])))
        pintor.drawEllipse(QPointF(centro, centro), TAMANHO_BASE * 0.38, TAMANHO_BASE * 0.38)
    pintor.end()
    return _pixmap(imagem, tamanho)


def pixmap_da_acao(nome: str, tamanho: int = TAMANHO_BASE) -> QPixmap:
    """Imagem do ícone pelo nome. Lança KeyError se o nome não existir."""
    if nome.startswith("tamanho-"):
        return _tamanho(nome.split("-", 1)[1], tamanho)
    if nome.startswith("cor-"):
        return _cor(nome.split("-", 1)[1], tamanho)
    if nome.startswith("carimbo-"):
        return carimbos.icone(nome.split("-", 1)[1]).scaled(tamanho, tamanho, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    if nome.startswith("forma-"):
        return formas.icone(nome.split("-", 1)[1], tamanho)
    if nome.startswith("efeito-"):
        return magia.icone(nome.split("-", 1)[1], tamanho)
    if nome in icones.DESENHOS or nome in icones.ESPECIAIS:
        return icones.desenhar(nome, tamanho)
    raise KeyError(f"icone desconhecido: {nome}")


def e_colorido(nome: str) -> bool:
    """Ícones com cor própria (cores e borrachas). Os restantes são monocromáticos e o teclado
    pinta-os com a cor do texto do tema, para aparecerem em temas claros e escuros."""
    return nome.startswith("cor-") or nome in ("borracha", "borracha_riscos")


def nomes_necessarios(nomes_das_acoes: list[str]) -> list[str]:
    """Todos os nomes que a ponte deve enviar: os das ações e os dos teclados de navegação."""
    return sorted(set(nomes_das_acoes) | set(ICONES_EXTRA))
