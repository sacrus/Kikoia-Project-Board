"""Desenho e exportação do Quadro. O ecrã e as exportações usam a mesma função, para ficarem iguais."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgGenerator

from quadro.modelo import Quadro, Traco

EXTENSAO = ".kquadro"


def caminho_do_traco(traco: Traco, largura: int, altura: int) -> QPainterPath:
    caminho = QPainterPath()
    x, y = traco.pontos[0]
    caminho.moveTo(x * largura, y * altura)
    for x, y in traco.pontos[1:]:
        caminho.lineTo(x * largura, y * altura)
    if len(traco.pontos) == 1:
        caminho.lineTo(x * largura, y * altura)
    return caminho


def desenhar(pintor: QPainter, quadro: Quadro, largura: int, altura: int) -> None:
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.fillRect(QRect(0, 0, largura, altura), QColor(quadro.fundo))
    for imagem in (quadro.camada_base, quadro.camada_preench):
        if imagem is not None:
            pintor.drawImage(QRect(0, 0, largura, altura), imagem)
    for traco in quadro.tracos:
        if not traco.pontos:
            continue
        pintor.setPen(
            QPen(
                QColor(traco.cor),
                traco.espessura * altura,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        pintor.drawPath(caminho_do_traco(traco, largura, altura))
    for imagem in (quadro.camada_carimbos, quadro.camada_efeitos):
        if imagem is not None:
            pintor.drawImage(QRect(0, 0, largura, altura), imagem)


def pasta_desenhos() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    pasta = Path(base) / "Kikoia" / "Quadro" / "desenhos"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def nome_sugerido() -> str:
    return f"desenho-{datetime.now():%Y%m%d-%H%M%S}{EXTENSAO}"


def exportar_png(quadro: Quadro, caminho: Path, largura: int, altura: int) -> None:
    imagem = QImage(max(1, largura), max(1, altura), QImage.Format.Format_ARGB32)
    pintor = QPainter(imagem)
    desenhar(pintor, quadro, max(1, largura), max(1, altura))
    pintor.end()
    if not imagem.save(str(caminho), "PNG"):
        raise OSError(f"não foi possível escrever {caminho}")


def exportar_svg(quadro: Quadro, caminho: Path, largura: int, altura: int) -> None:
    largura, altura = max(1, largura), max(1, altura)
    gerador = QSvgGenerator()
    gerador.setFileName(str(caminho))
    gerador.setSize(QSize(largura, altura))
    gerador.setViewBox(QRect(0, 0, largura, altura))
    gerador.setTitle("Kikoia - Quadro Interativo")
    pintor = QPainter(gerador)
    desenhar(pintor, quadro, largura, altura)
    pintor.end()
