"""Janela do Quadro: área de desenho, menu de bolhas, varinha, definições e ficheiros."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QShortcut,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from quadro.correio.modelo import Anexo
from quadro.desenho import (
    EXTENSAO,
    caminho_do_traco,
    desenhar,
    exportar_png,
    exportar_svg,
    nome_sugerido,
    pasta_desenhos,
)
from quadro import acoes, camadas, carimbos, formas, icones, jxl, magia, menu_prefs, tema_partilhado, textos

from quadro.icones_acoes import CORES_ACAO
from quadro.correio import contas as contas_correio
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA
from quadro.correio import voz
from quadro.correio.servidor import contar_nao_lidas
from quadro import openverse
from quadro.correio import supervisor as supervisor_correio
from quadro.janela_correio import DialogoCorreio, DialogoEscrever, correr_em_fundo, verificar_supervisor
from quadro.janela_imagens import DialogoPesquisaImagens
from quadro.janela_jogos import DialogoJogos
from quadro.modelo import (
    CORES_CANETA,
    CORES_FUNDO,
    ErroQuadro,
    Quadro,
    Traco,
    cor_caneta_automatica,
)

ESPESSURAS_CANETA = (0.003, 0.008, 0.016, 0.03)
DIAMETROS_CANETA = (6, 12, 20, 28)
RAIOS_BORRACHA = (0.012, 0.025, 0.045, 0.07)
DIAMETROS_BORRACHA = (8, 14, 22, 30)
TOLERANCIA_VARINHA = 0.012
CARIMBO_TAMANHOS = (0.06, 0.12, 0.2, 0.3)
CARIMBO_DIAMETROS = (12, 20, 30, 40)
RAIOS_MAGIA = (0.02, 0.04, 0.07, 0.1)
DIAMETROS_MAGIA = (12, 20, 30, 40)
TEXTO_TAMANHOS = (0.04, 0.07, 0.11, 0.16)
POLIGONO_FECHO = 0.03
TEXTO_DIAMETROS = (12, 20, 30, 40)
LIMIAR_AREA = 0.005
TEMPO_AVISO_MS = 6000
TEMPO_CONTROLO_TECLADO_S = 3.0
AVISO_MENU = "Toque com 3 dedos, ou carregue na tecla ESC para mostrar o menu"

TAMANHO_MIN_BOLHA = 34
TAMANHO_MAX_BOLHA = 64


class _BotaoEsfera(QPushButton):
    """Botao circular com aspeto de esfera 3D translucida (vidro fosco/brilhante)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cor_esfera: QColor | None = None
        self._sob_rato = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def definir_cor_esfera(self, cor: str | None) -> None:
        self._cor_esfera = QColor(cor) if cor else None
        self.update()

    def enterEvent(self, evento) -> None:  # noqa: N802
        self._sob_rato = True
        self.update()
        super().enterEvent(evento)

    def leaveEvent(self, evento) -> None:  # noqa: N802
        self._sob_rato = False
        self.update()
        super().leaveEvent(evento)

    def paintEvent(self, evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = float(self.width()), float(self.height())
        lado = min(w, h)
        margem = 2.5
        esfera = QRectF((w - lado) / 2 + margem, (h - lado) / 2 + margem, lado - 2 * margem, lado - 2 * margem)
        cx, cy = esfera.center().x(), esfera.center().y()
        raio = esfera.width() / 2.0

        if not self.isEnabled():
            pintor.setOpacity(0.42)

        # Sombra suave por baixo da esfera para dar profundidade flutuante
        sombra = QRadialGradient(cx, cy + raio * 0.14, raio * 1.05)
        sombra.setColorAt(0.0, QColor(0, 0, 0, 95))
        sombra.setColorAt(0.78, QColor(0, 0, 0, 45))
        sombra.setColorAt(1.0, QColor(0, 0, 0, 0))
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(sombra)
        pintor.drawEllipse(QPointF(cx, cy + raio * 0.12), raio * 1.02, raio * 1.02)

        # Corpo da esfera 3D translucida (gradiente radial deslocado para o foco de luz superior esquerdo)
        foco = QPointF(cx - raio * 0.34, cy - raio * 0.36)
        grad = QRadialGradient(QPointF(cx, cy), raio, foco)
        ativo = self.isChecked()
        premido = self.isDown()

        if self._cor_esfera is not None:
            base = QColor(self._cor_esfera)
            clara = base.lighter(145)
            escura = base.darker(155)
            clara.setAlpha(235)
            base.setAlpha(225)
            escura.setAlpha(242)
            grad.setColorAt(0.0, clara)
            grad.setColorAt(0.55, base)
            grad.setColorAt(1.0, escura)
        elif ativo:
            grad.setColorAt(0.0, QColor(125, 195, 255, 235))
            grad.setColorAt(0.48, QColor(37, 99, 235, 230))
            grad.setColorAt(1.0, QColor(23, 52, 138, 245))
        elif premido:
            grad.setColorAt(0.0, QColor(85, 100, 128, 225))
            grad.setColorAt(0.55, QColor(38, 48, 66, 232))
            grad.setColorAt(1.0, QColor(18, 24, 36, 245))
        elif self._sob_rato:
            grad.setColorAt(0.0, QColor(115, 132, 160, 212))
            grad.setColorAt(0.52, QColor(52, 63, 84, 212))
            grad.setColorAt(1.0, QColor(24, 31, 44, 232))
        else:
            grad.setColorAt(0.0, QColor(92, 106, 132, 192))
            grad.setColorAt(0.52, QColor(38, 46, 62, 198))
            grad.setColorAt(1.0, QColor(18, 23, 34, 222))

        pintor.setBrush(grad)
        pintor.drawEllipse(esfera)

        # Reflexo especular de vidro no topo esquerdo
        brilho_rect = QRectF(
            esfera.left() + esfera.width() * 0.16,
            esfera.top() + esfera.height() * 0.08,
            esfera.width() * 0.68,
            esfera.height() * 0.38,
        )
        brilho = QLinearGradient(brilho_rect.topLeft(), brilho_rect.bottomLeft())
        brilho.setColorAt(0.0, QColor(255, 255, 255, 135 if ativo or self._sob_rato else 108))
        brilho.setColorAt(0.65, QColor(255, 255, 255, 28))
        brilho.setColorAt(1.0, QColor(255, 255, 255, 0))
        pintor.setBrush(brilho)
        pintor.drawEllipse(brilho_rect)

        # Reflexo subtil de luz ambiente na borda inferior direita
        reflexo_inf = QRectF(
            esfera.left() + esfera.width() * 0.24,
            esfera.top() + esfera.height() * 0.66,
            esfera.width() * 0.52,
            esfera.height() * 0.24,
        )
        pintor.setBrush(QColor(255, 255, 255, 30))
        pintor.drawEllipse(reflexo_inf)

        # Contorno de vidro translucido (mais luminoso quando ativo)
        cor_borda = QColor(191, 219, 254, 225) if ativo else QColor(255, 255, 255, 110 if self._sob_rato else 76)
        pintor.setPen(QPen(cor_borda, 1.6 if ativo else 1.1))
        pintor.setBrush(Qt.BrushStyle.NoBrush)
        pintor.drawEllipse(esfera.adjusted(0.6, 0.6, -0.6, -0.6))

        # Icone centrado
        if not self.icon().isNull():
            tam_ic = self.iconSize()
            iw = min(tam_ic.width(), int(esfera.width() * 0.62))
            ih = min(tam_ic.height(), int(esfera.height() * 0.62))
            pix = self.icon().pixmap(iw, ih)
            # Se a bola da cor for muito clara (ex.: branco/amarelo), pinta o icone a escuro para contraste
            if self._cor_esfera is not None:
                lum = (0.299 * self._cor_esfera.red() + 0.587 * self._cor_esfera.green() + 0.114 * self._cor_esfera.blue()) / 255.0
                if lum > 0.72:
                    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                    p_ic = QPainter(img)
                    p_ic.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    p_ic.fillRect(img.rect(), QColor("#1E293B"))
                    p_ic.end()
                    pix = QPixmap.fromImage(img)
            ix = round(cx - pix.width() / 2)
            iy = round(cy - pix.height() / 2)
            pintor.drawPixmap(ix, iy, pix)

        # Badge numerico discreto (usado no correio quando ha mensagens por ler)
        texto = self.text().strip()
        if texto:
            digitos = "".join(ch for ch in texto if ch.isdigit())
            if digitos:
                badge_r = max(9.0, raio * 0.34)
                bx = esfera.right() - badge_r * 0.75
                by = esfera.top() + badge_r * 0.75
                pintor.setPen(QPen(QColor("#FFFFFF"), 1.4))
                pintor.setBrush(QColor("#EF4444"))
                pintor.drawEllipse(QPointF(bx, by), badge_r, badge_r)
                fonte = QFont(self.font())
                fonte.setPixelSize(max(10, int(badge_r * 1.15)))
                fonte.setBold(True)
                pintor.setFont(fonte)
                pintor.setPen(QColor("#FFFFFF"))
                pintor.drawText(
                    QRectF(bx - badge_r, by - badge_r, badge_r * 2, badge_r * 2),
                    Qt.AlignmentFlag.AlignCenter,
                    digitos,
                )

        pintor.end()


def _estilo_bolha(tamanho: int) -> str:
    raio = tamanho // 2
    letra = max(14, int(tamanho * 0.4))
    return (
        "QPushButton {"
        " background: qradialgradient(cx:0.32, cy:0.28, radius:0.8, stop:0 rgba(92, 106, 132, 220),"
        " stop:0.55 rgba(38, 46, 62, 232), stop:1 rgba(18, 23, 34, 245));"
        f" color: white; border: 1.2px solid rgba(255, 255, 255, 95); border-radius: {raio}px;"
        f" font-size: {letra}px; font-weight: bold; }}"
        " QPushButton:checked { background: #2563eb; border-color: #bfdbfe; }"
        " QPushButton:hover { background: qradialgradient(cx:0.32, cy:0.28, radius:0.8,"
        " stop:0 rgba(120, 140, 175, 235), stop:0.55 rgba(52, 63, 84, 238), stop:1 rgba(24, 31, 44, 248));"
        " border-color: rgba(255, 255, 255, 160); }"
        " QPushButton:disabled { color: #888888; background: rgba(40, 46, 58, 120); }"
    )


def _estilo_minimizar() -> str:
    return (
        "QPushButton { background: rgba(30, 38, 54, 130); color: white;"
        " border: 1px solid rgba(255, 255, 255, 70); border-radius: 24px; }"
        " QPushButton:hover, QPushButton:pressed { background: rgba(37, 99, 235, 220);"
        " border: 1px solid rgba(191, 219, 254, 210); }"
    )


def _amostra(cor: str, tamanho: int = 36) -> QPushButton:
    botao = QPushButton()
    botao.setFixedSize(tamanho, tamanho)
    botao.setCursor(Qt.CursorShape.PointingHandCursor)
    botao.setStyleSheet(
        f"QPushButton {{ background: {cor}; border: 2px solid rgba(255, 255, 255, 160); border-radius: {tamanho // 2}px; }}"
        f" QPushButton:hover {{ border: 2px solid #60A5FA; }}"
    )
    return botao


class _AmostraTamanho(QWidget):
    """Circulo de pre-visualizacao que acompanha ao vivo a posicao da barra de arraste."""

    def __init__(self, diametro: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._diametro = diametro
        self.setFixedSize(36, 36)

    def definir_diametro(self, diametro: float) -> None:
        self._diametro = diametro
        self.update()

    def paintEvent(self, evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        raio = max(3.0, min(15.0, self._diametro / 2.0))
        pintor.setPen(QPen(QColor(147, 197, 253, 180), 1.4))
        pintor.setBrush(QBrush(QColor("#FFFFFF")))
        pintor.drawEllipse(QPointF(18.0, 18.0), raio, raio)
        pintor.end()


class _BarraTamanho(QFrame):
    """Barra de arraste continua do tamanho mais pequeno ao maior, sempre visivel sobre qualquer fundo."""

    valor_alterado = Signal(float)
    _PASSOS = 1000

    def __init__(
        self,
        minimo: float,
        maximo: float,
        atual: float,
        diametro_min: int = 8,
        diametro_max: int = 30,
        *,
        com_fundo: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimo = float(minimo)
        self._maximo = float(maximo)
        self._d_min = float(diametro_min)
        self._d_max = float(diametro_max)
        self.setObjectName("barraTamanho")
        fundo_css = (
            "QFrame#barraTamanho { background: rgba(24, 31, 46, 232);"
            " border: 1px solid rgba(255, 255, 255, 70); border-radius: 18px; }"
            if com_fundo
            else "QFrame#barraTamanho { background: transparent; border: none; }"
        )
        self.setStyleSheet(
            fundo_css
            + " QSlider::groove:horizontal { height: 6px; background: rgba(255, 255, 255, 55); border-radius: 3px; }"
            + " QSlider::sub-page:horizontal { background: #3B82F6; border-radius: 3px; }"
            + " QSlider::handle:horizontal { background: #FFFFFF; border: 2px solid #2563EB;"
            + " width: 18px; height: 18px; margin: -7px 0; border-radius: 10px; }"
            + " QSlider::handle:horizontal:hover { background: #EFF6FF; border-color: #60A5FA; }"
        )

        ponto_min = _AmostraTamanho(6)
        ponto_min.setFixedSize(16, 36)
        self._deslizador = QSlider(Qt.Orientation.Horizontal)
        self._deslizador.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._deslizador.setRange(0, self._PASSOS)
        self._deslizador.setMinimumWidth(160)
        self._deslizador.setCursor(Qt.CursorShape.PointingHandCursor)
        self._amostra = _AmostraTamanho(self._d_min)

        linha = QHBoxLayout(self)
        linha.setContentsMargins(10, 2, 10, 2)
        linha.setSpacing(8)
        linha.addWidget(ponto_min)
        linha.addWidget(self._deslizador, 1)
        linha.addWidget(self._amostra)

        self._deslizador.valueChanged.connect(self._ao_mover)
        self.definir_valor(atual)

    def _fracao(self, valor: float) -> float:
        if self._maximo <= self._minimo:
            return 0.0
        return max(0.0, min(1.0, (valor - self._minimo) / (self._maximo - self._minimo)))

    def definir_valor(self, valor: float) -> None:
        frac = self._fracao(valor)
        self._deslizador.blockSignals(True)
        self._deslizador.setValue(round(frac * self._PASSOS))
        self._deslizador.blockSignals(False)
        self._amostra.definir_diametro(self._d_min + frac * (self._d_max - self._d_min))

    def _ao_mover(self, passo: int) -> None:
        frac = passo / self._PASSOS
        valor = self._minimo + frac * (self._maximo - self._minimo)
        self._amostra.definir_diametro(self._d_min + frac * (self._d_max - self._d_min))
        self.valor_alterado.emit(valor)


class _Bolinha(QWidget):
    clicado = Signal()

    def __init__(self, diametro: int, selecionada: bool) -> None:
        super().__init__()
        self._diametro = diametro
        self._selecionada = selecionada
        self.setFixedSize(44, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        centro = QPointF(22, 22)
        if self._selecionada:
            pintor.setPen(QPen(QColor("#2563eb"), 3))
            pintor.setBrush(Qt.BrushStyle.NoBrush)
            pintor.drawEllipse(centro, 20, 20)
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QBrush(QColor("#ffffff")))
        pintor.drawEllipse(centro, self._diametro / 2, self._diametro / 2)
        pintor.end()

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clicado.emit()


class Tela(QWidget):
    alterou = Signal()
    toque_com_tres = Signal()

    def __init__(self, quadro: Quadro) -> None:
        super().__init__()
        self.quadro = quadro
        self.ferramenta = "caneta"
        self.cor_caneta: str | None = None
        self.espessura = ESPESSURAS_CANETA[1]
        self.raio_borracha = RAIOS_BORRACHA[1]
        self.selecao: list[Traco] = []
        self._traco: Traco | None = None
        self._registado = False
        self._area: tuple[float, float, float, float] | None = None
        self.carimbo = "estrela"
        self.tamanho_carimbo = 0.12
        self.efeito = "desfocar"
        self.tamanho_texto = TEXTO_TAMANHOS[1]
        self._caixa = None
        self._colocacao: CaixaColocacao | None = None
        self._alvo: tuple[str, object, str | None] | None = None
        self.raio_magia = 0.04
        self._pincel: magia.Pincel | None = None
        self.forma = "retangulo"
        self._forma: tuple[float, float, float, float] | None = None
        self._poligono: list[tuple[float, float]] | None = None
        self._cursor: tuple[float, float] | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)

    def cor_ativa(self) -> str:
        return self.cor_caneta or cor_caneta_automatica(self.quadro.fundo)

    def limpar_selecao(self) -> None:
        self.selecao = []
        self._area = None
        self._poligono = None
        self._cursor = None

    def area_desenho(self) -> QRect:
        """A área do desenho: sempre com a proporção do quadro (1,6), centrada na janela.
        Assim o desenho não estica, qualquer que seja o tamanho da janela."""
        largura, altura = max(1, self.width()), max(1, self.height())
        proporcao = CAMADA_LARGURA / CAMADA_ALTURA
        if largura / altura > proporcao:
            altura_area = altura
            largura_area = int(altura * proporcao)
        else:
            largura_area = largura
            altura_area = int(largura / proporcao)
        return QRect((largura - largura_area) // 2, (altura - altura_area) // 2, largura_area, altura_area)

    def _normalizar(self, posicao: QPointF) -> tuple[float, float]:
        area = self.area_desenho()
        largura, altura = max(1, area.width()), max(1, area.height())
        x = (posicao.x() - area.x()) / largura
        y = (posicao.y() - area.y()) / altura
        return min(1.0, max(0.0, x)), min(1.0, max(0.0, y))

    def _proporcao(self) -> float:
        area = self.area_desenho()
        return max(1, area.width()) / max(1, area.height())

    def _apagar(self, x: float, y: float) -> None:
        alvo = self.quadro.tracos_perto(x, y, self.raio_borracha, self._proporcao())
        com_pixels = self.ferramenta == "borracha" and self.quadro.tem_pixels()
        if not alvo and not com_pixels:
            return
        if not self._registado:
            self.quadro.registar()
            self._registado = True
        self.quadro.remover(alvo)
        if com_pixels:
            self.quadro.apagar_pixels(x, y, self.raio_borracha)
        self.alterou.emit()
        self.update()

    def event(self, evento) -> bool:
        if evento.type() in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate) and len(evento.points()) >= 3:
            self.toque_com_tres.emit()
        return super().event(evento)

    def paintEvent(self, evento) -> None:  # noqa: N802 (nome do Qt)
        pintor = QPainter(self)
        pintor.fillRect(self.rect(), QColor("#2b2b2b"))
        area = self.area_desenho()
        pintor.translate(area.x(), area.y())
        largura, altura = area.width(), area.height()
        desenhar(pintor, self.quadro, largura, altura)
        for traco in self.selecao:
            if traco.pontos:
                pintor.setPen(
                    QPen(
                        QColor(0, 120, 255, 150),
                        traco.espessura * altura + 8,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin,
                    )
                )
                pintor.drawPath(caminho_do_traco(traco, largura, altura))
        if self._forma is not None:
            x0, y0, x1, y1 = self._forma
            contorno = formas.pontos(self.forma, x0, y0, x1, y1)
            pintor.setPen(
                QPen(
                    QColor(self.cor_ativa()),
                    self.espessura * altura,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            caminho = QPainterPath()
            caminho.moveTo(contorno[0][0] * largura, contorno[0][1] * altura)
            for px, py in contorno[1:]:
                caminho.lineTo(px * largura, py * altura)
            pintor.drawPath(caminho)
        if self._poligono:
            visiveis = self._poligono + ([self._cursor] if self._cursor else [])
            pintor.setPen(
                QPen(
                    QColor(self.cor_ativa()),
                    self.espessura * altura,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            caminho_v = QPainterPath()
            caminho_v.moveTo(visiveis[0][0] * largura, visiveis[0][1] * altura)
            for px, py in visiveis[1:]:
                caminho_v.lineTo(px * largura, py * altura)
            pintor.drawPath(caminho_v)
        if self._area is not None:
            x0, y0, x1, y1 = self._area
            retangulo = QRectF(x0 * largura, y0 * altura, (x1 - x0) * largura, (y1 - y0) * altura).normalized()
            pintor.setPen(QPen(QColor("#2563eb"), 2, Qt.PenStyle.DashLine))
            pintor.setBrush(QBrush(QColor(37, 99, 235, 40)))
            pintor.drawRect(retangulo)
        pintor.end()

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.RightButton and self._poligono is not None:
            self.limpar_selecao()
            self.update()
            return
        if evento.button() != Qt.MouseButton.LeftButton:
            return
        x, y = self._normalizar(evento.position())
        if self._colocacao is not None:
            self._colocacao.definir_posicao(x, y)
            return
        if self.ferramenta in ("borracha", "borracha_riscos"):
            self._registado = False
            self._apagar(x, y)
        elif self.ferramenta == "balde":
            self.quadro.registar()
            camadas.preencher(self.quadro, x, y, self.cor_ativa())
            self.alterou.emit()
            self.update()
        elif self.ferramenta == "texto":
            self._tocar_texto(x, y)
        elif self.ferramenta == "forma" and self.forma == "poligono":
            self._clique_poligono(x, y)
        elif self.ferramenta == "forma":
            self._forma = (x, y, x, y)
            self.update()
        elif self.ferramenta == "carimbo":
            self._abrir_carimbo(x, y)
        elif self.ferramenta == "magia":
            self.quadro.registar()
            self._pincel = magia.Pincel(self.quadro, self.efeito, self.cor_ativa())
            self._pincel.aplicar(x, y, self.raio_magia)
            self.update()
        elif self.ferramenta == "varinha":
            escolhido = self.quadro.traco_em(x, y, TOLERANCIA_VARINHA, self._proporcao())
            if escolhido is not None:
                self.selecao = [escolhido]
            else:
                self.selecao = []
                self._area = (x, y, x, y)
            self.alterou.emit()
            self.update()
        else:
            self.quadro.registar()
            self._traco = self.quadro.comecar_traco(self.cor_ativa(), self.espessura, x, y)
            self.update()

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if self._poligono is not None:
            self._cursor = self._normalizar(evento.position())
            self.update()
        if not evento.buttons() & Qt.MouseButton.LeftButton:
            return
        x, y = self._normalizar(evento.position())
        if self.ferramenta in ("borracha", "borracha_riscos"):
            self._apagar(x, y)
        elif self.ferramenta == "varinha":
            if self._area is not None:
                self._area = (self._area[0], self._area[1], x, y)
                self.update()
        elif self.ferramenta == "forma":
            if self._forma is not None:
                self._forma = (self._forma[0], self._forma[1], x, y)
                self.update()
        elif self.ferramenta == "magia":
            if self._pincel is not None:
                self._pincel.aplicar(x, y, self.raio_magia)
                self.update()
        elif self._traco is not None:
            self.quadro.acrescentar_ponto(self._traco, x, y)
            self.update()

    def _tocar_texto(self, x: float, y: float) -> None:
        if self._caixa is None:
            self._caixa = CaixaTexto(self, x, y, self.tamanho_texto)
        else:
            self._caixa.definir_posicao(x, y)

    def confirmar_texto(self) -> None:
        caixa = self._caixa
        if caixa is None:
            return
        texto, x, y, tamanho = caixa.texto(), caixa.x_norm, caixa.y_norm, caixa.tamanho
        self.tamanho_texto = tamanho
        self.cancelar_texto()
        if not texto.strip():
            return
        self.quadro.registar()
        textos.escrever(self.quadro, texto, x, y, tamanho, self.cor_ativa())
        self.alterou.emit()
        self.update()

    def cancelar_texto(self) -> None:
        if self._caixa is None:
            return
        self._caixa.hide()
        self._caixa.deleteLater()
        self._caixa = None
        self.update()

    def _abrir_carimbo(self, x: float, y: float) -> None:
        """O carimbo não é colocado logo: abre a caixa com a prévia, até ✔ ou ✖."""
        self._abrir_colocacao(x, y, "carimbo", None, self._previa_carimbo, self.tamanho_carimbo)

    def iniciar_imagem(self, imagem: QImage) -> None:
        """Uma imagem importada abre no centro do quadro, para ser posicionada e dimensionada."""
        previa = lambda altura_fracao, altura: QPixmap.fromImage(  # noqa: E731
            imagem.scaledToHeight(max(8, int(altura_fracao * altura)), Qt.TransformationMode.SmoothTransformation)
        )
        self._abrir_colocacao(0.5, 0.5, "imagem", imagem, previa, 0.5)

    def _previa_carimbo(self, tamanho: float, altura: int) -> QPixmap:
        return carimbos.previa(self.carimbo, self.cor_ativa(), max(8, int(tamanho * altura)))

    def _abrir_colocacao(self, x, y, tipo, dados, previa, tamanho) -> None:
        self.cancelar_colocacao()
        self._alvo = (tipo, dados, None)
        self._colocacao = CaixaColocacao(self, x, y, tamanho, previa)

    def atualizar_colocacao(self) -> None:
        if self._colocacao is not None:
            self._colocacao.atualizar_aparencia()

    def ao_mudar_ferramenta(self, nome: str) -> None:
        """Um carimbo por colocar cancela-se ao trocar de ferramenta. Uma imagem fica até ✔ ou ✖."""
        if self._alvo is not None and self._alvo[0] == "carimbo" and nome != "carimbo":
            self.cancelar_colocacao()

    def confirmar_colocacao(self) -> None:
        caixa, alvo = self._colocacao, self._alvo
        if caixa is None or alvo is None:
            return
        tipo, dados, _ = alvo
        x, y, tamanho = caixa.x_norm, caixa.y_norm, caixa.tamanho
        cor = self.cor_ativa()
        self.cancelar_colocacao()
        self.quadro.registar()
        if tipo == "carimbo":
            carimbos.tracar(self.quadro, self.carimbo, x, y, tamanho, cor)
        else:
            camadas.colocar_imagem(self.quadro, dados, x, y, tamanho)
        self.alterou.emit()
        self.update()

    def cancelar_colocacao(self) -> None:
        if self._colocacao is None:
            return
        self._colocacao.hide()
        self._colocacao.deleteLater()
        self._colocacao = None
        self._alvo = None
        self.update()

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        if self._caixa is not None:
            self._caixa.atualizar_aparencia()
        if self._colocacao is not None:
            self._colocacao.atualizar_aparencia()

    def _clique_poligono(self, x: float, y: float) -> None:
        if self._poligono is None:
            self._poligono = [(x, y)]
            self._cursor = (x, y)
            self.update()
            return
        primeiro = self._poligono[0]
        perto = math.hypot((x - primeiro[0]) * self._proporcao(), y - primeiro[1]) <= POLIGONO_FECHO
        if len(self._poligono) >= 3 and perto:
            self._fechar_poligono(True)
        else:
            self._poligono.append((x, y))
            self.update()

    def _fechar_poligono(self, fechado: bool) -> None:
        pontos = self._poligono or []
        self._poligono = None
        self._cursor = None
        limpos: list[tuple[float, float]] = []
        for ponto in pontos:
            if not limpos or math.hypot(ponto[0] - limpos[-1][0], ponto[1] - limpos[-1][1]) > 1e-4:
                limpos.append(ponto)
        if len(limpos) < 2:
            self.update()
            return
        contorno = limpos + [limpos[0]] if fechado and len(limpos) >= 3 else limpos
        self.quadro.registar()
        traco = self.quadro.comecar_traco(self.cor_ativa(), self.espessura, *contorno[0])
        for ponto in contorno[1:]:
            self.quadro.acrescentar_ponto(traco, *ponto)
        self.alterou.emit()
        self.update()

    def mouseDoubleClickEvent(self, evento) -> None:  # noqa: N802
        if self.ferramenta == "forma" and self.forma == "poligono" and self._poligono:
            self._fechar_poligono(False)
            return
        super().mouseDoubleClickEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        if self._forma is not None:
            x0, y0, x1, y1 = self._forma
            self._forma = None
            if abs(x1 - x0) > LIMIAR_AREA or abs(y1 - y0) > LIMIAR_AREA:
                self.quadro.registar()
                contorno = formas.pontos(self.forma, x0, y0, x1, y1)
                traco = self.quadro.comecar_traco(self.cor_ativa(), self.espessura, *contorno[0])
                for ponto in contorno[1:]:
                    self.quadro.acrescentar_ponto(traco, *ponto)
                self.alterou.emit()
            self.update()
        if self._area is not None:
            x0, y0, x1, y1 = self._area
            self._area = None
            if abs(x1 - x0) > LIMIAR_AREA or abs(y1 - y0) > LIMIAR_AREA:
                self.selecao = self.quadro.tracos_na_area(x0, y0, x1, y1)
            self.alterou.emit()
            self.update()
        self._traco = None
        self._pincel = None


class Menu(QWidget):
    def __init__(self, janela: JanelaQuadro) -> None:
        super().__init__(janela.tela)
        self.janela = janela
        self.tela = janela.tela
        self._paleta: QFrame | None = None
        self._grelha = QGridLayout(self)
        self._grelha.setContentsMargins(0, 0, 0, 0)
        self._tamanho = TAMANHO_MAX_BOLHA
        self._botoes: list[QPushButton] = []
        self._caneta = self._bolha(
            "caneta", "Caneta", lambda _=False: self._ferramenta_com_tamanhos("caneta", self._caneta))
        self._borracha = self._bolha(
            "borracha", "Borracha", lambda _=False: self._ferramenta_com_tamanhos("borracha", self._borracha)
        )
        self._borracha_riscos = self._bolha("", "Borracha de riscos", lambda _=False: self._ferramenta_com_tamanhos("borracha_riscos", self._borracha_riscos))
        self._borracha_riscos.setIcon(QIcon(icones.desenhar("borracha_riscos")))
        self._varinha = self._bolha(
            "varinha", "Varinha mágica", lambda _=False: self._escolher_ferramenta("varinha"))
        self._texto_botao = self._bolha("", "Escrever texto", lambda _=False: self._escolher_ferramenta("texto"))
        self._texto_botao.setIcon(QIcon(textos.icone()))
        self._balde = self._bolha(
            "balde", "Balde de tinta", lambda _=False: self._escolher_ferramenta("balde"))
        self._forma_botao = self._bolha(
            "forma", "Formas", lambda _=False: self._mostrar_formas())
        self._carimbo = self._bolha(
            "carimbo", "Carimbos", lambda _=False: self._mostrar_carimbos())
        self._magia = self._bolha(
            "magia", "Pincel mágico", lambda _=False: self._mostrar_efeitos())
        self._cor = self._bolha(
            "cor", "Cor", lambda _=False: self._mostrar_paleta())
        self._desfazer_botao = self._bolha(
            "desfazer", "Desfazer (Ctrl+Z)", lambda _=False: janela.desfazer())
        self._refazer_botao = self._bolha(
            "refazer", "Refazer (Ctrl+Y)", lambda _=False: janela.refazer())
        self._apagar_botao = self._bolha(
            "apagar", "Apagar seleção (Delete)", lambda _=False: janela.apagar_selecao())
        self._jogos = self._bolha(
            "jogos", "Jogos", lambda _=False: janela.abrir_jogos())
        if not menu_prefs.ler()["jogos"]:
            self._jogos.hide()
        self._correio = self._bolha(
            "correio", "Correio", lambda _=False: janela.abrir_correio())
        self._bolha(
            "definicoes", "Definições", lambda _=False: janela.abrir_definicoes())
        self._bolha(
            "pesquisar", "Pesquisar imagens", lambda _=False: janela.pesquisar_imagens())
        self._bolha(
            "ocultar", "Ocultar menu", lambda _=False: janela.ocultar_menu())
        self._escolher_ferramenta("caneta")
        self.tela.alterou.connect(self.atualizar_estados)
        self.atualizar_estados()
        self.ajustar(480)

    def _bolha(self, simbolo: str, dica: str, acao: Callable) -> QPushButton:
        botao = _BotaoEsfera()
        if simbolo:
            botao.setIcon(QIcon(icones.desenhar(simbolo)))
        botao.setToolTip(dica)
        botao.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        botao.clicked.connect(acao)
        self._botoes.append(botao)
        return botao

    def ajustar(self, altura_disponivel: int) -> None:
        """Escolhe o tamanho das bolhas e o número de colunas para o menu caber na altura disponível."""
        margem, espaco = 16, 8
        n = len(self._botoes)
        for colunas in (1, 2, 3):
            linhas = -(-n // colunas)
            tamanho = (altura_disponivel - margem - (linhas - 1) * espaco) // linhas
            tamanho = max(TAMANHO_MIN_BOLHA, min(TAMANHO_MAX_BOLHA, tamanho))
            cabe = tamanho * linhas + (linhas - 1) * espaco + margem <= altura_disponivel
            if cabe or colunas == 3:
                break
        self._tamanho = tamanho
        self._grelha.setSpacing(espaco)
        while self._grelha.count():
            self._grelha.takeAt(0)
        for indice, botao in enumerate(self._botoes):
            botao.setFixedSize(tamanho, tamanho)
            botao.setIconSize(QSize(int(tamanho * 0.6), int(tamanho * 0.6)))
            if not isinstance(botao, _BotaoEsfera):
                botao.setStyleSheet(_estilo_bolha(tamanho))
            self._grelha.addWidget(botao, indice // colunas, indice % colunas)
        self.atualizar_estados()
        self.adjustSize()

    def definir_correio(self, nao_lidas: int) -> None:
        self._correio.setText("✉" if nao_lidas == 0 else f"✉ {nao_lidas}")

    def mostrar_correio(self, visivel: bool) -> None:
        self._correio.setVisible(visivel)

    def _escolher_ferramenta(self, nome: str) -> None:
        self.tela.ferramenta = nome
        self.tela.ao_mudar_ferramenta(nome)
        if nome != "texto":
            self.tela.cancelar_texto()
        if nome != "varinha":
            self.tela.limpar_selecao()
        for botao, ferramenta in (
            (self._caneta, "caneta"),
            (self._borracha, "borracha"),
            (self._borracha_riscos, "borracha_riscos"),
            (self._varinha, "varinha"),
            (self._balde, "balde"),
            (self._carimbo, "carimbo"),
            (self._magia, "magia"),
            (self._forma_botao, "forma"),
            (self._texto_botao, "texto"),
        ):
            botao.setCheckable(True)
            botao.setChecked(ferramenta == nome)
        self.tela.update()
        self.atualizar_estados()

    def _ferramenta_com_tamanhos(self, nome: str, botao: QPushButton) -> None:
        self._escolher_ferramenta(nome)
        if nome == "caneta":
            self._mostrar_tamanhos(
                botao, DIAMETROS_CANETA, ESPESSURAS_CANETA, self.tela.espessura, self._definir_espessura
            )
        else:
            self._mostrar_tamanhos(
                botao, DIAMETROS_BORRACHA, RAIOS_BORRACHA, self.tela.raio_borracha, self._definir_raio
            )

    def _definir_espessura(self, valor: float) -> None:
        self.tela.espessura = valor

    def _definir_raio(self, valor: float) -> None:
        self.tela.raio_borracha = valor

    def atualizar_estados(self) -> None:
        quadro = self.tela.quadro
        self._desfazer_botao.setEnabled(quadro.pode_desfazer())
        self._refazer_botao.setEnabled(quadro.pode_refazer())
        self._apagar_botao.setEnabled(bool(self.tela.selecao))
        cor = self.tela.cor_ativa()
        if isinstance(self._cor, _BotaoEsfera):
            self._cor.definir_cor_esfera(cor)
        else:
            self._cor.setStyleSheet(
                f"QPushButton {{ background: {cor}; color: {'#000000' if cor == '#ffffff' else '#ffffff'};"
                f" border: 2px solid white; border-radius: {self._tamanho // 2}px; font-size: {max(14, int(self._tamanho * 0.4))}px; }}"
            )

    def _fechar_paleta(self) -> None:
        if self._paleta is not None:
            self._paleta.close()

    def _painel_popup(self, botao: QPushButton) -> QFrame:
        self._fechar_paleta()
        painel = QFrame(self, Qt.WindowType.Popup)
        painel.setStyleSheet(
            "QFrame { background: rgba(24, 31, 46, 232); border: 1px solid rgba(255, 255, 255, 65); border-radius: 16px; }"
            " QPushButton { background: rgba(255, 255, 255, 24); color: white; border: 1px solid rgba(255, 255, 255, 38); border-radius: 10px; }"
            " QPushButton:hover { background: rgba(96, 165, 250, 95); border-color: rgba(191, 219, 254, 180); }"
            " QPushButton:checked { background: #2563EB; border-color: #93C5FD; }"
        )
        self._paleta = painel
        painel.move(botao.mapToGlobal(QPoint(botao.width() + 12, 0)))
        return painel

    def _mostrar_carimbos(self) -> None:
        self._escolher_ferramenta("carimbo")
        painel = self._painel_popup(self._carimbo)
        caixa = QVBoxLayout(painel)
        grelha = QGridLayout()
        caixa.addLayout(grelha)
        for indice, nome in enumerate(carimbos.NOMES):
            botao = QPushButton()
            botao.setIcon(QIcon(carimbos.icone(nome)))
            botao.setIconSize(QSize(40, 40))
            botao.setFixedSize(52, 52)
            botao.setToolTip(carimbos.ROTULOS[nome])
            botao.clicked.connect(lambda _=False, n=nome: self._escolher_carimbo(painel, n))
            grelha.addWidget(botao, indice // 3, indice % 3)
        caixa.addLayout(self._linha_tamanhos(painel, CARIMBO_DIAMETROS, CARIMBO_TAMANHOS, self.tela.tamanho_carimbo, lambda v: setattr(self.tela, "tamanho_carimbo", v)))
        painel.show()

    def _escolher_carimbo(self, painel: QFrame, nome: str) -> None:
        self.tela.carimbo = nome
        self.tela.atualizar_colocacao()
        painel.close()

    def _linha_tamanhos(self, painel, diametros, valores, atual, aplicar) -> QHBoxLayout:
        linha = QHBoxLayout()
        barra = _BarraTamanho(valores[0], valores[-1], atual, diametros[0], diametros[-1], com_fundo=False)
        barra.valor_alterado.connect(aplicar)
        linha.addWidget(barra)
        return linha

    def _mostrar_formas(self) -> None:
        self._escolher_ferramenta("forma")
        painel = self._painel_popup(self._forma_botao)
        caixa = QVBoxLayout(painel)
        linha = QHBoxLayout()
        for tipo in formas.TIPOS:
            botao = QPushButton()
            botao.setIcon(QIcon(formas.icone(tipo)))
            botao.setIconSize(QSize(40, 40))
            botao.setFixedSize(52, 52)
            botao.setToolTip(formas.ROTULOS[tipo])
            botao.clicked.connect(lambda _=False, t=tipo: self._escolher_forma(painel, t))
            linha.addWidget(botao)
        caixa.addLayout(linha)
        caixa.addLayout(self._linha_tamanhos(painel, DIAMETROS_CANETA, ESPESSURAS_CANETA, self.tela.espessura, self._definir_espessura))
        painel.show()

    def _escolher_forma(self, painel: QFrame, tipo: str) -> None:
        self.tela.forma = tipo
        painel.close()

    def _mostrar_efeitos(self) -> None:
        self._escolher_ferramenta("magia")
        painel = self._painel_popup(self._magia)
        caixa = QVBoxLayout(painel)
        linha = QHBoxLayout()
        for efeito in magia.EFEITOS:
            botao = QPushButton()
            botao.setIcon(QIcon(magia.icone(efeito)))
            botao.setIconSize(QSize(40, 40))
            botao.setFixedSize(52, 52)
            botao.setToolTip(magia.ROTULOS[efeito])
            botao.setCheckable(True)
            botao.setChecked(efeito == self.tela.efeito)
            botao.clicked.connect(lambda _=False, e=efeito: self._escolher_efeito(painel, e))
            linha.addWidget(botao)
        caixa.addLayout(linha)
        caixa.addLayout(self._linha_tamanhos(painel, DIAMETROS_MAGIA, RAIOS_MAGIA, self.tela.raio_magia, lambda v: setattr(self.tela, "raio_magia", v)))
        painel.show()

    def _escolher_efeito(self, painel: QFrame, efeito: str) -> None:
        self.tela.efeito = efeito
        painel.close()

    def _mostrar_tamanhos(
        self,
        botao: QPushButton,
        diametros: tuple[int, ...],
        valores: tuple[float, ...],
        atual: float,
        aplicar: Callable[[float], None],
    ) -> None:
        self._fechar_paleta()
        painel = QFrame(self, Qt.WindowType.Popup)
        painel.setStyleSheet(
            "QFrame { background: rgba(24, 31, 46, 232); border: 1px solid rgba(255, 255, 255, 65); border-radius: 24px; }"
        )
        linha = QHBoxLayout(painel)
        linha.setContentsMargins(6, 4, 6, 4)
        barra = _BarraTamanho(valores[0], valores[-1], atual, diametros[0], diametros[-1], com_fundo=False)
        barra.valor_alterado.connect(aplicar)
        linha.addWidget(barra)
        self._paleta = painel
        painel.move(botao.mapToGlobal(QPoint(botao.width() + 12, 0)))
        painel.show()

    def _escolher_tamanho(self, painel: QFrame, aplicar: Callable[[float], None], valor: float) -> None:
        aplicar(valor)
        painel.close()

    def _mostrar_paleta(self) -> None:
        self._fechar_paleta()
        paleta = QFrame(self, Qt.WindowType.Popup)
        paleta.setStyleSheet(
            "QFrame { background: rgba(24, 31, 46, 235); border: 1px solid rgba(255, 255, 255, 65); border-radius: 16px; }"
            " QPushButton { background: rgba(255, 255, 255, 32); color: white; border: 1px solid rgba(255, 255, 255, 70); border-radius: 18px; font-weight: bold; }"
            " QPushButton:hover { background: rgba(96, 165, 250, 120); border-color: #93C5FD; }"
        )
        self._paleta = paleta
        grelha = QGridLayout(paleta)
        automatica = QPushButton("A")
        automatica.setToolTip("Automática")
        automatica.setFixedSize(36, 36)
        automatica.clicked.connect(lambda _=False: self._definir_cor(None))
        grelha.addWidget(automatica, 0, 0)
        for indice, cor in enumerate(CORES_CANETA, start=1):
            amostra = _amostra(cor)
            amostra.clicked.connect(lambda _=False, c=cor: self._definir_cor(c))
            grelha.addWidget(amostra, indice // 4, indice % 4)
        outra = QPushButton("…")
        outra.setToolTip("Outra cor")
        outra.setFixedSize(36, 36)
        outra.clicked.connect(lambda _=False: self._outra_cor())
        grelha.addWidget(outra, 2, 0)
        paleta.move(self._cor.mapToGlobal(QPoint(self._cor.width() + 12, 0)))
        paleta.show()

    def _outra_cor(self) -> None:
        escolhida = QColorDialog.getColor(QColor(self.tela.cor_ativa()), self, "Cor")
        if escolhida.isValid():
            self._definir_cor(escolhida.name())

    def _definir_cor(self, cor: str | None) -> None:
        self._fechar_paleta()
        if self.tela.selecao:
            cor_final = cor or cor_caneta_automatica(self.tela.quadro.fundo)
            self.tela.quadro.registar()
            self.tela.quadro.mudar_cor(self.tela.selecao, cor_final)
            self.tela.limpar_selecao()
            self.tela.alterou.emit()
            self.tela.update()
        else:
            self.tela.cor_caneta = cor
            self._escolher_ferramenta("caneta")
        self.atualizar_estados()


class CaixaTexto(QWidget):
    """Caixa de texto transparente sobre o quadro. Toques movem-na; ✔ grava, ✖ cancela.
    Os botões não tomam o foco, por isso quem escreve pode carregar num botão e continuar a escrever."""

    PASSO = 0.02

    def __init__(self, tela: Tela, x: float, y: float, tamanho: float) -> None:
        super().__init__(tela)
        self.tela = tela
        self.x_norm = x
        self.y_norm = y
        self.tamanho = tamanho
        self.campo = QLineEdit(self)
        self.campo.setFrame(False)
        self.campo.returnPressed.connect(tela.confirmar_texto)
        self.campo.textChanged.connect(lambda _=None: self.posicionar())
        self._barra_tamanho = _BarraTamanho(
            TEXTO_TAMANHOS[0], TEXTO_TAMANHOS[-1], tamanho, TEXTO_DIAMETROS[0], TEXTO_DIAMETROS[-1], com_fundo=True
        )
        self._barra_tamanho.valor_alterado.connect(self.definir_tamanho)
        comandos = QHBoxLayout()
        for simbolo, dx, dy in (("←", -self.PASSO, 0), ("↑", 0, -self.PASSO), ("↓", 0, self.PASSO), ("→", self.PASSO, 0)):
            comandos.addWidget(self._botao(simbolo, lambda _=False, a=dx, b=dy: self.mover(a, b)))
        comandos.addStretch(1)
        comandos.addWidget(self._botao("✖", lambda _=False: tela.cancelar_texto()))
        comandos.addWidget(self._botao("✔", lambda _=False: tela.confirmar_texto()))
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(6)
        raiz.addWidget(self.campo)
        raiz.addWidget(self._barra_tamanho)
        raiz.addLayout(comandos)
        self.atualizar_aparencia()
        self.show()
        self.campo.setFocus()

    def _botao(self, simbolo: str, acao: Callable) -> QPushButton:
        botao = QPushButton(simbolo)
        botao.setFixedSize(52, 52)
        botao.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        botao.setStyleSheet(_estilo_bolha(52))
        botao.clicked.connect(acao)
        return botao

    def atualizar_aparencia(self) -> None:
        altura = max(1, self.tela.area_desenho().height())
        fonte = QFont()
        fonte.setPixelSize(max(8, int(self.tamanho * altura)))
        fonte.setBold(True)
        self.campo.setFont(fonte)
        self.campo.setFixedHeight(QFontMetrics(fonte).height() + 10)
        self.campo.setStyleSheet(
            "QLineEdit { background: rgba(255, 255, 255, 70); border: 2px dashed #2563eb; "
            f"color: {self.tela.cor_ativa()}; padding: 4px; }}"
        )
        self.posicionar()

    def posicionar(self) -> None:
        """Mantém a caixa inteira dentro do quadro (o teclado virtual reduz a área visível)."""
        fonte = self.campo.font()
        self.campo.setFixedWidth(max(160, QFontMetrics(fonte).horizontalAdvance(self.campo.text() or " ") + 40))
        self.adjustSize()
        area = self.tela.area_desenho()
        largura, altura = max(1, area.width()), max(1, area.height())
        x = min(max(0.0, self.x_norm * largura), max(0, largura - self.width()))
        y = min(max(0.0, self.y_norm * altura), max(0, altura - self.height()))
        self.x_norm, self.y_norm = x / largura, y / altura
        self.move(area.x() + int(x), area.y() + int(y))

    def mover(self, dx: float, dy: float) -> None:
        self.x_norm += dx
        self.y_norm += dy
        self.posicionar()

    def definir_posicao(self, x: float, y: float) -> None:
        self.x_norm, self.y_norm = x, y
        self.posicionar()

    def definir_tamanho(self, valor: float) -> None:
        self.tamanho = valor
        self._barra_tamanho.definir_valor(valor)
        self.atualizar_aparencia()

    def texto(self) -> str:
        return self.campo.text()


class CaixaColocacao(QWidget):
    """Carimbo ou imagem a colocar, numa caixa transparente sobre o quadro. Toques movem-na; as setas
    afinam a posição; «−» e «+» mudam o tamanho; ✔ coloca, ✖ cancela. Os botões não tomam o foco."""

    PASSO = 0.02
    FATOR = 1.25
    TAMANHO_MIN, TAMANHO_MAX = 0.02, 4.0

    def __init__(self, tela: Tela, x: float, y: float, tamanho: float, previa: Callable[[float, int], QPixmap]) -> None:
        super().__init__(tela)
        self.tela = tela
        self.x_norm = x
        self.y_norm = y
        self.tamanho = tamanho
        self._previa = previa
        self.setObjectName("barraColocacao")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("#barraColocacao { background: rgba(255, 255, 255, 215); border-radius: 12px; }")
        self.rotulo = QLabel(tela)
        self.rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.rotulo.setStyleSheet("QLabel { border: 2px dashed #2563eb; background: transparent; }")
        comandos = QHBoxLayout()
        for simbolo, dx, dy in (("←", -self.PASSO, 0), ("↑", 0, -self.PASSO), ("↓", 0, self.PASSO), ("→", self.PASSO, 0)):
            comandos.addWidget(self._botao(simbolo, lambda _=False, a=dx, b=dy: self.mover(a, b)))
        comandos.addWidget(self._botao("−", lambda _=False: self.redimensionar(1 / self.FATOR)))
        comandos.addWidget(self._botao("+", lambda _=False: self.redimensionar(self.FATOR)))
        comandos.addStretch(1)
        comandos.addWidget(self._botao("✖", lambda _=False: tela.cancelar_colocacao()))
        comandos.addWidget(self._botao("✔", lambda _=False: tela.confirmar_colocacao()))
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(8, 6, 8, 6)
        raiz.addLayout(comandos)
        self.atualizar_aparencia()
        self.rotulo.show()
        self.show()

    def hide(self) -> None:  # noqa: D401 (sobrepõe o método do Qt)
        self.rotulo.hide()
        super().hide()

    def deleteLater(self) -> None:  # noqa: N802 (nome do Qt)
        self.rotulo.deleteLater()
        super().deleteLater()

    def _botao(self, simbolo: str, acao: Callable) -> QPushButton:
        botao = QPushButton(simbolo)
        botao.setFixedSize(52, 52)
        botao.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        botao.setStyleSheet(_estilo_bolha(52))
        botao.clicked.connect(acao)
        return botao

    def atualizar_aparencia(self) -> None:
        """O tamanho nunca passa do que cabe na área do desenho, com os botões por baixo.
        A confirmação usa este mesmo tamanho, por isso o resultado é igual ao que se vê."""
        area = self.tela.area_desenho()
        pixmap = self._previa(self.tamanho, max(1, area.height()))
        self.rotulo.setPixmap(pixmap)
        self.rotulo.setFixedSize(pixmap.width() + 4, pixmap.height() + 4)
        self.posicionar()

    def posicionar(self) -> None:
        """A imagem fica onde o utilizador a pôs (sempre dentro do quadro). Os botões acompanham-na:
        por baixo, se couberem; senão por cima; senão dentro da própria imagem."""
        area = self.tela.area_desenho()
        esquerda, topo = float(area.x()), float(area.y())
        direita, fundo = esquerda + area.width(), topo + area.height()
        iw, ih = self.rotulo.width(), self.rotulo.height()
        # O centro da imagem fica sempre sobre o quadro (para a poder agarrar); a imagem pode sair dos limites.
        cx = min(max(esquerda, esquerda + self.x_norm * area.width()), direita)
        cy = min(max(topo, topo + self.y_norm * area.height()), fundo)
        ix = cx - iw / 2
        iy = cy - ih / 2
        self.x_norm = (cx - esquerda) / max(1, area.width())
        self.y_norm = (cy - topo) / max(1, area.height())
        self.rotulo.move(int(ix), int(iy))
        self.adjustSize()
        bw, bh = self.width(), self.height()
        bx = min(max(esquerda, ix + iw / 2 - bw / 2), direita - bw)
        espaco = 8
        opcoes = (iy + ih + espaco, iy - espaco - bh, iy + ih - bh - espaco)
        by = next((y for y in opcoes if y >= topo and y + bh <= fundo), None)
        if by is None:
            by = min(max(topo, opcoes[2]), fundo - bh)
        self.move(int(bx), int(by))
        self.raise_()

    def mover(self, dx: float, dy: float) -> None:
        self.x_norm += dx
        self.y_norm += dy
        self.posicionar()

    def definir_posicao(self, x: float, y: float) -> None:
        self.x_norm, self.y_norm = x, y
        self.posicionar()

    def redimensionar(self, fator: float) -> None:
        self.tamanho = min(max(self.tamanho * fator, self.TAMANHO_MIN), self.TAMANHO_MAX)
        self.atualizar_aparencia()


def _estilo_definicoes_quadro(escuro: bool) -> str:
    if escuro:
        fundo, cartao, texto, borda, hover = "#16181D", "#1E222A", "#F1F5F9", "#333946", "#2B3242"
    else:
        fundo, cartao, texto, borda, hover = "#F1F5F9", "#FFFFFF", "#0F172A", "#CBD5E1", "#EFF6FF"
    return (
        f"QDialog {{ background-color: {fundo}; color: {texto}; }}"
        f" QLabel {{ color: {texto}; font-weight: 600; font-size: 13px; }}"
        f" QPushButton {{ background-color: {cartao}; color: {texto}; border: 1px solid {borda};"
        f" border-radius: 9px; padding: 7px 14px; font-size: 13px; font-weight: 600; }}"
        f" QPushButton:hover {{ background-color: {hover}; border-color: #3B82F6; }}"
        " QPushButton:checked { background-color: #2563EB; color: #FFFFFF; border-color: #2563EB; }"
    )


class DialogoDefinicoes(QDialog):
    def __init__(self, janela: JanelaQuadro) -> None:
        super().__init__(janela)
        self.setWindowTitle("Definições")
        self.janela = janela
        self.quadro = janela.quadro
        self.tela = janela.tela
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(18, 16, 18, 16)
        raiz.setSpacing(10)

        # Tema da interface (Claro / Escuro), sincronizado com todo o Quadro e com o Teclado Kikoia.
        raiz.addWidget(QLabel("Tema (Quadro e Teclado)"))
        linha_tema = QHBoxLayout()
        escuro_atual = tema_partilhado.e_escuro()
        self._botao_claro = QPushButton("☀ Claro")
        self._botao_claro.setCheckable(True)
        self._botao_claro.setChecked(not escuro_atual)
        self._botao_claro.clicked.connect(lambda _=False: self._definir_tema(False))
        self._botao_escuro = QPushButton("☾ Escuro")
        self._botao_escuro.setCheckable(True)
        self._botao_escuro.setChecked(escuro_atual)
        self._botao_escuro.clicked.connect(lambda _=False: self._definir_tema(True))
        linha_tema.addWidget(self._botao_claro, 1)
        linha_tema.addWidget(self._botao_escuro, 1)
        raiz.addLayout(linha_tema)
        self.setStyleSheet(_estilo_definicoes_quadro(escuro_atual))

        raiz.addWidget(QLabel("Cor de fundo"))
        linha = QHBoxLayout()
        for cor in CORES_FUNDO:
            amostra = _amostra(cor, 40)
            amostra.setToolTip(cor)
            amostra.clicked.connect(lambda _=False, c=cor: self._definir_fundo(c))
            linha.addWidget(amostra)
        outra = QPushButton("Outra...")
        outra.clicked.connect(lambda _=False: self._outra_cor())
        linha.addWidget(outra)
        raiz.addLayout(linha)

        raiz.addWidget(QLabel("Desenho"))
        ficheiros = QHBoxLayout()
        for texto, acao in (
            ("Gravar...", janela.gravar),
            ("Abrir...", janela.abrir),
        ):
            botao = QPushButton(texto)
            botao.clicked.connect(lambda _=False, a=acao: a())
            ficheiros.addWidget(botao)
        exportar = QPushButton("Exportar...")
        exportar.setCheckable(True)
        ficheiros.addWidget(exportar)
        raiz.addLayout(ficheiros)
        formatos_linha = QWidget()
        formatos = QHBoxLayout(formatos_linha)
        formatos.setContentsMargins(0, 0, 0, 0)
        for texto, acao in (("JXL", janela.exportar_jxl), ("PNG", janela.exportar_png), ("SVG", janela.exportar_svg)):
            botao = QPushButton(texto)
            botao.clicked.connect(lambda _=False, a=acao: a())
            formatos.addWidget(botao)
        formatos_linha.setVisible(False)
        exportar.toggled.connect(formatos_linha.setVisible)
        raiz.addWidget(formatos_linha)
        partilhar = QPushButton("Partilhar desenho por email...")
        partilhar.clicked.connect(lambda _=False: janela.partilhar_por_email())
        raiz.addWidget(partilhar)

        imagem = QHBoxLayout()
        for texto, acao in (
            ("Importar imagem...", janela.importar_imagem),
            ("Pesquisar imagens...", janela.pesquisar_imagens),
            ("Remover imagem", janela.remover_imagem),
        ):
            botao = QPushButton(texto)
            botao.clicked.connect(lambda _=False, a=acao: a())
            imagem.addWidget(botao)
        raiz.addLayout(imagem)

        acessos = QHBoxLayout()
        for texto, acao in (("Jogos...", janela.abrir_jogos), ("Correio...", janela.abrir_correio)):
            botao = QPushButton(texto)
            botao.clicked.connect(lambda _=False, a=acao: a())
            acessos.addWidget(botao)
        raiz.addLayout(acessos)

        limpar = QPushButton("Limpar quadro")
        limpar.clicked.connect(lambda _=False: self._limpar())
        raiz.addWidget(limpar)
        sair = QPushButton("Sair do Quadro")
        sair.setStyleSheet(
            "QPushButton { background: #dc2626; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: bold; }"
            " QPushButton:hover, QPushButton:pressed { background: #b91c1c; }"
        )
        sair.clicked.connect(lambda _=False: self._sair())
        raiz.addWidget(sair)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        raiz.addWidget(fechar)

    def _definir_tema(self, escuro: bool) -> None:
        tema_partilhado.guardar_tema(escuro)
        self._botao_claro.setChecked(not escuro)
        self._botao_escuro.setChecked(escuro)
        self.setStyleSheet(_estilo_definicoes_quadro(escuro))

    def _definir_fundo(self, cor: str) -> None:
        if cor == self.quadro.fundo:
            return
        self.quadro.registar()
        self.quadro.fundo = cor
        self.tela.update()

    def _outra_cor(self) -> None:
        escolhida = QColorDialog.getColor(QColor(self.quadro.fundo), self, "Cor de fundo")
        if escolhida.isValid():
            self._definir_fundo(escolhida.name())

    def _limpar(self) -> None:
        self.quadro.registar()
        self.quadro.limpar()
        self.tela.limpar_selecao()
        self.tela.alterou.emit()
        self.tela.update()

    def _sair(self) -> None:
        self.janela.close()
        self.accept()


MIME_QUADRO = "application/x-kikoia-quadro"


class JanelaQuadro(QWidget):
    def __init__(self, quadro: Quadro | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Kikoia - Quadro Interativo")
        self._acompanha_ecra = False
        self.modo_janela = False
        self.quadro = quadro if quadro is not None else Quadro()
        self.tela = Tela(self.quadro)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(self.tela)
        self.menu = Menu(self)
        self.menu.move(16, 16)
        self.menu.adjustSize()
        self.menu.raise_()

        self._aviso = QLabel(AVISO_MENU, self.tela)
        self._aviso.setStyleSheet(
            "QLabel { background: rgba(0, 0, 0, 190); color: white; font-size: 20px;"
            " padding: 14px 20px; border-radius: 12px; }"
        )
        self._aviso.hide()
        self._temporizador = QTimer(self)
        self._temporizador.setSingleShot(True)
        self._temporizador.timeout.connect(self._aviso.hide)
        self.tela.toque_com_tres.connect(self._mostrar_se_oculto)
        self._botao_restaurar = QPushButton(self.tela)
        self._botao_restaurar.setIcon(QIcon(icones.desenhar("menu")))
        self._botao_restaurar.setIconSize(QSize(34, 34))
        self._botao_restaurar.setFixedSize(56, 56)
        self._botao_restaurar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._botao_restaurar.setToolTip("Mostrar menu")
        self._botao_restaurar.setStyleSheet(_estilo_bolha(56))
        self._botao_restaurar.move(16, 16)
        self._botao_restaurar.clicked.connect(lambda _=False: self.mostrar_menu())
        self._botao_restaurar.hide()
        self._botao_minimizar = QPushButton(self)
        self._botao_minimizar.setIcon(QIcon(icones.desenhar("minimizar")))
        self._botao_minimizar.setIconSize(QSize(28, 28))
        self._botao_minimizar.setFixedSize(48, 48)
        self._botao_minimizar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._botao_minimizar.setToolTip("Minimizar")
        self._botao_minimizar.setStyleSheet(_estilo_minimizar())
        self._botao_minimizar.clicked.connect(lambda _=False: self.showMinimized())
        self._botao_minimizar.raise_()
        self._pelo_teclado = False
        self._ultimo_pedido_teclado = 0.0
        self._temporizador_teclado = QTimer(self)
        self._temporizador_teclado.timeout.connect(self._verificar_controlo_teclado)
        self._temporizador_teclado.start(1000)

        self._ultimas_nao_lidas = 0
        self._aviso_correio = QLabel(self.tela)
        self._aviso_correio.setStyleSheet(
            "QLabel { background: rgba(37, 99, 235, 220); color: white; font-size: 18px;"
            " padding: 10px 16px; border-radius: 10px; }"
        )
        self._aviso_correio.hide()
        self._temporizador_aviso_correio = QTimer(self)
        self._temporizador_aviso_correio.setSingleShot(True)
        self._temporizador_aviso_correio.timeout.connect(self._aviso_correio.hide)
        self._temporizador_correio = QTimer(self)
        self._temporizador_correio.timeout.connect(self.verificar_correio)
        self.aplicar_preferencias_correio()

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._mostrar_se_oculto)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.desfazer)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self.refazer)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self.refazer)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(self.apagar_selecao)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.gravar)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.abrir)

    def ajustar_a_area_util(self) -> None:
        """Ocupa a área útil do monitor (sem barra de tarefas nem o teclado virtual, quando ativo).
        No modo janela, ocupa 80% dessa área, centrada, e reage da mesma forma à presença do teclado."""
        ecra = self.screen() or QGuiApplication.primaryScreen()
        area = ecra.availableGeometry()
        if self.modo_janela:
            largura, altura = int(area.width() * 0.8), int(area.height() * 0.8)
            area = QRect(
                area.x() + (area.width() - largura) // 2,
                area.y() + (area.height() - altura) // 2,
                largura,
                altura,
            )
        self.setGeometry(area)
        if not self._acompanha_ecra:
            self._acompanha_ecra = True
            ecra.availableGeometryChanged.connect(lambda _area: self.ajustar_a_area_util())

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        if hasattr(self, "menu"):
            self.menu.ajustar(self.height())
        if hasattr(self, "_botao_minimizar"):
            self._botao_minimizar.move(self.width() - self._botao_minimizar.width() - 16, 16)
            self._botao_minimizar.raise_()

    def closeEvent(self, evento) -> None:  # noqa: N802
        voz.parar()
        super().closeEvent(evento)

    def abrir_definicoes(self) -> None:
        DialogoDefinicoes(self).exec()
        self.tela.update()

    def abrir_jogos(self) -> None:
        DialogoJogos(self).exec()

    # --- correio ---------------------------------------------------------------------

    def abrir_correio(self) -> None:
        DialogoCorreio(self).exec()
        self.aplicar_preferencias_correio()

    def aplicar_preferencias_correio(self) -> None:
        prefs = contas_correio.preferencias()
        self.menu.mostrar_correio(prefs["bolha"])
        self._temporizador_correio.stop()
        if not contas_correio.listar_enderecos():
            self.menu.definir_correio(0)
            return
        self.verificar_correio()
        if prefs["avisar"]:
            self._temporizador_correio.start(prefs["intervalo_min"] * 60 * 1000)

    def verificar_correio(self) -> None:
        """Soma os emails por ler de todas as contas guardadas."""
        enderecos = contas_correio.listar_enderecos()
        if not enderecos:
            return

        def trabalhar() -> int:
            total = 0
            for endereco in enderecos:
                carregada = contas_correio.carregar(endereco=endereco)
                if carregada is not None:
                    dados, senha = carregada
                    total += contar_nao_lidas(dados, senha)
            return total

        correr_em_fundo(self, trabalhar, self._contagem_pronta)

    def _contagem_pronta(self, resultado: tuple) -> None:
        estado, valor = resultado
        if estado != "ok":
            return
        nao_lidas = int(valor)
        self.menu.definir_correio(nao_lidas)
        if nao_lidas > self._ultimas_nao_lidas and contas_correio.preferencias()["avisar"]:
            self._mostrar_aviso_correio(nao_lidas)
        self._ultimas_nao_lidas = nao_lidas

    def _mostrar_aviso_correio(self, nao_lidas: int) -> None:
        self._aviso_correio.setText(f"Tem {nao_lidas} email(s) por ler")
        self._aviso_correio.adjustSize()
        self._aviso_correio.move(max(0, self.tela.width() - self._aviso_correio.width() - 24), 24)
        self._aviso_correio.show()
        self._aviso_correio.raise_()
        self._temporizador_aviso_correio.start(TEMPO_AVISO_MS)

    # --- menu escondido ------------------------------------------------------------

    def ocultar_menu(self) -> None:
        self.menu.hide()
        self._aviso.adjustSize()
        self._aviso.move(
            max(0, (self.tela.width() - self._aviso.width()) // 2),
            max(0, self.tela.height() - self._aviso.height() - 40),
        )
        self._aviso.show()
        self._aviso.raise_()
        self._temporizador.start(TEMPO_AVISO_MS)
        self._botao_restaurar.show()
        self._botao_restaurar.raise_()

    def mostrar_menu(self) -> None:
        self.menu.show()
        self.menu.raise_()
        self._aviso.hide()
        self._temporizador.stop()
        self._botao_restaurar.hide()

    def controlo_menu_teclado(self, visivel: bool) -> None:
        """O teclado virtual pede que o menu fique escondido (layout do Quadro) ou volte a aparecer.
        Se o teclado deixar de pedir (fechou ou crashou), o menu volta sozinho ao fim de alguns segundos."""
        if visivel:
            self._pelo_teclado = False
            self.mostrar_menu()
            return
        self._pelo_teclado = True
        self._ultimo_pedido_teclado = time.monotonic()
        self.menu.hide()
        self._aviso.hide()
        self._temporizador.stop()
        self._botao_restaurar.hide()

    def _verificar_controlo_teclado(self) -> None:
        if self._pelo_teclado and time.monotonic() - self._ultimo_pedido_teclado > TEMPO_CONTROLO_TECLADO_S:
            self._pelo_teclado = False
            self.mostrar_menu()

    def _mostrar_se_oculto(self) -> None:
        if self.menu.isHidden():
            self.mostrar_menu()

    # --- edição --------------------------------------------------------------------

    def _escrevendo(self) -> bool:
        return isinstance(QGuiApplication.focusObject(), QLineEdit)

    def desfazer(self) -> None:
        if self._escrevendo():
            return
        if self.quadro.desfazer():
            self._apos_alteracao()

    def refazer(self) -> None:
        if self._escrevendo():
            return
        if self.quadro.refazer():
            self._apos_alteracao()

    def _apos_alteracao(self) -> None:
        self.tela.limpar_selecao()
        self.tela.alterou.emit()
        self.tela.update()

    def apagar_selecao(self) -> None:
        if self._escrevendo() or not self.tela.selecao:
            return
        self.quadro.registar()
        self.quadro.remover(self.tela.selecao)
        self._apos_alteracao()

    # --- ficheiros -----------------------------------------------------------------

    def gravar(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Gravar desenho", str(pasta_desenhos() / nome_sugerido()), f"Desenho Kikoia (*{EXTENSAO})"
        )
        if not caminho:
            return
        if not caminho.endswith(EXTENSAO):
            caminho += EXTENSAO
        try:
            self.quadro.guardar(Path(caminho))
        except OSError as erro:
            QMessageBox.warning(self, "Gravar desenho", f"Não foi possível gravar: {erro}")

    def abrir(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir desenho", str(pasta_desenhos()), f"Desenho Kikoia (*{EXTENSAO});;Todos (*)"
        )
        if not caminho:
            return
        if self.quadro.tracos and QMessageBox.question(
            self, "Abrir desenho", "O desenho atual será substituído. Continuar?"
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            novo = Quadro.carregar(Path(caminho))
        except (ErroQuadro, OSError) as erro:
            QMessageBox.warning(self, "Abrir desenho", f"Não foi possível abrir o desenho: {erro}")
            return
        self._substituir_quadro(novo)

    def _substituir_quadro(self, novo: Quadro) -> None:
        """Passa a ser o desenho `novo` (traços, fundo, imagens e carimbos)."""
        self.quadro.registar()
        for atributo in ("fundo", "tracos", "camada_base", "camada_preench", "camada_carimbos", "camada_efeitos"):
            setattr(self.quadro, atributo, getattr(novo, atributo))
        self._apos_alteracao()

    def preparar_anexos_quadro(self) -> list[Anexo]:
        """O desenho atual, pronto a enviar por email: o ficheiro do Quadro (editável) e uma imagem (para ver em qualquer programa)."""
        from datetime import datetime

        pasta = pasta_desenhos().parent / "envio"
        pasta.mkdir(parents=True, exist_ok=True)
        base = f"desenho-{datetime.now():%Y%m%d-%H%M%S}"
        caminho = pasta / f"{base}{EXTENSAO}"
        self.quadro.guardar(caminho)
        imagem = pasta / f"{base}.png"
        exportar_png(self.quadro, imagem, 1600, 1000)
        anexos = []
        for ficheiro, tipo in ((caminho, MIME_QUADRO), (imagem, "image/png")):
            dados = ficheiro.read_bytes()
            anexos.append(Anexo(ficheiro.name, tipo, len(dados), dados))
        return anexos

    def partilhar_por_email(self) -> None:
        """Abre uma mensagem nova com o desenho já anexado. Escolhe-se o endereço de envio em «De:»."""
        from quadro.correio import regras as regras_correio
        from quadro.correio.composicao import Rascunho

        carregada = contas_correio.carregar()
        if carregada is None:
            QMessageBox.information(
                self, "Partilhar desenho",
                "Ainda não há conta de correio. Carregue em «Correio», depois em «Configurar», e entre com uma conta.",
            )
            return
        conta, senha = carregada
        try:
            anexos = self.preparar_anexos_quadro()
        except OSError as erro:
            QMessageBox.warning(self, "Partilhar desenho", f"Não foi possível preparar o desenho: {erro}")
            return
        regras, _ = regras_correio.carregar()
        inicial = Rascunho(assunto="Desenho do Quadro", texto="Envio um desenho feito no Quadro Interativo.", anexos=tuple(anexos))
        DialogoEscrever(
            conta, senha, regras, self, inicial,
            enderecos=contas_correio.listar_enderecos(), fornecer_quadro=self.preparar_anexos_quadro,
        ).exec()

    def abrir_quadro_recebido(self, nome: str, dados: bytes) -> str:
        """Abre um desenho do Quadro recebido por email. Devolve a mensagem para mostrar."""
        pasta = pasta_desenhos().parent / "recebidos"
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / Path(nome).name
        try:
            caminho.write_bytes(dados)
            novo = Quadro.carregar(caminho)
        except (ErroQuadro, OSError):
            return "Este ficheiro não é um desenho do Quadro válido."
        if self.quadro.tracos and QMessageBox.question(
            self, "Abrir desenho", "O desenho atual será substituído. Continuar?"
        ) != QMessageBox.StandardButton.Yes:
            return "Desenho não aberto."
        self._substituir_quadro(novo)
        return "Desenho do Quadro aberto."

    def pesquisar_imagens(self) -> None:
        """Openverse: aberto por omissão; com palavra-passe de supervisor definida, só entra quem a souber."""
        credencial = openverse.credenciais()
        if credencial is None:
            QMessageBox.information(self, "Pesquisar imagens", openverse.MENSAGENS["openverse.nao_configurado"])
            return
        if supervisor_correio.existe() and not verificar_supervisor(self):
            return
        DialogoPesquisaImagens(self, credencial, self._imagem_pesquisada).exec()

    def _imagem_pesquisada(self, imagem: QImage, origem: openverse.Imagem) -> None:
        self.tela.iniciar_imagem(imagem)
        QMessageBox.information(
            self,
            "Pesquisar imagens",
            f"Imagem de {origem.autor}, licença {origem.licenca}.\n"
            "Ao usar esta imagem, mantenha a indicação do autor e da licença.",
        )

    def importar_imagem(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Importar imagem", str(pasta_desenhos()), "Imagens (*.png *.jpg *.jpeg *.bmp *.webp *.jxl)"
        )
        if not caminho:
            return
        imagem = jxl.abrir_imagem(Path(caminho))
        if imagem.isNull():
            QMessageBox.warning(self, "Importar imagem", "Não foi possível abrir esta imagem.")
            return
        self.tela.iniciar_imagem(imagem)

    def executar_acao(self, identificador: str) -> bool:
        """Executa uma ação do catálogo (acoes.py), da mesma forma que um clique no menu."""
        acao = acoes.acao(identificador)
        partes = identificador.split(".")
        if acao.pai is None and acao.ferramenta:
            self.menu._escolher_ferramenta(acao.ferramenta)
            return True
        if acao.id == "cor":
            self.menu._mostrar_paleta()
            return True
        if acao.id == "desfazer":
            self.desfazer()
        elif acao.id == "refazer":
            self.refazer()
        elif acao.id == "apagar_selecao":
            self.apagar_selecao()
        elif acao.id == "jogos":
            self.abrir_jogos()
        elif acao.id == "correio":
            self.abrir_correio()
        elif acao.id == "definicoes":
            self.abrir_definicoes()
        elif acao.id == "importar_imagem":
            self.importar_imagem()
        elif acao.id == "pesquisar_imagens":
            self.pesquisar_imagens()
        elif acao.id == "ocultar_menu":
            self.ocultar_menu()
        elif acao.id == "minimizar":
            self.showMinimized()
        elif acao.pai == "cor":
            cor = None if partes[-1] == "automatica" else CORES_ACAO[partes[-1]]
            self.menu._definir_cor(cor)
        elif acao.pai in ("caneta", "borracha", "borracha_riscos", "carimbo", "magia", "texto") and ".tamanho." in identificador:
            tabelas = {
                "caneta": (ESPESSURAS_CANETA, "espessura"),
                "borracha": (RAIOS_BORRACHA, "raio_borracha"),
                "borracha_riscos": (RAIOS_BORRACHA, "raio_borracha"),
                "carimbo": (CARIMBO_TAMANHOS, "tamanho_carimbo"),
                "magia": (RAIOS_MAGIA, "raio_magia"),
                "texto": (TEXTO_TAMANHOS, "tamanho_texto"),
            }
            valores, atributo = tabelas[acao.pai]
            setattr(self.tela, atributo, valores[int(partes[-1]) - 1])
            self.menu._escolher_ferramenta(acao.pai)
        elif acao.pai == "carimbo":
            self.tela.carimbo = partes[-1]
            self.menu._escolher_ferramenta("carimbo")
        elif acao.pai == "forma":
            self.tela.forma = partes[-1]
            self.menu._escolher_ferramenta("forma")
        elif acao.pai == "magia":
            self.tela.efeito = partes[-1]
            self.menu._escolher_ferramenta("magia")
        else:
            return False
        return True

    def remover_imagem(self) -> None:
        if self.quadro.camada_base is None:
            return
        self.quadro.registar()
        self.quadro.definir_camada_base(None)
        self._apos_alteracao()

    def exportar_jxl(self) -> None:
        self._exportar("JPEG XL (*.jxl)", ".jxl", jxl.exportar_jxl)

    def exportar_png(self) -> None:
        self._exportar("PNG (*.png)", ".png", exportar_png)

    def exportar_svg(self) -> None:
        self._exportar("SVG (*.svg)", ".svg", exportar_svg)

    def _exportar(self, filtro: str, extensao: str, funcao: Callable) -> None:
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar desenho", str(pasta_desenhos() / f"desenho{extensao}"), filtro
        )
        if not caminho:
            return
        if not caminho.lower().endswith(extensao):
            caminho += extensao
        try:
            area = self.tela.area_desenho()
            funcao(self.quadro, Path(caminho), area.width(), area.height())
        except OSError as erro:
            QMessageBox.warning(self, "Exportar desenho", f"Não foi possível exportar: {erro}")
