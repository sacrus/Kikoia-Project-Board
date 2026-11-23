"""Pesquisa de imagens no Openverse, dentro do Quadro. Mostra sempre autor e licença antes de usar a imagem."""

from __future__ import annotations

import html as html_lib
from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from quadro import openverse
from quadro.janela_correio import botao_com_icone, correr_em_fundo


class DialogoPesquisaImagens(QDialog):
    def __init__(self, pai, credencial: tuple[str, str], ao_escolher: Callable[[QImage, openverse.Imagem], None]) -> None:
        super().__init__(pai)
        self.setWindowTitle("Pesquisar imagens")
        self.resize(860, 580)
        self._credencial = credencial
        self._ao_escolher = ao_escolher
        self._resultados: list[openverse.Imagem] = []
        self._termo = ""
        self._pagina = 0
        self._total = 0

        self._campo = QLineEdit()
        self._campo.setPlaceholderText("Ex.: gato, estrela, escola")
        self._campo.returnPressed.connect(self._pesquisar)
        pesquisar = botao_com_icone("Pesquisar", "pesquisar")
        pesquisar.clicked.connect(lambda _=False: self._pesquisar())

        self._lista = QListWidget()
        self._lista.setViewMode(QListWidget.ViewMode.IconMode)
        self._lista.setIconSize(QSize(120, 120))
        self._lista.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._lista.setGridSize(QSize(150, 160))
        self._lista.currentRowChanged.connect(self._selecionar)

        self._info = QLabel("Escolha uma imagem para ver o autor e a licença.")
        self._info.setWordWrap(True)
        self._info.setTextFormat(Qt.TextFormat.RichText)
        self._info.setOpenExternalLinks(True)

        self._mais = botao_com_icone("Mais resultados", "mais")
        self._mais.setEnabled(False)
        self._mais.clicked.connect(lambda _=False: self._proxima_pagina())
        self._usar = botao_com_icone("Usar esta imagem", "imagem")
        self._usar.setEnabled(False)
        self._usar.clicked.connect(lambda _=False: self._usar_selecionada())
        fechar = botao_com_icone("Fechar", "cancelar")
        fechar.clicked.connect(self.reject)
        self._estado = QLabel("")
        self._estado.setWordWrap(True)

        barra = QHBoxLayout()
        barra.addWidget(self._campo, 1)
        barra.addWidget(pesquisar)
        botoes = QHBoxLayout()
        botoes.addWidget(self._usar)
        botoes.addWidget(self._mais)
        botoes.addStretch(1)
        botoes.addWidget(fechar)
        raiz = QVBoxLayout(self)
        raiz.addLayout(barra)
        raiz.addWidget(self._lista, 1)
        raiz.addWidget(self._info)
        raiz.addWidget(self._estado)
        raiz.addLayout(botoes)

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
            item = QListWidgetItem(imagem.titulo[:30])
            item.setIcon(QIcon(QPixmap.fromImage(miniatura).scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
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
        destino = html_lib.escape(imagem.pagina or imagem.url, quote=True)
        self._info.setText(
            f"<b>{html_lib.escape(imagem.titulo)}</b><br>"
            f"Autor: {html_lib.escape(imagem.autor)}<br>"
            f"Licença: {html_lib.escape(imagem.licenca)}<br>"
            f"<a href='{destino}'>Ver a origem</a>"
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
