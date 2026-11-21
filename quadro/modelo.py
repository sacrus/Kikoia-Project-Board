"""Modelo do Quadro Interativo.

Os riscos são guardados em coordenadas normalizadas (0 a 1 em relação ao ecrã), para que o mesmo
desenho abra em ecrãs de tamanhos diferentes. A espessura e o raio da borracha são frações da altura.

Por baixo dos riscos há duas camadas de imagem (pixels), com resolução fixa e esticadas ao ecrã:
- camada de base: a imagem importada;
- camada de preenchimentos: o que o balde de tinta pinta.
"""

from __future__ import annotations

import base64
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

FORMATO = "kikoia-quadro"
VERSAO_FORMATO = 1
BRANCO = "#ffffff"
LIMITE_TRACOS = 100_000
LIMITE_BYTES = 50 * 1024 * 1024
LIMITE_HISTORICO = 100
CAMADA_LARGURA = 1600
CAMADA_ALTURA = 1000
_COR = re.compile(r"#[0-9a-fA-F]{6}")

CORES_FUNDO = ("#ffffff", "#fff8dc", "#e8f4ea", "#dbeafe", "#fde2e2", "#222222", "#000000")
CORES_CANETA = ("#000000", "#e11d48", "#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#ffffff")
CAMADAS = ("base", "preench", "carimbos", "efeitos")


class ErroQuadro(ValueError):
    """Ficheiro ou valor que o Quadro não aceita."""


@dataclass
class Traco:
    cor: str
    espessura: float
    pontos: list[tuple[float, float]] = field(default_factory=list)


def cor_caneta_automatica(fundo: str) -> str:
    """Caneta preta em fundos claros e branca em fundos escuros (pela luminância do fundo)."""
    r, g, b = (int(fundo[i : i + 2], 16) for i in (1, 3, 5))
    luminancia = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminancia >= 128 else BRANCO


def _distancia_ao_segmento(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    comprimento2 = dx * dx + dy * dy
    t = 0.0 if comprimento2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / comprimento2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distancia_ao_traco(traco: Traco, x: float, y: float, proporcao: float = 1.0) -> float:
    """Distância (em alturas de ecrã) do ponto ao traço. `proporcao` é largura/altura."""
    pontos = [(px * proporcao, py) for px, py in traco.pontos]
    px, py = x * proporcao, y
    if len(pontos) == 1:
        return math.hypot(px - pontos[0][0], py - pontos[0][1])
    return min(
        _distancia_ao_segmento(px, py, ax, ay, bx, by)
        for (ax, ay), (bx, by) in zip(pontos, pontos[1:])
    )


def _png(imagem: QImage | None) -> bytes | None:
    if imagem is None or imagem.isNull():
        return None
    armazenamento = QByteArray()
    buffer = QBuffer(armazenamento)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "PNG")
    return bytes(armazenamento)


def _de_png(dados: bytes) -> QImage:
    imagem = QImage()
    if not imagem.loadFromData(QByteArray(dados), "PNG"):
        raise ErroQuadro("imagem inválida")
    return imagem.convertToFormat(QImage.Format.Format_ARGB32)


def _propriedade_camada(nome: str) -> property:
    def obter(self) -> QImage | None:
        return self.camadas[nome]

    def definir(self, imagem: QImage | None) -> None:
        self.camadas[nome] = imagem

    return property(obter, definir)


class Quadro:
    camada_base = _propriedade_camada("base")
    camada_preench = _propriedade_camada("preench")
    camada_carimbos = _propriedade_camada("carimbos")
    camada_efeitos = _propriedade_camada("efeitos")

    def __init__(self, fundo: str = BRANCO) -> None:
        self.fundo = fundo
        self.tracos: list[Traco] = []
        self.camadas: dict[str, QImage | None] = {nome: None for nome in CAMADAS}
        self._desfazer: list[dict] = []
        self._refazer: list[dict] = []

    # --- histórico -----------------------------------------------------------------

    def _estado(self) -> dict:
        return {
            "fundo": self.fundo,
            "tracos": [Traco(t.cor, t.espessura, list(t.pontos)) for t in self.tracos],
            "camadas": {nome: _png(imagem) for nome, imagem in self.camadas.items()},
        }

    def _restaurar(self, estado: dict) -> None:
        self.fundo = estado["fundo"]
        self.tracos = [Traco(t.cor, t.espessura, list(t.pontos)) for t in estado["tracos"]]
        self.camadas = {nome: (_de_png(dados) if dados else None) for nome, dados in estado["camadas"].items()}

    def registar(self) -> None:
        """Guarda o estado atual antes de uma alteração. Cada gesto é um passo de desfazer."""
        self._desfazer.append(self._estado())
        del self._desfazer[:-LIMITE_HISTORICO]
        self._refazer.clear()

    def pode_desfazer(self) -> bool:
        return bool(self._desfazer)

    def pode_refazer(self) -> bool:
        return bool(self._refazer)

    def desfazer(self) -> bool:
        if not self._desfazer:
            return False
        self._refazer.append(self._estado())
        self._restaurar(self._desfazer.pop())
        return True

    def refazer(self) -> bool:
        if not self._refazer:
            return False
        self._desfazer.append(self._estado())
        self._restaurar(self._refazer.pop())
        return True

    # --- edição --------------------------------------------------------------------

    def comecar_traco(self, cor: str, espessura: float, x: float, y: float) -> Traco:
        traco = Traco(cor, espessura, [(x, y)])
        self.tracos.append(traco)
        return traco

    def acrescentar_ponto(self, traco: Traco, x: float, y: float) -> None:
        traco.pontos.append((x, y))

    def tracos_perto(self, x: float, y: float, raio: float, proporcao: float = 1.0) -> list[Traco]:
        return [t for t in self.tracos if distancia_ao_traco(t, x, y, proporcao) <= raio]

    def traco_em(self, x: float, y: float, tolerancia: float, proporcao: float = 1.0) -> Traco | None:
        """O traço mais recente que passa pelo ponto (o último desenhado fica por cima)."""
        perto = self.tracos_perto(x, y, tolerancia, proporcao)
        return perto[-1] if perto else None

    def tracos_na_area(self, x0: float, y0: float, x1: float, y1: float) -> list[Traco]:
        esquerda, direita = sorted((x0, x1))
        topo, base = sorted((y0, y1))
        return [
            t
            for t in self.tracos
            if any(esquerda <= px <= direita and topo <= py <= base for px, py in t.pontos)
        ]

    def apagar_perto(self, x: float, y: float, raio: float, proporcao: float = 1.0) -> int:
        """Remove os traços que passam a menos de `raio` do ponto. `proporcao` é largura/altura."""
        alvos = self.tracos_perto(x, y, raio, proporcao)
        self.remover(alvos)
        return len(alvos)

    def remover(self, alvos: list[Traco]) -> None:
        ids = {id(t) for t in alvos}
        self.tracos = [t for t in self.tracos if id(t) not in ids]

    def mudar_cor(self, alvos: list[Traco], cor: str) -> None:
        for traco in alvos:
            traco.cor = cor

    def limpar(self) -> None:
        self.tracos = []
        for nome in ("preench", "carimbos", "efeitos"):
            self.camadas[nome] = None

    def tem_pixels(self) -> bool:
        return any(self.camadas[nome] is not None for nome in ("preench", "carimbos", "efeitos"))

    def apagar_pixels(self, x: float, y: float, raio: float) -> None:
        """Torna transparentes os pixels de carimbos, efeitos e preenchimentos dentro do disco.
        A imagem importada (base) não é apagada: para a retirar há o botão «Remover imagem»."""
        cx, cy = x * CAMADA_LARGURA, y * CAMADA_ALTURA
        r = raio * CAMADA_ALTURA
        for nome in ("preench", "carimbos", "efeitos"):
            imagem = self.camadas[nome]
            if imagem is None:
                continue
            pintor = QPainter(imagem)
            pintor.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(0, 0, 0))
            pintor.drawEllipse(QPointF(cx, cy), r, r)
            pintor.end()

    def definir_camada_base(self, imagem: QImage | None) -> None:
        if imagem is None:
            self.camada_base = None
            return
        self.camada_base = imagem.convertToFormat(QImage.Format.Format_ARGB32)

    # --- ficheiros -----------------------------------------------------------------

    def para_dados(self) -> dict:
        dados = {
            "formato": FORMATO,
            "versao": VERSAO_FORMATO,
            "fundo": self.fundo,
            "tracos": [
                {"cor": t.cor, "espessura": t.espessura, "pontos": [[x, y] for x, y in t.pontos]}
                for t in self.tracos
            ],
        }
        for nome, imagem in self.camadas.items():
            png = _png(imagem)
            if png is not None:
                dados[f"camada_{nome}"] = base64.b64encode(png).decode("ascii")
        return dados

    def guardar(self, caminho: Path) -> None:
        Path(caminho).write_text(json.dumps(self.para_dados(), ensure_ascii=False), encoding="utf-8")

    @classmethod
    def carregar(cls, caminho: Path) -> Quadro:
        caminho = Path(caminho)
        try:
            if caminho.stat().st_size > LIMITE_BYTES:
                raise ErroQuadro("ficheiro demasiado grande")
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as erro:
            raise ErroQuadro("não foi possível ler o ficheiro") from erro
        return cls.de_dados(dados)

    @classmethod
    def de_dados(cls, dados: object) -> Quadro:
        if not isinstance(dados, dict) or dados.get("formato") != FORMATO:
            raise ErroQuadro("não é um quadro Kikoia")
        if dados.get("versao") != VERSAO_FORMATO:
            raise ErroQuadro("versão do ficheiro não suportada")
        tracos = dados.get("tracos")
        if not isinstance(tracos, list) or len(tracos) > LIMITE_TRACOS:
            raise ErroQuadro("lista de traços inválida")
        quadro = cls(_cor(dados.get("fundo")))
        for item in tracos:
            if not isinstance(item, dict):
                raise ErroQuadro("traço inválido")
            espessura = _numero(item.get("espessura"))
            if not 0 < espessura <= 1:
                raise ErroQuadro("espessura inválida")
            pontos_dados = item.get("pontos")
            if not isinstance(pontos_dados, list) or not pontos_dados:
                raise ErroQuadro("traço sem pontos")
            pontos = []
            for ponto in pontos_dados:
                if not isinstance(ponto, list) or len(ponto) != 2:
                    raise ErroQuadro("ponto inválido")
                pontos.append((_fracao(ponto[0]), _fracao(ponto[1])))
            quadro.tracos.append(Traco(_cor(item.get("cor")), espessura, pontos))
        for nome in CAMADAS:
            if f"camada_{nome}" in dados:
                quadro.camadas[nome] = _camada(dados[f"camada_{nome}"])
        return quadro


def _camada(valor: object) -> QImage:
    if not isinstance(valor, str):
        raise ErroQuadro("camada inválida")
    try:
        dados = base64.b64decode(valor, validate=True)
    except ValueError as erro:
        raise ErroQuadro("camada inválida") from erro
    return _de_png(dados)


def _cor(valor: object) -> str:
    if not isinstance(valor, str) or not _COR.fullmatch(valor):
        raise ErroQuadro("cor inválida")
    return valor


def _numero(valor: object) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ErroQuadro("valor inválido")
    return float(valor)


def _fracao(valor: object) -> float:
    numero = _numero(valor)
    if not 0 <= numero <= 1:
        raise ErroQuadro("coordenada fora do ecrã")
    return numero
