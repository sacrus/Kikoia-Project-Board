"""Pesquisa de imagens no Openverse, dentro do Quadro. Mostra sempre autor e licença antes de usar a imagem."""

from __future__ import annotations

import html as html_lib
from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from quadro import icones_correio, idiomas, openverse, tema_partilhado
from quadro.area_util import adaptar_a_area_util
from quadro.idiomas import t
from quadro.janela_correio import botao_com_icone, correr_em_fundo

_SUGESTOES_RAPIDAS = ("Gato", "Estrela", "Árvore", "Carro", "Flor", "Escola")


def _icone_tingido(nome: str, cor: str, tamanho: int = 18) -> QIcon:
    pix = icones_correio.desenhar(nome, tamanho)
    saida = QPixmap(pix.size())
    saida.fill(Qt.GlobalColor.transparent)
    p = QPainter(saida)
    p.drawPixmap(0, 0, pix)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(saida.rect(), QColor(cor))
    p.end()
    return QIcon(saida)


def _estilo_pesquisa_imagens(escuro: bool) -> str:
    if escuro:
        fundo = "#131720"
        topo = "#1A202E"
        cartao = "#1E2534"
        item_hover = "#252F44"
        item_sel = "#1E3A5F"
        texto = "#F1F5F9"
        texto_sec = "#CBD5E1"
        texto_suave = "#94A3B8"
        borda = "#2E374B"
        borda_sel = "#3B82F6"
        btn_sec = "#262F42"
        btn_sec_hover = "#313C54"
        input_bg = "#131824"
    else:
        fundo = "#EEF2F7"
        topo = "#FFFFFF"
        cartao = "#FFFFFF"
        item_hover = "#F1F5F9"
        item_sel = "#DBEAFE"
        texto = "#0F172A"
        texto_sec = "#334155"
        texto_suave = "#64748B"
        borda = "#CBD5E1"
        borda_sel = "#2563EB"
        btn_sec = "#F1F5F9"
        btn_sec_hover = "#E2E8F0"
        input_bg = "#F8FAFC"

    return f"""
QDialog {{
    background-color: {fundo};
    color: {texto};
}}
QFrame#cabecalhoImagens {{
    background-color: {topo};
    border-bottom: 1px solid {borda};
}}
QFrame#barraPesquisaImagens {{
    background-color: {topo};
    border-bottom: 1px solid {borda};
}}
QLabel#tituloImagens {{
    color: {texto};
    font-size: 20px;
    font-weight: 700;
}}
QLabel#subtituloImagens {{
    color: {texto_suave};
    font-size: 12px;
}}
QLineEdit#campoPesquisaImagens {{
    background-color: {input_bg};
    color: {texto};
    border: 1.5px solid {borda};
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 14px;
}}
QLineEdit#campoPesquisaImagens:focus {{
    border-color: {borda_sel};
}}
QListWidget#galeriaImagens {{
    background-color: {fundo};
    border: none;
    outline: none;
    padding: 10px;
}}
QListWidget#galeriaImagens::item {{
    background-color: {cartao};
    color: {texto};
    border: 1.5px solid {borda};
    border-radius: 12px;
    padding: 8px;
    margin: 5px;
}}
QListWidget#galeriaImagens::item:hover {{
    background-color: {item_hover};
    border-color: {borda_sel};
}}
QListWidget#galeriaImagens::item:selected {{
    background-color: {item_sel};
    color: {texto};
    border: 2px solid {borda_sel};
}}
QFrame#cartaoInfoImagem {{
    background-color: {cartao};
    border-top: 1px solid {borda};
}}
QLabel#infoImagem {{
    color: {texto_sec};
    font-size: 13px;
}}
QLabel#estadoImagens {{
    color: {texto_suave};
    font-size: 12px;
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
QPushButton[papel="primario"]:disabled {{
    background-color: {btn_sec};
    color: {texto_suave};
    border-color: {borda};
}}
QPushButton[papel="usar"] {{
    background-color: #16A34A;
    color: #FFFFFF;
    border: 1px solid #16A34A;
}}
QPushButton[papel="usar"]:hover {{
    background-color: #15803D;
}}
QPushButton[papel="usar"]:disabled {{
    background-color: {btn_sec};
    color: {texto_suave};
    border-color: {borda};
}}
QPushButton[papel="chip"] {{
    background-color: {btn_sec};
    color: {texto_sec};
    border: 1px solid {borda};
    border-radius: 12px;
    padding: 3px 11px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton[papel="chip"]:hover {{
    border-color: {borda_sel};
    color: {texto};
}}
"""


class DialogoPesquisaImagens(QDialog):
    def __init__(self, pai, credencial: tuple[str, str], ao_escolher: Callable[[QImage, openverse.Imagem], None]) -> None:
        super().__init__(pai)
        idiomas.carregar_partilhado()
        self.setWindowTitle(t("imagens.titulo"))
        self.resize(920, 650)
        adaptar_a_area_util(self)
        self._credencial = credencial
        self._ao_escolher = ao_escolher
        self._resultados: list[openverse.Imagem] = []
        self._termo = ""
        self._pagina = 0
        self._total = 0
        self._escuro = tema_partilhado.e_escuro()

        # --- Cabeçalho moderno ---
        cab = QFrame()
        cab.setObjectName("cabecalhoImagens")
        cab_lay = QHBoxLayout(cab)
        cab_lay.setContentsMargins(18, 12, 18, 12)
        cab_lay.setSpacing(12)

        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        lbl_titulo = QLabel(t("imagens.titulo"))
        lbl_titulo.setObjectName("tituloImagens")
        lbl_sub = QLabel(t("imagens.subtitulo"))
        lbl_sub.setObjectName("subtituloImagens")
        titulos.addWidget(lbl_titulo)
        titulos.addWidget(lbl_sub)

        fechar = QPushButton(t("geral.fechar"))
        fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        fechar.clicked.connect(self.reject)

        cab_lay.addLayout(titulos, 1)
        cab_lay.addWidget(fechar)

        # --- Barra de pesquisa + sugestões rápidas ---
        barra_frame = QFrame()
        barra_frame.setObjectName("barraPesquisaImagens")
        barra_v = QVBoxLayout(barra_frame)
        barra_v.setContentsMargins(18, 10, 18, 10)
        barra_v.setSpacing(8)

        self._campo = QLineEdit()
        self._campo.setObjectName("campoPesquisaImagens")
        self._campo.setPlaceholderText(t("imagens.placeholder"))
        self._campo.setClearButtonEnabled(True)
        self._campo.returnPressed.connect(self._pesquisar)

        pesquisar = botao_com_icone(t("imagens.pesquisar"), "pesquisar")
        pesquisar.setIcon(_icone_tingido("pesquisar", "#FFFFFF"))
        pesquisar.setProperty("papel", "primario")
        pesquisar.setCursor(Qt.CursorShape.PointingHandCursor)
        pesquisar.clicked.connect(lambda _=False: self._pesquisar())

        linha_pesq = QHBoxLayout()
        linha_pesq.setSpacing(10)
        linha_pesq.addWidget(self._campo, 1)
        linha_pesq.addWidget(pesquisar)

        linha_chips = QHBoxLayout()
        linha_chips.setSpacing(6)
        lbl_sug = QLabel(t("imagens.ideias"))
        lbl_sug.setObjectName("subtituloImagens")
        linha_chips.addWidget(lbl_sug)
        for termo_sug in [s.strip() for s in t("imagens.sugestoes").split(",") if s.strip()]:
            chip = QPushButton(termo_sug)
            chip.setProperty("papel", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, term=termo_sug: self._pesquisar_termo(term))
            linha_chips.addWidget(chip)
        linha_chips.addStretch(1)

        barra_v.addLayout(linha_pesq)
        barra_v.addLayout(linha_chips)

        # --- Galeria de resultados ---
        self._lista = QListWidget()
        self._lista.setObjectName("galeriaImagens")
        self._lista.setViewMode(QListWidget.ViewMode.IconMode)
        self._lista.setIconSize(QSize(136, 136))
        self._lista.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._lista.setGridSize(QSize(172, 186))
        self._lista.setMovement(QListWidget.Movement.Static)
        self._lista.setWordWrap(True)
        self._lista.currentRowChanged.connect(self._selecionar)
        self._lista.itemDoubleClicked.connect(lambda _item: self._usar_selecionada())

        # --- Cartão inferior com autor/licença e botões ---
        rodape_frame = QFrame()
        rodape_frame.setObjectName("cartaoInfoImagem")
        rodape_lay = QVBoxLayout(rodape_frame)
        rodape_lay.setContentsMargins(18, 12, 18, 12)
        rodape_lay.setSpacing(8)

        self._info = QLabel(t("imagens.info_inicial"))
        self._info.setObjectName("infoImagem")
        self._info.setWordWrap(True)
        self._info.setTextFormat(Qt.TextFormat.RichText)
        self._info.setOpenExternalLinks(True)

        self._usar = botao_com_icone(t("imagens.usar"), "imagem")
        self._usar.setIcon(_icone_tingido("imagem", "#FFFFFF"))
        self._usar.setProperty("papel", "usar")
        self._usar.setEnabled(False)
        self._usar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._usar.clicked.connect(lambda _=False: self._usar_selecionada())

        self._mais = botao_com_icone(t("imagens.mais"), "mais")
        self._mais.setIcon(_icone_tingido("mais", "#E2E8F0" if self._escuro else "#1E293B"))
        self._mais.setEnabled(False)
        self._mais.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mais.clicked.connect(lambda _=False: self._proxima_pagina())

        self._estado = QLabel("")
        self._estado.setObjectName("estadoImagens")
        self._estado.setWordWrap(True)

        botoes = QHBoxLayout()
        botoes.setSpacing(10)
        botoes.addWidget(self._usar)
        botoes.addWidget(self._mais)
        botoes.addSpacing(8)
        botoes.addWidget(self._estado, 1)

        rodape_lay.addWidget(self._info)
        rodape_lay.addLayout(botoes)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(cab)
        raiz.addWidget(barra_frame)
        raiz.addWidget(self._lista, 1)
        raiz.addWidget(rodape_frame)

        self.setStyleSheet(_estilo_pesquisa_imagens(self._escuro))

    def _pesquisar_termo(self, termo: str) -> None:
        self._campo.setText(termo)
        self._pesquisar()

    def _pesquisar(self) -> None:
        termo = self._campo.text().strip()
        if not termo:
            return
        self._termo = termo
        self._pagina = 0
        self._total = 0
        self._resultados = []
        self._lista.clear()
        self._usar.setEnabled(False)
        self._info.setText("Escolha uma imagem para ver o autor e a licença.")
        self._proxima_pagina()

    def _proxima_pagina(self) -> None:
        self._pagina += 1
        self._mais.setEnabled(False)
        self._estado.setText("A pesquisar…")
        termo, credencial, pagina = self._termo, self._credencial, self._pagina

        def trabalhar():
            resultados, total = openverse.pesquisar_pagina(termo, credencial, pagina=pagina)
            # Só entram imagens que se conseguem mostrar: uma entrada sem miniatura seria só texto.
            pares = []
            for imagem in resultados:
                try:
                    dados = openverse.descarregar(imagem.miniatura, openverse.LIMITE_MINIATURA_BYTES)
                except openverse.ErroOpenverse:
                    continue
                if QImage().loadFromData(dados):
                    pares.append((imagem, dados))
            return pares, total

        correr_em_fundo(self, trabalhar, self._pagina_pronta)

    def _pagina_pronta(self, resultado: tuple) -> None:
        estado, valor = resultado
        if estado == "erro":
            self._estado.setText(openverse.mensagem(valor))
            self._mais.setEnabled(self._pagina < self._total)
            return
        pares, total = valor
        self._total = total
        for imagem, dados in pares:
            miniatura = QImage()
            miniatura.loadFromData(dados)
            item = QListWidgetItem(imagem.titulo[:28])
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            item.setIcon(
                QIcon(
                    QPixmap.fromImage(miniatura).scaled(
                        136, 136, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    )
                )
            )
            self._resultados.append(imagem)
            self._lista.addItem(item)
        if not self._resultados and self._pagina >= self._total:
            self._estado.setText("Nenhuma imagem encontrada para este termo.")
        else:
            self._estado.setText(f"{len(self._resultados)} imagens (página {self._pagina} de {max(1, self._total)}).")
        self._mais.setEnabled(self._pagina < self._total)

    def _selecionar(self, linha: int) -> None:
        if not (0 <= linha < len(self._resultados)):
            self._usar.setEnabled(False)
            return
        imagem = self._resultados[linha]
        cor_link = "#60A5FA" if self._escuro else "#2563EB"
        destino = html_lib.escape(imagem.pagina or imagem.url, quote=True)
        self._info.setText(
            f"<b>{html_lib.escape(imagem.titulo)}</b><br>"
            f"<b>{html_lib.escape(t('imagens.autor'))}</b> {html_lib.escape(imagem.autor)} · "
            f"<b>{html_lib.escape(t('imagens.licenca'))}</b> {html_lib.escape(imagem.licenca)} · "
            f"<a href='{destino}' style='color:{cor_link}; text-decoration:none; font-weight:600;'>{html_lib.escape(t('imagens.origem'))}</a>"
        )
        self._usar.setEnabled(True)

    def _usar_selecionada(self) -> None:
        linha = self._lista.currentRow()
        if not (0 <= linha < len(self._resultados)):
            return
        imagem = self._resultados[linha]
        self._usar.setEnabled(False)
        self._estado.setText("A transferir a imagem…")

        def trabalhar():
            return openverse.descarregar(imagem.url)

        def pronta(resultado: tuple) -> None:
            estado, valor = resultado
            self._usar.setEnabled(True)
            if estado == "erro":
                self._estado.setText(openverse.mensagem(valor))
                return
            qimagem = QImage()
            if not qimagem.loadFromData(valor):
                self._estado.setText("Esta imagem não pode ser aberta.")
                return
            self._ao_escolher(qimagem, imagem)
            self.accept()

        correr_em_fundo(self, trabalhar, pronta)
