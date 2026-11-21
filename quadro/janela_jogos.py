"""Catálogo de jogos: lista, detalhes com créditos e licença, e transferência a pedido."""

from __future__ import annotations

import html
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from quadro import catalogo, menu_prefs
from quadro.catalogo import ErroCatalogo, Jogo, ResumoJogo
from quadro.interruptor import interruptor

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


def _ligacao(nome: str, url: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(nome)}</a>'


class DialogoJogos(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Jogos")
        self.resize(960, 600)
        self._base = catalogo.base_recursos()
        self._resumos: list[ResumoJogo] = []
        self._jogo: Jogo | None = None
        self._instalado: Path | None = None
        self._ocupado = False

        self._lista = QListWidget()
        self._lista.setMinimumWidth(220)
        self._lista.currentRowChanged.connect(self._selecionado)

        self._imagem = QLabel("Sem imagem")
        self._imagem.setFixedSize(360, 220)
        self._imagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._imagem.setStyleSheet("border: 1px solid #888888;")

        self._texto = QLabel()
        self._texto.setWordWrap(True)
        self._texto.setTextFormat(Qt.TextFormat.RichText)
        self._texto.setOpenExternalLinks(True)
        self._texto.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._estado = QLabel("A carregar o catálogo…")
        self._estado.setWordWrap(True)
        self._barra = QProgressBar()
        self._barra.setVisible(False)
        self._botao = QPushButton()
        self._botao.setEnabled(False)
        self._botao.clicked.connect(lambda _=False: self._acao())
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)

        direita = QVBoxLayout()
        direita.addWidget(self._imagem)
        direita.addWidget(self._texto, 1)
        direita.addWidget(self._estado)
        direita.addWidget(self._barra)
        botoes = QHBoxLayout()
        botoes.addWidget(self._botao)
        botoes.addStretch(1)
        botoes.addWidget(fechar)
        direita.addLayout(botoes)

        conteudo = QHBoxLayout()
        conteudo.addWidget(self._lista)
        conteudo.addLayout(direita, 1)
        self._menu = interruptor("Adicionar ao Menu", menu_prefs.ler()["jogos"])
        self._menu.toggled.connect(self._alterar_menu)
        topo = QHBoxLayout()
        topo.addStretch(1)
        topo.addWidget(self._menu)
        raiz = QVBoxLayout(self)
        raiz.addLayout(topo)
        raiz.addLayout(conteudo, 1)

        self._correr(lambda _: catalogo.carregar_indice(self._base), self._indice_pronto)

    # --- trabalho em segundo plano -------------------------------------------------

    def _alterar_menu(self, visivel: bool) -> None:
        menu_prefs.guardar({"jogos": visivel})
        janela = self.parent()
        if hasattr(janela, "menu"):
            janela.menu._jogos.setVisible(visivel)

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
            except Exception as erro:  # o erro é mostrado ao utilizador
                resultado = ("erro", _mensagem(erro))
            sinal.terminou.emit(resultado)

        threading.Thread(target=executar, daemon=True, name="quadro-jogos").start()

    # --- lista e detalhes ----------------------------------------------------------

    def _indice_pronto(self, resultado: object) -> None:
        estado, valor = resultado  # type: ignore[misc]
        if estado == "erro":
            self._estado.setText(str(valor))
            return
        self._resumos = list(valor)  # type: ignore[arg-type]
        self._lista.clear()
        for resumo in self._resumos:
            self._lista.addItem(resumo.nome)
        self._estado.setText("Escolha um jogo para ver os detalhes." if self._resumos else "Não há jogos.")
        if self._resumos:
            self._lista.setCurrentRow(0)

    def _selecionado(self, linha: int) -> None:
        if linha < 0 or linha >= len(self._resumos) or self._ocupado:
            return
        resumo = self._resumos[linha]
        self._jogo = None
        self._botao.setEnabled(False)
        self._texto.clear()
        self._imagem.setText("Sem imagem")
        self._imagem.setPixmap(QPixmap())
        self._estado.setText("A carregar os detalhes…")
        self._correr(lambda _: self._detalhes(resumo), self._detalhes_prontos)

    def _detalhes(self, resumo: ResumoJogo) -> tuple:
        jogo = catalogo.carregar_jogo(resumo, self._base)
        miniatura = catalogo.miniatura(jogo, catalogo.pasta_cache(), self._base)
        return jogo, miniatura, catalogo.instalado(jogo)

    def _detalhes_prontos(self, resultado: object) -> None:
        estado, valor = resultado  # type: ignore[misc]
        if estado == "erro":
            self._estado.setText(str(valor))
            return
        jogo, miniatura, instalado = valor  # type: ignore[misc]
        self._jogo = jogo
        self._instalado = instalado
        if miniatura is not None:
            pixmap = QPixmap(str(miniatura))
            if not pixmap.isNull():
                self._imagem.setPixmap(pixmap.scaled(360, 220, Qt.AspectRatioMode.KeepAspectRatio))
        self._texto.setText(self._texto_detalhe(jogo))
        self._estado.setText("")
        self._atualizar_botao()

    def _texto_detalhe(self, jogo: Jogo) -> str:
        escapar = html.escape
        linhas = [
            f"<h2>{escapar(jogo.nome)}</h2>",
            f"<p>{escapar(jogo.descricao)}</p>",
            f"<p><b>Autores:</b> {escapar(', '.join(jogo.autores))}<br>",
            f"<b>Copyright:</b> {escapar(jogo.copyright)}<br>",
            f"<b>Licença:</b> {_ligacao(jogo.licenca, jogo.licenca_url)}<br>",
            f"<b>Site:</b> {_ligacao(jogo.site, jogo.site)}<br>",
            f"<b>Fonte oficial:</b> {_ligacao('download', jogo.fonte_oficial)}</p>",
        ]
        if jogo.instalacao_windows is None:
            linhas.append("<p><i>Sem instalação para Windows nesta versão.</i></p>")
        return "".join(linhas)

    def _atualizar_botao(self) -> None:
        jogo = self._jogo
        if jogo is None:
            self._botao.setEnabled(False)
            return
        if self._instalado is not None and jogo.instalacao_windows is not None and jogo.instalacao_windows.tipo == "instalador":
            self._botao.setText("Executar instalador outra vez")
        elif self._instalado is not None:
            self._botao.setText("Abrir")
        elif jogo.instalacao_windows is not None:
            if jogo.instalacao_windows.tipo == "instalador":
                self._botao.setText("Descarregar e iniciar instalador")
            else:
                self._botao.setText("Descarregar e abrir")
        else:
            self._botao.setText("Indisponível")
        self._botao.setEnabled(self._instalado is not None or jogo.instalacao_windows is not None)

    # --- ações ---------------------------------------------------------------------

    def _acao(self) -> None:
        jogo = self._jogo
        if jogo is None or self._ocupado:
            return
        if self._instalado is not None:
            self._abrir(self._instalado, jogo)
            return
        if jogo.instalacao_windows is None:
            return
        self._ocupado = True
        self._botao.setEnabled(False)
        self._barra.setVisible(True)
        self._barra.setRange(0, 100)
        self._barra.setValue(0)
        self._estado.setText("A descarregar da fonte oficial…")
        self._correr(
            lambda progresso: catalogo.transferir(jogo, progresso=progresso),
            lambda resultado: self._transferido(jogo, resultado),
            self._progresso,
        )

    def _progresso(self, recebido: int, total: int) -> None:
        percentagem = int(recebido * 100 / total) if total else 0
        self._barra.setValue(percentagem)
        self._estado.setText(f"A descarregar… {percentagem}%")

    def _transferido(self, jogo: Jogo, resultado: object) -> None:
        self._ocupado = False
        self._barra.setVisible(False)
        estado, valor = resultado  # type: ignore[misc]
        if estado == "erro":
            self._estado.setText(str(valor))
            self._atualizar_botao()
            return
        self._instalado = valor  # type: ignore[assignment]
        self._estado.setText("Verificado (SHA-256 confere com o registo oficial).")
        self._atualizar_botao()
        self._abrir(valor, jogo)  # type: ignore[arg-type]

    def _abrir(self, caminho: Path, jogo: Jogo) -> None:
        tipo = jogo.instalacao_windows.tipo if jogo.instalacao_windows else "executavel"
        try:
            catalogo.abrir(caminho, tipo)
        except ErroCatalogo as erro:
            self._estado.setText(_mensagem(erro))
            return
        except OSError as erro:
            self._estado.setText(f"Não foi possível abrir o jogo: {erro}")
            return
        self._estado.setText(f"Aberto: {jogo.nome}.")
