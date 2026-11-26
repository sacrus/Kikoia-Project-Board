"""Menu de Definições moderno do Quadro Interativo em grelha de cartões Bento com tema Claro/Escuro e 4 idiomas."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from quadro import idiomas, tema_partilhado
from quadro.area_util import adaptar_a_area_util
from quadro.idiomas import t

if TYPE_CHECKING:
    from quadro.janela import JanelaQuadro

CORES_FUNDO_QUADRO = ("#ffffff", "#fdf6e3", "#e8f4f8", "#1e1e1e")
VERSAO_QUADRO = "1.0.0"


def _icone_cartao(nome: str, cor_hex: str, tamanho: int = 44) -> QPixmap:
    """Desenha uma ilustração vetorial original e nítida num medalhão circular suave."""
    pix = QPixmap(tamanho, tamanho)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(tamanho)
    cor = QColor(cor_hex)

    bg = QColor(cor)
    bg.setAlpha(34)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg)
    p.drawEllipse(QRectF(1.5, 1.5, s - 3.0, s - 3.0))

    pen = QPen(cor, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if nome == "gravar":
        p.drawRoundedRect(QRectF(s * 0.24, s * 0.22, s * 0.52, s * 0.56), 4, 4)
        p.drawRect(QRectF(s * 0.34, s * 0.22, s * 0.30, s * 0.18))
        p.drawRoundedRect(QRectF(s * 0.32, s * 0.52, s * 0.36, s * 0.24), 2, 2)
    elif nome == "abrir":
        path = QPainterPath()
        path.moveTo(s * 0.20, s * 0.32)
        path.lineTo(s * 0.40, s * 0.32)
        path.lineTo(s * 0.46, s * 0.39)
        path.lineTo(s * 0.78, s * 0.39)
        path.lineTo(s * 0.78, s * 0.72)
        path.lineTo(s * 0.20, s * 0.72)
        path.closeSubpath()
        p.drawPath(path)
    elif nome == "exportar":
        p.drawLine(QPointF(s * 0.24, s * 0.56), QPointF(s * 0.24, s * 0.74))
        p.drawLine(QPointF(s * 0.24, s * 0.74), QPointF(s * 0.76, s * 0.74))
        p.drawLine(QPointF(s * 0.76, s * 0.74), QPointF(s * 0.76, s * 0.56))
        p.drawLine(QPointF(s * 0.50, s * 0.60), QPointF(s * 0.50, s * 0.24))
        p.drawLine(QPointF(s * 0.36, s * 0.38), QPointF(s * 0.50, s * 0.24))
        p.drawLine(QPointF(s * 0.64, s * 0.38), QPointF(s * 0.50, s * 0.24))
    elif nome == "importar":
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.24, s * 0.56, s * 0.52), 5, 5)
        p.drawEllipse(QPointF(s * 0.36, s * 0.38), s * 0.055, s * 0.055)
        p.drawLine(QPointF(s * 0.24, s * 0.68), QPointF(s * 0.44, s * 0.48))
        p.drawLine(QPointF(s * 0.44, s * 0.48), QPointF(s * 0.56, s * 0.60))
        p.drawLine(QPointF(s * 0.56, s * 0.60), QPointF(s * 0.66, s * 0.50))
        p.drawLine(QPointF(s * 0.66, s * 0.50), QPointF(s * 0.76, s * 0.68))
    elif nome == "pesquisar":
        p.drawEllipse(QPointF(s * 0.44, s * 0.44), s * 0.20, s * 0.20)
        p.drawLine(QPointF(s * 0.59, s * 0.59), QPointF(s * 0.76, s * 0.76))
    elif nome == "partilhar":
        path = QPainterPath()
        path.moveTo(s * 0.22, s * 0.48)
        path.lineTo(s * 0.78, s * 0.24)
        path.lineTo(s * 0.62, s * 0.76)
        path.lineTo(s * 0.46, s * 0.56)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(s * 0.46, s * 0.56), QPointF(s * 0.78, s * 0.24))
    elif nome == "jogos":
        p.drawRoundedRect(QRectF(s * 0.20, s * 0.34, s * 0.60, s * 0.34), 10, 10)
        p.drawLine(QPointF(s * 0.32, s * 0.51), QPointF(s * 0.42, s * 0.51))
        p.drawLine(QPointF(s * 0.37, s * 0.46), QPointF(s * 0.37, s * 0.56))
        p.setBrush(cor)
        p.drawEllipse(QPointF(s * 0.62, s * 0.47), 2.2, 2.2)
        p.drawEllipse(QPointF(s * 0.68, s * 0.54), 2.2, 2.2)
    elif nome == "correio":
        p.drawRoundedRect(QRectF(s * 0.20, s * 0.28, s * 0.60, s * 0.44), 5, 5)
        p.drawLine(QPointF(s * 0.22, s * 0.31), QPointF(s * 0.50, s * 0.53))
        p.drawLine(QPointF(s * 0.78, s * 0.31), QPointF(s * 0.50, s * 0.53))
    elif nome == "documentos":
        # Folha de documento com canto dobrado e linhas de texto
        path = QPainterPath()
        path.moveTo(s * 0.26, s * 0.18)
        path.lineTo(s * 0.58, s * 0.18)
        path.lineTo(s * 0.74, s * 0.34)
        path.lineTo(s * 0.74, s * 0.82)
        path.lineTo(s * 0.26, s * 0.82)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(s * 0.58, s * 0.18), QPointF(s * 0.58, s * 0.34))
        p.drawLine(QPointF(s * 0.58, s * 0.34), QPointF(s * 0.74, s * 0.34))
        p.drawLine(QPointF(s * 0.36, s * 0.48), QPointF(s * 0.64, s * 0.48))
        p.drawLine(QPointF(s * 0.36, s * 0.60), QPointF(s * 0.64, s * 0.60))
        p.drawLine(QPointF(s * 0.36, s * 0.72), QPointF(s * 0.54, s * 0.72))
    elif nome == "limpar":
        p.drawLine(QPointF(s * 0.26, s * 0.74), QPointF(s * 0.68, s * 0.32))
        p.drawLine(QPointF(s * 0.22, s * 0.58), QPointF(s * 0.42, s * 0.78))
        p.drawLine(QPointF(s * 0.62, s * 0.22), QPointF(s * 0.62, s * 0.34))
        p.drawLine(QPointF(s * 0.56, s * 0.28), QPointF(s * 0.68, s * 0.28))
    elif nome == "remover_imagem":
        p.drawRoundedRect(QRectF(s * 0.22, s * 0.26, s * 0.50, s * 0.48), 5, 5)
        p.drawLine(QPointF(s * 0.24, s * 0.64), QPointF(s * 0.42, s * 0.48))
        p.drawLine(QPointF(s * 0.42, s * 0.48), QPointF(s * 0.56, s * 0.60))
        p.drawLine(QPointF(s * 0.62, s * 0.22), QPointF(s * 0.78, s * 0.38))
        p.drawLine(QPointF(s * 0.78, s * 0.22), QPointF(s * 0.62, s * 0.38))

    p.end()
    return pix


class _CartaoAcao(QFrame):
    """Cartão clicável da grelha Bento com ícone vetorial, título e subtítulo."""

    clicado = Signal()

    def __init__(self, icone: str, chave_titulo: str, chave_sub: str, cor: str) -> None:
        super().__init__()
        self.setObjectName("cartaoBento")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chave_titulo = chave_titulo
        self._chave_sub = chave_sub

        lbl_ic = QLabel()
        lbl_ic.setPixmap(_icone_cartao(icone, cor, 44))
        lbl_ic.setFixedSize(44, 44)
        lbl_ic.setStyleSheet("background: transparent; border: none;")

        self._lbl_tit = QLabel()
        self._lbl_tit.setObjectName("tituloCartao")
        self._lbl_tit.setWordWrap(True)

        self._lbl_sub = QLabel()
        self._lbl_sub.setObjectName("subtituloCartao")
        self._lbl_sub.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        lay.addWidget(lbl_ic, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self._lbl_tit)
        lay.addWidget(self._lbl_sub)
        lay.addStretch(1)
        self.retraduzir()

    def retraduzir(self) -> None:
        self._lbl_tit.setText(t(self._chave_titulo))
        self._lbl_sub.setText(t(self._chave_sub))

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self.clicado.emit()
        super().mousePressEvent(evento)


def _estilo_definicoes(escuro: bool) -> str:
    if escuro:
        fundo = "#131720"
        topo = "#1A202E"
        cartao = "#1E2534"
        cartao_hover = "#252F44"
        texto = "#F1F5F9"
        texto_suave = "#94A3B8"
        borda = "#2E374B"
        borda_hover = "#3B82F6"
        btn_sec = "#262F42"
        btn_sec_hover = "#313C54"
    else:
        fundo = "#EEF2F7"
        topo = "#FFFFFF"
        cartao = "#FFFFFF"
        cartao_hover = "#F8FAFC"
        texto = "#0F172A"
        texto_suave = "#64748B"
        borda = "#CBD5E1"
        borda_hover = "#2563EB"
        btn_sec = "#F1F5F9"
        btn_sec_hover = "#E2E8F0"

    return f"""
QDialog {{
    background-color: {fundo};
    color: {texto};
}}
QFrame#cabecalhoDef {{
    background-color: {topo};
    border-bottom: 1px solid {borda};
}}
QLabel#tituloDef {{
    color: {texto};
    font-size: 20px;
    font-weight: 700;
}}
QLabel#subtituloDef {{
    color: {texto_suave};
    font-size: 12px;
}}
QFrame#cartaoFaixa {{
    background-color: {cartao};
    border: 1px solid {borda};
    border-radius: 13px;
}}
QLabel#rotuloFaixa {{
    color: {texto};
    font-size: 13px;
    font-weight: 700;
    background: transparent;
}}
QLabel#tituloSeccao {{
    color: {texto_suave};
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: transparent;
    padding-top: 2px;
}}
QFrame#cartaoBento {{
    background-color: {cartao};
    border: 1.5px solid {borda};
    border-radius: 14px;
}}
QFrame#cartaoBento:hover {{
    background-color: {cartao_hover};
    border-color: {borda_hover};
}}
QLabel#tituloCartao {{
    color: {texto};
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}}
QLabel#subtituloCartao {{
    color: {texto_suave};
    font-size: 11.5px;
    background: transparent;
}}
QFrame#painelExportar {{
    background-color: {cartao};
    border: 1.5px solid {borda_hover};
    border-radius: 12px;
}}
QComboBox#seletorIdioma {{
    background-color: {btn_sec};
    color: {texto};
    border: 1px solid {borda};
    border-radius: 9px;
    padding: 6px 10px;
    font-size: 9.5pt;
    font-weight: 600;
}}
QComboBox#seletorIdioma QAbstractItemView {{
    background-color: {topo};
    color: {texto};
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
    font-size: 9.5pt;
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
QPushButton:checked {{
    background-color: #2563EB;
    color: #FFFFFF;
    border: 1px solid #2563EB;
}}
QPushButton[papel="perigo"] {{
    background-color: #DC2626;
    color: #FFFFFF;
    border: 1px solid #DC2626;
}}
QPushButton[papel="perigo"]:hover {{
    background-color: #B91C1C;
}}
QPushButton[papel="formato"] {{
    background-color: #0891B2;
    color: #FFFFFF;
    border: 1px solid #0891B2;
}}
QPushButton[papel="formato"]:hover {{
    background-color: #0E7490;
}}
"""


class DialogoDefinicoes(QDialog):
    def __init__(self, janela: JanelaQuadro) -> None:
        super().__init__(janela)
        idiomas.carregar_partilhado()
        self.resize(880, 680)
        self.janela = janela
        self.quadro = janela.quadro
        self.tela = janela.tela
        self._escuro = tema_partilhado.e_escuro()
        self._cartoes: list[_CartaoAcao] = []

        # --- Cabeçalho ---
        cab = QFrame()
        cab.setObjectName("cabecalhoDef")
        cab_lay = QHBoxLayout(cab)
        cab_lay.setContentsMargins(20, 14, 20, 14)

        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        self._lbl_t = QLabel()
        self._lbl_t.setObjectName("tituloDef")
        self._lbl_s = QLabel()
        self._lbl_s.setObjectName("subtituloDef")
        titulos.addWidget(self._lbl_t)
        titulos.addWidget(self._lbl_s)

        self._btn_fechar = QPushButton()
        self._btn_fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_fechar.clicked.connect(self.accept)

        cab_lay.addLayout(titulos, 1)
        cab_lay.addWidget(self._btn_fechar)

        # --- Corpo principal ---
        corpo = QWidget()
        corpo_lay = QVBoxLayout(corpo)
        corpo_lay.setContentsMargins(18, 14, 18, 14)
        corpo_lay.setSpacing(12)

        # --- Faixa rápida: Tema + Idioma + Cor de fundo ---
        faixa = QHBoxLayout()
        faixa.setSpacing(10)

        # Cartão Tema
        card_tema = QFrame()
        card_tema.setObjectName("cartaoFaixa")
        lay_tema = QVBoxLayout(card_tema)
        lay_tema.setContentsMargins(12, 10, 12, 12)
        lay_tema.setSpacing(8)
        self._lbl_tema = QLabel()
        self._lbl_tema.setObjectName("rotuloFaixa")

        linha_tema = QHBoxLayout()
        linha_tema.setSpacing(6)
        self._botao_claro = QPushButton()
        self._botao_claro.setCheckable(True)
        self._botao_claro.setChecked(not self._escuro)
        self._botao_claro.setCursor(Qt.CursorShape.PointingHandCursor)
        self._botao_claro.clicked.connect(lambda _=False: self._definir_tema(False))

        self._botao_escuro = QPushButton()
        self._botao_escuro.setCheckable(True)
        self._botao_escuro.setChecked(self._escuro)
        self._botao_escuro.setCursor(Qt.CursorShape.PointingHandCursor)
        self._botao_escuro.clicked.connect(lambda _=False: self._definir_tema(True))

        linha_tema.addWidget(self._botao_claro, 1)
        linha_tema.addWidget(self._botao_escuro, 1)
        lay_tema.addWidget(self._lbl_tema)
        lay_tema.addLayout(linha_tema)

        # Cartão Idioma (Quadro e Teclado)
        card_idioma = QFrame()
        card_idioma.setObjectName("cartaoFaixa")
        lay_idioma = QVBoxLayout(card_idioma)
        lay_idioma.setContentsMargins(12, 10, 12, 12)
        lay_idioma.setSpacing(8)
        self._lbl_idioma = QLabel()
        self._lbl_idioma.setObjectName("rotuloFaixa")

        self._combo_idioma = QComboBox()
        self._combo_idioma.setObjectName("seletorIdioma")
        for cod, nome in idiomas.IDIOMAS.items():
            self._combo_idioma.addItem(nome, cod)
        idx_atual = self._combo_idioma.findData(idiomas.atual())
        if idx_atual >= 0:
            self._combo_idioma.setCurrentIndex(idx_atual)
        self._combo_idioma.currentIndexChanged.connect(self._alterar_idioma)

        lay_idioma.addWidget(self._lbl_idioma)
        lay_idioma.addWidget(self._combo_idioma)

        # Cartão Cor de fundo
        card_fundo = QFrame()
        card_fundo.setObjectName("cartaoFaixa")
        lay_fundo = QVBoxLayout(card_fundo)
        lay_fundo.setContentsMargins(12, 10, 12, 12)
        lay_fundo.setSpacing(8)
        self._lbl_fundo = QLabel()
        self._lbl_fundo.setObjectName("rotuloFaixa")

        linha_cores = QHBoxLayout()
        linha_cores.setSpacing(7)
        self._botoes_cor: list[tuple[str, QPushButton]] = []
        for cor in CORES_FUNDO_QUADRO:
            btn_c = QPushButton()
            btn_c.setFixedSize(32, 32)
            btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_c.setToolTip(cor)
            btn_c.clicked.connect(lambda _=False, c=cor: self._definir_fundo(c))
            self._botoes_cor.append((cor, btn_c))
            linha_cores.addWidget(btn_c)
        self._btn_outra_cor = QPushButton()
        self._btn_outra_cor.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_outra_cor.clicked.connect(lambda _=False: self._outra_cor())
        linha_cores.addWidget(self._btn_outra_cor)
        linha_cores.addStretch(1)
        lay_fundo.addWidget(self._lbl_fundo)
        lay_fundo.addLayout(linha_cores)

        faixa.addWidget(card_tema, 1)
        faixa.addWidget(card_idioma, 1)
        faixa.addWidget(card_fundo, 1)
        corpo_lay.addLayout(faixa)

        # --- Secção 1: Ações do Quadro (4 colunas x 2 filas) ---
        self._lbl_sec_quadro = QLabel()
        self._lbl_sec_quadro.setObjectName("tituloSeccao")
        corpo_lay.addWidget(self._lbl_sec_quadro)

        grelha_quadro = QGridLayout()
        grelha_quadro.setSpacing(10)

        self._painel_exportar = QFrame()
        self._painel_exportar.setObjectName("painelExportar")
        self._painel_exportar.setVisible(False)
        lay_exp = QHBoxLayout(self._painel_exportar)
        lay_exp.setContentsMargins(14, 10, 14, 10)
        lay_exp.setSpacing(10)
        self._lbl_exp = QLabel()
        self._lbl_exp.setObjectName("rotuloFaixa")
        lay_exp.addWidget(self._lbl_exp)
        for rot, acao in (("JXL", janela.exportar_jxl), ("PNG", janela.exportar_png), ("SVG", janela.exportar_svg)):
            b = QPushButton(rot)
            b.setProperty("papel", "formato")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, a=acao: a())
            lay_exp.addWidget(b)
        lay_exp.addStretch(1)

        acoes_quadro: list[tuple[str, str, str, str, Callable[[], None]]] = [
            ("gravar", "def.gravar", "def.gravar_sub", "#2563EB", janela.gravar),
            ("abrir", "def.abrir", "def.abrir_sub", "#4F46E5", janela.abrir),
            ("exportar", "def.exportar", "def.exportar_sub", "#0891B2", self._alternar_exportar),
            ("limpar", "def.limpar", "def.limpar_sub", "#D97706", self._limpar),
            ("importar", "def.importar", "def.importar_sub", "#16A34A", janela.importar_imagem),
            ("pesquisar", "def.pesquisar", "def.pesquisar_sub", "#059669", janela.pesquisar_imagens),
            ("partilhar", "def.partilhar", "def.partilhar_sub", "#7C3AED", janela.partilhar_por_email),
            ("remover_imagem", "def.remover_imagem", "def.remover_imagem_sub", "#E11D48", janela.remover_imagem),
        ]

        for idx, (ic, c_tit, c_sub, cor, cb) in enumerate(acoes_quadro):
            card = _CartaoAcao(ic, c_tit, c_sub, cor)
            card.clicado.connect(cb)
            self._cartoes.append(card)
            grelha_quadro.addWidget(card, idx // 4, idx % 4)

        corpo_lay.addLayout(grelha_quadro)
        corpo_lay.addWidget(self._painel_exportar)

        # --- Secção 2: Aplicações e Ferramentas ---
        self._lbl_sec_apps = QLabel()
        self._lbl_sec_apps.setObjectName("tituloSeccao")
        corpo_lay.addWidget(self._lbl_sec_apps)

        linha_apps = QHBoxLayout()
        linha_apps.setSpacing(10)
        apps_def: list[tuple[str, str, str, str, Callable[[], None]]] = [
            ("jogos", "def.jogos", "def.jogos_sub", "#EA580C", janela.abrir_jogos),
            ("correio", "def.correio", "def.correio_sub", "#0284C7", janela.abrir_correio),
            ("documentos", "def.documentos", "def.documentos_sub", "#0D9488", janela.abrir_documentos),
        ]
        for ic, c_tit, c_sub, cor, cb in apps_def:
            card = _CartaoAcao(ic, c_tit, c_sub, cor)
            card.clicado.connect(cb)
            self._cartoes.append(card)
            linha_apps.addWidget(card, 1)

        corpo_lay.addLayout(linha_apps)
        corpo_lay.addStretch(1)

        # --- Rodapé ---
        self._rodape_info = QLabel()
        self._rodape_info.setObjectName("subtituloDef")
        self._rodape_info.setTextFormat(Qt.TextFormat.RichText)
        self._rodape_info.setOpenExternalLinks(True)

        rodape = QHBoxLayout()
        rodape.setSpacing(10)
        self._btn_sair = QPushButton()
        self._btn_sair.setProperty("papel", "perigo")
        self._btn_sair.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_sair.clicked.connect(lambda _=False: self._sair())

        rodape.addWidget(self._rodape_info, 1)
        rodape.addWidget(self._btn_sair)
        corpo_lay.addLayout(rodape)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
        scroll.setWidget(corpo)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(cab)
        raiz.addWidget(scroll, 1)

        self._atualizar_estilo_cores()
        self._retraduzir()
        self.setStyleSheet(_estilo_definicoes(self._escuro))
        adaptar_a_area_util(self)

    def _retraduzir(self) -> None:
        self.setWindowTitle(t("def.titulo"))
        self._lbl_t.setText(t("def.cabecalho"))
        self._lbl_s.setText(t("def.subtitulo"))
        self._btn_fechar.setText(t("geral.fechar"))
        self._lbl_tema.setText(t("def.tema"))
        self._botao_claro.setText(t("geral.claro"))
        self._botao_escuro.setText(t("geral.escuro"))
        self._lbl_idioma.setText(t("def.idioma"))
        self._lbl_fundo.setText(t("def.cor_fundo"))
        self._btn_outra_cor.setText(t("def.outra_cor"))
        self._lbl_sec_quadro.setText(t("def.sec_quadro"))
        self._lbl_sec_apps.setText(t("def.sec_apps"))
        self._lbl_exp.setText(t("def.escolher_formato"))
        self._btn_sair.setText(t("def.sair"))
        for card in self._cartoes:
            card.retraduzir()
        self._atualizar_rodape()

    def _alterar_idioma(self) -> None:
        codigo = str(self._combo_idioma.currentData() or idiomas.IDIOMA_PADRAO)
        idiomas.definir(codigo, guardar=True)
        self._retraduzir()
        if hasattr(self.janela, "retraduzir"):
            self.janela.retraduzir()

    def _atualizar_rodape(self) -> None:
        cor_link = "#60A5FA" if self._escuro else "#2563EB"
        self._rodape_info.setText(
            t("def.rodape", versao=VERSAO_QUADRO)
            + f'<a href="https://www.lplogic.net" style="color:{cor_link}; text-decoration:none; font-weight:600;">www.lplogic.net</a>'
        )

    def _alternar_exportar(self) -> None:
        self._painel_exportar.setVisible(not self._painel_exportar.isVisible())

    def _atualizar_estilo_cores(self) -> None:
        atual = self.quadro.fundo.lower()
        for cor, btn in self._botoes_cor:
            ativo = cor.lower() == atual
            borda = "3px solid #2563EB" if ativo else "2px solid #94A3B8"
            btn.setStyleSheet(f"QPushButton {{ background-color: {cor}; border: {borda}; border-radius: 16px; padding: 0; }}")

    def _definir_tema(self, escuro: bool) -> None:
        self._escuro = escuro
        tema_partilhado.guardar_tema(escuro)
        self._botao_claro.setChecked(not escuro)
        self._botao_escuro.setChecked(escuro)
        self._atualizar_rodape()
        self.setStyleSheet(_estilo_definicoes(escuro))

    def _definir_fundo(self, cor: str) -> None:
        if cor == self.quadro.fundo:
            return
        self.quadro.registar()
        self.quadro.fundo = cor
        self.tela.update()
        self._atualizar_estilo_cores()

    def _outra_cor(self) -> None:
        escolhida = QColorDialog.getColor(QColor(self.quadro.fundo), self, t("def.cor_fundo"))
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
