"""Camadas de imagem: balde de tinta e importação de imagens.

O balde de tinta lê a imagem completa (fundo, imagem importada, preenchimentos e riscos) e pinta a área
contínua que tem a mesma cor do ponto escolhido. Como os riscos fazem parte da leitura, o preenchimento
para nas linhas. O resultado vai para a camada de preenchimentos, que fica por baixo dos riscos.
"""

from __future__ import annotations

from array import array

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from quadro.desenho import desenhar
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro

TOLERANCIA_PADRAO = 24


def colocar_imagem(quadro: Quadro, imagem: QImage, x: float, y: float, altura: float) -> None:
    """Desenha a imagem na camada base, com o centro em (x, y) e a altura em fração da altura do quadro.
    A largura segue a proporção da imagem; o resto da camada base fica como estava."""
    escalada = imagem.scaledToHeight(max(1, round(altura * CAMADA_ALTURA)), Qt.TransformationMode.SmoothTransformation)
    base = quadro.camada_base.copy() if quadro.camada_base is not None else QImage(CAMADA_LARGURA, CAMADA_ALTURA, QImage.Format.Format_ARGB32)
    if quadro.camada_base is None:
        base.fill(0)
    pintor = QPainter(base)
    pintor.drawImage(
        round(x * CAMADA_LARGURA - escalada.width() / 2),
        round(y * CAMADA_ALTURA - escalada.height() / 2),
        escalada,
    )
    pintor.end()
    quadro.definir_camada_base(base)


def preparar_imagem(imagem: QImage) -> QImage:
    """Encaixa a imagem na área do quadro sem a distorcer. O resto fica transparente."""
    escalada = imagem.scaled(
        CAMADA_LARGURA,
        CAMADA_ALTURA,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    resultado = QImage(CAMADA_LARGURA, CAMADA_ALTURA, QImage.Format.Format_ARGB32)
    resultado.fill(0)
    pintor = QPainter(resultado)
    pintor.drawImage(
        (CAMADA_LARGURA - escalada.width()) // 2,
        (CAMADA_ALTURA - escalada.height()) // 2,
        escalada,
    )
    pintor.end()
    return resultado


def _composto(quadro: Quadro) -> QImage:
    imagem = QImage(CAMADA_LARGURA, CAMADA_ALTURA, QImage.Format.Format_ARGB32)
    pintor = QPainter(imagem)
    desenhar(pintor, quadro, CAMADA_LARGURA, CAMADA_ALTURA)
    pintor.end()
    return imagem


def _valores(imagem: QImage) -> array:
    valores = array("I")
    valores.frombytes(bytes(imagem.constBits())[: imagem.sizeInBytes()])
    return valores


def _parecidas(a: int, b: int, tolerancia: int) -> bool:
    return all(abs(((a >> canal) & 255) - ((b >> canal) & 255)) <= tolerancia for canal in (0, 8, 16))


def preencher(quadro: Quadro, x: float, y: float, cor: str, tolerancia: int = TOLERANCIA_PADRAO) -> bool:
    """Pinta a área contínua à volta de (x, y), com coordenadas normalizadas. Devolve False se nada mudar."""
    largura, altura = CAMADA_LARGURA, CAMADA_ALTURA
    composto = _valores(_composto(quadro))
    px = min(largura - 1, max(0, int(x * largura)))
    py = min(altura - 1, max(0, int(y * altura)))
    inicio = py * largura + px
    alvo = composto[inicio]
    marca = bytearray(largura * altura)
    marca[inicio] = 1
    pilha = [inicio]
    while pilha:
        i = pilha.pop()
        yy, xx = divmod(i, largura)
        vizinhos = []
        if xx > 0:
            vizinhos.append(i - 1)
        if xx < largura - 1:
            vizinhos.append(i + 1)
        if yy > 0:
            vizinhos.append(i - largura)
        if yy < altura - 1:
            vizinhos.append(i + largura)
        for j in vizinhos:
            if not marca[j] and _parecidas(composto[j], alvo, tolerancia):
                marca[j] = 1
                pilha.append(j)

    base = quadro.camada_preench
    if base is not None:
        atual = _valores(base)
    else:
        atual = array("I")
        atual.frombytes(bytes(largura * altura * 4))
    cor_q = QColor(cor)
    valor = 0xFF000000 | (cor_q.red() << 16) | (cor_q.green() << 8) | cor_q.blue()
    alterou = False
    for i, pintada in enumerate(marca):
        if pintada and atual[i] != valor:
            atual[i] = valor
            alterou = True
    if not alterou:
        return False
    dados = atual.tobytes()
    quadro.camada_preench = QImage(dados, largura, altura, largura * 4, QImage.Format.Format_ARGB32).copy()
    return True
