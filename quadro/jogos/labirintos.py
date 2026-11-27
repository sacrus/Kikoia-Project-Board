"""Labirintos Mágicos — jogo educativo de motricidade fina e aperfeiçoamento do traço.

A criança guia personagens e animais pelos seus habitats, estações do ano
(com frutos e flores da época) e cenários do dia a dia (árvores, casas,
frutas e objetos), em labirintos de complexidade progressiva.

Pode ser aberto a partir do Catálogo de Jogos do Quadro ou diretamente via:
    py -m quadro.jogos.labirintos
"""

from __future__ import annotations

import math
import random
import sys
import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from quadro import idiomas, tema_partilhado
from quadro.correio import voz
from quadro.idiomas import t
from quadro.jogos import sons


@dataclass(frozen=True)
class CenarioLabirinto:
    id: str
    chave_nome: str
    chave_missao: str
    cor_fundo_1: str
    cor_fundo_2: str
    cor_caminho: str
    cor_borda_caminho: str
    cor_parede: str
    cor_parede_borda: str
    cor_traco: str
    icone_inicio: str
    icone_fim: str
    tipo_obstaculo: str


CENARIOS: tuple[CenarioLabirinto, ...] = (
    # Animais nos seus habitats
    CenarioLabirinto(
        id="floresta",
        chave_nome="lab.cen_floresta",
        chave_missao="lab.mis_floresta",
        cor_fundo_1="#DCFCE7",
        cor_fundo_2="#BBF7D0",
        cor_caminho="#FEF9C3",
        cor_borda_caminho="#D97706",
        cor_parede="#15803D",
        cor_parede_borda="#14532D",
        cor_traco="#EA580C",
        icone_inicio="coelho",
        icone_fim="cenoura",
        tipo_obstaculo="arvore",
    ),
    CenarioLabirinto(
        id="savana",
        chave_nome="lab.cen_savana",
        chave_missao="lab.mis_savana",
        cor_fundo_1="#FEF3C7",
        cor_fundo_2="#FDE68A",
        cor_caminho="#FFFBEB",
        cor_borda_caminho="#B45309",
        cor_parede="#B45309",
        cor_parede_borda="#78350F",
        cor_traco="#D97706",
        icone_inicio="leao",
        icone_fim="oasis",
        tipo_obstaculo="cacto",
    ),
    CenarioLabirinto(
        id="oceano",
        chave_nome="lab.cen_oceano",
        chave_missao="lab.mis_oceano",
        cor_fundo_1="#DBEAFE",
        cor_fundo_2="#BAE6FD",
        cor_caminho="#F0F9FF",
        cor_borda_caminho="#0284C7",
        cor_parede="#0369A1",
        cor_parede_borda="#0C4A6E",
        cor_traco="#0284C7",
        icone_inicio="peixe",
        icone_fim="concha",
        tipo_obstaculo="coral",
    ),
    CenarioLabirinto(
        id="quinta",
        chave_nome="lab.cen_quinta",
        chave_missao="lab.mis_quinta",
        cor_fundo_1="#ECFCCB",
        cor_fundo_2="#D9F99D",
        cor_caminho="#FEFCE8",
        cor_borda_caminho="#A16207",
        cor_parede="#A16207",
        cor_parede_borda="#713F12",
        cor_traco="#CA8A04",
        icone_inicio="cao",
        icone_fim="casota",
        tipo_obstaculo="cerca",
    ),
    # Estações do ano associadas a frutos e flores da época
    CenarioLabirinto(
        id="primavera",
        chave_nome="lab.cen_primavera",
        chave_missao="lab.mis_primavera",
        cor_fundo_1="#FCE7F3",
        cor_fundo_2="#DCFCE7",
        cor_caminho="#FFFDF7",
        cor_borda_caminho="#DB2777",
        cor_parede="#16A34A",
        cor_parede_borda="#166534",
        cor_traco="#EC4899",
        icone_inicio="borboleta",
        icone_fim="flor",
        tipo_obstaculo="tulipa",
    ),
    CenarioLabirinto(
        id="verao",
        chave_nome="lab.cen_verao",
        chave_missao="lab.mis_verao",
        cor_fundo_1="#FEF9C3",
        cor_fundo_2="#BAE6FD",
        cor_caminho="#FFFBEB",
        cor_borda_caminho="#EA580C",
        cor_parede="#0EA5E9",
        cor_parede_borda="#0369A1",
        cor_traco="#F97316",
        icone_inicio="crianca",
        icone_fim="melancia",
        tipo_obstaculo="guardasol",
    ),
    CenarioLabirinto(
        id="outono",
        chave_nome="lab.cen_outono",
        chave_missao="lab.mis_outono",
        cor_fundo_1="#FFEDD5",
        cor_fundo_2="#FED7AA",
        cor_caminho="#FFFBEB",
        cor_borda_caminho="#C2410C",
        cor_parede="#C2410C",
        cor_parede_borda="#7C2D12",
        cor_traco="#EA580C",
        icone_inicio="esquilo",
        icone_fim="castanha",
        tipo_obstaculo="cogumelo",
    ),
    CenarioLabirinto(
        id="inverno",
        chave_nome="lab.cen_inverno",
        chave_missao="lab.mis_inverno",
        cor_fundo_1="#E0F2FE",
        cor_fundo_2="#E2E8F0",
        cor_caminho="#FFFFFF",
        cor_borda_caminho="#2563EB",
        cor_parede="#3B82F6",
        cor_parede_borda="#1E40AF",
        cor_traco="#2563EB",
        icone_inicio="pinguim",
        icone_fim="laranja",
        tipo_obstaculo="neve",
    ),
    # Objetos do dia a dia & cenários cotidianos
    CenarioLabirinto(
        id="escola",
        chave_nome="lab.cen_escola",
        chave_missao="lab.mis_escola",
        cor_fundo_1="#E0E7FF",
        cor_fundo_2="#C7D2FE",
        cor_caminho="#F8FAFC",
        cor_borda_caminho="#4F46E5",
        cor_parede="#4338CA",
        cor_parede_borda="#312E81",
        cor_traco="#4F46E5",
        icone_inicio="mochila",
        icone_fim="escola",
        tipo_obstaculo="casa",
    ),
    CenarioLabirinto(
        id="cozinha",
        chave_nome="lab.cen_cozinha",
        chave_missao="lab.mis_cozinha",
        cor_fundo_1="#FEE2E2",
        cor_fundo_2="#FEF3C7",
        cor_caminho="#FFFDF7",
        cor_borda_caminho="#DC2626",
        cor_parede="#E11D48",
        cor_parede_borda="#881337",
        cor_traco="#DC2626",
        icone_inicio="cesto",
        icone_fim="maca",
        tipo_obstaculo="chavena",
    ),
)

_CENARIOS_POR_ID = {c.id: c for c in CENARIOS}


@dataclass
class LabirintoDados:
    """Estrutura de um labirinto perfeito (sempre solucionável) em grelha cols x rows."""

    cols: int
    rows: int
    # Arestas abertas entre células adjacentes: conjunto de pares ordenados ((c1, r1), (c2, r2))
    passagens: set[tuple[tuple[int, int], tuple[int, int]]]
    inicio: tuple[int, int]
    fim: tuple[int, int]
    caminho_solucao: list[tuple[int, int]]

    def tem_passagem(self, a: tuple[int, int], b: tuple[int, int]) -> bool:
        par = (a, b) if a <= b else (b, a)
        return par in self.passagens


def dimensoes_para_nivel(nivel: int) -> tuple[int, int]:
    """Progressão suave de complexidade: de labirintos curtos (4x3) até labirintos longos (12x7)."""
    tabela = (
        (4, 3),   # Nível 1 — muito curto e largo
        (5, 3),   # Nível 2
        (5, 4),   # Nível 3
        (6, 4),   # Nível 4
        (7, 5),   # Nível 5
        (8, 5),   # Nível 6
        (9, 6),   # Nível 7
        (10, 6),  # Nível 8
        (11, 7),  # Nível 9
    )
    if nivel <= 1:
        return tabela[0]
    if nivel <= len(tabela):
        return tabela[nivel - 1]
    return (12, 7)


def gerar_labirinto(cols: int, rows: int, rng: random.Random | None = None) -> LabirintoDados:
    """Gera um labirinto perfeito via DFS (Recursive Backtracker) e escolhe a chegada mais distante via BFS."""
    r = rng or random.Random()
    inicio = (0, 0)
    visitadas = {inicio}
    pilha = [inicio]
    passagens: set[tuple[tuple[int, int], tuple[int, int]]] = set()

    while pilha:
        c, l = pilha[-1]
        vizinhos = []
        for dc, dl in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nl = c + dc, l + dl
            if 0 <= nc < cols and 0 <= nl < rows and (nc, nl) not in visitadas:
                vizinhos.append((nc, nl))
        if vizinhos:
            prox = r.choice(vizinhos)
            par = ((c, l), prox) if (c, l) <= prox else (prox, (c, l))
            passagens.add(par)
            visitadas.add(prox)
            pilha.append(prox)
        else:
            pilha.pop()

    # BFS a partir do início para encontrar a célula mais distante (garante percurso interessante)
    fila: deque[tuple[int, int]] = deque([inicio])
    pai: dict[tuple[int, int], tuple[int, int] | None] = {inicio: None}
    dist: dict[tuple[int, int], int] = {inicio: 0}
    mais_longe = inicio

    while fila:
        atual = fila.popleft()
        if dist[atual] > dist[mais_longe]:
            mais_longe = atual
        c, l = atual
        for dc, dl in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            prox = (c + dc, l + dl)
            if 0 <= prox[0] < cols and 0 <= prox[1] < rows and prox not in pai:
                par = (atual, prox) if atual <= prox else (prox, atual)
                if par in passagens:
                    pai[prox] = atual
                    dist[prox] = dist[atual] + 1
                    fila.append(prox)

    caminho: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = mais_longe
    while cur is not None:
        caminho.append(cur)
        cur = pai[cur]
    caminho.reverse()

    return LabirintoDados(
        cols=cols,
        rows=rows,
        passagens=passagens,
        inicio=inicio,
        fim=mais_longe,
        caminho_solucao=caminho,
    )


# --- Ilustrações vetoriais simpáticas (personagens, animais, frutos, flores, objetos) ---


def _desenhar_item_vetorial(p: QPainter, tipo: str, cx: float, cy: float, r: float) -> None:
    """Desenha um ícone vetorial colorido centrado em (cx, cy) com raio r."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    if tipo == "coelho":
        p.setPen(QPen(QColor("#94A3B8"), 1.6))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(cx - r * 0.28, cy - r * 0.65), r * 0.18, r * 0.45)
        p.drawEllipse(QPointF(cx + r * 0.28, cy - r * 0.65), r * 0.18, r * 0.45)
        p.setBrush(QColor("#FBCFE8"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx - r * 0.28, cy - r * 0.65), r * 0.08, r * 0.28)
        p.drawEllipse(QPointF(cx + r * 0.28, cy - r * 0.65), r * 0.08, r * 0.28)
        p.setPen(QPen(QColor("#94A3B8"), 1.6))
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(cx, cy + r * 0.05), r * 0.56, r * 0.50)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1E293B"))
        p.drawEllipse(QPointF(cx - r * 0.18, cy - r * 0.02), r * 0.08, r * 0.08)
        p.drawEllipse(QPointF(cx + r * 0.18, cy - r * 0.02), r * 0.08, r * 0.08)
        p.setBrush(QColor("#F472B6"))
        p.drawEllipse(QPointF(cx, cy + r * 0.14), r * 0.10, r * 0.07)

    elif tipo == "cenoura":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#16A34A"))
        p.drawEllipse(QPointF(cx - r * 0.14, cy - r * 0.52), r * 0.18, r * 0.26)
        p.drawEllipse(QPointF(cx + r * 0.14, cy - r * 0.52), r * 0.18, r * 0.26)
        p.setBrush(QColor("#F97316"))
        p.setPen(QPen(QColor("#C2410C"), 1.4))
        poly = QPolygonF([
            QPointF(cx - r * 0.34, cy - r * 0.32),
            QPointF(cx + r * 0.34, cy - r * 0.32),
            QPointF(cx, cy + r * 0.66),
        ])
        p.drawPolygon(poly)

    elif tipo == "leao":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#B45309"))
        for ang in range(0, 360, 30):
            rad = math.radians(ang)
            p.drawEllipse(QPointF(cx + math.cos(rad) * r * 0.52, cy + math.sin(rad) * r * 0.52), r * 0.24, r * 0.24)
        p.setBrush(QColor("#FBBF24"))
        p.drawEllipse(QPointF(cx, cy), r * 0.52, r * 0.50)
        p.setBrush(QColor("#1E293B"))
        p.drawEllipse(QPointF(cx - r * 0.18, cy - r * 0.06), r * 0.07, r * 0.07)
        p.drawEllipse(QPointF(cx + r * 0.18, cy - r * 0.06), r * 0.07, r * 0.07)
        p.setBrush(QColor("#78350F"))
        p.drawEllipse(QPointF(cx, cy + r * 0.12), r * 0.12, r * 0.08)

    elif tipo == "oasis":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0EA5E9"))
        p.drawEllipse(QPointF(cx, cy + r * 0.25), r * 0.68, r * 0.34)
        p.setPen(QPen(QColor("#92400E"), max(2.0, r * 0.14), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(cx - r * 0.15, cy + r * 0.15), QPointF(cx - r * 0.05, cy - r * 0.42))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#16A34A"))
        p.drawEllipse(QPointF(cx - r * 0.32, cy - r * 0.44), r * 0.32, r * 0.13)
        p.drawEllipse(QPointF(cx + r * 0.22, cy - r * 0.44), r * 0.32, r * 0.13)

    elif tipo == "peixe":
        p.setPen(QPen(QColor("#EA580C"), 1.4))
        p.setBrush(QColor("#FB923C"))
        cauda = QPolygonF([
            QPointF(cx - r * 0.32, cy),
            QPointF(cx - r * 0.74, cy - r * 0.36),
            QPointF(cx - r * 0.74, cy + r * 0.36),
        ])
        p.drawPolygon(cauda)
        p.drawEllipse(QPointF(cx + r * 0.10, cy), r * 0.56, r * 0.38)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(cx + r * 0.34, cy - r * 0.08), r * 0.12, r * 0.12)
        p.setBrush(QColor("#0F172A"))
        p.drawEllipse(QPointF(cx + r * 0.37, cy - r * 0.08), r * 0.06, r * 0.06)

    elif tipo == "concha":
        p.setPen(QPen(QColor("#DB2777"), 1.5))
        p.setBrush(QColor("#F9A8D4"))
        p.drawChord(QRectF(cx - r * 0.65, cy - r * 0.45, r * 1.30, r * 1.15), 0, 180 * 16)
        p.setBrush(QColor("#FEF08A"))
        p.drawEllipse(QPointF(cx, cy + r * 0.12), r * 0.18, r * 0.18)

    elif tipo == "cao":
        p.setPen(QPen(QColor("#78350F"), 1.5))
        p.setBrush(QColor("#92400E"))
        p.drawEllipse(QPointF(cx - r * 0.48, cy - r * 0.05), r * 0.22, r * 0.40)
        p.drawEllipse(QPointF(cx + r * 0.48, cy - r * 0.05), r * 0.22, r * 0.40)
        p.setBrush(QColor("#D97706"))
        p.drawEllipse(QPointF(cx, cy), r * 0.50, r * 0.48)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1E293B"))
        p.drawEllipse(QPointF(cx - r * 0.18, cy - r * 0.08), r * 0.08, r * 0.08)
        p.drawEllipse(QPointF(cx + r * 0.18, cy - r * 0.08), r * 0.08, r * 0.08)
        p.drawEllipse(QPointF(cx, cy + r * 0.12), r * 0.12, r * 0.09)

    elif tipo == "casota":
        p.setPen(QPen(QColor("#991B1B"), 1.5))
        p.setBrush(QColor("#FDE68A"))
        p.drawRect(QRectF(cx - r * 0.48, cy - r * 0.08, r * 0.96, r * 0.64))
        p.setBrush(QColor("#DC2626"))
        teto = QPolygonF([
            QPointF(cx - r * 0.64, cy - r * 0.05),
            QPointF(cx, cy - r * 0.64),
            QPointF(cx + r * 0.64, cy - r * 0.05),
        ])
        p.drawPolygon(teto)
        p.setBrush(QColor("#78350F"))
        p.drawRoundedRect(QRectF(cx - r * 0.18, cy + r * 0.12, r * 0.36, r * 0.44), 6, 6)

    elif tipo == "borboleta":
        p.setPen(QPen(QColor("#9D174D"), 1.3))
        p.setBrush(QColor("#F472B6"))
        p.drawEllipse(QPointF(cx - r * 0.34, cy - r * 0.18), r * 0.34, r * 0.28)
        p.drawEllipse(QPointF(cx + r * 0.34, cy - r * 0.18), r * 0.34, r * 0.28)
        p.setBrush(QColor("#C084FC"))
        p.drawEllipse(QPointF(cx - r * 0.26, cy + r * 0.24), r * 0.24, r * 0.22)
        p.drawEllipse(QPointF(cx + r * 0.26, cy + r * 0.24), r * 0.24, r * 0.22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1E293B"))
        p.drawRoundedRect(QRectF(cx - r * 0.08, cy - r * 0.42, r * 0.16, r * 0.84), 4, 4)

    elif tipo == "flor":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F43F5E"))
        for ang in range(0, 360, 60):
            rad = math.radians(ang)
            p.drawEllipse(QPointF(cx + math.cos(rad) * r * 0.38, cy + math.sin(rad) * r * 0.38), r * 0.26, r * 0.26)
        p.setBrush(QColor("#FACC15"))
        p.drawEllipse(QPointF(cx, cy), r * 0.28, r * 0.28)

    elif tipo == "crianca":
        p.setPen(QPen(QColor("#B45309"), 1.4))
        p.setBrush(QColor("#FDE68A"))
        p.drawEllipse(QPointF(cx, cy - r * 0.05), r * 0.50, r * 0.50)
        p.setBrush(QColor("#F59E0B"))
        p.drawChord(QRectF(cx - r * 0.52, cy - r * 0.58, r * 1.04, r * 0.55), 0, 180 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1E293B"))
        p.drawEllipse(QPointF(cx - r * 0.16, cy - r * 0.06), r * 0.07, r * 0.07)
        p.drawEllipse(QPointF(cx + r * 0.16, cy - r * 0.06), r * 0.07, r * 0.07)
        p.setPen(QPen(QColor("#DC2626"), 2.0))
        p.drawArc(QRectF(cx - r * 0.20, cy + r * 0.02, r * 0.40, r * 0.26), 200 * 16, 140 * 16)

    elif tipo == "melancia":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#16A34A"))
        p.drawChord(QRectF(cx - r * 0.68, cy - r * 0.52, r * 1.36, r * 1.18), 180 * 16, 180 * 16)
        p.setBrush(QColor("#EF4444"))
        p.drawChord(QRectF(cx - r * 0.56, cy - r * 0.42, r * 1.12, r * 0.96), 180 * 16, 180 * 16)
        p.setBrush(QColor("#1E293B"))
        for dx in (-0.22, 0.0, 0.22):
            p.drawEllipse(QPointF(cx + dx * r, cy + r * 0.22), r * 0.05, r * 0.08)

    elif tipo == "esquilo":
        p.setPen(QPen(QColor("#7C2D12"), 1.4))
        p.setBrush(QColor("#C2410C"))
        p.drawEllipse(QPointF(cx - r * 0.36, cy - r * 0.08), r * 0.30, r * 0.48)
        p.setBrush(QColor("#EA580C"))
        p.drawEllipse(QPointF(cx + r * 0.12, cy + r * 0.04), r * 0.44, r * 0.42)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1E293B"))
        p.drawEllipse(QPointF(cx + r * 0.26, cy - r * 0.06), r * 0.07, r * 0.07)

    elif tipo == "castanha":
        p.setPen(QPen(QColor("#451A03"), 1.5))
        p.setBrush(QColor("#92400E"))
        p.drawEllipse(QPointF(cx, cy + r * 0.08), r * 0.48, r * 0.44)
        p.setBrush(QColor("#FDE68A"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy + r * 0.36), r * 0.26, r * 0.12)

    elif tipo == "pinguim":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0F172A"))
        p.drawEllipse(QPointF(cx, cy), r * 0.50, r * 0.60)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(cx, cy + r * 0.10), r * 0.32, r * 0.40)
        p.setBrush(QColor("#F97316"))
        bico = QPolygonF([QPointF(cx - r * 0.12, cy - r * 0.16), QPointF(cx + r * 0.12, cy - r * 0.16), QPointF(cx, cy - r * 0.02)])
        p.drawPolygon(bico)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(cx - r * 0.14, cy - r * 0.28), r * 0.07, r * 0.07)
        p.drawEllipse(QPointF(cx + r * 0.14, cy - r * 0.28), r * 0.07, r * 0.07)

    elif tipo == "laranja":
        p.setPen(QPen(QColor("#C2410C"), 1.5))
        p.setBrush(QColor("#FB923C"))
        p.drawEllipse(QPointF(cx, cy + r * 0.06), r * 0.50, r * 0.48)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#16A34A"))
        p.drawEllipse(QPointF(cx + r * 0.18, cy - r * 0.46), r * 0.22, r * 0.12)

    elif tipo == "mochila":
        p.setPen(QPen(QColor("#1E3A8A"), 1.6))
        p.setBrush(QColor("#3B82F6"))
        p.drawRoundedRect(QRectF(cx - r * 0.44, cy - r * 0.46, r * 0.88, r * 0.96), 10, 10)
        p.setBrush(QColor("#93C5FD"))
        p.drawRoundedRect(QRectF(cx - r * 0.30, cy + r * 0.04, r * 0.60, r * 0.34), 6, 6)

    elif tipo == "escola":
        p.setPen(QPen(QColor("#991B1B"), 1.5))
        p.setBrush(QColor("#FEF08A"))
        p.drawRect(QRectF(cx - r * 0.54, cy - r * 0.14, r * 1.08, r * 0.68))
        p.setBrush(QColor("#EF4444"))
        teto = QPolygonF([QPointF(cx - r * 0.66, cy - r * 0.12), QPointF(cx, cy - r * 0.66), QPointF(cx + r * 0.66, cy - r * 0.12)])
        p.drawPolygon(teto)
        p.setBrush(QColor("#3B82F6"))
        p.drawRect(QRectF(cx - r * 0.16, cy + r * 0.14, r * 0.32, r * 0.40))

    elif tipo == "cesto":
        p.setPen(QPen(QColor("#92400E"), 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx - r * 0.38, cy - r * 0.56, r * 0.76, r * 0.64), 0, 180 * 16)
        p.setBrush(QColor("#D97706"))
        p.drawRoundedRect(QRectF(cx - r * 0.52, cy - r * 0.14, r * 1.04, r * 0.64), 8, 8)

    elif tipo == "maca":
        p.setPen(QPen(QColor("#991B1B"), 1.5))
        p.setBrush(QColor("#EF4444"))
        p.drawEllipse(QPointF(cx, cy + r * 0.06), r * 0.50, r * 0.48)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#16A34A"))
        p.drawEllipse(QPointF(cx + r * 0.18, cy - r * 0.46), r * 0.22, r * 0.12)

    p.restore()


def _desenhar_obstaculo_mini(p: QPainter, tipo: str, cx: float, cy: float, s: float) -> None:
    """Desenha um pequeno elemento decorativo temático sobre os nós das paredes do labirinto."""
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    if tipo == "arvore":
        p.setBrush(QColor("#14532D"))
        p.drawEllipse(QPointF(cx, cy), s * 0.58, s * 0.58)
        p.setBrush(QColor("#22C55E"))
        p.drawEllipse(QPointF(cx - s * 0.12, cy - s * 0.12), s * 0.32, s * 0.32)
    elif tipo == "cacto":
        p.setBrush(QColor("#15803D"))
        p.drawRoundedRect(QRectF(cx - s * 0.22, cy - s * 0.52, s * 0.44, s * 1.04), 4, 4)
    elif tipo == "coral":
        p.setBrush(QColor("#F472B6"))
        p.drawEllipse(QPointF(cx, cy), s * 0.46, s * 0.46)
    elif tipo == "cerca":
        p.setBrush(QColor("#FDE047"))
        p.drawRoundedRect(QRectF(cx - s * 0.42, cy - s * 0.32, s * 0.84, s * 0.64), 3, 3)
    elif tipo == "tulipa":
        p.setBrush(QColor("#F43F5E"))
        p.drawEllipse(QPointF(cx, cy - s * 0.12), s * 0.36, s * 0.36)
        p.setBrush(QColor("#FACC15"))
        p.drawEllipse(QPointF(cx, cy - s * 0.12), s * 0.16, s * 0.16)
    elif tipo == "guardasol":
        p.setBrush(QColor("#F97316"))
        p.drawEllipse(QPointF(cx, cy), s * 0.50, s * 0.50)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(cx, cy), s * 0.20, s * 0.20)
    elif tipo == "cogumelo":
        p.setBrush(QColor("#FEF3C7"))
        p.drawRect(QRectF(cx - s * 0.16, cy, s * 0.32, s * 0.42))
        p.setBrush(QColor("#DC2626"))
        p.drawChord(QRectF(cx - s * 0.46, cy - s * 0.42, s * 0.92, s * 0.80), 0, 180 * 16)
    elif tipo == "neve":
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(cx, cy), s * 0.48, s * 0.48)
        p.setBrush(QColor("#93C5FD"))
        p.drawEllipse(QPointF(cx, cy), s * 0.18, s * 0.18)
    elif tipo == "casa":
        p.setBrush(QColor("#FDE68A"))
        p.drawRect(QRectF(cx - s * 0.38, cy - s * 0.12, s * 0.76, s * 0.52))
        p.setBrush(QColor("#EF4444"))
        p.drawPolygon(QPolygonF([QPointF(cx - s * 0.46, cy - s * 0.10), QPointF(cx, cy - s * 0.52), QPointF(cx + s * 0.46, cy - s * 0.10)]))
    elif tipo == "chavena":
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(cx - s * 0.36, cy - s * 0.28, s * 0.72, s * 0.56), 4, 4)
        p.setBrush(QColor("#F97316"))
        p.drawEllipse(QPointF(cx, cy), s * 0.16, s * 0.16)
    p.restore()


class AreaLabirinto(QWidget):
    """Canvas interativo de labirintos com deteção de colisão, instrução visual e celebração."""

    estado_alterado = Signal(str)
    nivel_alterado = Signal(int, str)  # nivel, nome_cenario

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(760, 480)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

        self._rng = random.Random()
        self._escuro = tema_partilhado.e_escuro()
        self.som_ativo = True
        self.nivel = 1
        self.modo_progressivo = True  # True = Progressivo (sobe nível), False = Manual (mantém nível)
        self.borracha_ativa = False
        self._ronda_manual = 0
        self.cenario_fixo: str | None = None  # None = roda automaticamente pelos 10 cenários
        self.cenario: CenarioLabirinto = CENARIOS[0]
        self.labirinto: LabirintoDados = gerar_labirinto(4, 3, self._rng)

        self.estado = "pronto"  # "pronto", "a_tracar", "pausado", "erro", "vitoria"
        self._traco: list[QPointF] = []
        self._ponto_erro: QPointF | None = None
        self._tempo_erro = 0.0
        self._tempo_vitoria = 0.0
        self._pulso = 0.0
        self._confetes: list[tuple[float, float, float, float, QColor]] = []

        # Controlo de palm rejection (caneta > toque > rato)
        self._usando_caneta = False
        self._ultimo_toque_s = 0.0

        # Geometria calculada do labirinto em ecrã
        self._rect_grelha = QRectF()
        self._cell_w = 80.0
        self._cell_h = 80.0
        self._esp_parede = 14.0
        self._paredes: list[QRectF] = []

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.iniciar_nivel(1)

    # --- Controlo de níveis e cenários --------------------------------------------

    def definir_tema(self, escuro: bool) -> None:
        self._escuro = escuro
        self.update()

    def definir_cenario_fixo(self, cenario_id: str | None) -> None:
        self.cenario_fixo = cenario_id if cenario_id in _CENARIOS_POR_ID else None
        self.iniciar_nivel(self.nivel)

    def definir_modo_progressivo(self, progressivo: bool) -> None:
        self.modo_progressivo = bool(progressivo)

    def definir_borracha(self, ativa: bool) -> None:
        self.borracha_ativa = bool(ativa)
        if self.borracha_ativa:
            if self.estado == "a_tracar":
                self.estado = "pausado" if self._traco else "pronto"
            self.estado_alterado.emit(t("lab.borracha_dica"))
        else:
            self.estado_alterado.emit(t(self.cenario.chave_missao))
        self.update()

    def iniciar_nivel(self, nivel: int) -> None:
        self.nivel = max(1, nivel)
        if self.cenario_fixo is not None:
            self.cenario = _CENARIOS_POR_ID[self.cenario_fixo]
        else:
            idx_cen = (self.nivel - 1 + self._ronda_manual) % len(CENARIOS)
            self.cenario = CENARIOS[idx_cen]

        cols, rows = dimensoes_para_nivel(self.nivel)
        self.labirinto = gerar_labirinto(cols, rows, self._rng)
        self._traco.clear()
        self._ponto_erro = None
        self._confetes.clear()
        self.estado = "pronto"
        self._reconstruir_geometria()
        self.nivel_alterado.emit(self.nivel, t(self.cenario.chave_nome))
        self.estado_alterado.emit(t(self.cenario.chave_missao))
        self.update()

    def proximo_nivel(self) -> None:
        if self.modo_progressivo:
            self.iniciar_nivel(self.nivel + 1)
        else:
            self._ronda_manual += 1
            self.iniciar_nivel(self.nivel)

    def reiniciar_traco(self) -> None:
        self._traco.clear()
        self._ponto_erro = None
        self.estado = "pronto"
        self.estado_alterado.emit(t(self.cenario.chave_missao))
        self.update()

    # --- Geometria e paredes ------------------------------------------------------

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        self._reconstruir_geometria()

    def _centro_celula(self, cel: tuple[int, int]) -> QPointF:
        c, l = cel
        return QPointF(
            self._rect_grelha.x() + (c + 0.5) * self._cell_w,
            self._rect_grelha.y() + (l + 0.5) * self._cell_h,
        )

    def _reconstruir_geometria(self) -> None:
        w = max(320.0, float(self.width()))
        h = max(240.0, float(self.height()))
        margem_x = max(26.0, w * 0.045)
        margem_topo = max(42.0, h * 0.08)
        margem_baixo = max(26.0, h * 0.05)

        disp_w = max(200.0, w - margem_x * 2)
        disp_h = max(160.0, h - margem_topo - margem_baixo)

        cols, rows = self.labirinto.cols, self.labirinto.rows
        lado = min(disp_w / cols, disp_h / rows)
        gw = lado * cols
        gh = lado * rows
        gx = (w - gw) / 2.0
        gy = margem_topo + (disp_h - gh) / 2.0

        self._rect_grelha = QRectF(gx, gy, gw, gh)
        self._cell_w = lado
        self._cell_h = lado
        # Espessura generosa das paredes (mas sempre deixando corredores largos para a criança)
        self._esp_parede = max(8.0, min(18.0, lado * 0.14))

        e = self._esp_parede
        meio = e / 2.0
        paredes: list[QRectF] = []

        # Moldura exterior (4 lados)
        paredes.append(QRectF(gx - meio, gy - meio, gw + e, e))           # Topo
        paredes.append(QRectF(gx - meio, gy + gh - meio, gw + e, e))     # Base
        paredes.append(QRectF(gx - meio, gy - meio, e, gh + e))          # Esquerda
        paredes.append(QRectF(gx + gw - meio, gy - meio, e, gh + e))     # Direita

        # Paredes internas verticais e horizontais onde NÃO há passagem
        for l in range(rows):
            for c in range(cols):
                if c + 1 < cols and not self.labirinto.tem_passagem((c, l), (c + 1, l)):
                    x = gx + (c + 1) * lado - meio
                    y = gy + l * lado - meio
                    paredes.append(QRectF(x, y, e, lado + e))
                if l + 1 < rows and not self.labirinto.tem_passagem((c, l), (c, l + 1)):
                    x = gx + c * lado - meio
                    y = gy + (l + 1) * lado - meio
                    paredes.append(QRectF(x, y, lado + e, e))

        self._paredes = paredes

    # --- Deteção de colisão e progressão ------------------------------------------

    def _ponto_colide_parede(self, pt: QPointF) -> bool:
        """Verifica se `pt` atravessou uma parede ou saiu fora da grelha."""
        if not self._rect_grelha.contains(pt):
            return True
        # Pequena margem de tolerância (2 px) para não punir toques de raspão na borda do corredor
        tol = max(1.0, self._esp_parede * 0.14)
        for parede in self._paredes:
            efetiva = parede.adjusted(tol, tol, -tol, -tol)
            if efetiva.width() > 0 and efetiva.height() > 0 and efetiva.contains(pt):
                return True
        return False

    def _apagar_em(self, pt: QPointF) -> None:
        """Apaga parte do traço a partir do ponto mais próximo tocado pela borracha."""
        if not self._traco:
            return
        raio = max(18.0, self._cell_w * 0.30)
        # Percorre do fim para o início para recuar o traço suavemente
        idx_corte: int | None = None
        for i in range(len(self._traco) - 1, -1, -1):
            p = self._traco[i]
            if math.hypot(pt.x() - p.x(), pt.y() - p.y()) <= raio:
                idx_corte = i
        if idx_corte is not None:
            self._traco = self._traco[:idx_corte]
            if not self._traco:
                self.estado = "pronto"
            else:
                self.estado = "pausado"
            self.update()

    def _iniciar_traco(self, pt: QPointF) -> None:
        if self.estado == "vitoria":
            return
        if self.borracha_ativa:
            self._apagar_em(pt)
            return
        if self.estado == "erro":
            # Permite retomar imediatamente sem ficar bloqueado pelo flash
            self._ponto_erro = None
            self.estado = "pausado" if self._traco else "pronto"

        # Se já existe traço no ecrã, retoma a partir da ponta atual do traço
        if self._traco:
            ponta = self._traco[-1]
            raio_retomar = max(24.0, self._cell_w * 0.56)
            if math.hypot(pt.x() - ponta.x(), pt.y() - ponta.y()) <= raio_retomar:
                self.estado = "a_tracar"
                self._ponto_erro = None
                self.update()
                return
            self.estado_alterado.emit(t("lab.continua_na_ponta"))
            self.update()
            return

        centro_ini = self._centro_celula(self.labirinto.inicio)
        raio_ini = self._cell_w * 0.56
        if math.hypot(pt.x() - centro_ini.x(), pt.y() - centro_ini.y()) <= raio_ini:
            self.estado = "a_tracar"
            self._traco = [pt]
            self._ponto_erro = None
            if self.som_ativo:
                sons.tocar_ding()
            self.update()
        else:
            # Lembra gentilmente que tem de começar no ponto verde
            self.estado_alterado.emit(t("lab.comeca_no_verde"))
            self.update()

    def _continuar_traco(self, pt: QPointF) -> None:
        if self.borracha_ativa:
            if self.estado != "vitoria":
                self._apagar_em(pt)
            return
        if self.estado != "a_tracar" or not self._traco:
            return
        anterior = self._traco[-1]
        dist = math.hypot(pt.x() - anterior.x(), pt.y() - anterior.y())
        if dist < 2.0:
            return

        # Amostra pontos ao longo do segmento para impedir "saltos" por cima de paredes
        passos = max(1, int(math.ceil(dist / 4.0)))
        for i in range(1, passos + 1):
            f = i / passos
            amostra = QPointF(anterior.x() + (pt.x() - anterior.x()) * f, anterior.y() + (pt.y() - anterior.y()) * f)
            if self._ponto_colide_parede(amostra):
                self._falhar_obstaculo(amostra)
                return

        self._traco.append(pt)

        # Verifica se chegou ao objetivo (célula de chegada)
        centro_fim = self._centro_celula(self.labirinto.fim)
        if math.hypot(pt.x() - centro_fim.x(), pt.y() - centro_fim.y()) <= self._cell_w * 0.42:
            self._vencer_nivel()
            return
        self.update()

    def _falhar_obstaculo(self, ponto: QPointF) -> None:
        # Não apaga o traço nem volta ao início: fica exatamente onde estava!
        self.estado = "erro"
        self._ponto_erro = ponto
        self._tempo_erro = 0.65
        if self.som_ativo:
            sons.tocar_embate()
        self.estado_alterado.emit(t("lab.erro_obstaculo"))
        self.update()

    def _vencer_nivel(self) -> None:
        self.estado = "vitoria"
        self._tempo_vitoria = 2.8
        if self.som_ativo:
            sons.tocar_musica_descanso()
            if self.isVisible():
                elogio = t(self._rng.choice(("jogos.elogio_1", "jogos.elogio_2", "jogos.elogio_3", "jogos.elogio_4")))
                try:
                    voz.falar(elogio)
                except Exception:
                    pass
        w = max(400.0, float(self.width()))
        h = max(300.0, float(self.height()))
        cores = ("#FACC15", "#22C55E", "#3B82F6", "#EC4899", "#F97316", "#A855F7")
        self._confetes = [
            (
                self._rng.uniform(w * 0.15, w * 0.85),
                self._rng.uniform(h * 0.10, h * 0.45),
                self._rng.uniform(-1.8, 1.8),
                self._rng.uniform(1.8, 4.2),
                QColor(self._rng.choice(cores)),
            )
            for _ in range(36)
        ]
        self.estado_alterado.emit(t("lab.vitoria", n=self.nivel))
        self.update()

    def _tick(self) -> None:
        dt = 0.03
        self._pulso += 0.14
        if self.estado == "erro":
            self._tempo_erro -= dt
            if self._tempo_erro <= 0.0:
                self._ponto_erro = None
                self.estado = "pausado" if self._traco else "pronto"
        elif self.estado == "vitoria":
            self._tempo_vitoria -= dt
            self._confetes = [(x + vx, y + vy, vx, vy, c) for (x, y, vx, vy, c) in self._confetes]
            if self._tempo_vitoria <= 0.0:
                self.proximo_nivel()
        self.update()

    # --- Entrada: Caneta (Palm Rejection) > Toque > Rato --------------------------

    def tabletEvent(self, evento: QTabletEvent) -> None:  # noqa: N802
        tipo = evento.type()
        if tipo == QEvent.Type.TabletPress:
            self._usando_caneta = True
            self._iniciar_traco(evento.position())
            evento.accept()
            return
        if tipo == QEvent.Type.TabletMove and self._usando_caneta:
            self._continuar_traco(evento.position())
            evento.accept()
            return
        if tipo == QEvent.Type.TabletRelease:
            self._usando_caneta = False
            if self.estado == "a_tracar":
                self.estado = "pausado" if self._traco else "pronto"
                self.update()
            evento.accept()
            return
        super().tabletEvent(evento)

    def event(self, evento: QEvent) -> bool:
        tipo = evento.type()
        if tipo in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd):
            if self._usando_caneta:
                evento.accept()
                return True
            self._ultimo_toque_s = time.monotonic()
            te: QTouchEvent = evento  # type: ignore[assignment]
            if tipo == QEvent.Type.TouchEnd:
                if self.estado == "a_tracar":
                    self.estado = "pausado" if self._traco else "pronto"
                    self.update()
            elif te.points():
                pt = te.points()[0].position()
                if tipo == QEvent.Type.TouchBegin:
                    self._iniciar_traco(pt)
                elif tipo == QEvent.Type.TouchUpdate:
                    self._continuar_traco(pt)
            evento.accept()
            return True
        return super().event(evento)

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if self._usando_caneta or (time.monotonic() - self._ultimo_toque_s) < 0.30:
            evento.accept()
            return
        if evento.button() == Qt.MouseButton.LeftButton:
            self._iniciar_traco(evento.position())
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if self._usando_caneta or (time.monotonic() - self._ultimo_toque_s) < 0.30:
            evento.accept()
            return
        if evento.buttons() & Qt.MouseButton.LeftButton:
            self._continuar_traco(evento.position())
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        if self.estado == "a_tracar":
            self.estado = "pausado" if self._traco else "pronto"
            self.update()
        super().mouseReleaseEvent(evento)

    # --- Desenho ------------------------------------------------------------------

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        cen = self.cenario

        # 1. Fundo temático suave
        grad = QLinearGradient(0, 0, 0, h)
        if self._escuro:
            grad.setColorAt(0.0, QColor("#0F172A"))
            grad.setColorAt(1.0, QColor("#1E293B"))
        else:
            grad.setColorAt(0.0, QColor(cen.cor_fundo_1))
            grad.setColorAt(1.0, QColor(cen.cor_fundo_2))
        p.fillRect(QRectF(0, 0, w, h), grad)

        # 2. Tabuleiro do labirinto (caminhos)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1E293B") if self._escuro else QColor(cen.cor_caminho))
        p.drawRoundedRect(self._rect_grelha, 14, 14)

        # 3. Paredes / Obstáculos temáticos
        cor_p = QColor(cen.cor_parede)
        cor_pb = QColor(cen.cor_parede_borda)
        p.setBrush(cor_p)
        p.setPen(QPen(cor_pb, 1.5))
        for parede in self._paredes:
            p.drawRoundedRect(parede, self._esp_parede * 0.45, self._esp_parede * 0.45)

        # Pequenos desenhos temáticos (árvores, casas, flores, corais, neve, chávenas...) nos vértices das paredes
        gx, gy = self._rect_grelha.x(), self._rect_grelha.y()
        lado = self._cell_w
        s_mini = max(7.0, min(14.0, self._esp_parede * 0.85))
        for l in range(self.labirinto.rows + 1):
            for c in range(self.labirinto.cols + 1):
                if (c + l) % 2 == 0:
                    _desenhar_obstaculo_mini(p, cen.tipo_obstaculo, gx + c * lado, gy + l * lado, s_mini)

        # 4. Instrução visual de INÍCIO (halo verde pulsante + seta inicial) e FIM (halo dourado pulsante)
        pulso = 0.5 + 0.5 * math.sin(self._pulso * 2.0)
        c_ini = self._centro_celula(self.labirinto.inicio)
        c_fim = self._centro_celula(self.labirinto.fim)
        raio_icone = max(14.0, self._cell_w * 0.30)

        # Halo INÍCIO
        halo_ini = QRadialGradient(c_ini, raio_icone * (1.55 + 0.25 * pulso))
        halo_ini.setColorAt(0.0, QColor(34, 197, 94, 150))
        halo_ini.setColorAt(1.0, QColor(34, 197, 94, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo_ini)
        p.drawEllipse(c_ini, raio_icone * (1.55 + 0.25 * pulso), raio_icone * (1.55 + 0.25 * pulso))
        p.setPen(QPen(QColor("#16A34A"), 3.0))
        p.setBrush(QColor(220, 252, 231, 180))
        p.drawEllipse(c_ini, raio_icone * 1.12, raio_icone * 1.12)
        _desenhar_item_vetorial(p, cen.icone_inicio, c_ini.x(), c_ini.y(), raio_icone * 0.92)

        # Seta guia discreta apontando para a 1.ª direção do labirinto (enquanto ainda não começou a traçar)
        if self.estado == "pronto" and len(self.labirinto.caminho_solucao) >= 2:
            prox_c = self._centro_celula(self.labirinto.caminho_solucao[1])
            dx = prox_c.x() - c_ini.x()
            dy = prox_c.y() - c_ini.y()
            d = max(1.0, math.hypot(dx, dy))
            ux, uy = dx / d, dy / d
            p_seta = QPointF(c_ini.x() + ux * (lado * (0.48 + 0.08 * pulso)), c_ini.y() + uy * (lado * (0.48 + 0.08 * pulso)))
            p.setPen(QPen(QColor("#16A34A"), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(c_ini.x() + ux * (raio_icone * 1.15), c_ini.y() + uy * (raio_icone * 1.15)), p_seta)
            # Ponta da seta
            perp_x, perp_y = -uy, ux
            ponta = QPolygonF([
                QPointF(p_seta.x() + ux * 9, p_seta.y() + uy * 9),
                QPointF(p_seta.x() - ux * 4 + perp_x * 7, p_seta.y() - uy * 4 + perp_y * 7),
                QPointF(p_seta.x() - ux * 4 - perp_x * 7, p_seta.y() - uy * 4 - perp_y * 7),
            ])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#16A34A"))
            p.drawPolygon(ponta)

        # Halo FIM
        halo_fim = QRadialGradient(c_fim, raio_icone * (1.55 + 0.25 * pulso))
        halo_fim.setColorAt(0.0, QColor(250, 204, 21, 175))
        halo_fim.setColorAt(1.0, QColor(250, 204, 21, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo_fim)
        p.drawEllipse(c_fim, raio_icone * (1.55 + 0.25 * pulso), raio_icone * (1.55 + 0.25 * pulso))
        p.setPen(QPen(QColor("#CA8A04"), 3.0))
        p.setBrush(QColor(254, 249, 195, 200))
        p.drawEllipse(c_fim, raio_icone * 1.12, raio_icone * 1.12)
        _desenhar_item_vetorial(p, cen.icone_fim, c_fim.x(), c_fim.y(), raio_icone * 0.92)

        # Etiquetas visuais claras «INÍCIO» e «FIM»
        f_tag = QFont("Segoe UI", max(8, min(11, int(lado * 0.11))), QFont.Weight.Bold)
        p.setFont(f_tag)
        self._desenhar_etiqueta(p, QPointF(c_ini.x(), self._rect_grelha.y() - 16), t("lab.inicio"), "#16A34A")
        self._desenhar_etiqueta(p, QPointF(c_fim.x(), min(h - 14, c_fim.y() + raio_icone + 14)), t("lab.fim"), "#CA8A04")

        # 5. Traço desenhado pela criança
        if len(self._traco) >= 2:
            caminho_p = QPainterPath(self._traco[0])
            for pt in self._traco[1:]:
                caminho_p.lineTo(pt)
            cor_tr = QColor("#EF4444") if self.estado == "erro" else QColor(cen.cor_traco)
            larg_tr = max(6.0, min(14.0, lado * 0.14))
            p.setPen(QPen(cor_tr, larg_tr, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(caminho_p)
            # Bolinha brilhante na ponta do traço
            p.setPen(QPen(QColor("#FFFFFF"), 2.0))
            p.setBrush(cor_tr)
            p.drawEllipse(self._traco[-1], larg_tr * 0.65, larg_tr * 0.65)

        # 6. Flash de colisão
        if self.estado == "erro" and self._ponto_erro is not None:
            p.setPen(QPen(QColor("#FFFFFF"), 2.5))
            p.setBrush(QColor(239, 68, 68, 225))
            p.drawEllipse(self._ponto_erro, 18, 18)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            p.drawText(QRectF(self._ponto_erro.x() - 18, self._ponto_erro.y() - 18, 36, 36), Qt.AlignmentFlag.AlignCenter, "✕")

        # 7. Celebração de vitória
        if self.estado == "vitoria":
            p.setPen(Qt.PenStyle.NoPen)
            for cx, cy, _vx, _vy, cor in self._confetes:
                p.setBrush(cor)
                p.drawEllipse(QPointF(cx, cy), 7, 7)

            caixa = QRectF(w * 0.24, h * 0.36, w * 0.52, 112)
            p.setBrush(QColor(16, 185, 129, 240))
            p.setPen(QPen(QColor("#FFFFFF"), 3.0))
            p.drawRoundedRect(caixa, 22, 22)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
            p.drawText(QRectF(caixa.x(), caixa.y() + 14, caixa.width(), 44), Qt.AlignmentFlag.AlignCenter, t("lab.parabens"))
            p.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
            p.drawText(QRectF(caixa.x() + 12, caixa.y() + 62, caixa.width() - 24, 36), Qt.AlignmentFlag.AlignCenter, t("lab.vitoria", n=self.nivel))

    def _desenhar_etiqueta(self, p: QPainter, centro: QPointF, texto: str, cor_hex: str) -> None:
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(texto) + 16
        th = fm.height() + 6
        r = QRectF(centro.x() - tw / 2.0, centro.y() - th / 2.0, tw, th)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(cor_hex))
        p.drawRoundedRect(r, th / 2.0, th / 2.0)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, texto)


def _icone_ferramenta_lab(tipo: str, tamanho: int = 56) -> QIcon:
    """Desenha ilustrações vetoriais grandes e amigáveis da Caneta e da Borracha."""
    pix = QPixmap(tamanho, tamanho)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(tamanho)

    if tipo == "caneta":
        p.translate(s * 0.5, s * 0.5)
        p.rotate(-38.0)
        # Corpo da caneta
        p.setPen(QPen(QColor("#1E3A8A"), 2.0))
        p.setBrush(QColor("#3B82F6"))
        p.drawRoundedRect(QRectF(-s * 0.14, -s * 0.34, s * 0.28, s * 0.50), 6, 6)
        # Faixa metálica
        p.setBrush(QColor("#E2E8F0"))
        p.drawRect(QRectF(-s * 0.14, s * 0.08, s * 0.28, s * 0.08))
        # Ponta da caneta
        p.setBrush(QColor("#FDE68A"))
        p.drawPolygon(QPolygonF([
            QPointF(-s * 0.13, s * 0.16),
            QPointF(s * 0.13, s * 0.16),
            QPointF(0.0, s * 0.40),
        ]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1E3A8A"))
        p.drawPolygon(QPolygonF([
            QPointF(-s * 0.05, s * 0.30),
            QPointF(s * 0.05, s * 0.30),
            QPointF(0.0, s * 0.40),
        ]))
        # Topo arredondado
        p.setBrush(QColor("#1D4ED8"))
        p.drawRoundedRect(QRectF(-s * 0.14, -s * 0.38, s * 0.28, s * 0.10), 4, 4)
    else:
        # Borracha escolar clássica bicolor (rosa + azul)
        p.translate(s * 0.5, s * 0.5)
        p.rotate(-28.0)
        p.setPen(QPen(QColor("#9D174D"), 2.0))
        p.setBrush(QColor("#F472B6"))
        p.drawRoundedRect(QRectF(-s * 0.32, -s * 0.18, s * 0.40, s * 0.36), 6, 6)
        p.setPen(QPen(QColor("#1E40AF"), 2.0))
        p.setBrush(QColor("#3B82F6"))
        p.drawRoundedRect(QRectF(s * 0.02, -s * 0.18, s * 0.30, s * 0.36), 6, 6)
        # Faixa central branca
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRect(QRectF(-s * 0.02, -s * 0.16, s * 0.08, s * 0.32))

    p.end()
    return QIcon(pix)


class DialogoLabirintos(QDialog):
    """Janela principal em ecrã completo do jogo Labirintos Mágicos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        idiomas.carregar_partilhado()
        self.setWindowTitle(t("lab.titulo"))
        self.resize(1040, 700)
        self._escuro = tema_partilhado.e_escuro()
        sons.precarregar()

        cab = QFrame()
        cab.setObjectName("cabecalhoLab")
        cab_lay = QHBoxLayout(cab)
        cab_lay.setContentsMargins(14, 10, 14, 10)
        cab_lay.setSpacing(8)

        self._lbl_nivel = QLabel(t("lab.nivel", n=1))
        self._lbl_nivel.setObjectName("badgeNivelLab")

        self._combo_cenario = QComboBox()
        self._combo_cenario.addItem(t("lab.cenario_auto"), None)
        for cen in CENARIOS:
            self._combo_cenario.addItem(t(cen.chave_nome), cen.id)
        self._combo_cenario.currentIndexChanged.connect(self._mudar_cenario)

        self._combo_nivel = QComboBox()
        for n in range(1, 11):
            cols, rows = dimensoes_para_nivel(n)
            self._combo_nivel.addItem(f"{t('lab.nivel', n=n)} ({cols}×{rows})", n)
        self._combo_nivel.currentIndexChanged.connect(self._mudar_nivel_combo)

        self._btn_modo = QPushButton(t("lab.modo_progressivo"))
        self._btn_modo.setCheckable(True)
        self._btn_modo.setChecked(True)
        self._btn_modo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_modo.toggled.connect(self._alternar_modo)

        btn_instr = QPushButton(t("jogos.instrucoes_voz"))
        btn_instr.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_instr.clicked.connect(self._falar_instrucoes)

        btn_novo = QPushButton(t("lab.novo_labirinto"))
        btn_novo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_novo.clicked.connect(lambda: self.area.iniciar_nivel(self.area.nivel))

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
        cab_lay.addWidget(self._combo_cenario)
        cab_lay.addWidget(self._combo_nivel)
        cab_lay.addWidget(self._btn_modo)
        cab_lay.addStretch(1)
        cab_lay.addWidget(btn_instr)
        cab_lay.addWidget(btn_novo)
        cab_lay.addWidget(self._btn_som)
        cab_lay.addWidget(self._btn_ecra)
        cab_lay.addWidget(btn_fechar)

        self.area = AreaLabirinto()
        self.area.estado_alterado.connect(self._atualizar_estado)
        self.area.nivel_alterado.connect(self._ao_mudar_nivel)

        # Barra lateral ilustrada ao lado do labirinto: Caneta e Borracha
        barra_lat = QFrame()
        barra_lat.setObjectName("barraLateralLab")
        lat_lay = QVBoxLayout(barra_lat)
        lat_lay.setContentsMargins(10, 18, 10, 18)
        lat_lay.setSpacing(14)
        lat_lay.addStretch(1)

        self._btn_caneta = QToolButton()
        self._btn_caneta.setObjectName("ferramentaLab")
        self._btn_caneta.setIcon(_icone_ferramenta_lab("caneta", 56))
        self._btn_caneta.setIconSize(QSize(56, 56))
        self._btn_caneta.setText(t("lab.caneta"))
        self._btn_caneta.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._btn_caneta.setCheckable(True)
        self._btn_caneta.setChecked(True)
        self._btn_caneta.setFixedSize(98, 98)
        self._btn_caneta.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_caneta.clicked.connect(lambda: self._selecionar_ferramenta(False))

        self._btn_borracha = QToolButton()
        self._btn_borracha.setObjectName("ferramentaLab")
        self._btn_borracha.setIcon(_icone_ferramenta_lab("borracha", 56))
        self._btn_borracha.setIconSize(QSize(56, 56))
        self._btn_borracha.setText(t("lab.borracha"))
        self._btn_borracha.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._btn_borracha.setCheckable(True)
        self._btn_borracha.setChecked(False)
        self._btn_borracha.setFixedSize(98, 98)
        self._btn_borracha.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_borracha.clicked.connect(lambda: self._selecionar_ferramenta(True))

        lat_lay.addWidget(self._btn_caneta, 0, Qt.AlignmentFlag.AlignHCenter)
        lat_lay.addWidget(self._btn_borracha, 0, Qt.AlignmentFlag.AlignHCenter)
        lat_lay.addStretch(1)

        corpo = QHBoxLayout()
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)
        corpo.addWidget(barra_lat)
        corpo.addWidget(self.area, 1)

        self._estado = QLabel(t(self.area.cenario.chave_missao))
        self._estado.setObjectName("rodapeLab")
        self._estado.setContentsMargins(14, 7, 14, 8)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(cab)
        raiz.addLayout(corpo, 1)
        raiz.addWidget(self._estado)

        self._aplicar_tema()

    def _aplicar_tema(self) -> None:
        self.area.definir_tema(self._escuro)
        if self._escuro:
            bg, topo, txt, borda, btn = "#0F172A", "#1A202E", "#F1F5F9", "#2E374B", "#262F42"
        else:
            bg, topo, txt, borda, btn = "#F0FDF4", "#FFFFFF", "#0F172A", "#CBD5E1", "#F8FAFC"
        self.setStyleSheet(
            f"""
            QDialog {{ background: {bg}; color: {txt}; }}
            QFrame#cabecalhoLab {{ background: {topo}; border-bottom: 1px solid {borda}; }}
            QFrame#barraLateralLab {{ background: {topo}; border-right: 1px solid {borda}; }}
            QToolButton#ferramentaLab {{
                background: {btn}; color: {txt}; border: 2px solid {borda};
                border-radius: 16px; padding: 6px; font-size: 11pt; font-weight: 700;
            }}
            QToolButton#ferramentaLab:hover {{ border-color: #3B82F6; }}
            QToolButton#ferramentaLab:checked {{
                background: #DBEAFE; color: #1E3A8A; border: 3px solid #2563EB;
            }}
            QLabel#badgeNivelLab {{
                background: #16A34A; color: #FFFFFF; border-radius: 10px;
                padding: 4px 12px; font-size: 13px; font-weight: 700;
            }}
            QLabel#rodapeLab {{ background: {topo}; color: {txt}; border-top: 1px solid {borda}; font-size: 13.5px; font-weight: 600; }}
            QPushButton, QComboBox {{
                background: {btn}; color: {txt}; border: 1px solid {borda};
                border-radius: 8px; padding: 6px 12px; font-size: 10pt; font-weight: 600;
            }}
            QPushButton:checked {{
                background: #2563EB; color: #FFFFFF; border: 1px solid #2563EB;
            }}
            QComboBox QAbstractItemView {{ background: {topo}; color: {txt}; font-size: 10pt; }}
            """
        )

    def _mudar_cenario(self) -> None:
        self.area.definir_cenario_fixo(self._combo_cenario.currentData())

    def _mudar_nivel_combo(self) -> None:
        n = int(self._combo_nivel.currentData() or 1)
        if n != self.area.nivel:
            self.area.iniciar_nivel(n)

    def _alternar_modo(self, progressivo: bool) -> None:
        self.area.definir_modo_progressivo(progressivo)
        self._btn_modo.setText(t("lab.modo_progressivo") if progressivo else t("lab.modo_manual"))

    def _selecionar_ferramenta(self, borracha: bool) -> None:
        self._btn_caneta.setChecked(not borracha)
        self._btn_borracha.setChecked(borracha)
        self.area.definir_borracha(borracha)

    def _ao_mudar_nivel(self, nivel: int, nome_cen: str) -> None:
        self._lbl_nivel.setText(f"{t('lab.nivel', n=nivel)} · {nome_cen}")
        self._combo_nivel.blockSignals(True)
        idx = min(self._combo_nivel.count() - 1, max(0, nivel - 1))
        self._combo_nivel.setCurrentIndex(idx)
        self._combo_nivel.blockSignals(False)

    def _atualizar_estado(self, texto: str) -> None:
        self._estado.setText(texto)

    def _alternar_som(self, ligado: bool) -> None:
        self.area.som_ativo = ligado
        self._btn_som.setText(t("geral.som_ligado") if ligado else t("geral.som_desligado"))
        if not ligado:
            voz.parar()

    def iniciar_ecra_completo(self) -> None:
        if sys.platform != "win32":
            ecra = self.screen() or QGuiApplication.primaryScreen()
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            if ecra is not None:
                self.setGeometry(ecra.availableGeometry())
            self.show()
        else:
            self.showFullScreen()
        self._btn_ecra.setText(t("geral.sair_ecra_completo"))
        QTimer.singleShot(500, self._falar_instrucoes_se_ativo)

    def _alternar_ecra_completo(self) -> None:
        if self.isFullScreen() or bool(self.windowFlags() & Qt.WindowType.FramelessWindowHint):
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
            self.showNormal()
            self._btn_ecra.setText(t("geral.ecra_completo"))
        else:
            self.iniciar_ecra_completo()

    def _falar_instrucoes(self) -> None:
        try:
            missao = t(self.area.cenario.chave_missao)
            voz.falar(f"{missao} {t('lab.voz_instrucoes')}")
        except Exception:
            pass

    def _falar_instrucoes_se_ativo(self) -> None:
        if self.isVisible() and self.area.som_ativo:
            self._falar_instrucoes()

    def _parar_jogo(self) -> None:
        self.area._timer.stop()
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


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = DialogoLabirintos()
    dlg.iniciar_ecra_completo()
    return dlg.exec()


if __name__ == "__main__":
    raise SystemExit(main())
