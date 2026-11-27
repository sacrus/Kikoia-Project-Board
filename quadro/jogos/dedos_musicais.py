"""Dedos Musicais — jogo cognitivo e de motricidade das duas mãos para ecrã de toque.

A criança posiciona as duas mãos sobre o monitor; quando um ou mais pads
piscam com uma cor e tocam uma nota musical em frente aos dedos, deve tocar
com os dedos respetivos no ecrã.

Pode ser aberto a partir do Catálogo de Jogos do Quadro ou diretamente via:
    py -m quadro.jogos.dedos_musicais
"""

from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTouchEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from quadro import idiomas, tema_partilhado
from quadro.correio import voz
from quadro.idiomas import t
from quadro.jogos import sons

# 10 dedos: 0..4 Mão Esquerda (Mindinho -> Polegar), 5..9 Mão Direita (Polegar -> Mindinho)
_NOMES_DEDOS = (
    "Mindinho Esq.",
    "Anelar Esq.",
    "Médio Esq.",
    "Indicador Esq.",
    "Polegar Esq.",
    "Polegar Dir.",
    "Indicador Dir.",
    "Médio Dir.",
    "Anelar Dir.",
    "Mindinho Dir.",
)

_NOTAS_ROTULO = ("Dó", "Ré", "Mi", "Fá", "Sol", "Lá", "Si", "Dó", "Ré", "Mi")

_CORES_DEDOS = (
    "#EF4444",  # 0 Vermelho
    "#F97316",  # 1 Laranja
    "#EAB308",  # 2 Amarelo
    "#22C55E",  # 3 Verde
    "#06B6D4",  # 4 Ciano
    "#3B82F6",  # 5 Azul
    "#6366F1",  # 6 Índigo
    "#8B5CF6",  # 7 Violeta
    "#EC4899",  # 8 Rosa
    "#F43F5E",  # 9 Coral
)


@dataclass(frozen=True)
class _ConfigNivel:
    rondas: int
    min_dedos: int
    max_dedos: int
    tempo_s: float


def config_para_nivel(nivel: int) -> _ConfigNivel:
    """Progressão suave de velocidade e número de dedos por nível."""
    if nivel <= 1:
        return _ConfigNivel(rondas=5, min_dedos=1, max_dedos=1, tempo_s=4.5)
    if nivel == 2:
        return _ConfigNivel(rondas=6, min_dedos=1, max_dedos=1, tempo_s=3.5)
    if nivel == 3:
        return _ConfigNivel(rondas=6, min_dedos=1, max_dedos=2, tempo_s=3.4)
    if nivel == 4:
        return _ConfigNivel(rondas=6, min_dedos=2, max_dedos=2, tempo_s=3.0)
    if nivel == 5:
        return _ConfigNivel(rondas=7, min_dedos=2, max_dedos=2, tempo_s=2.5)
    tempo = max(1.8, 2.6 - (nivel - 5) * 0.15)
    return _ConfigNivel(rondas=8, min_dedos=2, max_dedos=3, tempo_s=tempo)


@dataclass
class _PadDedo:
    indice: int
    ponta_dedo: QPointF
    base_dedo: QPointF
    centro_pad: QPointF
    raio_pad: float
    largura_dedo: float


@dataclass
class _Onda:
    x: float
    y: float
    cor: QColor
    progresso: float = 0.0


class AreaDedosMusicais(QWidget):
    """Canvas interativo multi-toque com 2 mãos ilustradas, 10 pads luminosos e descanso musical."""

    estado_alterado = Signal(str)
    progresso_alterado = Signal(int, int, int)  # nivel, ronda_atual, total_rondas

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 380)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._rng = random.Random()
        self._escuro = tema_partilhado.e_escuro()
        self.som_ativo = True
        self.tamanho_maos = "M"  # "P" (~6,2 cm), "M" (~7,6 cm), "G" (~9,2 cm)
        self.modo_maos = "duas"  # "duas", "dir_amiga", "esq_amiga", "so_direita", "so_esquerda"

        self.nivel = 1
        self.ronda_atual = 0
        self.total_rondas = 5
        self.estado = "pronto"  # "pronto", "tutorial_1", "tutorial_2", "tutorial_ok", "ativo", "erro", "descanso"
        self._tempo_tutorial_ok = 0.0

        self._pads: list[_PadDedo] = []
        self._palmas: list[tuple[str, QRectF]] = []
        self._alvos: set[int] = set()
        self._acertados: set[int] = set()
        self._dedo_erro: int | None = None
        self._ultimo_toque_real = 0.0
        self._ignorar_ate = 0.0
        self._protecao_dedos: tuple[set[int], float] = (set(), 0.0)
        self._flash_acertos: dict[int, float] = {}

        self._tempo_total_ronda = 4.5
        self._tempo_restante = 4.5
        self._tempo_descanso = 0.0
        self._tempo_erro = 0.0
        self._pulso = 0.0
        self._ondas: list[_Onda] = []
        self._notas_flutuantes: list[tuple[float, float, float, QColor]] = []

        self._timer_som_ronda = QTimer(self)
        self._timer_som_ronda.setSingleShot(True)
        self._timer_som_ronda.timeout.connect(self._tocar_acorde_ronda_atual)

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._reconstruir_geometria()
        sons.precarregar(("embate", "ding", "descanso", *(f"acorde_{i}" for i in range(10))))

    # --- Controlo do jogo ---------------------------------------------------------

    def definir_tema(self, escuro: bool) -> None:
        self._escuro = escuro
        self.update()

    def definir_tamanho_maos(self, tamanho: str) -> None:
        if tamanho in ("P", "M", "G"):
            self.tamanho_maos = tamanho
            self._reconstruir_geometria()
            self.update()

    def definir_modo_maos(self, modo: str) -> None:
        if modo in ("duas", "dir_amiga", "esq_amiga", "so_direita", "so_esquerda"):
            self.modo_maos = modo
            self._reconstruir_geometria()
            self.reiniciar_jogo()

    def reiniciar_jogo(self) -> None:
        """Volta sempre ao Nível 1 (pedido explícito ao reiniciar/sair)."""
        self.nivel = 1
        self.ronda_atual = 0
        self._alvos.clear()
        self._acertados.clear()
        self._dedo_erro = None
        self._ondas.clear()
        self.estado = "pronto"
        cfg = config_para_nivel(1)
        self.total_rondas = cfg.rondas
        self.progresso_alterado.emit(self.nivel, 0, self.total_rondas)
        self.estado_alterado.emit("Posiciona as duas mãos sobre o ecrã e carrega em «Começar»!")
        self.update()

    def _falar_se_visivel(self, texto: str) -> None:
        if self.som_ativo and self.isVisible():
            try:
                voz.falar(texto)
            except Exception:
                pass

    def iniciar_tutorial(self, falar: bool = True) -> None:
        """Tutorial passo a passo simples para crianças."""
        self._timer_som_ronda.stop()
        self._alvos.clear()
        self._acertados.clear()
        self._dedo_erro = None
        self._ondas.clear()
        self.estado = "tutorial_1"
        self._ignorar_ate = time.monotonic() + 0.65
        msg = t("dedos.tut_1")
        self.estado_alterado.emit(msg)
        if falar:
            self._falar_se_visivel(msg)
        self.update()

    def _avancar_tutorial_passo_2(self) -> None:
        self.estado = "tutorial_2"
        self._ignorar_ate = time.monotonic() + 0.35
        self._acertados.clear()
        self._dedo_erro = None
        dedo_demo = 3 if self.modo_maos == "so_esquerda" else 6
        self._alvos = {dedo_demo}
        msg = t("dedos.tut_2")
        self.estado_alterado.emit(msg)
        self._falar_se_visivel(msg)
        self.update()

    def comecar(self) -> None:
        voz.parar()
        self._ignorar_ate = time.monotonic() + 0.22
        self.iniciar_nivel(1)

    def _tocar_acorde_ronda_atual(self) -> None:
        if self.som_ativo and self.estado == "ativo" and self._alvos:
            sons.tocar_acorde(sorted(self._alvos))

    def _escolher_alvos_ronda(self, qtd: int) -> set[int]:
        if self.modo_maos == "so_direita":
            qtd_mao = min(qtd, 2)
            return set(self._rng.sample(range(5, 10), qtd_mao))
        if self.modo_maos == "so_esquerda":
            qtd_mao = min(qtd, 2)
            return set(self._rng.sample(range(0, 5), qtd_mao))
        if self.modo_maos == "dir_amiga":
            if qtd == 1:
                faixa = range(5, 10) if self._rng.random() < 0.80 else range(0, 5)
                return {self._rng.choice(list(faixa))}
            if self._rng.random() < 0.55:
                return {self._rng.randint(0, 4), self._rng.randint(5, 9)}
            return set(self._rng.sample(range(5, 10), min(qtd, 3)))
        if self.modo_maos == "esq_amiga":
            if qtd == 1:
                faixa = range(0, 5) if self._rng.random() < 0.80 else range(5, 10)
                return {self._rng.choice(list(faixa))}
            if self._rng.random() < 0.55:
                return {self._rng.randint(0, 4), self._rng.randint(5, 9)}
            return set(self._rng.sample(range(0, 5), min(qtd, 3)))
        if qtd == 2 and self._rng.random() < 0.70:
            return {self._rng.randint(0, 4), self._rng.randint(5, 9)}
        return set(self._rng.sample(range(10), qtd))

    def iniciar_nivel(self, nivel: int) -> None:
        self.nivel = max(1, nivel)
        cfg = config_para_nivel(self.nivel)
        self.ronda_atual = 0
        self.total_rondas = cfg.rondas
        self._alvos.clear()
        self._acertados.clear()
        self._dedo_erro = None
        self._notas_flutuantes.clear()
        self._proxima_ronda()

    def _proxima_ronda(self, atrasar_som: bool = False) -> None:
        cfg = config_para_nivel(self.nivel)
        anteriores = set(self._alvos)
        self.ronda_atual += 1
        if self.ronda_atual > cfg.rondas:
            self._entrar_descanso()
            return

        self.estado = "ativo"
        self._acertados.clear()
        self._dedo_erro = None
        self._tempo_total_ronda = cfg.tempo_s
        self._tempo_restante = cfg.tempo_s

        qtd = self._rng.randint(cfg.min_dedos, cfg.max_dedos)
        novos = self._escolher_alvos_ronda(qtd)
        # Evita repetir exatamente o mesmo dedo em duas rondas seguidas para a mudança visual ser sempre clara!
        for _ in range(8):
            if novos != anteriores:
                break
            novos = self._escolher_alvos_ronda(qtd)
        self._alvos = novos

        self._timer_som_ronda.stop()
        if self.som_ativo:
            if atrasar_som:
                self._timer_som_ronda.start(240)
            else:
                sons.tocar_acorde(sorted(self._alvos))

        nomes = " + ".join(_NOMES_DEDOS[i] for i in sorted(self._alvos))
        self.progresso_alterado.emit(self.nivel, self.ronda_atual, cfg.rondas)
        self.estado_alterado.emit(f"Nível {self.nivel} ({self.ronda_atual}/{cfg.rondas}) — Toca com: {nomes}")
        self.update()

    def _entrar_descanso(self) -> None:
        self.estado = "descanso"
        self._alvos.clear()
        self._acertados.clear()
        self._tempo_descanso = 5.0
        if self.som_ativo:
            sons.tocar_musica_descanso()
        w = max(400.0, float(self.width()))
        h = max(300.0, float(self.height()))
        self._notas_flutuantes = [
            (self._rng.uniform(w * 0.12, w * 0.88), self._rng.uniform(h * 0.35, h * 0.85), self._rng.uniform(0.6, 1.4), QColor(self._rng.choice(_CORES_DEDOS)))
            for _ in range(18)
        ]
        self.estado_alterado.emit(f"Muito bem! Concluíste o Nível {self.nivel}. Descansa as mãos!")
        self.update()

    def _falhar_ronda(self, msg: str, dedo_errado: int | None = None) -> None:
        self.estado = "erro"
        self._dedo_erro = dedo_errado
        self._tempo_erro = 1.15
        self._alvos.clear()
        self._acertados.clear()
        if self.som_ativo:
            sons.tocar_embate()
        self.estado_alterado.emit(msg)
        self.update()

    # --- Loop de tempo e animações ------------------------------------------------

    def _tick(self) -> None:
        dt = 0.03
        self._pulso += 0.16

        if self._ondas:
            for o in self._ondas:
                o.progresso += 0.055
            self._ondas = [o for o in self._ondas if o.progresso < 1.0]

        if self._flash_acertos:
            novos_flash = {k: v - dt for k, v in self._flash_acertos.items() if v - dt > 0.0}
            self._flash_acertos = novos_flash

        if self.estado == "ativo":
            self._tempo_restante -= dt
            if self._tempo_restante <= 0.0:
                self._falhar_ronda(f"O tempo acabou! Vamos recomeçar o Nível {self.nivel}.")
        elif self.estado == "erro":
            self._tempo_erro -= dt
            if self._tempo_erro <= 0.0:
                self.iniciar_nivel(self.nivel)
        elif self.estado == "tutorial_ok":
            self._tempo_tutorial_ok -= dt
            if self._tempo_tutorial_ok <= 0.0:
                self.iniciar_nivel(1)
        elif self.estado == "descanso":
            self._tempo_descanso -= dt
            self._notas_flutuantes = [(x, y - vel * 1.4, vel, c) for (x, y, vel, c) in self._notas_flutuantes]
            if self._tempo_descanso <= 0.0:
                self.iniciar_nivel(self.nivel + 1)

        self.update()

    # --- Geometria ergonómica em mm físicos (meia palma na base + dedos) ---------

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        self._reconstruir_geometria()

    def _px_por_mm(self) -> float:
        """Converte milímetros físicos reais em píxeis lógicos do Qt para manter tamanho real em 10\"–27\"."""
        ecra = self.screen() or QApplication.primaryScreen()
        if ecra is None:
            return 3.8
        dpi = ecra.physicalDotsPerInchX() or 96.0
        dpr = max(1.0, float(ecra.devicePixelRatio()))
        px_mm = (dpi / 25.4) / dpr
        if px_mm < 1.5 or px_mm > 12.0:
            return 3.8
        return px_mm

    def _reconstruir_geometria(self) -> None:
        w = max(500.0, float(self.width()))
        h = max(360.0, float(self.height()))
        px_mm = self._px_por_mm()

        # Tamanho máximo confortável que cabe na janela e respeita escala física (~9,8 cm no máximo),
        # garantindo que o pad mais alto (dy = -1.62) nunca corta no topo do ecrã.
        altura_segura_pad = (h - 46.0) / 1.92
        base_max = min(w * 0.25, h * 0.36, altura_segura_pad, 98.0 * px_mm)
        escala_tam = {"P": 0.62, "M": 0.80, "G": 1.00}.get(self.tamanho_maos, 0.80)
        palma_w = max(76.0, base_max * escala_tam)
        palma_h = palma_w * 0.62  # Meia palma encostada à base do ecrã

        raio_pad = max(16.0, min(38.0, palma_w * 0.165))
        larg_dedo = max(11.0, min(28.0, palma_w * 0.135))

        # Distância natural entre as duas mãos (ou mão centrada nos modos de uma só mão)
        separacao = min(w * 0.44, palma_w * 2.55)
        cx_esq = w * 0.5 if self.modo_maos == "so_esquerda" else (w * 0.5 - separacao * 0.5)
        cx_dir = w * 0.5 if self.modo_maos == "so_direita" else (w * 0.5 + separacao * 0.5)
        # Meia palma apoiada na margem inferior do ecrã
        cy_base = h - palma_h * 0.25

        mostrar_esq = self.modo_maos != "so_direita"
        mostrar_dir = self.modo_maos != "so_esquerda"

        palmas: list[tuple[str, QRectF]] = []
        if mostrar_esq:
            palmas.append(("dedos.mao_esq", QRectF(cx_esq - palma_w / 2, cy_base - palma_h * 0.55, palma_w, palma_h * 1.15)))
        if mostrar_dir:
            palmas.append(("dedos.mao_dir", QRectF(cx_dir - palma_w / 2, cy_base - palma_h * 0.55, palma_w, palma_h * 1.15)))
        self._palmas = palmas

        # Offsets proporcionais à largura da palma (Mindinho -> Polegar na Mão Esquerda)
        # (dx_base, dy_base, dx_ponta, dy_ponta, dx_pad, dy_pad)
        dedos_esq = [
            (-0.42, -0.22, -0.56, -0.82, -0.68, -1.24),  # Mindinho
            (-0.18, -0.34, -0.25, -1.08, -0.31, -1.52),  # Anelar
            (0.05, -0.36, 0.06, -1.16, 0.07, -1.62),     # Médio
            (0.28, -0.32, 0.35, -1.04, 0.42, -1.48),     # Indicador
            (0.45, 0.02, 0.80, -0.32, 1.06, -0.58),      # Polegar
        ]

        pads: list[_PadDedo] = []
        if mostrar_esq:
            for i, (bx, by, px, py, ax, ay) in enumerate(dedos_esq):
                pads.append(
                    _PadDedo(
                        indice=i,
                        base_dedo=QPointF(cx_esq + bx * palma_w, cy_base + by * palma_w),
                        ponta_dedo=QPointF(cx_esq + px * palma_w, cy_base + py * palma_w),
                        centro_pad=QPointF(cx_esq + ax * palma_w, cy_base + ay * palma_w),
                        raio_pad=raio_pad,
                        largura_dedo=larg_dedo,
                    )
                )

        if mostrar_dir:
            for j, (bx, by, px, py, ax, ay) in enumerate(reversed(dedos_esq)):
                idx = 5 + j
                pads.append(
                    _PadDedo(
                        indice=idx,
                        base_dedo=QPointF(cx_dir - bx * palma_w, cy_base + by * palma_w),
                        ponta_dedo=QPointF(cx_dir - px * palma_w, cy_base + py * palma_w),
                        centro_pad=QPointF(cx_dir - ax * palma_w, cy_base + ay * palma_w),
                        raio_pad=raio_pad,
                        largura_dedo=larg_dedo,
                    )
                )
        self._pads = pads

    # --- Entrada Multi-Toque, Rato/Touchpad e Teclado -----------------------------

    _MAPA_TECLAS_DEDOS = {
        Qt.Key.Key_1: 0, Qt.Key.Key_A: 0,
        Qt.Key.Key_2: 1, Qt.Key.Key_S: 1,
        Qt.Key.Key_3: 2, Qt.Key.Key_D: 2,
        Qt.Key.Key_4: 3, Qt.Key.Key_F: 3,
        Qt.Key.Key_5: 4, Qt.Key.Key_G: 4, Qt.Key.Key_V: 4,
        Qt.Key.Key_6: 5, Qt.Key.Key_H: 5, Qt.Key.Key_N: 5,
        Qt.Key.Key_7: 6, Qt.Key.Key_J: 6,
        Qt.Key.Key_8: 7, Qt.Key.Key_K: 7,
        Qt.Key.Key_9: 8, Qt.Key.Key_L: 8,
        Qt.Key.Key_0: 9, Qt.Key.Key_Ccedilla: 9, Qt.Key.Key_Semicolon: 9,
    }

    def event(self, evento: QEvent) -> bool:
        tipo = evento.type()
        if tipo in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd):
            self._ultimo_toque_real = time.monotonic()
            self._tratar_multi_toque(evento)  # type: ignore[arg-type]
            evento.accept()
            return True
        return super().event(evento)

    def _tratar_multi_toque(self, evento: QTouchEvent) -> None:
        agora = time.monotonic()
        if agora < self._ignorar_ate:
            return
        if self.estado == "tutorial_1":
            if evento.type() == QEvent.Type.TouchBegin:
                self._avancar_tutorial_passo_2()
            return
        if self.estado == "pronto":
            if evento.type() == QEvent.Type.TouchBegin:
                self.comecar()
            return
        if self.estado not in ("ativo", "tutorial_2"):
            return
        for pt in evento.points():
            if pt.state() == pt.State.Pressed:
                self._processar_toque_em(pt.position())

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        # Só ignora cliques sintetizados se tiver acabado de chegar um QTouchEvent nativo (evita duplicação
        # no Windows sem bloquear touchpads / ecrãs táteis sob XWayland no Linux).
        if (
            evento.source() != Qt.MouseEventSource.MouseEventNotSynthesized
            and (time.monotonic() - self._ultimo_toque_real) < 0.30
        ):
            evento.accept()
            return
        if time.monotonic() < self._ignorar_ate:
            evento.accept()
            return
        if evento.button() == Qt.MouseButton.LeftButton:
            if self.estado == "tutorial_1":
                self._avancar_tutorial_passo_2()
            elif self.estado == "pronto":
                self.comecar()
            elif self.estado in ("ativo", "tutorial_2"):
                self._processar_toque_em(evento.position())
        super().mousePressEvent(evento)

    def keyPressEvent(self, evento: QKeyEvent) -> None:  # noqa: N802
        if evento.isAutoRepeat() or time.monotonic() < self._ignorar_ate:
            evento.accept()
            return
        tecla = evento.key()
        if tecla in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.estado == "tutorial_1":
                self._avancar_tutorial_passo_2()
                evento.accept()
                return
            if self.estado == "pronto":
                self.comecar()
                evento.accept()
                return
        idx = self._MAPA_TECLAS_DEDOS.get(Qt.Key(tecla))
        if idx is not None:
            if self.estado == "tutorial_1":
                self._avancar_tutorial_passo_2()
            elif self.estado == "pronto":
                self.comecar()
            elif self.estado in ("ativo", "tutorial_2"):
                self._processar_indice_dedo(idx)
            evento.accept()
            return
        super().keyPressEvent(evento)

    @staticmethod
    def _dist_segmento(p: QPointF, a: QPointF, b: QPointF) -> float:
        """Distância mínima de um ponto P ao segmento de reta AB."""
        vx, vy = b.x() - a.x(), b.y() - a.y()
        comp2 = vx * vx + vy * vy
        if comp2 < 1e-6:
            return math.hypot(p.x() - a.x(), p.y() - a.y())
        t = max(0.0, min(1.0, ((p.x() - a.x()) * vx + (p.y() - a.y()) * vy) / comp2))
        proj_x = a.x() + t * vx
        proj_y = a.y() + t * vy
        return math.hypot(p.x() - proj_x, p.y() - proj_y)

    def _pad_em(self, pos: QPointF) -> int | None:
        """Identifica o dedo/pad mais próximo (cobre o pad, o espaço intermédio e o comprimento do dedo)."""
        melhor_idx: int | None = None
        melhor_dist = 1e9
        for pad in self._pads:
            # 1. Zona generosa à volta do círculo luminoso (pad)
            d_pad = math.hypot(pos.x() - pad.centro_pad.x(), pos.y() - pad.centro_pad.y())
            if d_pad <= pad.raio_pad * 1.45 and d_pad < melhor_dist:
                melhor_dist = d_pad
                melhor_idx = pad.indice
            # 2. Corredor contínuo desde o pad até ~80% do comprimento do dedo (desde a ponta em direção à base)
            meio_base = QPointF(
                pad.ponta_dedo.x() + (pad.base_dedo.x() - pad.ponta_dedo.x()) * 0.78,
                pad.ponta_dedo.y() + (pad.base_dedo.y() - pad.ponta_dedo.y()) * 0.78,
            )
            d_corredor = self._dist_segmento(pos, pad.centro_pad, meio_base)
            raio_corredor = max(pad.largura_dedo * 1.15, pad.raio_pad * 0.95)
            if d_corredor <= raio_corredor and d_corredor < melhor_dist:
                melhor_dist = d_corredor
                melhor_idx = pad.indice
        return melhor_idx

    def _pad_por_indice(self, idx: int) -> _PadDedo | None:
        for p in self._pads:
            if p.indice == idx:
                return p
        return None

    def _processar_toque_em(self, pos: QPointF) -> None:
        idx = self._pad_em(pos)
        if idx is None:
            return
        self._processar_indice_dedo(idx)

    def _processar_indice_dedo(self, idx: int) -> None:
        pad = self._pad_por_indice(idx)
        if pad is None:
            return
        if self.estado == "tutorial_2":
            if idx in self._alvos:
                self._acertados.add(idx)
                self._flash_acertos[idx] = 0.35
                self._ondas.append(_Onda(pad.centro_pad.x(), pad.centro_pad.y(), QColor(_CORES_DEDOS[idx])))
                if self.som_ativo:
                    sons.tocar_acorde([idx])
                self.estado = "tutorial_ok"
                self._tempo_tutorial_ok = 2.2
                msg = t("dedos.tut_ok")
                self.estado_alterado.emit(msg)
                self._falar_se_visivel(msg)
                self.update()
            else:
                msg = t("dedos.tut_erro")
                self.estado_alterado.emit(msg)
                self._falar_se_visivel(msg)
                self.update()
            return
        agora = time.monotonic()
        if idx in self._alvos:
            if idx not in self._acertados:
                self._acertados.add(idx)
                self._flash_acertos[idx] = 0.28
                self._ondas.append(_Onda(pad.centro_pad.x(), pad.centro_pad.y(), QColor(_CORES_DEDOS[idx])))
                completou = self._acertados == self._alvos
                if self.som_ativo:
                    # Toca sempre a nota musical exata do dedo tocado!
                    sons.tocar_acorde([idx])
                if completou:
                    # Protege brevemente os dedos acabados de tocar contra duplo toque involuntário!
                    self._protecao_dedos = (set(self._alvos), agora + 0.25)
                    self._proxima_ronda(atrasar_som=True)
                else:
                    self.update()
        else:
            protegidos, ate = self._protecao_dedos
            if idx in protegidos and agora < ate:
                return
            # Tocou num dedo errado -> volta ao início do nível atual!
            self._falhar_ronda(
                f"Ups! Tocaste em {_NOMES_DEDOS[idx]}. Vamos recomeçar o Nível {self.nivel}!",
                dedo_errado=idx,
            )

    # --- Desenho visual (2 mãos bonitas, pads luminosos, tempo e descanso) --------

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        self._desenhar_fundo(p, w, h)
        self._desenhar_barra_tempo(p, w)
        self._desenhar_maos(p, w, h)
        self._desenhar_pads(p)
        self._desenhar_ondas(p)
        self._desenhar_overlays(p, w, h)
        p.end()

    def _desenhar_fundo(self, p: QPainter, w: float, h: float) -> None:
        grad = QLinearGradient(0, 0, 0, h)
        if self._escuro:
            grad.setColorAt(0.0, QColor("#0F172A"))
            grad.setColorAt(1.0, QColor("#1E293B"))
        else:
            grad.setColorAt(0.0, QColor("#EFF6FF"))
            grad.setColorAt(1.0, QColor("#E0E7FF"))
        p.fillRect(QRectF(0, 0, w, h), grad)

        # Halo suave decorativo no centro
        halo = QRadialGradient(w * 0.5, h * 0.48, min(w, h) * 0.55)
        halo.setColorAt(0.0, QColor(99, 102, 241, 38 if self._escuro else 26))
        halo.setColorAt(1.0, QColor(99, 102, 241, 0))
        p.fillRect(QRectF(0, 0, w, h), halo)

    def _desenhar_barra_tempo(self, p: QPainter, w: float) -> None:
        if self.estado != "ativo":
            return
        frac = max(0.0, min(1.0, self._tempo_restante / max(0.1, self._tempo_total_ronda)))
        barra_w = w * 0.56
        x0 = (w - barra_w) / 2.0
        y0 = 18.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(148, 163, 184, 70))
        p.drawRoundedRect(QRectF(x0, y0, barra_w, 12), 6, 6)
        cor = QColor("#22C55E") if frac > 0.45 else (QColor("#F59E0B") if frac > 0.22 else QColor("#EF4444"))
        p.setBrush(cor)
        p.drawRoundedRect(QRectF(x0, y0, barra_w * frac, 12), 6, 6)

    def _desenhar_maos(self, p: QPainter, w: float, h: float) -> None:
        cor_pele = QColor("#FDE2C8") if not self._escuro else QColor("#E2B896")
        cor_contorno = QColor("#D97706") if not self._escuro else QColor("#F59E0B")
        cor_unha = QColor("#FFF7ED")

        # 1. Desenhar os 10 dedos (cápsulas suaves ligadas à palma)
        for pad in self._pads:
            ativo = pad.indice in self._alvos and pad.indice not in self._acertados
            acertado = pad.indice in self._acertados or (pad.indice in self._flash_acertos and not ativo)
            errado = pad.indice == self._dedo_erro

            if errado:
                cor_dedo = QColor("#FCA5A5")
            elif acertado:
                cor_dedo = QColor("#86EFAC")
            elif ativo:
                cor_dedo = QColor(_CORES_DEDOS[pad.indice]).lighter(140)
            else:
                cor_dedo = cor_pele

            # Contorno do dedo
            p.setPen(QPen(cor_contorno, pad.largura_dedo + 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(pad.base_dedo, pad.ponta_dedo)
            # Preenchimento do dedo
            p.setPen(QPen(cor_dedo, pad.largura_dedo, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(pad.base_dedo, pad.ponta_dedo)

            # Pequena unha simpática na ponta
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(cor_unha)
            p.drawEllipse(pad.ponta_dedo, pad.largura_dedo * 0.28, pad.largura_dedo * 0.22)

        # 2. Desenhar as meias palmas apoiadas suavemente na base do ecrã
        for chave_rotulo, rect in self._palmas:
            p.setBrush(cor_pele)
            p.setPen(QPen(cor_contorno, 2.2))
            p.drawRoundedRect(rect, rect.width() * 0.36, rect.height() * 0.42)

            # Rótulo discreto na parte visível da meia palma
            p.setPen(QColor("#78350F") if not self._escuro else QColor("#451A03"))
            tam_f = max(9, min(12, int(rect.width() * 0.068)))
            p.setFont(QFont("Segoe UI", tam_f, QFont.Weight.Bold))
            rotulo = t(chave_rotulo)
            zona_txt = QRectF(rect.x(), rect.y() + 6, rect.width(), min(rect.height() * 0.65, h - rect.y() - 6))
            p.drawText(zona_txt, Qt.AlignmentFlag.AlignCenter, rotulo)

    def _desenhar_pads(self, p: QPainter) -> None:
        brilho_pulso = 0.5 + 0.5 * math.sin(self._pulso * 2.2)

        for pad in self._pads:
            cor_base = QColor(_CORES_DEDOS[pad.indice])
            ativo = pad.indice in self._alvos and pad.indice not in self._acertados
            acertado = pad.indice in self._acertados or (pad.indice in self._flash_acertos and not ativo)
            errado = pad.indice == self._dedo_erro
            c = pad.centro_pad
            r = pad.raio_pad

            # Halo pulsante forte quando o dedo é pedido!
            if ativo:
                r_halo = r * (1.30 + 0.28 * brilho_pulso)
                halo = QRadialGradient(c, r_halo)
                cor_h = QColor(cor_base)
                cor_h.setAlpha(int(190 * (0.65 + 0.35 * brilho_pulso)))
                halo.setColorAt(0.0, cor_h)
                cor_h.setAlpha(0)
                halo.setColorAt(1.0, cor_h)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawEllipse(c, r_halo, r_halo)

            # Corpo do pad
            if errado:
                preench = QColor("#EF4444")
                borda = QColor("#FFFFFF")
            elif acertado:
                preench = QColor("#22C55E")
                borda = QColor("#FFFFFF")
            elif ativo:
                preench = cor_base
                borda = QColor("#FFFFFF")
            else:
                preench = QColor(cor_base)
                preench.setAlpha(72 if self._escuro else 58)
                borda = QColor(cor_base)
                borda.setAlpha(155)

            p.setPen(QPen(borda, 3.2 if (ativo or acertado or errado) else 2.0))
            p.setBrush(preench)
            p.drawEllipse(c, r, r)

            # Reflexo vítreo suave no topo do pad
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 95 if ativo else 55))
            p.drawEllipse(QPointF(c.x(), c.y() - r * 0.36), r * 0.54, r * 0.26)

            # Nota musical no centro do pad
            p.setPen(QColor("#FFFFFF") if (ativo or acertado or errado or self._escuro) else QColor("#0F172A"))
            fonte = QFont("Segoe UI", 11 if r < 32 else 13, QFont.Weight.Bold)
            p.setFont(fonte)
            texto = "✓" if acertado else ("✕" if errado else _NOTAS_ROTULO[pad.indice])
            p.drawText(QRectF(c.x() - r, c.y() - r, r * 2, r * 2), Qt.AlignmentFlag.AlignCenter, texto)

    def _desenhar_ondas(self, p: QPainter) -> None:
        for o in self._ondas:
            cor = QColor(o.cor)
            cor.setAlpha(int(210 * (1.0 - o.progresso)))
            p.setPen(QPen(cor, 4.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            raio = 30.0 + o.progresso * 65.0
            p.drawEllipse(QPointF(o.x, o.y), raio, raio)

    def _desenhar_overlays(self, p: QPainter, w: float, h: float) -> None:
        if self.estado == "pronto":
            caixa = QRectF(w * 0.25, h * 0.08, w * 0.50, 96)
            p.setBrush(QColor(37, 99, 235, 235))
            p.setPen(QPen(QColor("#FFFFFF"), 2.5))
            p.drawRoundedRect(caixa, 18, 18)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            p.drawText(QRectF(caixa.x(), caixa.y() + 10, caixa.width(), 38), Qt.AlignmentFlag.AlignCenter, t("dedos.toca_comecar"))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(
                QRectF(caixa.x() + 14, caixa.y() + 50, caixa.width() - 28, 36),
                Qt.AlignmentFlag.AlignCenter,
                t("dedos.instrucao"),
            )

        elif self.estado in ("tutorial_1", "tutorial_2", "tutorial_ok"):
            caixa = QRectF(w * 0.16, h * 0.06, w * 0.68, 92)
            cor_bg = QColor(16, 185, 129, 240) if self.estado == "tutorial_ok" else QColor(37, 99, 235, 238)
            p.setBrush(cor_bg)
            p.setPen(QPen(QColor("#FFFFFF"), 2.5))
            p.drawRoundedRect(caixa, 18, 18)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            chave = {"tutorial_1": "dedos.tut_1", "tutorial_2": "dedos.tut_2", "tutorial_ok": "dedos.tut_ok"}[self.estado]
            p.drawText(
                caixa.adjusted(16, 8, -16, -8),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                t(chave),
            )

        elif self.estado == "descanso":
            # Notas musicais a flutuar suavemente
            p.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
            for x, y, _vel, cor in self._notas_flutuantes:
                p.setPen(cor)
                p.drawText(QPointF(x, y), "♪")

            segs = max(1, int(math.ceil(self._tempo_descanso)))
            caixa = QRectF(w * 0.22, h * 0.10, w * 0.56, 108)
            p.setBrush(QColor(16, 185, 129, 240))
            p.setPen(QPen(QColor("#FFFFFF"), 2.5))
            p.drawRoundedRect(caixa, 20, 20)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
            p.drawText(
                QRectF(caixa.x(), caixa.y() + 12, caixa.width(), 42),
                Qt.AlignmentFlag.AlignCenter,
                t("dedos.descanso_titulo", n=self.nivel),
            )
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
            p.drawText(
                QRectF(caixa.x(), caixa.y() + 58, caixa.width(), 36),
                Qt.AlignmentFlag.AlignCenter,
                t("dedos.descanso_sub", s=segs),
            )


class DialogoDedosMusicais(QDialog):
    """Janela principal em ecrã completo do jogo Dedos Musicais."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        idiomas.carregar_partilhado()
        self.setWindowTitle(t("dedos.titulo"))
        self.resize(1024, 680)
        self._escuro = tema_partilhado.e_escuro()
        self._ecra_completo = False

        cab = QFrame()
        cab.setObjectName("cabecalhoDedos")
        cab_lay = QHBoxLayout(cab)
        cab_lay.setContentsMargins(14, 10, 14, 10)
        cab_lay.setSpacing(10)

        self._lbl_nivel = QLabel(t("dedos.nivel", n=1))
        self._lbl_nivel.setObjectName("badgeNivel")
        self._lbl_ronda = QLabel(t("dedos.exercicio", atual=0, total=5))
        self._lbl_ronda.setObjectName("badgeRonda")

        self._combo_modo = QComboBox()
        self._combo_modo.addItem(t("dedos.modo_duas"), "duas")
        self._combo_modo.addItem(t("dedos.modo_dir_amiga"), "dir_amiga")
        self._combo_modo.addItem(t("dedos.modo_esq_amiga"), "esq_amiga")
        self._combo_modo.addItem(t("dedos.modo_so_dir"), "so_direita")
        self._combo_modo.addItem(t("dedos.modo_so_esq"), "so_esquerda")
        self._combo_modo.currentIndexChanged.connect(self._mudar_modo_maos)

        self._combo_tamanho = QComboBox()
        self._combo_tamanho.addItem(t("dedos.maos_p"), "P")
        self._combo_tamanho.addItem(t("dedos.maos_m"), "M")
        self._combo_tamanho.addItem(t("dedos.maos_g"), "G")
        self._combo_tamanho.setCurrentIndex(1)
        self._combo_tamanho.currentIndexChanged.connect(self._mudar_tamanho_maos)

        btn_instr = QPushButton(t("jogos.instrucoes_voz"))
        btn_instr.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_instr.clicked.connect(self._falar_instrucoes)

        btn_reiniciar = QPushButton(t("dedos.reiniciar"))
        btn_reiniciar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reiniciar.clicked.connect(lambda: self.area.reiniciar_jogo())

        self._btn_som = QPushButton(t("geral.som_ligado"))
        self._btn_som.setCheckable(True)
        self._btn_som.setChecked(True)
        self._btn_som.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_som.toggled.connect(self._alternar_som)

        self._btn_ecra = QPushButton(t("geral.sair_ecra_completo"))
        self._btn_ecra.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ecra.clicked.connect(self._alternar_ecra_completo)

        btn_fechar = QPushButton(t("geral.fechar"))
        btn_fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_fechar.clicked.connect(self.accept)

        cab_lay.addWidget(self._lbl_nivel)
        cab_lay.addWidget(self._lbl_ronda)
        cab_lay.addStretch(1)
        cab_lay.addWidget(self._combo_modo)
        cab_lay.addWidget(self._combo_tamanho)
        cab_lay.addWidget(btn_instr)
        cab_lay.addWidget(btn_reiniciar)
        cab_lay.addWidget(self._btn_som)
        cab_lay.addWidget(self._btn_ecra)
        cab_lay.addWidget(btn_fechar)

        self.area = AreaDedosMusicais()
        self.area.estado_alterado.connect(self._atualizar_estado)
        self.area.progresso_alterado.connect(self._atualizar_progresso)

        self._estado = QLabel("Posiciona as duas mãos sobre o ecrã e toca para começar!")
        self._estado.setObjectName("rodapeDedos")
        self._estado.setContentsMargins(14, 6, 14, 8)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(cab)
        raiz.addWidget(self.area, 1)
        raiz.addWidget(self._estado)

        self._aplicar_tema()
        ecra = self.screen() or QGuiApplication.primaryScreen()
        if ecra is not None:
            ecra.availableGeometryChanged.connect(lambda _a: self._aplicar_geometria_ecra() if self._ecra_completo else None)

    def iniciar_ecra_completo(self) -> None:
        """Ativa modo de área útil completa compatível com Windows e gestores X11/Wayland no Linux."""
        self._ecra_completo = True
        self.area.iniciar_tutorial(falar=False)
        self._btn_ecra.setText(t("geral.sair_ecra_completo"))
        QTimer.singleShot(450, self._falar_instrucoes_se_ativo)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self._aplicar_geometria_ecra()

    def _aplicar_geometria_ecra(self) -> None:
        ecra = self.screen() or QGuiApplication.primaryScreen()
        if ecra is None:
            return
        area = ecra.availableGeometry()
        if area.width() <= 0 or area.height() <= 0:
            return
        if self._ecra_completo:
            self.setGeometry(area)
        else:
            w = max(760, int(area.width() * 0.84))
            h = max(480, int(area.height() * 0.84))
            x = area.x() + (area.width() - w) // 2
            y = area.y() + (area.height() - h) // 2
            self.setGeometry(QRect(x, y, w, h))

    def showEvent(self, evento) -> None:  # noqa: N802
        super().showEvent(evento)
        if self._ecra_completo:
            self._aplicar_geometria_ecra()
            QTimer.singleShot(0, self._aplicar_geometria_ecra)
        self.area.setFocus()

    def _falar_instrucoes(self) -> None:
        self.area.iniciar_tutorial(falar=True)

    def _falar_instrucoes_se_ativo(self) -> None:
        if self.isVisible() and self.area.som_ativo:
            self.area._falar_se_visivel(t("dedos.tut_1"))

    def _parar_jogo(self) -> None:
        self.area._timer.stop()
        self.area._timer_som_ronda.stop()
        self.area.som_ativo = False
        self.area.estado = "pronto"
        sons.parar()
        voz.parar()

    def done(self, resultado: int) -> None:  # noqa: N802
        self._parar_jogo()
        super().done(resultado)

    def closeEvent(self, evento) -> None:  # noqa: N802
        self._parar_jogo()
        super().closeEvent(evento)

    def reject(self) -> None:
        self._parar_jogo()
        super().reject()

    def accept(self) -> None:
        sons.parar()
        super().accept()

    def _aplicar_tema(self) -> None:
        self.area.definir_tema(self._escuro)
        if self._escuro:
            bg, topo, txt, borda, btn = "#0F172A", "#1A202E", "#F1F5F9", "#2E374B", "#262F42"
        else:
            bg, topo, txt, borda, btn = "#EFF6FF", "#FFFFFF", "#0F172A", "#CBD5E1", "#F8FAFC"
        self.setStyleSheet(
            f"""
            QDialog {{ background: {bg}; color: {txt}; }}
            QFrame#cabecalhoDedos {{ background: {topo}; border-bottom: 1px solid {borda}; }}
            QLabel#badgeNivel {{
                background: #2563EB; color: #FFFFFF; border-radius: 10px;
                padding: 4px 12px; font-size: 13px; font-weight: 700;
            }}
            QLabel#badgeRonda {{
                background: #8B5CF6; color: #FFFFFF; border-radius: 10px;
                padding: 4px 12px; font-size: 13px; font-weight: 700;
            }}
            QLabel#rodapeDedos {{ background: {topo}; color: {txt}; border-top: 1px solid {borda}; font-size: 13px; font-weight: 600; }}
            QPushButton, QComboBox {{
                background: {btn}; color: {txt}; border: 1px solid {borda};
                border-radius: 8px; padding: 6px 12px; font-size: 10pt; font-weight: 600;
            }}
            QComboBox QAbstractItemView {{
                background: {topo}; color: {txt}; font-size: 10pt;
            }}
            """
        )

    def _mudar_modo_maos(self) -> None:
        self.area.definir_modo_maos(str(self._combo_modo.currentData() or "duas"))

    def _mudar_tamanho_maos(self) -> None:
        self.area.definir_tamanho_maos(str(self._combo_tamanho.currentData() or "M"))

    def _alternar_som(self, ligado: bool) -> None:
        self.area.som_ativo = ligado
        self._btn_som.setText(t("geral.som_ligado") if ligado else t("geral.som_desligado"))
        if not ligado:
            voz.parar()

    def _alternar_ecra_completo(self) -> None:
        self._ecra_completo = not self._ecra_completo
        if self._ecra_completo:
            self._btn_ecra.setText(t("geral.sair_ecra_completo"))
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            self.show()
            self._aplicar_geometria_ecra()
        else:
            self._btn_ecra.setText(t("geral.ecra_completo"))
            if self.isFullScreen():
                self.showNormal()
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
            self.show()
            self._aplicar_geometria_ecra()
        self.area.setFocus()

    def _atualizar_estado(self, texto: str) -> None:
        self._estado.setText(texto)

    def _atualizar_progresso(self, nivel: int, ronda: int, total: int) -> None:
        self._lbl_nivel.setText(t("dedos.nivel", n=nivel))
        self._lbl_ronda.setText(t("dedos.exercicio", atual=ronda, total=total))


def gerar_miniatura(destino: str, largura: int = 320, altura: int = 200) -> None:
    """Renderiza uma captura limpa do jogo para `thumb.png` no catálogo."""
    area = AreaDedosMusicais()
    area.som_ativo = False
    area.definir_tema(False)
    area.resize(largura * 3, altura * 3)
    area.estado = "ativo"
    area._alvos = {3, 6}
    area._acertados = set()
    pix = QPixmap(area.size())
    area.render(pix)
    pix.scaled(largura, altura, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation).save(destino, "PNG")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = DialogoDedosMusicais()
    dlg.iniciar_ecra_completo()
    dlg.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
