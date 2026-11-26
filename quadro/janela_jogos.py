"""Catálogo de jogos em cartões expansíveis: imagem, créditos, transferência e arranque direto."""

from __future__ import annotations

import html
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from quadro import catalogo, icones, idiomas, menu_prefs, tema_partilhado
from quadro.area_util import adaptar_a_area_util
from quadro.catalogo import ErroCatalogo, Jogo, ResumoJogo
from quadro.idiomas import t
from quadro.interruptor import interruptor
from quadro.jogos import abrir_jogo_integrado

MENSAGENS = {
    "catalogo.sem_rede": "Não foi possível contactar o repositório de recursos. Verifique a ligação à internet.",
    "catalogo.sem_recursos": "Não foi possível ler os recursos do catálogo.",
    "catalogo.metadados_invalidos": "Os dados de um jogo não são válidos. Nada foi transferido.",
    "catalogo.ficheiro_grande": "Um ficheiro do catálogo é demasiado grande. Nada foi transferido.",
    "catalogo.caminho_invalido": "Um caminho nos dados do catálogo não é válido.",
    "catalogo.verificacao_falhou": "A verificação do ficheiro falhou. Nada foi instalado.",
    "catalogo.sem_windows": "Este jogo ainda não tem instalação para Windows.",
    "catalogo.so_windows": "Só é possível abrir jogos no Windows nesta versão.",
}


class _Sinal(QObject):
    progresso = Signal(int, int)
    terminou = Signal(object)


def _mensagem(erro: BaseException) -> str:
    if isinstance(erro, ErroCatalogo):
        return MENSAGENS.get(str(erro), str(erro))
    return f"Erro inesperado: {erro}"


def _ligacao(nome: str, url: str, cor: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}" style="color:{cor}; text-decoration:none; font-weight:600;">{html.escape(nome)}</a>'


def _rotulo_controlo(tipo: str) -> str:
    return t(f"jogos.ctrl_{tipo}") if tipo in ("rato", "teclado", "caneta", "toque") else tipo


def _rotulo_nivel(nivel: str) -> str:
    return t(f"jogos.nivel_{nivel}") if nivel in ("necessario", "aconselhado", "suportado") else nivel


def _icone_controlo(tipo: str, cor: str, tamanho: int = 16) -> QPixmap:
    """Desenha um ícone vetorial nítido para o dispositivo de entrada (rato, teclado, caneta, toque)."""
    pix = QPixmap(tamanho, tamanho)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(cor)
    caneta = QPen(c, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(caneta)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = float(tamanho)

    if tipo == "rato":
        # Corpo do rato + divisoria dos botoes + roda
        p.drawRoundedRect(QRectF(s * 0.25, s * 0.12, s * 0.50, s * 0.76), s * 0.24, s * 0.24)
        p.drawLine(QPointF(s * 0.50, s * 0.14), QPointF(s * 0.50, s * 0.42))
        p.drawLine(QPointF(s * 0.26, s * 0.44), QPointF(s * 0.74, s * 0.44))
    elif tipo == "teclado":
        # Moldura do teclado + duas filas de teclas + barra de espacos
        p.drawRoundedRect(QRectF(s * 0.08, s * 0.22, s * 0.84, s * 0.56), s * 0.12, s * 0.12)
        p.setBrush(c)
        p.setPen(Qt.PenStyle.NoPen)
        for linha_y in (0.35, 0.50):
            for col_x in (0.20, 0.36, 0.52, 0.68):
                p.drawRoundedRect(QRectF(s * col_x, s * linha_y, s * 0.10, s * 0.09), 1.0, 1.0)
        p.drawRoundedRect(QRectF(s * 0.28, s * 0.64, s * 0.44, s * 0.08), 1.0, 1.0)
    elif tipo == "caneta":
        # Caneta stylus inclinada com ponta
        p.drawLine(QPointF(s * 0.22, s * 0.78), QPointF(s * 0.76, s * 0.24))
        p.drawLine(QPointF(s * 0.66, s * 0.14), QPointF(s * 0.86, s * 0.34))
        p.drawLine(QPointF(s * 0.14, s * 0.86), QPointF(s * 0.28, s * 0.80))
        p.drawLine(QPointF(s * 0.14, s * 0.86), QPointF(s * 0.20, s * 0.72))
    elif tipo == "toque":
        # Ecra / ondas de toque + indicador de dedo
        p.drawArc(QRectF(s * 0.24, s * 0.10, s * 0.52, s * 0.52), 20 * 16, 140 * 16)
        p.drawEllipse(QPointF(s * 0.50, s * 0.38), s * 0.11, s * 0.11)
        p.drawLine(QPointF(s * 0.50, s * 0.49), QPointF(s * 0.50, s * 0.86))
        p.drawLine(QPointF(s * 0.36, s * 0.72), QPointF(s * 0.50, s * 0.86))
        p.drawLine(QPointF(s * 0.64, s * 0.72), QPointF(s * 0.50, s * 0.86))

    p.end()
    return pix


def _criar_etiqueta_controlo(tipo: str, nivel: str, escuro: bool) -> QFrame:
    """Cria uma etiqueta (pill) com ícone vetorial + texto legível para o dispositivo de entrada."""
    nome = _rotulo_controlo(tipo)
    nivel_txt = _rotulo_nivel(nivel)

    if nivel == "necessario":
        bg = "rgba(234, 88, 12, 48)" if escuro else "rgba(234, 88, 12, 26)"
        borda = "#FB923C" if escuro else "#EA580C"
        cor_txt = "#FDBA74" if escuro else "#C2410C"
        rotulo = f"{nome} · {t('jogos.nivel_necessario_curto')}"
    elif nivel == "aconselhado":
        bg = "rgba(59, 130, 246, 36)" if escuro else "rgba(37, 99, 235, 20)"
        borda = "rgba(96, 165, 250, 95)" if escuro else "rgba(37, 99, 235, 75)"
        cor_txt = "#93C5FD" if escuro else "#1D4ED8"
        rotulo = nome
    else:
        bg = "rgba(148, 163, 184, 28)" if escuro else "rgba(100, 116, 139, 18)"
        borda = "rgba(148, 163, 184, 70)" if escuro else "rgba(100, 116, 139, 55)"
        cor_txt = "#CBD5E1" if escuro else "#475569"
        rotulo = nome

    pill = QFrame()
    pill.setStyleSheet(
        f"QFrame {{ background: {bg}; border: 1px solid {borda}; border-radius: 9px; }}"
    )
    pill.setToolTip(f"{nome}: {nivel_txt}")
    lay = QHBoxLayout(pill)
    lay.setContentsMargins(7, 2, 8, 2)
    lay.setSpacing(5)

    lbl_ic = QLabel()
    lbl_ic.setStyleSheet("background: transparent; border: none;")
    lbl_ic.setPixmap(_icone_controlo(tipo, cor_txt, 14))
    lbl_ic.setFixedSize(14, 14)

    lbl_txt = QLabel(rotulo)
    lbl_txt.setStyleSheet(
        f"background: transparent; border: none; color: {cor_txt}; font-size: 11px; font-weight: 600;"
    )

    lay.addWidget(lbl_ic)
    lay.addWidget(lbl_txt)
    return pill


def _miniatura_padrao(largura: int, altura: int, cor_fundo: str) -> QPixmap:
    """Miniatura vetorial limpa quando o jogo ainda não tem screenshot."""
    pix = QPixmap(largura, altura)
    pix.fill(QColor(cor_fundo))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    ic = icones.desenhar("jogos", min(largura, altura) - 24)
    p.drawPixmap((largura - ic.width()) // 2, (altura - ic.height()) // 2, ic)
    p.end()
    return pix


def _estilo_jogos(escuro: bool) -> str:
    if escuro:
        fundo = "#131720"
        topo = "#1A202E"
        cartao = "#1E2534"
        cartao_hover = "#242D3F"
        cartao_aberto = "#222B3D"
        texto = "#F1F5F9"
        texto_sec = "#CBD5E1"
        texto_suave = "#94A3B8"
        borda = "#2E374B"
        borda_aberto = "#3B82F6"
        btn_sec = "#262F42"
        btn_sec_hover = "#313C54"
    else:
        fundo = "#EEF2F7"
        topo = "#FFFFFF"
        cartao = "#FFFFFF"
        cartao_hover = "#F8FAFC"
        cartao_aberto = "#FFFFFF"
        texto = "#0F172A"
        texto_sec = "#334155"
        texto_suave = "#64748B"
        borda = "#CBD5E1"
        borda_aberto = "#2563EB"
        btn_sec = "#F1F5F9"
        btn_sec_hover = "#E2E8F0"

    return f"""
QDialog {{
    background-color: {fundo};
    color: {texto};
}}
QFrame#cabecalhoJogos {{
    background-color: {topo};
    border-bottom: 1px solid {borda};
}}
QFrame#barraFiltrosJogos {{
    background-color: {topo};
    border-bottom: 1px solid {borda};
}}
QLineEdit#pesquisaJogos, QComboBox#filtroJogos {{
    background-color: {btn_sec};
    color: {texto};
    border: 1px solid {borda};
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 9.5pt;
}}
QComboBox#filtroJogos QAbstractItemView {{
    background-color: {topo};
    color: {texto};
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
    font-size: 9.5pt;
}}
QLabel#tituloJogos {{
    color: {texto};
    font-size: 20px;
    font-weight: 700;
}}
QLabel#subtituloJogos {{
    color: {texto_suave};
    font-size: 12px;
}}
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QFrame#cartaoJogo {{
    background-color: {cartao};
    border: 1px solid {borda};
    border-radius: 14px;
}}
QFrame#cartaoJogo:hover {{
    background-color: {cartao_hover};
    border-color: {borda_aberto};
}}
QFrame#cartaoJogo[expandido="true"] {{
    background-color: {cartao_aberto};
    border: 1.5px solid {borda_aberto};
}}
QLabel#nomeJogo {{
    color: {texto};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#resumoJogo {{
    color: {texto_sec};
    font-size: 13px;
}}
QLabel#detalheJogo {{
    color: {texto_sec};
    font-size: 13px;
}}
QLabel#setaJogo {{
    color: {texto_suave};
    font-size: 18px;
    font-weight: 700;
}}
QLabel#estadoJogos {{
    color: {texto_suave};
    font-size: 12px;
    padding: 4px 2px;
}}
QPushButton {{
    background-color: {btn_sec};
    color: {texto};
    border: 1px solid {borda};
    border-radius: 9px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {btn_sec_hover};
}}
QPushButton:disabled {{
    color: {texto_suave};
}}
QPushButton[papel="primario"] {{
    background-color: #2563EB;
    color: #FFFFFF;
    border: 1px solid #2563EB;
}}
QPushButton[papel="primario"]:hover {{
    background-color: #1D4ED8;
}}
QPushButton[papel="iniciar"] {{
    background-color: #16A34A;
    color: #FFFFFF;
    border: 1px solid #16A34A;
}}
QPushButton[papel="iniciar"]:hover {{
    background-color: #15803D;
}}
QProgressBar {{
    background-color: {btn_sec};
    border: 1px solid {borda};
    border-radius: 6px;
    text-align: center;
    color: {texto};
    height: 16px;
}}
QProgressBar::chunk {{
    background-color: #2563EB;
    border-radius: 5px;
}}
"""


class _CartaoJogo(QFrame):
    """Cartao expansivel de um jogo: clique alterna entre vista resumida e detalhes + botoes."""

    clicado = Signal(object)

    def __init__(self, resumo: ResumoJogo, ao_acao: Callable[[_CartaoJogo], None], ao_reinstalar: Callable[[_CartaoJogo], None], ao_atualizar: Callable[[_CartaoJogo], None]) -> None:
        super().__init__()
        self.setObjectName("cartaoJogo")
        self.setProperty("expandido", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.resumo = resumo
        self.jogo: Jogo | None = None
        self.miniatura_path: Path | None = None
        self.instalado: Path | None = None
        self.executavel: Path | None = None
        self._expandido = False

        # --- cabecalho clicavel do cartao (sempre visivel) ---
        self._thumb = QLabel()
        self._thumb.setFixedSize(116, 74)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet("border-radius: 10px; background: #1E3A8A;")
        self._thumb.setPixmap(_miniatura_padrao(116, 74, "#2563EB"))

        self._nome = QLabel(resumo.nome)
        self._nome.setObjectName("nomeJogo")

        self._badge = QLabel("A carregar…")
        self._badge.setStyleSheet(
            "background: rgba(148, 163, 184, 50); color: #64748B; border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 700;"
        )

        self._resumo_txt = QLabel("Clique para ver detalhes e iniciar")
        self._resumo_txt.setObjectName("resumoJogo")
        self._resumo_txt.setWordWrap(True)

        self._caixa_controlos = QWidget()
        self._layout_controlos = QHBoxLayout(self._caixa_controlos)
        self._layout_controlos.setContentsMargins(0, 2, 0, 0)
        self._layout_controlos.setSpacing(6)
        self._layout_controlos.addStretch(1)
        self._caixa_controlos.setVisible(False)

        self._seta = QLabel("▸")
        self._seta.setObjectName("setaJogo")
        self._seta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._seta.setFixedWidth(24)

        linha_titulo = QHBoxLayout()
        linha_titulo.setSpacing(8)
        linha_titulo.addWidget(self._nome)
        linha_titulo.addWidget(self._badge)
        linha_titulo.addStretch(1)

        info_topo = QVBoxLayout()
        info_topo.setSpacing(4)
        info_topo.addLayout(linha_titulo)
        info_topo.addWidget(self._resumo_txt)
        info_topo.addWidget(self._caixa_controlos)

        topo = QHBoxLayout()
        topo.setSpacing(14)
        topo.addWidget(self._thumb)
        topo.addLayout(info_topo, 1)
        topo.addWidget(self._seta)

        # --- area expansivel (detalhes, imagem grande, progresso e botoes) ---
        self._corpo = QWidget()
        self._corpo.setVisible(False)
        corpo_layout = QVBoxLayout(self._corpo)
        corpo_layout.setContentsMargins(0, 10, 0, 0)
        corpo_layout.setSpacing(10)

        detalhes_linha = QHBoxLayout()
        detalhes_linha.setSpacing(14)

        self._imagem_grande = QLabel()
        self._imagem_grande.setFixedSize(240, 150)
        self._imagem_grande.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._imagem_grande.setStyleSheet("border-radius: 10px; background: rgba(148, 163, 184, 30);")
        self._imagem_grande.setVisible(False)

        self.texto_detalhe = QLabel()
        self.texto_detalhe.setObjectName("detalheJogo")
        self.texto_detalhe.setWordWrap(True)
        self.texto_detalhe.setTextFormat(Qt.TextFormat.RichText)
        self.texto_detalhe.setOpenExternalLinks(True)
        self.texto_detalhe.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        detalhes_linha.addWidget(self._imagem_grande)
        detalhes_linha.addWidget(self.texto_detalhe, 1)
        corpo_layout.addLayout(detalhes_linha)

        self.barra = QProgressBar()
        self.barra.setVisible(False)
        corpo_layout.addWidget(self.barra)

        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        self.botao_principal = QPushButton("A carregar…")
        self.botao_principal.setEnabled(False)
        self.botao_principal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao_principal.clicked.connect(lambda _=False: ao_acao(self))

        self.botao_reinstalar = QPushButton("Executar instalador")
        self.botao_reinstalar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao_reinstalar.setVisible(False)
        self.botao_reinstalar.clicked.connect(lambda _=False: ao_reinstalar(self))

        self.botao_atualizar = QPushButton("Já instalei — atualizar")
        self.botao_atualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao_atualizar.setVisible(False)
        self.botao_atualizar.clicked.connect(lambda _=False: ao_atualizar(self))

        botoes.addWidget(self.botao_principal)
        botoes.addWidget(self.botao_reinstalar)
        botoes.addWidget(self.botao_atualizar)
        botoes.addStretch(1)
        corpo_layout.addLayout(botoes)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(14, 12, 14, 12)
        raiz.setSpacing(0)
        raiz.addLayout(topo)
        raiz.addWidget(self._corpo)

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clicado.emit(self)
        super().mousePressEvent(evento)

    def definir_expandido(self, expandido: bool) -> None:
        self._expandido = expandido
        self._corpo.setVisible(expandido)
        self._seta.setText("▾" if expandido else "▸")
        self.setProperty("expandido", expandido)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def preencher_dados(self, jogo: Jogo, miniatura: Path | None, instalado: Path | None, executavel: Path | None, escuro: bool) -> None:
        self.jogo = jogo
        self.miniatura_path = miniatura
        self.instalado = instalado
        self.executavel = executavel
        self._nome.setText(jogo.nome)
        self._resumo_txt.setText(jogo.descricao)

        if miniatura is not None:
            pix = QPixmap(str(miniatura))
            if not pix.isNull():
                self._thumb.setPixmap(pix.scaled(116, 74, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
                self._imagem_grande.setPixmap(pix.scaled(240, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self._imagem_grande.setVisible(True)
        else:
            cor = "#E11D48" if jogo.id == "gcompris" else "#2563EB"
            self._thumb.setPixmap(_miniatura_padrao(116, 74, cor))
            self._imagem_grande.setVisible(False)

        self.atualizar_texto_e_estado(escuro)

    def _atualizar_controlos(self, escuro: bool) -> None:
        while self._layout_controlos.count() > 1:
            item = self._layout_controlos.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if self.jogo is None or not self.jogo.controlos:
            self._caixa_controlos.setVisible(False)
            return
        ordem_nivel = {"necessario": 0, "aconselhado": 1, "suportado": 2}
        itens = sorted(
            self.jogo.controlos.items(),
            key=lambda par: (ordem_nivel.get(par[1], 9), catalogo.DISPOSITIVOS_CONTROLO.index(par[0])),
        )
        for tipo, nivel in itens:
            pill = _criar_etiqueta_controlo(tipo, nivel, escuro)
            self._layout_controlos.insertWidget(self._layout_controlos.count() - 1, pill)
        self._caixa_controlos.setVisible(True)

    def atualizar_texto_e_estado(self, escuro: bool) -> None:
        if self.jogo is None:
            return
        jogo = self.jogo
        self._atualizar_controlos(escuro)
        cor_link = "#60A5FA" if escuro else "#2563EB"
        escapar = html.escape
        linhas = [
            f"<p style='margin:0 0 8px 0;'>{escapar(jogo.descricao)}</p>",
        ]
        if jogo.categoria:
            linhas.append(f"<p style='margin:0 0 6px 0;'><b>{escapar(t('jogos.categoria'))}</b> {escapar(jogo.categoria)}</p>")
        if jogo.controlos:
            ordem_nivel = {"necessario": 0, "aconselhado": 1, "suportado": 2}
            itens = sorted(
                jogo.controlos.items(),
                key=lambda par: (ordem_nivel.get(par[1], 9), catalogo.DISPOSITIVOS_CONTROLO.index(par[0])),
            )
            partes = [
                f"{_rotulo_controlo(t_)} ({_rotulo_nivel(n_)})"
                for t_, n_ in itens
            ]
            linhas.append(f"<p style='margin:0 0 8px 0;'><b>{escapar(t('jogos.como_jogar'))}</b> {escapar(' · '.join(partes))}</p>")
        linhas.extend([
            f"<p style='margin:0;'><b>{escapar(t('jogos.autores'))}</b> {escapar(', '.join(jogo.autores))}<br>",
            f"<b>{escapar(t('jogos.copyright'))}</b> {escapar(jogo.copyright)}<br>",
            f"<b>{escapar(t('jogos.licenca'))}</b> {_ligacao(jogo.licenca, jogo.licenca_url, cor_link)} · "
            f"<b>{escapar(t('jogos.site'))}</b> {_ligacao(jogo.site, jogo.site, cor_link)} · "
            f"<b>{escapar(t('jogos.fonte'))}</b> {_ligacao(t('jogos.download_oficial'), jogo.fonte_oficial, cor_link)}</p>",
        ])
        if jogo.instalacao_windows is None and jogo.instalacao_linux is None:
            linhas.append(f"<p><i>{escapar(t('jogos.sem_windows'))}</i></p>")
        elif sys.platform != "win32" and self.executavel is None and not (jogo.instalacao_windows and jogo.instalacao_windows.tipo == "integrado"):
            cmd_linux = catalogo.comando_instalacao_linux(jogo)
            if cmd_linux:
                linhas.append(f"<p style='margin:6px 0 0 0;'><b>Linux:</b> <code>{escapar(cmd_linux)}</code></p>")
        self.texto_detalhe.setText("".join(linhas))

        # Estado do badge e dos botoes (suporta jogos integrados e arranque direto como o GCompris!)
        eh_integrado = (
            (jogo.instalacao_windows is not None and jogo.instalacao_windows.tipo == "integrado")
            or (jogo.instalacao_linux is not None and jogo.instalacao_linux.tipo == "integrado")
        )
        eh_instalador = jogo.instalacao_windows is not None and jogo.instalacao_windows.tipo == "instalador"
        eh_pacote_linux = sys.platform != "win32" and not eh_integrado
        if eh_integrado:
            self._badge.setText(t("jogos.badge_integrado"))
            self._badge.setStyleSheet(
                "background: rgba(16, 185, 129, 44); color: #10B981; border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 700;"
            )
            self.botao_principal.setText(t("jogos.btn_iniciar"))
            self.botao_principal.setProperty("papel", "iniciar")
            self.botao_principal.setEnabled(True)
            self.botao_reinstalar.setVisible(False)
            self.botao_atualizar.setVisible(False)
        elif self.executavel is not None or (not eh_pacote_linux and self.instalado is not None and not eh_instalador):
            self._badge.setText(t("jogos.badge_instalado"))
            self._badge.setStyleSheet(
                "background: rgba(22, 163, 74, 42); color: #16A34A; border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 700;"
            )
            self.botao_principal.setText(t("jogos.btn_iniciar"))
            self.botao_principal.setProperty("papel", "iniciar")
            self.botao_principal.setEnabled(True)
            self.botao_reinstalar.setVisible(not eh_pacote_linux and eh_instalador and self.instalado is not None)
            self.botao_atualizar.setVisible(False)
        elif not eh_pacote_linux and self.instalado is not None and eh_instalador:
            self._badge.setText(t("jogos.badge_instalador"))
            self._badge.setStyleSheet(
                "background: rgba(245, 158, 11, 45); color: #D97706; border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 700;"
            )
            self.botao_principal.setText(t("jogos.btn_instalador"))
            self.botao_principal.setProperty("papel", "primario")
            self.botao_principal.setEnabled(True)
            self.botao_reinstalar.setVisible(False)
            self.botao_atualizar.setVisible(True)
        elif eh_pacote_linux and (jogo.instalacao_linux is not None or jogo.instalacao_windows is not None):
            self._badge.setText(t("jogos.badge_disponivel"))
            self._badge.setStyleSheet(
                "background: rgba(37, 99, 235, 36); color: #2563EB; border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 700;"
            )
            self.botao_principal.setText(t("jogos.btn_desc_iniciar"))
            self.botao_principal.setProperty("papel", "primario")
            self.botao_principal.setEnabled(True)
            self.botao_reinstalar.setVisible(False)
            self.botao_atualizar.setVisible(False)
        elif jogo.instalacao_windows is not None:
            self._badge.setText(t("jogos.badge_disponivel"))
            self._badge.setStyleSheet(
                "background: rgba(37, 99, 235, 36); color: #2563EB; border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 700;"
            )
            self.botao_principal.setText(t("jogos.btn_desc_instalar") if eh_instalador else t("jogos.btn_desc_iniciar"))
            self.botao_principal.setProperty("papel", "primario")
            self.botao_principal.setEnabled(True)
            self.botao_reinstalar.setVisible(False)
            self.botao_atualizar.setVisible(eh_instalador)
        else:
            self._badge.setText(t("jogos.badge_indisponivel"))
            self.botao_principal.setText(t("jogos.badge_indisponivel"))
            self.botao_principal.setProperty("papel", "")
            self.botao_principal.setEnabled(False)
            self.botao_reinstalar.setVisible(False)
            self.botao_atualizar.setVisible(False)

        self.botao_principal.style().unpolish(self.botao_principal)
        self.botao_principal.style().polish(self.botao_principal)


class _AdaptadorLista:
    """Mantem compatibilidade com testes que consultam dialogo._lista.count()."""

    def __init__(self, cartoes: list[_CartaoJogo]) -> None:
        self._cartoes = cartoes

    def count(self) -> int:
        return len(self._cartoes)


class DialogoJogos(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        idiomas.carregar_partilhado()
        self.setWindowTitle(t("jogos.titulo"))
        self.resize(860, 620)
        adaptar_a_area_util(self)
        self._base = catalogo.base_recursos()
        self._resumos: list[ResumoJogo] = []
        self._cartoes: list[_CartaoJogo] = []
        self._lista = _AdaptadorLista(self._cartoes)
        self._cartao_ativo: _CartaoJogo | None = None
        self._jogo: Jogo | None = None
        self._instalado: Path | None = None
        self._texto = QLabel()
        self._ocupado = False
        self._escuro = tema_partilhado.e_escuro()

        # --- cabecalho moderno ---
        cabecalho_frame = QFrame()
        cabecalho_frame.setObjectName("cabecalhoJogos")
        cab_layout = QHBoxLayout(cabecalho_frame)
        cab_layout.setContentsMargins(18, 12, 18, 12)
        cab_layout.setSpacing(12)

        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        lbl_titulo = QLabel(t("jogos.titulo"))
        lbl_titulo.setObjectName("tituloJogos")
        lbl_sub = QLabel(t("jogos.subtitulo"))
        lbl_sub.setObjectName("subtituloJogos")
        titulos.addWidget(lbl_titulo)
        titulos.addWidget(lbl_sub)

        self._menu = interruptor(t("geral.no_menu"), menu_prefs.ler()["jogos"])
        self._menu.setToolTip(t("jogos.tooltip_menu"))
        self._menu.toggled.connect(self._alterar_menu)

        fechar = QPushButton(t("geral.fechar"))
        fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        fechar.clicked.connect(self.accept)

        cab_layout.addLayout(titulos, 1)
        cab_layout.addWidget(self._menu)
        cab_layout.addWidget(fechar)

        # --- barra de filtros (pesquisa, tipo, categoria, controlos) ---
        filtros_frame = QFrame()
        filtros_frame.setObjectName("barraFiltrosJogos")
        filtros_lay = QHBoxLayout(filtros_frame)
        filtros_lay.setContentsMargins(18, 8, 18, 8)
        filtros_lay.setSpacing(8)

        self._pesquisa = QLineEdit()
        self._pesquisa.setObjectName("pesquisaJogos")
        self._pesquisa.setPlaceholderText(t("jogos.procurar"))
        self._pesquisa.setClearButtonEnabled(True)
        self._pesquisa.textChanged.connect(self._aplicar_filtros)

        self._filtro_tipo = QComboBox()
        self._filtro_tipo.setObjectName("filtroJogos")
        self._filtro_tipo.addItem(t("jogos.todos_tipos"), "")
        self._filtro_tipo.addItem(t("jogos.tipo_integrado"), "integrado")
        self._filtro_tipo.addItem(t("jogos.tipo_instalado"), "instalado")
        self._filtro_tipo.addItem(t("jogos.tipo_disponivel"), "disponivel")
        self._filtro_tipo.currentIndexChanged.connect(self._aplicar_filtros)

        self._filtro_categoria = QComboBox()
        self._filtro_categoria.setObjectName("filtroJogos")
        self._filtro_categoria.addItem(t("jogos.todas_categorias"), "")
        self._filtro_categoria.currentIndexChanged.connect(self._aplicar_filtros)

        self._filtro_controlos = QComboBox()
        self._filtro_controlos.setObjectName("filtroJogos")
        self._filtro_controlos.addItem(t("jogos.todos_controlos"), "")
        self._filtro_controlos.addItem(t("jogos.ctrl_caneta"), "caneta")
        self._filtro_controlos.addItem(t("jogos.ctrl_toque"), "toque")
        self._filtro_controlos.addItem(t("jogos.ctrl_rato"), "rato")
        self._filtro_controlos.addItem(t("jogos.ctrl_teclado"), "teclado")
        self._filtro_controlos.currentIndexChanged.connect(self._aplicar_filtros)

        self._btn_limpar_filtros = QPushButton(t("geral.limpar"))
        self._btn_limpar_filtros.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_limpar_filtros.clicked.connect(self._limpar_filtros)

        filtros_lay.addWidget(self._pesquisa, 2)
        filtros_lay.addWidget(self._filtro_tipo, 1)
        filtros_lay.addWidget(self._filtro_categoria, 1)
        filtros_lay.addWidget(self._filtro_controlos, 1)
        filtros_lay.addWidget(self._btn_limpar_filtros)

        # --- area de cartoes com scroll ---
        self._conteudo_cartoes = QWidget()
        self._layout_cartoes = QVBoxLayout(self._conteudo_cartoes)
        self._layout_cartoes.setContentsMargins(16, 14, 16, 14)
        self._layout_cartoes.setSpacing(10)
        self._layout_cartoes.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._conteudo_cartoes)

        self._estado = QLabel("A carregar o catálogo…")
        self._estado.setObjectName("estadoJogos")
        self._estado.setWordWrap(True)

        rodape = QHBoxLayout()
        rodape.setContentsMargins(18, 4, 18, 10)
        rodape.addWidget(self._estado, 1)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(cabecalho_frame)
        raiz.addWidget(filtros_frame)
        raiz.addWidget(scroll, 1)
        raiz.addLayout(rodape)

        self._aplicar_tema()
        self._correr(lambda _: catalogo.carregar_indice(self._base), self._indice_pronto)

    # --- tema e preferencias -------------------------------------------------------

    def _aplicar_tema(self) -> None:
        self.setStyleSheet(_estilo_jogos(self._escuro))
        if hasattr(self._menu, "definir_cor_texto"):
            self._menu.definir_cor_texto("#E2E8F0" if self._escuro else "#1E293B")
        for cartao in self._cartoes:
            cartao.atualizar_texto_e_estado(self._escuro)

    def _alterar_menu(self, visivel: bool) -> None:
        menu_prefs.guardar({"jogos": visivel})
        janela = self.parent()
        if hasattr(janela, "menu"):
            janela.menu._jogos.setVisible(visivel)

    # --- trabalho em segundo plano -------------------------------------------------

    def _correr(
        self,
        trabalho: Callable[[Callable[[int, int], None]], object],
        ao_terminar: Callable[[object], None],
        ao_progresso: Callable[[int, int], None] | None = None,
    ) -> None:
        sinal = _Sinal(self)
        sinal.terminou.connect(ao_terminar, Qt.ConnectionType.QueuedConnection)
        if ao_progresso is not None:
            sinal.progresso.connect(ao_progresso, Qt.ConnectionType.QueuedConnection)

        def executar() -> None:
            try:
                resultado: tuple = ("ok", trabalho(sinal.progresso.emit))
            except Exception as erro:
                resultado = ("erro", _mensagem(erro))
            sinal.terminou.emit(resultado)

        threading.Thread(target=executar, daemon=True, name="quadro-jogos").start()

    # --- cartoes e detalhes --------------------------------------------------------

    def _indice_pronto(self, resultado: object) -> None:
        estado, valor = resultado  # type: ignore[misc]
        if estado == "erro":
            self._estado.setText(str(valor))
            return
        self._resumos = list(valor)  # type: ignore[arg-type]
        self._cartoes.clear()
        while self._layout_cartoes.count() > 1:
            item = self._layout_cartoes.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        for resumo in self._resumos:
            cartao = _CartaoJogo(resumo, self._acao_cartao, self._reinstalar_cartao, self._reverificar_cartao)
            cartao.clicado.connect(self._alternar_cartao)
            self._cartoes.append(cartao)
            self._layout_cartoes.insertWidget(self._layout_cartoes.count() - 1, cartao)
            self._correr(lambda _, r=resumo: self._carregar_dados_cartao(r), lambda res, c=cartao: self._dados_prontos(c, res))

        self._estado.setText("" if self._resumos else "Não há jogos disponíveis.")
        if self._cartoes:
            self._alternar_cartao(self._cartoes[0])

    def _carregar_dados_cartao(self, resumo: ResumoJogo) -> tuple:
        jogo = catalogo.carregar_jogo(resumo, self._base)
        miniatura = catalogo.miniatura(jogo, catalogo.pasta_cache(), self._base)
        instalado = catalogo.instalado(jogo)
        executavel = catalogo.executavel_instalado(jogo)
        return jogo, miniatura, instalado, executavel

    def _dados_prontos(self, cartao: _CartaoJogo, resultado: object) -> None:
        estado, valor = resultado  # type: ignore[misc]
        if estado == "erro":
            self._estado.setText(str(valor))
            return
        jogo, miniatura, instalado, executavel = valor  # type: ignore[misc]
        cartao.preencher_dados(jogo, miniatura, instalado, executavel, self._escuro)
        self._registar_categoria(jogo.categoria)
        if cartao is self._cartao_ativo:
            self._jogo = jogo
            self._instalado = executavel or instalado
            self._texto = cartao.texto_detalhe
        self._aplicar_filtros()

    def _registar_categoria(self, categoria: str) -> None:
        if not categoria:
            return
        existentes = [self._filtro_categoria.itemData(i) for i in range(self._filtro_categoria.count())]
        if categoria not in existentes:
            atual = self._filtro_categoria.currentData()
            self._filtro_categoria.blockSignals(True)
            self._filtro_categoria.addItem(categoria, categoria)
            # Mantem as categorias ordenadas alfabeticamente apos "Todas as categorias"
            cats = sorted(
                [self._filtro_categoria.itemData(i) for i in range(1, self._filtro_categoria.count())],
                key=lambda s: str(s).lower(),
            )
            self._filtro_categoria.clear()
            self._filtro_categoria.addItem(t("jogos.todas_categorias"), "")
            for c in cats:
                self._filtro_categoria.addItem(str(c), c)
            idx = self._filtro_categoria.findData(atual)
            if idx >= 0:
                self._filtro_categoria.setCurrentIndex(idx)
            self._filtro_categoria.blockSignals(False)

    def _limpar_filtros(self) -> None:
        self._pesquisa.clear()
        self._filtro_tipo.setCurrentIndex(0)
        self._filtro_categoria.setCurrentIndex(0)
        self._filtro_controlos.setCurrentIndex(0)

    def _corresponde_filtros(self, cartao: _CartaoJogo) -> bool:
        termo = self._pesquisa.text().strip().lower()
        tipo_sel = str(self._filtro_tipo.currentData() or "")
        cat_sel = str(self._filtro_categoria.currentData() or "")
        ctrl_sel = str(self._filtro_controlos.currentData() or "")

        jogo = cartao.jogo
        if termo:
            alvo = f"{cartao.resumo.nome} {jogo.descricao if jogo else ''} {jogo.categoria if jogo else ''}".lower()
            if termo not in alvo:
                return False

        if jogo is None:
            return not (tipo_sel or cat_sel or ctrl_sel)

        if tipo_sel:
            eh_integrado = jogo.instalacao_windows is not None and jogo.instalacao_windows.tipo == "integrado"
            eh_instalador = jogo.instalacao_windows is not None and jogo.instalacao_windows.tipo == "instalador"
            pronto = eh_integrado or cartao.executavel is not None or (cartao.instalado is not None and not eh_instalador)
            if tipo_sel == "integrado" and not eh_integrado:
                return False
            if tipo_sel == "instalado" and not pronto:
                return False
            if tipo_sel == "disponivel" and (pronto or jogo.instalacao_windows is None):
                return False

        if cat_sel and jogo.categoria != cat_sel:
            return False

        if ctrl_sel and ctrl_sel not in jogo.controlos:
            return False

        return True

    def _aplicar_filtros(self) -> None:
        visiveis = 0
        for cartao in self._cartoes:
            mostrar = self._corresponde_filtros(cartao)
            cartao.setVisible(mostrar)
            if mostrar:
                visiveis += 1
        tem_filtro = bool(
            self._pesquisa.text().strip()
            or self._filtro_tipo.currentData()
            or self._filtro_categoria.currentData()
            or self._filtro_controlos.currentData()
        )
        if tem_filtro:
            if visiveis == 0:
                self._estado.setText(t("jogos.nenhum_filtro"))
            else:
                self._estado.setText(t("jogos.mostrar_contagem", visiveis=visiveis, total=len(self._cartoes)))
        elif not self._ocupado and self._cartoes:
            self._estado.setText("")

    def _alternar_cartao(self, cartao: _CartaoJogo) -> None:
        if self._ocupado:
            return
        if self._cartao_ativo is cartao and cartao._expandido:
            cartao.definir_expandido(False)
            self._cartao_ativo = None
            return
        for outro in self._cartoes:
            outro.definir_expandido(outro is cartao)
        self._cartao_ativo = cartao
        if cartao.jogo is not None:
            self._jogo = cartao.jogo
            self._instalado = cartao.executavel or cartao.instalado
            self._texto = cartao.texto_detalhe

    # --- acoes ---------------------------------------------------------------------

    def _reverificar_cartao(self, cartao: _CartaoJogo) -> None:
        if cartao.jogo is None:
            return
        cartao.executavel = catalogo.executavel_instalado(cartao.jogo)
        cartao.instalado = catalogo.instalado(cartao.jogo)
        cartao.atualizar_texto_e_estado(self._escuro)
        if cartao.executavel is not None:
            self._estado.setText(f"{cartao.jogo.nome} detetado e pronto a iniciar!")
        else:
            self._estado.setText(f"{cartao.jogo.nome} ainda não foi detetado no sistema.")

    def _reinstalar_cartao(self, cartao: _CartaoJogo) -> None:
        if cartao.jogo is None or cartao.instalado is None or self._ocupado:
            return
        self._abrir(cartao.instalado, cartao.jogo, "instalador")

    def _acao_cartao(self, cartao: _CartaoJogo) -> None:
        jogo = cartao.jogo
        if jogo is None or self._ocupado:
            return
        # Jogos nativos integrados no Quadro arrancam imediatamente
        if jogo.instalacao_windows is not None and jogo.instalacao_windows.tipo == "integrado" and jogo.instalacao_windows.modulo:
            self._estado.setText(f"A abrir {jogo.nome}…")
            abrir_jogo_integrado(jogo.instalacao_windows.modulo, self)
            self._estado.setText(f"{jogo.nome} concluído.")
            return
        # Se ja existe executavel instalado (ex.: GCompris.exe ou gcompris-qt / sgt-puzzles), arranca diretamente!
        if cartao.executavel is not None:
            self._abrir(cartao.executavel, jogo, "executavel")
            return
        if sys.platform != "win32":
            self._ocupado = True
            cartao.botao_principal.setEnabled(False)
            cartao.barra.setVisible(True)
            cartao.barra.setRange(0, 100)
            cartao.barra.setValue(0)
            self._estado.setText(f"A instalar a versão Linux de {jogo.nome}…")
            self._correr(
                lambda progresso: catalogo.transferir_linux(jogo, progresso=progresso),
                lambda resultado: self._transferido(cartao, jogo, resultado),
                lambda rec, tot: self._progresso(cartao, rec, tot),
            )
            return
        if cartao.instalado is not None:
            tipo = jogo.instalacao_windows.tipo if jogo.instalacao_windows else "executavel"
            self._abrir(cartao.instalado, jogo, tipo)
            return
        if jogo.instalacao_windows is None:
            return
        self._ocupado = True
        cartao.botao_principal.setEnabled(False)
        cartao.barra.setVisible(True)
        cartao.barra.setRange(0, 100)
        cartao.barra.setValue(0)
        self._estado.setText(f"A descarregar {jogo.nome} da fonte oficial…")
        self._correr(
            lambda progresso: catalogo.transferir(jogo, progresso=progresso),
            lambda resultado: self._transferido(cartao, jogo, resultado),
            lambda rec, tot: self._progresso(cartao, rec, tot),
        )

    def _progresso(self, cartao: _CartaoJogo, recebido: int, total: int) -> None:
        percentagem = int(recebido * 100 / total) if total else 0
        cartao.barra.setValue(percentagem)
        self._estado.setText(f"A descarregar… {percentagem}%")

    def _transferido(self, cartao: _CartaoJogo, jogo: Jogo, resultado: object) -> None:
        self._ocupado = False
        cartao.barra.setVisible(False)
        estado, valor = resultado  # type: ignore[misc]
        if estado == "erro":
            self._estado.setText(str(valor))
            cartao.atualizar_texto_e_estado(self._escuro)
            return
        cartao.instalado = valor  # type: ignore[assignment]
        cartao.executavel = catalogo.executavel_instalado(jogo)
        if sys.platform != "win32":
            # A colecao sgt-puzzles instala os 40 jogos de uma so vez: atualiza todos os cartoes!
            for outro in self._cartoes:
                if outro.jogo is not None:
                    outro.executavel = catalogo.executavel_instalado(outro.jogo)
                    outro.atualizar_texto_e_estado(self._escuro)
        else:
            cartao.atualizar_texto_e_estado(self._escuro)
        self._estado.setText("Instalado e verificado com sucesso. A iniciar o jogo…")
        tipo = "executavel" if (sys.platform != "win32" or cartao.executavel) else (jogo.instalacao_windows.tipo if jogo.instalacao_windows else "executavel")
        self._abrir(cartao.executavel or valor, jogo, tipo)  # type: ignore[arg-type]

    def _abrir(self, caminho: Path, jogo: Jogo, tipo: str) -> None:
        try:
            catalogo.abrir(caminho, tipo)
        except ErroCatalogo as erro:
            self._estado.setText(_mensagem(erro))
            return
        except OSError as erro:
            self._estado.setText(f"Não foi possível abrir o jogo: {erro}")
            return
        if tipo == "instalador":
            self._estado.setText(f"Instalador de {jogo.nome} aberto. Depois de instalar, clique em «Já instalei — atualizar».")
        else:
            self._estado.setText(f"Aberto: {jogo.nome}.")
