"""Caminho das Letras — jogo educativo de caligrafia cursiva e números para o Quadro Kikoia.

Pode ser aberto a partir do Catálogo de Jogos do Quadro ou diretamente via:
    py -m quadro.jogos.caminho_letras
"""

from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QTabletEvent,
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
from quadro.jogos import caligrafia, sons

_CENARIOS = ("floresta", "cidade", "obra")
_NOMES_CENARIO = {
    "floresta": "Floresta",
    "cidade": "Cidade",
    "obra": "Obra",
}
_SILABAS_CURSIVAS = ["sol", "lua", "mar", "avo", "rio", "ceu", "mel", "pao", "ola", "dia"]
_SEQUENCIAS_NUMEROS = ["123", "246", "321", "456", "789", "105", "208"]


@dataclass
class _Obstaculo:
    tipo: str  # "arvore", "carro", "mota", "escavadora", "cone", "pedra", "casa"
    x: float
    y: float
    raio: float
    cor: str
    espelhado: bool = False


@dataclass
class _TracoNivel:
    caractere: str
    pontos: list[QPointF]
    progresso: int = 0
    concluido: bool = False


@dataclass
class _Confetti:
    x: float
    y: float
    vx: float
    vy: float
    cor: QColor
    tamanho: float
    angulo: float
    vel_rot: float


def _escolher_sequencia(nivel: int, modo: str, rng: random.Random) -> list[str]:
    """Escolhe os caracteres do nível conforme a progressão (1 -> 2 -> 3 caracteres)."""
    letras = sorted(caligrafia.LETRAS_CURSIVAS.keys())
    numeros = sorted(caligrafia.NUMEROS_MANUSCRITOS.keys())

    if nivel <= 2:
        qtd = 1
    elif nivel <= 5:
        qtd = 2
    else:
        qtd = 3

    if modo == "letras":
        if qtd == 3 and rng.random() < 0.55:
            return list(rng.choice(_SILABAS_CURSIVAS))
        return [rng.choice(letras) for _ in range(qtd)]
    if modo == "numeros":
        if qtd == 3 and rng.random() < 0.55:
            return list(rng.choice(_SEQUENCIAS_NUMEROS))
        return [rng.choice(numeros) for _ in range(qtd)]

    # Modo mistura
    if qtd == 1:
        pool = letras if rng.random() < 0.65 else numeros
        return [rng.choice(pool)]
    if qtd == 2:
        # 1 letra + 1 numero ou 2 letras ou 2 numeros
        r = rng.random()
        if r < 0.45:
            return [rng.choice(letras), rng.choice(numeros)]
        if r < 0.80:
            return [rng.choice(letras), rng.choice(letras)]
        return [rng.choice(numeros), rng.choice(numeros)]
    # qtd == 3
    r = rng.random()
    if r < 0.40:
        return list(rng.choice(_SILABAS_CURSIVAS))
    if r < 0.65:
        return list(rng.choice(_SEQUENCIAS_NUMEROS))
    return [rng.choice(letras), rng.choice(numeros), rng.choice(letras)]


class AreaCaminhoLetras(QWidget):
    """Canvas interativo do jogo com cenários vetoriais, caligrafia, obstáculos e partículas."""

    estado_alterado = Signal(str)
    nivel_concluido = Signal(int, int)  # nivel, estrelas

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(780, 480)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

        self._rng = random.Random()
        self.nivel = 1
        self.estrelas = 0
        self.modo = "mistura"  # "mistura", "letras", "numeros"
        self.som_ativo = True

        self._cenario = "floresta"
        self._sequencia: list[str] = ["a"]
        self._tracos: list[_TracoNivel] = []
        self._traco_ativo_idx = 0
        self._obstaculos: list[_Obstaculo] = []
        self._largura_estrada = 48.0
        self._a_desenhar = False
        self._celebrando = False

        # Proteção para caneta em monitor touchscreen (rejeição de palma e multi-toque)
        self._caneta_em_proximidade = False
        self._ultimo_uso_caneta = 0.0
        self._ultimo_toque_real = 0.0
        self._touch_id_ativo: int | None = None
        self._origem_ativa: str | None = None  # "caneta", "toque", "rato"

        # Efeitos visuais
        self._pulso = 0.0
        self._aviso_embate = 0.0
        self._ponto_embate: QPointF | None = None
        self._cooldown_som = 0.0
        self._confettis: list[_Confetti] = []
        self._mensagem_banner = ""

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._timer_proximo = QTimer(self)
        self._timer_proximo.setSingleShot(True)
        self._timer_proximo.timeout.connect(self.proximo_nivel)

        self.iniciar_nivel(1)
        sons.precarregar(("embate", "ding", "aplausos"))

    # --- Gestão de níveis e geometria ---------------------------------------------

    def instrucao_caractere_atual(self) -> str:
        """Frase simples para crianças com a letra ou o número exato do traço atual."""
        traco = self._traco_atual()
        car = traco.caractere if traco is not None else (self._sequencia[0] if self._sequencia else "")
        if not car:
            return t("caminho.voz_instrucoes")
        if car.isdigit():
            return t("caminho.voz_numero", valor=car)
        return t("caminho.voz_letra", valor=car.upper())

    def falar_caractere_atual(self) -> None:
        if self.som_ativo and self.isVisible():
            try:
                voz.falar(self.instrucao_caractere_atual())
            except Exception:
                pass

    def iniciar_nivel(self, nivel: int, sequencia_fixa: list[str] | None = None) -> None:
        self._timer_proximo.stop()
        self.nivel = max(1, nivel)
        self._celebrando = False
        self._a_desenhar = False
        self._confettis.clear()
        self._mensagem_banner = ""
        self._aviso_embate = 0.0
        self._ponto_embate = None
        self._cenario = _CENARIOS[(self.nivel - 1) % len(_CENARIOS)]
        self._sequencia = list(sequencia_fixa) if sequencia_fixa else _escolher_sequencia(self.nivel, self.modo, self._rng)
        self._reconstruir_geometria()
        seq_txt = " · ".join(self._sequencia)
        self.estado_alterado.emit(f"Nível {self.nivel} ({_NOMES_CENARIO[self._cenario]}) — Percorre: {seq_txt}")
        self.falar_caractere_atual()
        self.update()

    def proximo_nivel(self) -> None:
        self.iniciar_nivel(self.nivel + 1)

    def novo_percurso(self) -> None:
        self.iniciar_nivel(self.nivel)

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        self._reconstruir_geometria(preservar_progresso=True)

    def _reconstruir_geometria(self, preservar_progresso: bool = False) -> None:
        w = max(400.0, float(self.width()))
        h = max(300.0, float(self.height()))
        qtd = max(1, len(self._sequencia))

        margem_x = w * 0.09
        margem_topo = h * 0.19
        margem_base = h * 0.09
        area_w = w - 2.0 * margem_x
        area_h = h - margem_topo - margem_base

        espaco = 24.0 if qtd > 1 else 0.0
        celula_w = (area_w - espaco * (qtd - 1)) / qtd
        lado = min(celula_w, area_h)
        total_w = lado * qtd + espaco * (qtd - 1)
        x0 = (w - total_w) / 2.0
        y0 = margem_topo + (area_h - lado) / 2.0

        self._largura_estrada = max(32.0, min(54.0, lado * (0.145 if qtd == 1 else 0.165)))

        progresso_antigo = [(t.progresso, t.concluido) for t in self._tracos] if preservar_progresso else []
        novos: list[_TracoNivel] = []
        for idx_c, car in enumerate(self._sequencia):
            cx = x0 + idx_c * (lado + espaco)
            for traco_norm in caligrafia.tracos_do_caractere(car):
                pts = [QPointF(cx + px * lado, y0 + py * lado) for px, py in traco_norm]
                novos.append(_TracoNivel(caractere=car, pontos=pts))

        if preservar_progresso and len(progresso_antigo) == len(novos):
            for t, (prog, conc) in zip(novos, progresso_antigo):
                t.progresso = min(prog, max(0, len(t.pontos) - 1))
                t.concluido = conc
        else:
            self._traco_ativo_idx = 0

        self._tracos = novos
        self._gerar_obstaculos(w, h)

    def _distancia_minima_estrada(self, x: float, y: float) -> float:
        melhor = 1e9
        for traco in self._tracos:
            for p in traco.pontos[::2]:
                d = math.hypot(p.x() - x, p.y() - y)
                if d < melhor:
                    melhor = d
        return melhor

    def _gerar_obstaculos(self, w: float, h: float) -> None:
        """Coloca obstáculos bonitos nas margens do cenário sem nunca bloquear a estrada."""
        rng = random.Random(self.nivel * 997 + sum(ord(c) for c in self._sequencia) * 31)
        if self._cenario == "floresta":
            tipos = ["arvore", "arvore", "pedra", "mota", "casa"]
            cores = ["#15803D", "#16A34A", "#E11D48", "#F97316", "#2563EB"]
        elif self._cenario == "cidade":
            tipos = ["carro", "mota", "casa", "arvore", "carro"]
            cores = ["#EF4444", "#2563EB", "#F59E0B", "#10B981", "#8B5CF6"]
        else:
            tipos = ["escavadora", "cone", "cone", "pedra", "carro"]
            cores = ["#F59E0B", "#EA580C", "#EAB308", "#64748B", "#DC2626"]

        obstaculos: list[_Obstaculo] = []
        alvo = min(14, 8 + self.nivel)
        margem_estrada = self._largura_estrada * 0.62 + 30.0

        for _ in range(260):
            if len(obstaculos) >= alvo:
                break
            tipo = rng.choice(tipos)
            raio = {"cone": 16.0, "pedra": 18.0, "mota": 22.0, "arvore": 24.0, "carro": 26.0, "casa": 28.0, "escavadora": 28.0}[tipo]
            x = rng.uniform(raio + 16.0, w - raio - 16.0)
            y = rng.uniform(h * 0.16 + raio, h - raio - 16.0)
            if self._distancia_minima_estrada(x, y) < margem_estrada + raio * 0.65:
                continue
            if any(math.hypot(o.x - x, o.y - y) < o.raio + raio + 22.0 for o in obstaculos):
                continue
            obstaculos.append(
                _Obstaculo(
                    tipo=tipo,
                    x=x,
                    y=y,
                    raio=raio,
                    cor=rng.choice(cores),
                    espelhado=rng.random() < 0.5,
                )
            )
        self._obstaculos = obstaculos

    # --- Loop de animação ----------------------------------------------------------

    def _tick(self) -> None:
        self._pulso += 0.12
        if self._cooldown_som > 0.0:
            self._cooldown_som = max(0.0, self._cooldown_som - 0.03)
        if self._aviso_embate > 0.0:
            self._aviso_embate = max(0.0, self._aviso_embate - 0.04)
        if self._confettis:
            h = float(self.height())
            for c in self._confettis:
                c.x += c.vx
                c.y += c.vy
                c.vy += 0.18
                c.angulo += c.vel_rot
            self._confettis = [c for c in self._confettis if c.y < h + 30]
        self.update()

    # --- Entrada (Caneta virtual com rejeição de palma, Toque único e Rato) -------

    def _caneta_prioritaria(self) -> bool:
        """Verdadeiro quando a caneta está próxima ou foi usada recentemente (ignora palma/toques)."""
        return self._caneta_em_proximidade or (time.monotonic() - self._ultimo_uso_caneta) < 1.5

    def event(self, evento: QEvent) -> bool:
        tipo = evento.type()
        if tipo == QEvent.Type.TabletEnterProximity:
            self._caneta_em_proximidade = True
            self._ultimo_uso_caneta = time.monotonic()
            return True
        if tipo == QEvent.Type.TabletLeaveProximity:
            self._caneta_em_proximidade = False
            self._ultimo_uso_caneta = time.monotonic()
            return True
        if tipo in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
            self._ultimo_toque_real = time.monotonic()
            # Se a caneta estiver ativa/próxima, ignora completamente qualquer toque (palma da mão!)
            if self._caneta_prioritaria():
                evento.accept()
                return True
            self._tratar_toque(evento)  # type: ignore[arg-type]
            evento.accept()
            return True
        return super().event(evento)

    def _tratar_toque(self, evento: QTouchEvent) -> None:
        pontos = evento.points()
        tipo = evento.type()
        if tipo == QEvent.Type.TouchCancel:
            self._touch_id_ativo = None
            self._terminar_traco()
            return
        if tipo == QEvent.Type.TouchBegin:
            if self._touch_id_ativo is None and pontos:
                # Só aceita o primeiro toque (ignora multi-toques acidentais da palma/outros dedos)
                pt = pontos[0]
                self._touch_id_ativo = pt.id()
                self._origem_ativa = "toque"
                self._iniciar_traco(pt.position())
            return
        # TouchUpdate / TouchEnd: acompanha apenas o ponto de toque ativo
        for pt in pontos:
            if pt.id() != self._touch_id_ativo:
                continue
            if tipo == QEvent.Type.TouchEnd or pt.state() == pt.State.Released:
                self._touch_id_ativo = None
                self._terminar_traco()
            elif self._a_desenhar and self._origem_ativa == "toque":
                self._mover_traco(pt.position())
            return

    def tabletEvent(self, evento: QTabletEvent) -> None:  # noqa: N802
        self._ultimo_uso_caneta = time.monotonic()
        self._caneta_em_proximidade = True
        self._touch_id_ativo = None
        pos = evento.position()
        tipo = evento.type()
        if tipo == QTabletEvent.Type.TabletPress:
            self._origem_ativa = "caneta"
            self._iniciar_traco(pos)
            evento.accept()
        elif tipo == QTabletEvent.Type.TabletMove and self._a_desenhar and self._origem_ativa == "caneta":
            self._mover_traco(pos)
            evento.accept()
        elif tipo == QTabletEvent.Type.TabletRelease:
            self._terminar_traco()
            evento.accept()
        else:
            super().tabletEvent(evento)

    def _rato_sintetizado_recente(self, evento) -> bool:
        return (
            evento.source() != Qt.MouseEventSource.MouseEventNotSynthesized
            and (time.monotonic() - self._ultimo_toque_real) < 0.30
        )

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        # Ignora eventos de rato sintetizados apenas quando acabou de ocorrer um QTouchEvent real
        if self._rato_sintetizado_recente(evento) or self._caneta_prioritaria():
            evento.accept()
            return
        if evento.button() == Qt.MouseButton.LeftButton:
            self._origem_ativa = "rato"
            self._iniciar_traco(evento.position())
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if self._rato_sintetizado_recente(evento) or self._caneta_prioritaria():
            evento.accept()
            return
        if self._a_desenhar and self._origem_ativa == "rato":
            self._mover_traco(evento.position())
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        if self._rato_sintetizado_recente(evento) or self._caneta_prioritaria():
            evento.accept()
            return
        if evento.button() == Qt.MouseButton.LeftButton:
            self._terminar_traco()
        super().mouseReleaseEvent(evento)

    def _terminar_traco(self) -> None:
        """Ao levantar a caneta/rato antes de concluir o traço, reinicia o traço para exigir continuidade."""
        estava = self._a_desenhar
        self._a_desenhar = False
        self._origem_ativa = None
        if estava and not self._celebrando:
            traco = self._traco_atual()
            if traco is not None and not traco.concluido and traco.progresso > 0:
                traco.progresso = 0
                self.estado_alterado.emit("Levantaste a caneta a meio! Volta ao início da estrada e tenta de novo.")
                self.update()

    def _traco_atual(self) -> _TracoNivel | None:
        if 0 <= self._traco_ativo_idx < len(self._tracos):
            return self._tracos[self._traco_ativo_idx]
        return None

    def _iniciar_traco(self, pos: QPointF) -> None:
        if self._celebrando:
            return
        traco = self._traco_atual()
        if traco is None or not traco.pontos:
            return
        alvo = traco.pontos[traco.progresso]
        tolerancia = self._largura_estrada * 1.05
        if math.hypot(pos.x() - alvo.x(), pos.y() - alvo.y()) <= tolerancia:
            self._a_desenhar = True
            self._mover_traco(pos)
        else:
            if not self._verificar_embate_obstaculo(pos):
                self._disparar_embate(pos, "Começa no veículo verde para iniciar o percurso!")

    def _mover_traco(self, pos: QPointF) -> None:
        if self._celebrando:
            return
        traco = self._traco_atual()
        if traco is None or not traco.pontos:
            return

        # 1. Verificar embate direto num obstáculo
        if self._verificar_embate_obstaculo(pos):
            self._a_desenhar = False
            return

        # 2. Avançar o progresso ao longo do traço ativo (janela à frente para evitar saltos)
        n = len(traco.pontos)
        limite_frente = min(n - 1, traco.progresso + 16)
        melhor_idx = traco.progresso
        melhor_dist = 1e9
        for i in range(traco.progresso, limite_frente + 1):
            p = traco.pontos[i]
            d = math.hypot(p.x() - pos.x(), p.y() - pos.y())
            if d < melhor_dist:
                melhor_dist = d
                melhor_idx = i

        tolerancia_estrada = self._largura_estrada * 0.82
        if melhor_dist <= tolerancia_estrada:
            if melhor_idx > traco.progresso:
                traco.progresso = melhor_idx
            # Concluiu o traço atual?
            if traco.progresso >= n - 2:
                traco.progresso = n - 1
                traco.concluido = True
                self._a_desenhar = False
                self._origem_ativa = None
                self._avancar_traco()
        elif melhor_dist > self._largura_estrada * 1.15:
            # Saiu da estrada: volta ao início do traço!
            self._disparar_embate(pos, "Ups! Saíste da estrada — volta ao início para tentar de novo!")
            self._a_desenhar = False

        self.update()

    def _verificar_embate_obstaculo(self, pos: QPointF) -> bool:
        for obs in self._obstaculos:
            if math.hypot(pos.x() - obs.x, pos.y() - obs.y) <= obs.raio + 8.0:
                self._disparar_embate(pos, "Ups! Embateu num obstáculo — volta ao início da estrada!")
                return True
        return False

    def _disparar_embate(self, pos: QPointF, msg: str) -> None:
        traco = self._traco_atual()
        if traco is not None and not traco.concluido:
            traco.progresso = 0
        self._a_desenhar = False
        self._origem_ativa = None
        self._aviso_embate = 1.0
        self._ponto_embate = pos
        self.estado_alterado.emit(msg)
        if self.som_ativo and self._cooldown_som <= 0.0:
            sons.tocar_embate()
            self._cooldown_som = 0.45
        self.update()

    def _avancar_traco(self) -> None:
        if self._traco_ativo_idx + 1 < len(self._tracos):
            anterior = self._tracos[self._traco_ativo_idx].caractere
            self._traco_ativo_idx += 1
            if self.som_ativo:
                sons.tocar_ding()
            proximo = self._tracos[self._traco_ativo_idx]
            self.estado_alterado.emit(f"Boa! Agora continua com «{proximo.caractere}»!")
            if proximo.caractere != anterior:
                self.falar_caractere_atual()
        else:
            self._concluir_nivel()

    def _concluir_nivel(self) -> None:
        self._celebrando = True
        self.estrelas += len(self._sequencia)
        seq_txt = "".join(self._sequencia)
        elogio = t(self._rng.choice(("jogos.elogio_1", "jogos.elogio_2", "jogos.elogio_3", "jogos.elogio_4")))
        self._mensagem_banner = f"{elogio} «{seq_txt}»"
        self.estado_alterado.emit(self._mensagem_banner)
        if self.som_ativo:
            if self.isVisible():
                try:
                    voz.falar(elogio)
                except Exception:
                    sons.tocar_aplausos()
            else:
                sons.tocar_aplausos()
        self._lancar_confettis()
        self.nivel_concluido.emit(self.nivel, self.estrelas)
        self._timer_proximo.start(2600)

    def _lancar_confettis(self) -> None:
        cores = [
            QColor("#EF4444"),
            QColor("#F59E0B"),
            QColor("#10B981"),
            QColor("#3B82F6"),
            QColor("#A855F7"),
            QColor("#EC4899"),
        ]
        w = float(self.width())
        self._confettis = [
            _Confetti(
                x=self._rng.uniform(40, max(100, w - 40)),
                y=self._rng.uniform(-40, 80),
                vx=self._rng.uniform(-2.6, 2.6),
                vy=self._rng.uniform(1.5, 5.2),
                cor=self._rng.choice(cores),
                tamanho=self._rng.uniform(7, 13),
                angulo=self._rng.uniform(0, 360),
                vel_rot=self._rng.uniform(-8, 8),
            )
            for _ in range(70)
        ]

    # --- Desenho do cenário, estrada, obstáculos e veículo ------------------------

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        self._desenhar_fundo(p, w, h)
        self._desenhar_estradas(p)
        for obs in self._obstaculos:
            self._desenhar_obstaculo(p, obs)
        self._desenhar_indicadores_e_veiculo(p)
        self._desenhar_efeitos(p, w, h)
        p.end()

    def _desenhar_fundo(self, p: QPainter, w: float, h: float) -> None:
        # Céu
        ceu = QLinearGradient(0, 0, 0, h * 0.25)
        if self._cenario == "floresta":
            ceu.setColorAt(0.0, QColor("#7DD3FC"))
            ceu.setColorAt(1.0, QColor("#E0F2FE"))
            solo_cor1, solo_cor2 = QColor("#BBF7D0"), QColor("#86EFAC")
        elif self._cenario == "cidade":
            ceu.setColorAt(0.0, QColor("#60A5FA"))
            ceu.setColorAt(1.0, QColor("#DBEAFE"))
            solo_cor1, solo_cor2 = QColor("#E2E8F0"), QColor("#CBD5E1")
        else:  # obra
            ceu.setColorAt(0.0, QColor("#93C5FD"))
            ceu.setColorAt(1.0, QColor("#FEF3C7"))
            solo_cor1, solo_cor2 = QColor("#FDE68A"), QColor("#FCD34D")

        p.fillRect(QRectF(0, 0, w, h * 0.22), ceu)

        # Nuvens fofinhas
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 215))
        for cx, cy, sc in ((w * 0.14, h * 0.08, 1.0), (w * 0.48, h * 0.06, 1.15), (w * 0.82, h * 0.09, 0.95)):
            p.drawEllipse(QPointF(cx, cy), 26 * sc, 15 * sc)
            p.drawEllipse(QPointF(cx - 18 * sc, cy + 4 * sc), 18 * sc, 12 * sc)
            p.drawEllipse(QPointF(cx + 18 * sc, cy + 4 * sc), 18 * sc, 12 * sc)

        # Sol
        p.setBrush(QColor("#FACC15"))
        p.drawEllipse(QPointF(w - 54, 42), 20, 20)

        # Terreno com horizonte suave
        solo = QLinearGradient(0, h * 0.16, 0, h)
        solo.setColorAt(0.0, solo_cor1)
        solo.setColorAt(1.0, solo_cor2)
        p.setBrush(solo)
        horizonte = QPainterPath()
        horizonte.moveTo(0, h * 0.17)
        horizonte.quadTo(w * 0.28, h * 0.12, w * 0.55, h * 0.17)
        horizonte.quadTo(w * 0.80, h * 0.21, w, h * 0.16)
        horizonte.lineTo(w, h)
        horizonte.lineTo(0, h)
        horizonte.closeSubpath()
        p.drawPath(horizonte)

    def _caminho_de_pontos(self, pontos: list[QPointF]) -> QPainterPath:
        path = QPainterPath()
        if not pontos:
            return path
        path.moveTo(pontos[0])
        for pt in pontos[1:]:
            path.lineTo(pt)
        return path

    def _desenhar_estradas(self, p: QPainter) -> None:
        larg = self._largura_estrada
        if self._cenario == "floresta":
            cor_borda = QColor("#92400E")
            cor_piso = QColor("#FEF3C7")
            cor_traco_guia = QColor("#D97706")
        elif self._cenario == "cidade":
            cor_borda = QColor("#334155")
            cor_piso = QColor("#475569")
            cor_traco_guia = QColor("#F8FAFC")
        else:
            cor_borda = QColor("#78350F")
            cor_piso = QColor("#D6D3D1")
            cor_traco_guia = QColor("#F59E0B")

        for idx, traco in enumerate(self._tracos):
            if len(traco.pontos) < 2:
                continue
            path = self._caminho_de_pontos(traco.pontos)
            ativo = idx == self._traco_ativo_idx and not traco.concluido

            # Sombra suave da estrada
            p.setPen(QPen(QColor(15, 23, 42, 40), larg + 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

            # Borda da estrada (brilha ligeiramente quando ativa)
            borda = QColor("#2563EB") if ativo else cor_borda
            p.setPen(QPen(borda, larg + 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)

            # Piso da estrada
            p.setPen(QPen(cor_piso, larg, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)

            # Linha guia tracejada no centro
            pen_guia = QPen(cor_traco_guia, 3.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            pen_guia.setDashPattern([8, 8])
            p.setPen(pen_guia)
            p.drawPath(path)

            # Parte já pintada pelo utilizador!
            if traco.progresso > 0:
                pintado = self._caminho_de_pontos(traco.pontos[: traco.progresso + 1])
                grad = QLinearGradient(traco.pontos[0], traco.pontos[-1])
                grad.setColorAt(0.0, QColor("#22C55E"))
                grad.setColorAt(0.5, QColor("#06B6D4"))
                grad.setColorAt(1.0, QColor("#8B5CF6"))
                p.setPen(QPen(QBrush(grad), larg * 0.72, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawPath(pintado)

    def _desenhar_obstaculo(self, p: QPainter, obs: _Obstaculo) -> None:
        p.save()
        p.translate(obs.x, obs.y)
        if obs.espelhado:
            p.scale(-1.0, 1.0)
        r = obs.raio

        # Sombra no chão
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(15, 23, 42, 42))
        p.drawEllipse(QPointF(0, r * 0.65), r * 0.85, r * 0.30)

        if obs.tipo == "arvore":
            # Tronco
            p.setBrush(QColor("#78350F"))
            p.drawRoundedRect(QRectF(-r * 0.18, r * 0.1, r * 0.36, r * 0.6), 3, 3)
            # Copa em camadas
            p.setBrush(QColor("#15803D"))
            p.drawPolygon(QPolygonF([QPointF(0, -r), QPointF(-r * 0.82, r * 0.25), QPointF(r * 0.82, r * 0.25)]))
            p.setBrush(QColor("#22C55E"))
            p.drawPolygon(QPolygonF([QPointF(0, -r * 1.1), QPointF(-r * 0.64, -r * 0.1), QPointF(r * 0.64, -r * 0.1)]))

        elif obs.tipo == "carro":
            # Carro colorido estilizado
            p.setBrush(QColor(obs.cor))
            p.setPen(QPen(QColor("#1E293B"), 1.4))
            p.drawRoundedRect(QRectF(-r * 0.92, -r * 0.18, r * 1.84, r * 0.62), 7, 7)
            p.drawRoundedRect(QRectF(-r * 0.52, -r * 0.64, r * 1.04, r * 0.54), 6, 6)
            p.setBrush(QColor("#BAE6FD"))
            p.drawRoundedRect(QRectF(-r * 0.40, -r * 0.54, r * 0.80, r * 0.34), 4, 4)
            # Rodas
            p.setBrush(QColor("#0F172A"))
            p.drawEllipse(QPointF(-r * 0.52, r * 0.44), r * 0.24, r * 0.24)
            p.drawEllipse(QPointF(r * 0.52, r * 0.44), r * 0.24, r * 0.24)

        elif obs.tipo == "mota":
            # Mota divertida
            p.setPen(QPen(QColor("#0F172A"), 2.2))
            p.setBrush(QColor("#1E293B"))
            p.drawEllipse(QPointF(-r * 0.56, r * 0.35), r * 0.28, r * 0.28)
            p.drawEllipse(QPointF(r * 0.56, r * 0.35), r * 0.28, r * 0.28)
            p.setBrush(QColor(obs.cor))
            p.setPen(QPen(QColor("#1E293B"), 1.4))
            p.drawRoundedRect(QRectF(-r * 0.55, -r * 0.22, r * 1.05, r * 0.38), 6, 6)
            p.drawLine(QPointF(r * 0.30, -r * 0.22), QPointF(r * 0.52, -r * 0.56))

        elif obs.tipo == "escavadora":
            # Máquina de construção amarela com braço
            p.setBrush(QColor("#F59E0B"))
            p.setPen(QPen(QColor("#78350F"), 1.6))
            p.drawRoundedRect(QRectF(-r * 0.72, -r * 0.15, r * 1.25, r * 0.56), 6, 6)
            p.drawRoundedRect(QRectF(-r * 0.55, -r * 0.65, r * 0.72, r * 0.56), 5, 5)
            p.setBrush(QColor("#E0F2FE"))
            p.drawRoundedRect(QRectF(-r * 0.44, -r * 0.55, r * 0.50, r * 0.34), 3, 3)
            # Braço e pá
            p.setPen(QPen(QColor("#B45309"), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(r * 0.42, -r * 0.10), QPointF(r * 0.90, -r * 0.58))
            p.drawLine(QPointF(r * 0.90, -r * 0.58), QPointF(r * 1.05, r * 0.10))
            # Lagarta
            p.setBrush(QColor("#1E293B"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(-r * 0.78, r * 0.34, r * 1.38, r * 0.30), 6, 6)

        elif obs.tipo == "cone":
            # Cone de obra laranja e branco
            p.setBrush(QColor("#EA580C"))
            p.setPen(QPen(QColor("#9A3412"), 1.2))
            p.drawPolygon(QPolygonF([QPointF(0, -r * 0.85), QPointF(-r * 0.62, r * 0.62), QPointF(r * 0.62, r * 0.62)]))
            p.setBrush(QColor("#FFFFFF"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(QPolygonF([QPointF(-r * 0.25, -r * 0.15), QPointF(r * 0.25, -r * 0.15), QPointF(r * 0.38, r * 0.18), QPointF(-r * 0.38, r * 0.18)]))

        elif obs.tipo == "casa":
            # Casinha simpática
            p.setBrush(QColor("#FEF3C7"))
            p.setPen(QPen(QColor("#78350F"), 1.4))
            p.drawRoundedRect(QRectF(-r * 0.68, -r * 0.12, r * 1.36, r * 0.82), 4, 4)
            p.setBrush(QColor("#DC2626"))
            p.drawPolygon(QPolygonF([QPointF(0, -r * 0.85), QPointF(-r * 0.84, -r * 0.08), QPointF(r * 0.84, -r * 0.08)]))
            p.setBrush(QColor("#38BDF8"))
            p.drawRect(QRectF(-r * 0.42, r * 0.08, r * 0.32, r * 0.28))
            p.setBrush(QColor("#92400E"))
            p.drawRect(QRectF(r * 0.12, r * 0.18, r * 0.30, r * 0.52))

        else:  # pedra
            p.setBrush(QColor("#94A3B8"))
            p.setPen(QPen(QColor("#475569"), 1.4))
            p.drawEllipse(QPointF(0, r * 0.15), r * 0.82, r * 0.55)
            p.setBrush(QColor("#CBD5E1"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(-r * 0.22, 0), r * 0.32, r * 0.18)

        p.restore()

    def _desenhar_indicadores_e_veiculo(self, p: QPainter) -> None:
        traco = self._traco_atual()
        if traco is None or len(traco.pontos) < 2:
            return

        # Bandeira de chegada no fim do traço ativo
        fim = traco.pontos[-1]
        p.save()
        p.translate(fim.x(), fim.y())
        p.setPen(QPen(QColor("#0F172A"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(0, 8), QPointF(0, -24))
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#0F172A"), 1.2))
        p.drawRect(QRectF(0, -24, 22, 14))
        p.setBrush(QColor("#0F172A"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(0, -24, 7, 7))
        p.drawRect(QRectF(14, -24, 8, 7))
        p.drawRect(QRectF(7, -17, 7, 7))
        p.restore()

        # Posição e direção atual do veículo do jogador
        idx = traco.progresso
        atual = traco.pontos[idx]
        seguinte = traco.pontos[min(len(traco.pontos) - 1, idx + 1)]
        angulo = math.degrees(math.atan2(seguinte.y() - atual.y(), seguinte.x() - atual.x()))

        # Anel pulsante para guiar a criança até ao veículo
        if not self._a_desenhar and not self._celebrando:
            raio_pulso = 24.0 + math.sin(self._pulso) * 5.0
            p.setPen(QPen(QColor("#16A34A"), 3.0))
            p.setBrush(QColor(34, 197, 94, 48))
            p.drawEllipse(atual, raio_pulso, raio_pulso)

        # Desenho do veículo do jogador (adaptado ao cenário)
        p.save()
        p.translate(atual.x(), atual.y())
        p.rotate(angulo)
        cor_veic = "#EF4444" if self._cenario == "cidade" else ("#F59E0B" if self._cenario == "obra" else "#2563EB")
        p.setBrush(QColor(cor_veic))
        p.setPen(QPen(QColor("#FFFFFF"), 2.0))
        p.drawRoundedRect(QRectF(-18, -11, 36, 22), 7, 7)
        # Para-brisas a apontar para a frente (+x)
        p.setBrush(QColor("#E0F2FE"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(2, -7, 10, 14), 3, 3)
        # Faróis
        p.setBrush(QColor("#FEF08A"))
        p.drawEllipse(QPointF(17, -6), 2.5, 2.5)
        p.drawEllipse(QPointF(17, 6), 2.5, 2.5)
        p.restore()

    def _desenhar_efeitos(self, p: QPainter, w: float, h: float) -> None:
        # Efeito de embate
        if self._aviso_embate > 0.0 and self._ponto_embate is not None:
            alpha = int(220 * self._aviso_embate)
            raio = 14.0 + (1.0 - self._aviso_embate) * 28.0
            p.setPen(QPen(QColor(239, 68, 68, alpha), 4.0))
            p.setBrush(QColor(251, 146, 60, int(alpha * 0.4)))
            p.drawEllipse(self._ponto_embate, raio, raio)

        # Confettis de vitória
        p.setPen(Qt.PenStyle.NoPen)
        for c in self._confettis:
            p.save()
            p.translate(c.x, c.y)
            p.rotate(c.angulo)
            p.setBrush(c.cor)
            p.drawRoundedRect(QRectF(-c.tamanho / 2, -c.tamanho / 3, c.tamanho, c.tamanho * 0.65), 2, 2)
            p.restore()

        # Banner de celebração
        if self._celebrando and self._mensagem_banner:
            caixa = QRectF(w * 0.18, h * 0.06, w * 0.64, 54)
            p.setBrush(QColor(22, 163, 74, 235))
            p.setPen(QPen(QColor("#FFFFFF"), 2.5))
            p.drawRoundedRect(caixa, 16, 16)
            p.setPen(QColor("#FFFFFF"))
            fonte = QFont("Segoe UI", 16, QFont.Weight.Bold)
            p.setFont(fonte)
            p.drawText(caixa, Qt.AlignmentFlag.AlignCenter, self._mensagem_banner)


class DialogoCaminhoLetras(QDialog):
    """Janela principal do jogo Caminho das Letras."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        idiomas.carregar_partilhado()
        self.setWindowTitle(t("caminho.titulo"))
        self.resize(980, 680)
        self._escuro = tema_partilhado.e_escuro()
        self._ecra_completo = False

        cab = QFrame()
        cab.setObjectName("cabecalhoJogo")
        cab_lay = QHBoxLayout(cab)
        cab_lay.setContentsMargins(14, 10, 14, 10)
        cab_lay.setSpacing(10)

        self._lbl_nivel = QLabel(t("caminho.nivel", n=1))
        self._lbl_nivel.setObjectName("badgeNivel")
        self._lbl_estrelas = QLabel("★ 0")
        self._lbl_estrelas.setObjectName("badgeEstrelas")

        self._combo_modo = QComboBox()
        self._combo_modo.addItem(t("caminho.modo_mistura"), "mistura")
        self._combo_modo.addItem(t("caminho.modo_letras"), "letras")
        self._combo_modo.addItem(t("caminho.modo_numeros"), "numeros")
        self._combo_modo.currentIndexChanged.connect(self._mudar_modo)

        btn_instr = QPushButton(t("jogos.instrucoes_voz"))
        btn_instr.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_instr.clicked.connect(self._falar_instrucoes)

        btn_novo = QPushButton(t("caminho.novo"))
        btn_novo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_novo.clicked.connect(lambda: self.area.novo_percurso())

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
        cab_lay.addWidget(self._lbl_estrelas)
        cab_lay.addStretch(1)
        cab_lay.addWidget(self._combo_modo)
        cab_lay.addWidget(btn_instr)
        cab_lay.addWidget(btn_novo)
        cab_lay.addWidget(self._btn_som)
        cab_lay.addWidget(self._btn_ecra)
        cab_lay.addWidget(btn_fechar)

        self.area = AreaCaminhoLetras()
        self.area.estado_alterado.connect(self._atualizar_estado)
        self.area.nivel_concluido.connect(self._ao_concluir)

        self._estado = QLabel("Usa a caneta virtual (ou o rato) para conduzir o veículo pela estrada!")
        self._estado.setObjectName("rodapeJogo")
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
        self._btn_ecra.setText(t("geral.sair_ecra_completo"))
        QTimer.singleShot(500, self._falar_instrucoes_se_ativo)
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

    def _falar_instrucoes(self) -> None:
        try:
            voz.falar(self.area.instrucao_caractere_atual())
        except Exception:
            pass

    def _falar_instrucoes_se_ativo(self) -> None:
        if self.isVisible() and self.area.som_ativo:
            self._falar_instrucoes()

    def _parar_jogo(self) -> None:
        self.area._timer.stop()
        self.area._timer_proximo.stop()
        self.area.som_ativo = False
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
        if self._escuro:
            bg, topo, txt, borda, btn = "#131720", "#1A202E", "#F1F5F9", "#2E374B", "#262F42"
        else:
            bg, topo, txt, borda, btn = "#F1F5F9", "#FFFFFF", "#0F172A", "#CBD5E1", "#F8FAFC"
        self.setStyleSheet(
            f"""
            QDialog {{ background: {bg}; color: {txt}; }}
            QFrame#cabecalhoJogo {{ background: {topo}; border-bottom: 1px solid {borda}; }}
            QLabel#badgeNivel {{
                background: #2563EB; color: #FFFFFF; border-radius: 10px;
                padding: 4px 12px; font-size: 13px; font-weight: 700;
            }}
            QLabel#badgeEstrelas {{
                background: #F59E0B; color: #FFFFFF; border-radius: 10px;
                padding: 4px 12px; font-size: 13px; font-weight: 700;
            }}
            QLabel#rodapeJogo {{ background: {topo}; color: {txt}; border-top: 1px solid {borda}; font-size: 13px; font-weight: 600; }}
            QPushButton, QComboBox {{
                background: {btn}; color: {txt}; border: 1px solid {borda};
                border-radius: 8px; padding: 6px 12px; font-size: 10pt; font-weight: 600;
            }}
            QComboBox QAbstractItemView {{
                background: {topo}; color: {txt}; font-size: 10pt;
            }}
            """
        )

    def _mudar_modo(self) -> None:
        self.area.modo = str(self._combo_modo.currentData() or "mistura")
        self.area.iniciar_nivel(self.area.nivel)

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

    def _atualizar_estado(self, texto: str) -> None:
        self._estado.setText(texto)
        self._lbl_nivel.setText(t("caminho.nivel", n=self.area.nivel))

    def _ao_concluir(self, _nivel: int, estrelas: int) -> None:
        self._lbl_estrelas.setText(f"★ {estrelas}")


def gerar_miniatura(destino: str, largura: int = 320, altura: int = 200) -> None:
    """Renderiza uma captura limpa do jogo para usar como `thumb.png` no catálogo."""
    area = AreaCaminhoLetras()
    area.resize(largura * 2, altura * 2)
    area.iniciar_nivel(1, sequencia_fixa=["a"])
    if area._tracos:
        area._tracos[0].progresso = len(area._tracos[0].pontos) // 2
    pix = QPixmap(area.size())
    area.render(pix)
    pix.scaled(largura, altura, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation).save(destino, "PNG")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = DialogoCaminhoLetras()
    dlg.iniciar_ecra_completo()
    dlg.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
