"""Correio dentro do Quadro.

Por defeito, o correio funciona sem supervisão: abre tudo (formatação, imagens e anexos), e envia para qualquer endereço.
A supervisão existe quando há palavra-passe de supervisor. Então formatação, imagens e anexos começam bloqueados,
as regras aplicam-se, e as alterações pedem a palavra-passe de supervisor.
"""

from __future__ import annotations

import html as html_lib
import mimetypes
import os
import re
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QObject, QStringListModel, Qt, QUrl, Signal
from PySide6.QtGui import QImage, QTextCursor, QTextDocument, QTextImageFormat, QTextListFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from quadro.correio import contatos as contactos
from quadro.correio import contas, oauth, supervisor, voz
from quadro.correio import regras as R
from quadro.correio.html import CID_PREFIXO, sanitizar_html
from quadro.correio.modelo import Anexo, Conta, ErroCorreio, Mensagem, conta_cpanel
from quadro import jxl
from quadro.correio import composicao, ordenacao
from quadro.correio.composicao import Rascunho
from quadro.correio.servidor import Pasta, cliente_de, guardar_em_enviados, montar_mensagem
from quadro.interruptor import interruptor

MENSAGENS = {
    "correio.autenticacao_falhou": "A conta ou a palavra-passe não estão corretas.",
    "correio.sem_ligacao": "Não foi possível ligar ao servidor de correio. Verifique a ligação e o endereço do servidor.",
    "correio.mensagem_nao_encontrada": "Não foi possível obter esta mensagem.",
    "correio.envio_falhou": "A mensagem não foi enviada. Tente outra vez.",
    "correio.sem_destinatarios": "Indique pelo menos um destinatário.",
    "correio.destinatarios_bloqueados": "Há destinatários que não estão na lista permitida.",
    "correio.regras_alteradas": "O ficheiro de regras foi alterado fora do programa. Repõe as regras nas definições do correio.",
    "correio.voz_so_windows": "A leitura em voz alta só está disponível no Windows nesta versão.",
    "correio.segredos_so_windows": "A palavra-passe da conta só pode ser guardada no Windows nesta versão.",
    "correio.segredos_falhou": "Não foi possível proteger a palavra-passe da conta.",
    "correio.entrada_invalida": "Endereço ou domínio inválido.",
    "correio.regras_invalidas": "O ficheiro de regras não é válido.",
    "supervisor.palavra_curta": "A palavra-passe de supervisor deve ter pelo menos 6 caracteres.",
    "supervisor.palavra_incorreta": "A palavra-passe de supervisor não está correta.",
    "supervisor.nao_definido": "Crie primeiro a palavra-passe de supervisor.",
    "correio.apagar_falhou": "Não foi possível mover o email para o lixo. Tente outra vez.",
    "correio.mover_falhou": "Não foi possível mover o email. Tente outra vez.",
    "correio.sem_pasta_rascunhos": "O servidor não tem uma pasta de rascunhos.",
    "correio.sem_conta": "Esta conta já não está guardada neste computador.",
    "correio.oauth_nao_configurado": "Esta forma de entrar ainda não está ativada nesta versão. Use a conta e a palavra-passe.",
    "correio.oauth_cancelado": "A entrada não foi confirmada. Tente outra vez.",
    "correio.oauth_expirou": "Não houve resposta a tempo. Tente outra vez.",
    "correio.oauth_falhou": "O fornecedor recusou a entrada. Tente outra vez.",
    "correio.oauth_sem_renovacao": "O fornecedor não autorizou o acesso prolongado. Tente outra vez.",
    "correio.oauth_sem_email": "Não foi possível identificar o endereço desta conta.",
    "correio.oauth_sem_correio": (
        "A Google não deu permissão para o correio. Confirme que o âmbito https://mail.google.com/ está no ecrã de "
        "consentimento do projeto, revogue o acesso da Kikoia em myaccount.google.com/permissions e entre de novo, "
        "marcando a permissão do Gmail."
    ),
}


def texto_erro(erro: BaseException) -> str:
    if isinstance(erro, ErroCorreio):
        return MENSAGENS.get(str(erro), str(erro))
    return f"Erro inesperado: {erro}"


def supervisionado() -> bool:
    return supervisor.existe()


MAX_IMAGEM_BYTES = 5 * 1024 * 1024
TEMPO_LIMITE_IMAGEM_S = 5


def _buscar_imagem_remota(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=TEMPO_LIMITE_IMAGEM_S) as resposta:
            dados = resposta.read(MAX_IMAGEM_BYTES + 1)
    except (OSError, ValueError):
        return None
    return dados if len(dados) <= MAX_IMAGEM_BYTES else None


def _imagem_do_email(origem: str, mensagem: Mensagem) -> QImage | None:
    """A imagem de uma origem do HTML: embutida no email (cid:) ou de um site (http/https)."""
    if origem.startswith(CID_PREFIXO):
        nome = origem[len(CID_PREFIXO):]
        dados = next((a.dados for a in mensagem.anexos if a.cid == nome), None)
    elif origem.startswith(("http://", "https://")):
        dados = _buscar_imagem_remota(origem)
    else:
        dados = None
    if not dados:
        return None
    imagem = QImage()
    return imagem if imagem.loadFromData(dados) else None


def guardar_anexo(anexo: Anexo) -> Path:
    """Grava o anexo numa pasta do Quadro, com o nome do ficheiro (sem caminhos)."""
    raiz = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    pasta = Path(raiz) / "Kikoia" / "Quadro" / "anexos"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / (Path(anexo.nome).name or "anexo")
    destino.write_bytes(anexo.dados)
    return destino


def confirmar_executavel(pai: QWidget, nome: str) -> bool:
    """Aviso a vermelho antes de abrir um ficheiro que pode danificar o computador. Por defeito, responde «Não»."""
    caixa = QMessageBox(pai)
    caixa.setWindowTitle("Correio")
    caixa.setIcon(QMessageBox.Icon.Warning)
    caixa.setTextFormat(Qt.TextFormat.RichText)
    caixa.setText(
        "<b><span style='color:#dc2626;'>Atenção: este tipo de ficheiro pode danificar o computador.</span></b>"
        f"<br><br>Quer mesmo abrir «{html_lib.escape(nome)}»?"
    )
    nao = caixa.addButton("Não", QMessageBox.ButtonRole.RejectRole)
    sim = caixa.addButton("Sim, abrir", QMessageBox.ButtonRole.AcceptRole)
    caixa.setDefaultButton(nao)
    caixa.exec()
    return caixa.clickedButton() is sim


def substituir_ultimo_destinatario(texto: str, endereco: str) -> str:
    """Troca o último destinatário (depois da última vírgula) pelo endereço escolhido."""
    anteriores = [parte.strip() for parte in texto.split(",")][:-1]
    return ", ".join(anteriores + [endereco]) + ", "


class _CompletadorDestinatarios(QCompleter):
    """Completa o endereço que está a ser escrito, sem apagar os destinatários já introduzidos."""

    def splitPath(self, caminho: str) -> list[str]:  # noqa: N802 (nome do Qt)
        return [caminho.split(",")[-1].strip()]

    def pathFromIndex(self, indice) -> str:  # noqa: N802
        escolhido = super().pathFromIndex(indice)
        campo = self.widget()
        texto = campo.text() if campo is not None else ""
        return substituir_ultimo_destinatario(texto, escolhido)


class _Sinal(QObject):
    terminou = Signal(object)


def correr_em_fundo(pai: QObject, trabalho: Callable[[], object], ao_terminar: Callable[[tuple], None]) -> None:
    """Executa `trabalho` numa thread; `ao_terminar` recebe ("ok", valor) ou ("erro", excecao) na thread principal."""
    sinal = _Sinal(pai)
    sinal.terminou.connect(ao_terminar, Qt.ConnectionType.QueuedConnection)

    def executar() -> None:
        try:
            resultado: tuple = ("ok", trabalho())
        except Exception as erro:  # mostrado ao utilizador pela janela
            resultado = ("erro", erro)
        sinal.terminou.emit(resultado)

    threading.Thread(target=executar, daemon=True, name="quadro-correio").start()


def verificar_supervisor(pai: QWidget) -> bool:
    if not supervisor.existe():
        QMessageBox.information(pai, "Correio", MENSAGENS["supervisor.nao_definido"])
        return False
    palavra, ok = QInputDialog.getText(
        pai, "Supervisor", "Palavra-passe de supervisor:", QLineEdit.EchoMode.Password
    )
    if not ok:
        return False
    if not supervisor.verificar(palavra):
        QMessageBox.warning(pai, "Supervisor", MENSAGENS["supervisor.palavra_incorreta"])
        return False
    return True


def _palavra_passe_nova(pai: QWidget) -> str | None:
    primeira, ok = QInputDialog.getText(pai, "Supervisor", "Nova palavra-passe de supervisor:", QLineEdit.EchoMode.Password)
    if not ok:
        return None
    segunda, ok = QInputDialog.getText(pai, "Supervisor", "Repita a palavra-passe:", QLineEdit.EchoMode.Password)
    if not ok or primeira != segunda:
        QMessageBox.warning(pai, "Supervisor", "As palavras-passe não coincidem.")
        return None
    return primeira


class DialogoCorreio(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Correio")
        self.resize(980, 620)
        self._conta: tuple[Conta, str] | None = contas.carregar()
        self._regras, self._integras = R.carregar()
        self._mensagens: list[Mensagem] = []
        self._pastas: list[Pasta] = [Pasta("INBOX")]
        self._pasta_atual = "INBOX"
        self._pasta_mensagens = "INBOX"
        self._termo = ""
        self._visoes: list[R.Visao] = []
        self._desbloqueadas: set[str] = set()
        self._ocupado = False

        self._lista = QListWidget()
        self._lista.setMinimumWidth(320)
        self._lista.currentRowChanged.connect(self._mostrar_selecionada)
        self._seletor_contas = QComboBox()
        self._seletor_contas.setMinimumWidth(320)
        self._seletor_contas.currentIndexChanged.connect(self._mudar_conta)
        self._seletor_pastas = QComboBox()
        self._seletor_pastas.setMinimumWidth(320)
        self._seletor_pastas.currentIndexChanged.connect(self._mudar_pasta)
        self._cabecalho = QLabel("")
        self._cabecalho.setWordWrap(True)
        self._texto = QTextEdit()
        self._texto.setReadOnly(True)
        self._anexos = QListWidget()
        self._anexos.setMaximumHeight(120)
        self._estado = QLabel("")
        self._estado.setWordWrap(True)

        self._atualizar = QPushButton("Atualizar")
        self._atualizar.clicked.connect(lambda _=False: self.atualizar())
        self._voz = QPushButton("Ler em voz alta")
        self._voz.clicked.connect(lambda _=False: self._ler_em_voz_alta())
        self._parar_voz = QPushButton("Parar leitura")
        self._parar_voz.clicked.connect(lambda _=False: voz.parar())
        self._desbloquear = QPushButton("Desbloquear com supervisor...")
        self._desbloquear.clicked.connect(lambda _=False: self._desbloquear_mensagem())
        self._adicionar = QPushButton("Permitir este remetente...")
        self._adicionar.clicked.connect(lambda _=False: self._permitir_remetente())
        self._escrever = QPushButton("Escrever...")
        self._escrever.clicked.connect(lambda _=False: self._abrir_escrever())
        self._configurar = QPushButton("Configurar...")
        self._configurar.clicked.connect(lambda _=False: self._abrir_configurar())
        self._contactos = QPushButton("Contactos...")
        self._contactos.clicked.connect(lambda _=False: DialogoContactos(self).exec())
        self._guardar_contacto = QPushButton("Guardar remetente como contacto")
        self._guardar_contacto.clicked.connect(lambda _=False: self._guardar_remetente())
        self._botao_anexo = QPushButton("Abrir anexo")
        self._botao_anexo.clicked.connect(lambda _=False: self._abrir_anexo())
        self._apagar = QPushButton("Apagar email")
        self._apagar.clicked.connect(lambda _=False: self._apagar_mensagem())
        self._responder = QPushButton("Responder")
        self._responder.clicked.connect(lambda _=False: self._responder_a(False))
        self._responder_todos = QPushButton("Responder a todos")
        self._responder_todos.clicked.connect(lambda _=False: self._responder_a(True))
        self._encaminhar = QPushButton("Encaminhar")
        self._encaminhar.clicked.connect(lambda _=False: self._encaminhar_mensagem())
        self._editar_rascunho = QPushButton("Editar rascunho")
        self._editar_rascunho.clicked.connect(lambda _=False: self._editar_rascunho_mensagem())
        self._lido = QPushButton("Marcar como lido")
        self._lido.clicked.connect(lambda _=False: self._alternar_lida())
        self._estrela = QPushButton("Marcar com estrela")
        self._estrela.clicked.connect(lambda _=False: self._alternar_estrela())
        self._mover = QPushButton("Mover para...")
        self._mover.clicked.connect(lambda _=False: self._mover_mensagem())
        self._acoes_mensagem = (
            self._responder, self._responder_todos, self._encaminhar, self._editar_rascunho,
            self._lido, self._estrela, self._mover,
        )
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)

        botoes = QHBoxLayout()
        for botao in (self._atualizar, self._escrever, self._contactos, self._configurar):
            botoes.addWidget(botao)
        botoes.addStretch(1)
        botoes.addWidget(fechar)

        direita = QVBoxLayout()
        direita.addWidget(self._cabecalho)
        direita.addWidget(self._texto, 1)
        direita.addWidget(QLabel("Anexos"))
        direita.addWidget(self._anexos)
        acoes = QHBoxLayout()
        for botao in (self._voz, self._parar_voz, self._botao_anexo, self._apagar, self._desbloquear, self._adicionar, self._guardar_contacto):
            acoes.addWidget(botao)
        direita.addLayout(acoes)
        acoes_mensagem = QHBoxLayout()
        for botao in self._acoes_mensagem:
            acoes_mensagem.addWidget(botao)
        acoes_mensagem.addStretch(1)
        direita.addLayout(acoes_mensagem)
        direita.addWidget(self._estado)

        self._menu = interruptor("Adicionar ao Menu", contas.preferencias()["bolha"])
        self._menu.toggled.connect(self._alterar_menu)
        topo = QHBoxLayout()
        topo.addStretch(1)
        topo.addWidget(self._menu)
        raiz = QVBoxLayout(self)
        raiz.addLayout(topo)
        esquerda = QVBoxLayout()
        esquerda.addWidget(self._seletor_contas)
        esquerda.addWidget(self._seletor_pastas)
        pesquisa = QHBoxLayout()
        self._pesquisa = QLineEdit()
        self._pesquisa.setPlaceholderText("Pesquisar no correio...")
        self._pesquisa.returnPressed.connect(self._pesquisar)
        pesquisar = QPushButton("Pesquisar")
        pesquisar.clicked.connect(lambda _=False: self._pesquisar())
        limpar_pesquisa = QPushButton("Limpar")
        limpar_pesquisa.clicked.connect(lambda _=False: self._limpar_pesquisa())
        for botao in (self._pesquisa, pesquisar, limpar_pesquisa):
            pesquisa.addWidget(botao)
        self._ordem = QComboBox()
        for chave, rotulo in ordenacao.CRITERIOS:
            self._ordem.addItem(rotulo, chave)
        self._ordem.currentIndexChanged.connect(lambda _=False: self._aplicar_ordem())
        esquerda.addWidget(self._ordem)
        esquerda.addLayout(pesquisa)
        esquerda.addWidget(self._lista, 1)
        conteudo = QHBoxLayout()
        conteudo.addLayout(esquerda)
        conteudo.addLayout(direita, 1)
        raiz.addLayout(conteudo, 1)
        raiz.addLayout(botoes)

        self._preencher_contas()
        self._atualizar_estado_botoes()
        if self._conta is None:
            self._estado.setText("Ainda não há conta configurada. Carregue em «Configurar...».")
        elif supervisionado() and not self._integras:
            self._estado.setText(MENSAGENS["correio.regras_alteradas"])
        else:
            self.atualizar()

    # --- estado da janela -----------------------------------------------------------

    def done(self, resultado: int) -> None:  # noqa: N802 (nome do Qt)
        voz.parar()
        super().done(resultado)

    def _alterar_menu(self, visivel: bool) -> None:
        contas.guardar_preferencias({**contas.preferencias(), "bolha": visivel})
        janela = self.parent()
        if hasattr(janela, "aplicar_preferencias_correio"):
            janela.aplicar_preferencias_correio()

    def _atualizar_estado_botoes(self) -> None:
        tem_conta = self._conta is not None
        self._atualizar.setEnabled(tem_conta and not self._ocupado)
        self._seletor_contas.setEnabled(tem_conta and not self._ocupado)
        self._seletor_pastas.setEnabled(tem_conta and not self._ocupado)
        self._apagar.setEnabled(tem_conta and not self._ocupado and self._lista.currentRow() >= 0)
        self._escrever.setEnabled(tem_conta)
        self._mostrar_selecionada(self._lista.currentRow())

    def _recalcular_visoes(self) -> None:
        sup = supervisionado()
        prefs = contas.preferencias()
        self._visoes = [
            R.ver(
                self._regras,
                m,
                m.uid in self._desbloqueadas,
                supervisionado=sup,
                html_ativo=prefs["html"],
                imagens=prefs["imagens"],
                anexos_ativos=prefs["anexos"],
            )
            for m in self._mensagens
        ]

    def _preencher(self) -> None:
        self._lista.blockSignals(True)
        self._lista.clear()
        for indice, visao in enumerate(self._visoes):
            prefixo = "🔒 " if not visao.aberta else ""
            mensagem = self._mensagens[indice] if indice < len(self._mensagens) else None
            if mensagem is not None and not mensagem.lida:
                prefixo = "● " + prefixo
            if mensagem is not None and mensagem.marcada:
                prefixo = "★ " + prefixo
            self._lista.addItem(f"{prefixo}{visao.remetente}\n{visao.assunto}")
        self._lista.blockSignals(False)
        if self._visoes:
            self._lista.setCurrentRow(0)
        self._mostrar_selecionada(self._lista.currentRow())

    # --- caixa de entrada -----------------------------------------------------------

    def atualizar(self) -> None:
        if self._conta is None or self._ocupado:
            return
        conta, senha = self._conta
        self._ocupado = True
        self._estado.setText("A ligar ao servidor…")
        self._atualizar_estado_botoes()
        pasta = self._pasta_atual
        termo = self._termo or None

        def trabalhar() -> tuple[list[Pasta], list[Mensagem], str]:
            with cliente_de(conta, senha) as correio:
                pastas = correio.listar_pastas()
                return pastas, correio.listar(limite=30, pasta=pasta, termo=termo), pasta

        correr_em_fundo(self, trabalhar, self._recebidas)

    def _recebidas(self, resultado: tuple) -> None:
        self._ocupado = False
        estado, valor = resultado
        if estado == "erro":
            self._estado.setText(texto_erro(valor))
        else:
            pastas, mensagens, pasta = valor
            self._pastas = pastas
            self._pasta_mensagens = pasta
            self._preencher_pastas()
            self._mensagens = ordenacao.ordenar(mensagens, self._ordem.currentData() or "recentes")
            self._recalcular_visoes()
            self._preencher()
            self._estado.setText(f"{len(self._visoes)} mensagens.")
        self._atualizar_estado_botoes()

    def _preencher_contas(self) -> None:
        """Lista as contas guardadas. A conta ativa mantém-se se ainda existir; senão, usa-se a primeira."""
        enderecos = contas.listar_enderecos()
        atual = self._conta[0].endereco if self._conta else None
        self._seletor_contas.blockSignals(True)
        self._seletor_contas.clear()
        for endereco in enderecos:
            self._seletor_contas.addItem(endereco, endereco)
        indice = enderecos.index(atual) if atual in enderecos else 0
        self._seletor_contas.setCurrentIndex(indice if enderecos else -1)
        self._seletor_contas.blockSignals(False)
        if enderecos and atual not in enderecos:
            self._conta = contas.carregar(endereco=enderecos[0])
        elif not enderecos:
            self._conta = None

    def _mudar_conta(self, indice: int) -> None:
        endereco = self._seletor_contas.itemData(indice)
        if not endereco or self._ocupado or (self._conta and self._conta[0].endereco == endereco):
            return
        self._conta = contas.carregar(endereco=endereco)
        self._pasta_atual = "INBOX"
        self._pastas = [Pasta("INBOX")]
        self._pasta_mensagens = "INBOX"
        self._preencher_pastas()
        self._mensagens = []
        self._recalcular_visoes()
        self._preencher()
        self._estado.setText("")
        self._atualizar_estado_botoes()
        self.atualizar()

    def _nome_pasta(self, pasta: Pasta) -> str:
        if pasta.nome.upper() == "INBOX":
            base = "Caixa de entrada"
        else:
            nome = pasta.nome[len("INBOX."):] if pasta.nome.upper().startswith("INBOX.") else pasta.nome
            base = {"lixo": f"Lixo ({nome})", "spam": f"Spam ({nome})"}.get(pasta.especial or "", nome)
        return f"{base} ({pasta.nao_lidas})" if pasta.nao_lidas else base

    def _preencher_pastas(self) -> None:
        self._seletor_pastas.blockSignals(True)
        self._seletor_pastas.clear()
        for pasta in self._pastas:
            self._seletor_pastas.addItem(self._nome_pasta(pasta), pasta.nome)
        indice = next((i for i, p in enumerate(self._pastas) if p.nome == self._pasta_atual), 0)
        self._seletor_pastas.setCurrentIndex(indice)
        self._seletor_pastas.blockSignals(False)

    def _mudar_pasta(self, indice: int) -> None:
        nome = self._seletor_pastas.itemData(indice)
        if not nome or nome == self._pasta_atual or self._ocupado:
            return
        self._pasta_atual = nome
        self.atualizar()

    def _nome_lixo(self) -> str | None:
        return next((p.nome for p in self._pastas if p.especial == "lixo"), None)

    def _apagar_mensagem(self) -> None:
        linha = self._lista.currentRow()
        if not (0 <= linha < len(self._mensagens)) or self._conta is None or self._ocupado:
            return
        mensagem = self._mensagens[linha]
        pasta = self._pasta_mensagens
        lixo = self._nome_lixo()
        definitivo = lixo is None or lixo == pasta
        pergunta = (
            "Apagar definitivamente este email? Não pode ser recuperado."
            if definitivo
            else "Mover este email para o lixo?"
        )
        if QMessageBox.question(self, "Apagar email", f"{pergunta}\n\n{mensagem.assunto}") != QMessageBox.StandardButton.Yes:
            return
        conta, senha = self._conta
        self._ocupado = True
        self._estado.setText("A apagar…")
        self._atualizar_estado_botoes()

        def trabalhar() -> None:
            with cliente_de(conta, senha) as correio:
                correio.apagar(mensagem.uid, pasta, lixo)

        correr_em_fundo(self, trabalhar, self._apagada)

    def _apagada(self, resultado: tuple) -> None:
        self._ocupado = False
        estado, valor = resultado
        if estado == "erro":
            self._estado.setText(texto_erro(valor))
            self._atualizar_estado_botoes()
            return
        self._estado.setText("Email apagado.")
        self.atualizar()

    def _visao_atual(self) -> R.Visao | None:
        linha = self._lista.currentRow()
        return self._visoes[linha] if 0 <= linha < len(self._visoes) else None

    def _mostrar_selecionada(self, linha: int) -> None:
        visao = self._visao_atual()
        sup = supervisionado()
        self._voz.setEnabled(visao is not None and visao.aberta)
        atual = self._mensagem_atual()
        for botao in self._acoes_mensagem:
            botao.setEnabled(atual is not None)
        self._lido.setText("Marcar como não lido" if atual is not None and atual.lida else "Marcar como lido")
        self._estrela.setText("Retirar estrela" if atual is not None and atual.marcada else "Marcar com estrela")
        self._guardar_contacto.setEnabled(visao is not None)
        self._desbloquear.setVisible(sup)
        self._adicionar.setVisible(sup)
        self._desbloquear.setEnabled(visao is not None and not visao.aberta and self._integras)
        self._adicionar.setEnabled(visao is not None and visao.aberta and not visao.remetente_permitido and self._integras)
        if visao is None:
            self._cabecalho.setText("")
            self._texto.clear()
            self._anexos.clear()
            return
        self._cabecalho.setTextFormat(Qt.TextFormat.RichText)
        linha = self._lista.currentRow()
        mensagem = self._mensagens[linha] if 0 <= linha < len(self._mensagens) else None
        linhas = [f"<b>{html_lib.escape(visao.assunto)}</b>", f"De: {html_lib.escape(visao.remetente)}"]
        if mensagem is not None:
            if mensagem.destinatarios:
                linhas.append("Para: " + html_lib.escape(", ".join(mensagem.destinatarios)))
            if mensagem.cc:
                linhas.append("Cc: " + html_lib.escape(", ".join(mensagem.cc)))
            if mensagem.cco:
                linhas.append("Cco (cópia oculta): " + html_lib.escape(", ".join(mensagem.cco)))
        linhas.append(html_lib.escape(visao.data))
        self._cabecalho.setText("<br>".join(linhas))
        if visao.html is not None:
            # Os emails costumam ter fundo branco e cor de texto por omissão: a área fica clara,
            # para o texto que não tem cor definida ser sempre legível.
            self._texto.setStyleSheet("QTextEdit { background: #ffffff; color: #000000; }")
            self._registar_imagens(visao.html)
            self._texto.setHtml(visao.html)
        else:
            self._texto.setStyleSheet("")
            self._texto.setPlainText(visao.texto if visao.texto is not None else "Mensagem bloqueada.")
        self._anexos.clear()
        for anexo in visao.anexos:
            partes = []
            if anexo.nome.lower().endswith(".kquadro"):
                partes.append("desenho do Quadro")
            if not anexo.permitido:
                partes.append("bloqueado pelo supervisor")
            if anexo.executavel:
                partes.append("executável")
            estado = f" ({', '.join(partes)})" if partes else ""
            self._anexos.addItem(f"{anexo.nome} ({anexo.tamanho // 1024} KB){estado}")

    def _mensagem_atual(self) -> Mensagem | None:
        linha = self._lista.currentRow()
        return self._mensagens[linha] if 0 <= linha < len(self._mensagens) else None

    def _escrever_com(self, inicial: Rascunho | None) -> None:
        if self._conta is None:
            return
        conta, senha = self._conta
        fornecer = getattr(self.parent(), "preparar_anexos_quadro", None)
        DialogoEscrever(
            conta, senha, self._regras, self, inicial,
            enderecos=contas.listar_enderecos(), fornecer_quadro=fornecer,
        ).exec()

    def _responder_a(self, todos: bool) -> None:
        mensagem = self._mensagem_atual()
        if mensagem is not None and self._conta is not None:
            self._escrever_com(composicao.responder(mensagem, self._conta[0].endereco, todos))

    def _encaminhar_mensagem(self) -> None:
        mensagem = self._mensagem_atual()
        if mensagem is not None:
            self._escrever_com(composicao.encaminhar(mensagem))

    def _editar_rascunho_mensagem(self) -> None:
        mensagem = self._mensagem_atual()
        if mensagem is not None:
            self._escrever_com(composicao.editar(mensagem))

    def _operar(self, trabalhar: Callable[[object], object], rotulo: str) -> None:
        """Uma operação no servidor (marcar, mover), fora da janela, e depois a lista atualizada."""
        if self._conta is None or self._ocupado:
            return
        conta, senha = self._conta
        self._ocupado = True
        self._estado.setText(rotulo)
        self._atualizar_estado_botoes()

        def correr() -> object:
            with cliente_de(conta, senha) as correio:
                return trabalhar(correio)

        correr_em_fundo(self, correr, self._operacao_pronta)

    def _operacao_pronta(self, resultado: tuple) -> None:
        self._ocupado = False
        estado, valor = resultado
        if estado == "erro":
            self._estado.setText(texto_erro(valor))
            self._atualizar_estado_botoes()
            return
        self.atualizar()

    def _alternar_lida(self) -> None:
        mensagem = self._mensagem_atual()
        if mensagem is None:
            return
        pasta, uid, nova = self._pasta_mensagens, mensagem.uid, not mensagem.lida
        self._operar(lambda c: c.marcar(uid, pasta, lida=nova), "A atualizar…")

    def _alternar_estrela(self) -> None:
        mensagem = self._mensagem_atual()
        if mensagem is None:
            return
        pasta, uid, nova = self._pasta_mensagens, mensagem.uid, not mensagem.marcada
        self._operar(lambda c: c.marcar(uid, pasta, marcada=nova), "A atualizar…")

    def _mover_mensagem(self) -> None:
        mensagem = self._mensagem_atual()
        if mensagem is None:
            return
        origem = self._pasta_mensagens
        destinos = [p for p in self._pastas if p.nome != origem]
        if not destinos:
            return
        nomes = [self._nome_pasta(p) for p in destinos]
        escolha, ok = QInputDialog.getItem(self, "Mover", "Mover para a pasta:", nomes, 0, False)
        if not ok:
            return
        destino = destinos[nomes.index(escolha)].nome
        uid = mensagem.uid
        self._operar(lambda c: c.mover(uid, origem, destino), "A mover…")

    def _aplicar_ordem(self) -> None:
        criterio = self._ordem.currentData()
        if not criterio or not self._mensagens:
            return
        self._mensagens = ordenacao.ordenar(self._mensagens, criterio)
        self._recalcular_visoes()
        self._preencher()

    def _pesquisar(self) -> None:
        self._termo = self._pesquisa.text().strip()
        self.atualizar()

    def _limpar_pesquisa(self) -> None:
        self._pesquisa.clear()
        self._termo = ""
        self.atualizar()

    def _registar_imagens(self, html: str) -> None:
        """Dá ao visualizador as imagens que o HTML referencia (embutidas no email ou de sites)."""
        linha = self._lista.currentRow()
        if not (0 <= linha < len(self._mensagens)):
            return
        mensagem = self._mensagens[linha]
        documento = self._texto.document()
        for origem_escapada in set(re.findall(r'src="([^"]+)"', html)):
            origem = html_lib.unescape(origem_escapada)
            imagem = _imagem_do_email(origem, mensagem)
            if imagem is not None:
                documento.addResource(int(QTextDocument.ResourceType.ImageResource), QUrl(origem), imagem)

    def _abrir_anexo(self) -> None:
        linha_mensagem = self._lista.currentRow()
        linha = self._anexos.currentRow()
        if not (0 <= linha_mensagem < len(self._mensagens)) or not (0 <= linha < len(self._mensagens[linha_mensagem].anexos)):
            self._estado.setText("Escolha primeiro um anexo na lista.")
            return
        visto = self._visoes[linha_mensagem].anexos[linha]
        anexo = self._mensagens[linha_mensagem].anexos[linha]
        if not visto.permitido:
            self._estado.setText("Este anexo está bloqueado pelo supervisor.")
            return
        if anexo.nome.lower().endswith(".kquadro"):
            abrir = getattr(self.parent(), "abrir_quadro_recebido", None)
            self._estado.setText(
                abrir(anexo.nome, anexo.dados) if abrir else "Os desenhos do Quadro só se abrem a partir do Quadro."
            )
            return
        if visto.executavel and not confirmar_executavel(self, anexo.nome):
            return
        try:
            caminho = guardar_anexo(anexo)
        except OSError:
            self._estado.setText("Não foi possível guardar o anexo.")
            return
        if not hasattr(os, "startfile"):
            self._estado.setText("Abrir anexos só está disponível no Windows nesta versão.")
            return
        try:
            os.startfile(caminho)
        except OSError:
            self._estado.setText("Não foi possível abrir o anexo.")

    def _desbloquear_mensagem(self) -> None:
        visao = self._visao_atual()
        if visao is None or not verificar_supervisor(self):
            return
        self._desbloqueadas.add(visao.uid)
        self._recarregar_lista()

    def _permitir_remetente(self) -> None:
        visao = self._visao_atual()
        if visao is None or not verificar_supervisor(self):
            return
        try:
            self._regras = R.alterar("remetentes", visao.remetente)
        except ErroCorreio as erro:
            self._estado.setText(texto_erro(erro))
            return
        self._estado.setText(f"{visao.remetente} passou a ser remetente permitido.")
        self._recarregar_lista()

    def _recarregar_lista(self) -> None:
        linha = self._lista.currentRow()
        self._recalcular_visoes()
        self._preencher()
        if 0 <= linha < len(self._visoes):
            self._lista.setCurrentRow(linha)

    def _guardar_remetente(self) -> None:
        visao = self._visao_atual()
        if visao is None:
            return
        try:
            contactos.acrescentar(visao.remetente, visao.remetente)
        except ErroCorreio as erro:
            self._estado.setText(texto_erro(erro))
            return
        self._estado.setText(f"{visao.remetente} guardado nos contactos.")

    def _ler_em_voz_alta(self) -> None:
        visao = self._visao_atual()
        if visao is None or visao.texto is None:
            return
        try:
            voz.falar(f"Mensagem de {visao.remetente}. Assunto: {visao.assunto}. {visao.texto}")
        except ErroCorreio as erro:
            self._estado.setText(texto_erro(erro))

    def _abrir_escrever(self) -> None:
        if self._conta is None:
            return
        self._escrever_com(None)

    def _abrir_configurar(self) -> None:
        DialogoConfigurar(self).exec()
        self._preencher_contas()
        self._regras, self._integras = R.carregar()
        self._atualizar_estado_botoes()
        if self._conta is not None and (not supervisionado() or self._integras):
            self.atualizar()


class DialogoContactos(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Contactos")
        self.resize(520, 420)
        self._lista = QListWidget()
        self._nome = QLineEdit()
        self._nome.setPlaceholderText("Nome")
        self._endereco = QLineEdit()
        self._endereco.setPlaceholderText("endereco@exemplo.pt")
        self._recarregar()
        acrescentar = QPushButton("Acrescentar")
        acrescentar.clicked.connect(lambda _=False: self._acrescentar())
        remover = QPushButton("Remover selecionado")
        remover.clicked.connect(lambda _=False: self._remover())
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        formulario = QFormLayout()
        formulario.addRow("Nome:", self._nome)
        formulario.addRow("Endereço:", self._endereco)
        raiz = QVBoxLayout(self)
        raiz.addWidget(self._lista, 1)
        raiz.addLayout(formulario)
        botoes = QHBoxLayout()
        botoes.addWidget(acrescentar)
        botoes.addWidget(remover)
        botoes.addStretch(1)
        botoes.addWidget(fechar)
        raiz.addLayout(botoes)

    def _recarregar(self) -> None:
        self._lista.clear()
        for contacto in contactos.carregar():
            self._lista.addItem(f"{contacto['nome']} <{contacto['endereco']}>")

    def _acrescentar(self) -> None:
        try:
            contactos.acrescentar(self._nome.text(), self._endereco.text())
        except ErroCorreio as erro:
            QMessageBox.warning(self, "Contactos", texto_erro(erro))
            return
        self._nome.clear()
        self._endereco.clear()
        self._recarregar()

    def _remover(self) -> None:
        linha = self._lista.currentRow()
        contacto = contactos.carregar()
        if 0 <= linha < len(contacto):
            contactos.remover(contacto[linha]["endereco"])
            self._recarregar()


class DialogoEscrever(QDialog):
    def __init__(
        self,
        conta: Conta,
        senha: str,
        regras: R.Regras,
        parent: QWidget | None = None,
        inicial: Rascunho | None = None,
        enderecos: list[str] | None = None,
        fornecer_quadro: Callable[[], list] | None = None,
    ) -> None:
        super().__init__(parent)
        self._fornecer_quadro = fornecer_quadro
        self.setWindowTitle("Escrever mensagem")
        self.resize(640, 480)
        self._conta = conta
        self._senha = senha
        self._regras = regras
        self._de = QComboBox()
        for endereco in enderecos or [conta.endereco]:
            self._de.addItem(endereco, endereco)
        self._de.setCurrentIndex(max(0, self._de.findData(conta.endereco)))
        self._para = self._campo_destinatarios("destinatario@exemplo.pt, outro@exemplo.pt")
        self._cc = self._campo_destinatarios("")
        self._cco = self._campo_destinatarios("")
        self._anexos: list[Anexo] = []
        self._imagens: dict[str, tuple[str, bytes, str]] = {}
        self._assunto = QLineEdit()
        self._texto = QTextEdit()
        self._texto.currentCharFormatChanged.connect(self._sincronizar_formatacao)
        self._negrito = QPushButton("N")
        self._negrito.setCheckable(True)
        self._negrito.setStyleSheet("QPushButton { font-weight: bold; }")
        self._negrito.toggled.connect(lambda v: self._texto.setFontWeight(700 if v else 400))
        self._italico = QPushButton("I")
        self._italico.setCheckable(True)
        self._italico.setStyleSheet("QPushButton { font-style: italic; }")
        self._italico.toggled.connect(self._texto.setFontItalic)
        self._sublinhado = QPushButton("S")
        self._sublinhado.setCheckable(True)
        self._sublinhado.setStyleSheet("QPushButton { text-decoration: underline; }")
        self._sublinhado.toggled.connect(self._texto.setFontUnderline)
        lista = QPushButton("• Lista")
        lista.clicked.connect(lambda _=False: self._texto.textCursor().createList(QTextListFormat.Style.ListDisc))
        imagem = QPushButton("Imagem...")
        imagem.clicked.connect(lambda _=False: self._inserir_imagem())
        anexar = QPushButton("Anexar...")
        anexar.clicked.connect(lambda _=False: self._anexar())
        desenho = QPushButton("Anexar desenho do Quadro")
        desenho.setEnabled(fornecer_quadro is not None)
        desenho.clicked.connect(lambda _=False: self._anexar_desenho())
        ferramentas = QHBoxLayout()
        for botao in (self._negrito, self._italico, self._sublinhado, lista, imagem, anexar, desenho):
            ferramentas.addWidget(botao)
        ferramentas.addStretch(1)
        self._lista_anexos = QListWidget()
        self._lista_anexos.setMaximumHeight(90)
        remover_anexo = QPushButton("Remover anexo")
        remover_anexo.clicked.connect(lambda _=False: self._remover_anexo())
        self._estado = QLabel("")
        self._estado.setWordWrap(True)
        enviar_botao = QPushButton("Enviar")
        enviar_botao.clicked.connect(lambda _=False: self._enviar())
        rascunho_botao = QPushButton("Guardar rascunho")
        rascunho_botao.clicked.connect(lambda _=False: self._guardar_rascunho())
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        formulario = QFormLayout()
        formulario.addRow("De:", self._de)
        formulario.addRow("Para:", self._para)
        formulario.addRow("Cc:", self._cc)
        formulario.addRow("Cco:", self._cco)
        formulario.addRow("Assunto:", self._assunto)
        raiz = QVBoxLayout(self)
        raiz.addLayout(formulario)
        raiz.addLayout(ferramentas)
        raiz.addWidget(self._texto, 1)
        anexos = QHBoxLayout()
        anexos.addWidget(self._lista_anexos, 1)
        anexos.addWidget(remover_anexo)
        raiz.addLayout(anexos)
        raiz.addWidget(self._estado)
        botoes = QHBoxLayout()
        botoes.addStretch(1)
        botoes.addWidget(cancelar)
        botoes.addWidget(rascunho_botao)
        botoes.addWidget(enviar_botao)
        raiz.addLayout(botoes)
        self._preencher(inicial)

    def _preencher(self, inicial: Rascunho | None) -> None:
        """Dados de uma resposta, de um encaminhamento ou de um rascunho. Um email novo leva a assinatura."""
        if inicial is None:
            assinatura = contas.preferencias()["assinatura"].strip()
            if assinatura:
                self._texto.setPlainText(f"\n\n-- \n{assinatura}")
                self._texto.moveCursor(QTextCursor.MoveOperation.Start)
            return
        self._para.setText(", ".join(inicial.para))
        self._cc.setText(", ".join(inicial.cc))
        self._assunto.setText(inicial.assunto)
        self._texto.setPlainText(inicial.texto)
        self._anexos = list(inicial.anexos)
        for anexo in self._anexos:
            self._lista_anexos.addItem(f"{anexo.nome} ({anexo.tamanho // 1024} KB)")

    def _sincronizar_formatacao(self, formato) -> None:
        """Os botões mostram o estado do texto onde está o cursor."""
        for botao, ativo in (
            (self._negrito, formato.fontWeight() > 500),
            (self._italico, formato.fontItalic()),
            (self._sublinhado, formato.fontUnderline()),
        ):
            botao.blockSignals(True)
            botao.setChecked(ativo)
            botao.blockSignals(False)

    def _campo_destinatarios(self, dica: str) -> QLineEdit:
        campo = QLineEdit()
        campo.setPlaceholderText(dica)
        completador = _CompletadorDestinatarios(self)
        completador.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completador.setModel(QStringListModel(contactos.enderecos(), completador))
        campo.setCompleter(completador)
        return campo

    def _destinatarios(self) -> list[str]:
        return self._lista_enderecos(self._para)

    @staticmethod
    def _lista_enderecos(campo: QLineEdit) -> list[str]:
        return [d.strip() for d in campo.text().replace(";", ",").split(",") if d.strip()]

    def _adicionar_anexo(self, anexo: Anexo) -> None:
        self._anexos.append(anexo)
        self._lista_anexos.addItem(f"{anexo.nome} ({anexo.tamanho // 1024} KB)")

    def _anexar_desenho(self) -> None:
        if self._fornecer_quadro is None:
            return
        try:
            for anexo in self._fornecer_quadro():
                self._adicionar_anexo(anexo)
        except OSError:
            self._estado.setText("Não foi possível preparar o desenho.")

    def _anexar(self) -> None:
        caminhos, _ = QFileDialog.getOpenFileNames(self, "Anexar ficheiros")
        for caminho in caminhos:
            try:
                dados = Path(caminho).read_bytes()
            except OSError:
                self._estado.setText(f"Não foi possível ler {Path(caminho).name}.")
                continue
            tipo = mimetypes.guess_type(caminho)[0] or "application/octet-stream"
            self._adicionar_anexo(Anexo(Path(caminho).name, tipo, len(dados), dados))

    def _remover_anexo(self) -> None:
        linha = self._lista_anexos.currentRow()
        if 0 <= linha < len(self._anexos):
            del self._anexos[linha]
            self._lista_anexos.takeItem(linha)

    def _inserir_imagem(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Inserir imagem", "", "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.jxl)"
        )
        if not caminho:
            return
        imagem = jxl.abrir_imagem(Path(caminho))
        if imagem.isNull():
            self._estado.setText("Não foi possível abrir esta imagem.")
            return
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        imagem.save(buffer, "PNG")
        dados = bytes(buffer.data())
        numero = len(self._imagens) + 1
        nome = f"cid:kikoia-img{numero}"
        self._imagens[nome] = (nome[4:], dados, "image/png")
        self._texto.document().addResource(int(QTextDocument.ResourceType.ImageResource), QUrl(nome), imagem)
        formato = QTextImageFormat()
        formato.setName(nome)
        if imagem.width() > 480:
            formato.setWidth(480)
        self._texto.textCursor().insertImage(formato)

    def _conteudo(self) -> tuple:
        """Destinatários, texto, HTML, anexos e imagens da mensagem, como vão ser enviados ou guardados."""
        para = self._lista_enderecos(self._para)
        cc = self._lista_enderecos(self._cc)
        cco = self._lista_enderecos(self._cco)
        assunto, texto = self._assunto.text(), self._texto.toPlainText()
        html = sanitizar_html(self._texto.toHtml(), None, imagens=True, anexos_cid=frozenset(c for c, _, _ in self._imagens.values()))
        for cid, _, _ in self._imagens.values():
            html = html.replace(f'src="{CID_PREFIXO}{cid}"', f'src="cid:{cid}"')
        imagens = tuple(Anexo(cid, tipo, len(dados), dados, cid) for cid, dados, tipo in self._imagens.values())
        return para, cc, cco, assunto, texto, html, tuple(self._anexos), imagens

    def _credenciais(self) -> tuple[Conta, str]:
        """Conta e palavra-passe do endereço escolhido em «De:». Chamar fora da janela principal (pode renovar o token)."""
        endereco = self._de.currentText()
        if endereco == self._conta.endereco:
            return self._conta, self._senha
        carregada = contas.carregar(endereco=endereco)
        if carregada is None:
            raise ErroCorreio("correio.sem_conta")
        return carregada

    def _guardar_rascunho(self) -> None:
        para, cc, cco, assunto, texto, html, anexos, imagens = self._conteudo()
        self._estado.setText("A guardar rascunho…")

        def trabalhar() -> None:
            conta, senha = self._credenciais()
            mensagem = montar_mensagem(
                conta.endereco, para, assunto, texto, html=html, cc=cc, cco=cco,
                anexos=anexos, imagens=imagens, com_bcc=True,
            )
            with cliente_de(conta, senha) as correio:
                correio.guardar_em_pasta("rascunhos", mensagem.as_bytes(), "(\\Draft \\Seen)")

        correr_em_fundo(
            self,
            trabalhar,
            lambda resultado: self._estado.setText(
                "Rascunho guardado." if resultado[0] == "ok" else texto_erro(resultado[1])
            ),
        )

    def _enviar(self, desbloqueado: bool = False) -> None:
        para, cc, cco, assunto, texto, html, anexos, imagens = self._conteudo()
        todos = para + cc + cco
        if not todos:
            self._estado.setText(MENSAGENS["correio.sem_destinatarios"])
            return
        self._estado.setText("A enviar…")
        sup = supervisionado()

        def trabalhar() -> str:
            conta, senha = self._credenciais()
            copia = R.enviar(
                conta,
                senha,
                self._regras,
                para,
                assunto,
                texto,
                desbloqueado,
                supervisionado=sup,
                html=html,
                cc=cc,
                cco=cco,
                anexos=anexos,
                imagens=imagens,
            )
            try:
                guardar_em_enviados(conta, senha, copia)
            except ErroCorreio:
                return "sem_copia"
            return "guardada"

        correr_em_fundo(self, trabalhar, lambda resultado: self._enviado(resultado, todos, desbloqueado))

    def _enviado(self, resultado: tuple, destinatarios: list[str], desbloqueado: bool) -> None:
        estado, valor = resultado
        if estado == "ok":
            aviso = "" if valor == "guardada" else " Não foi possível guardar uma cópia em Enviados."
            QMessageBox.information(self, "Correio", "Mensagem enviada." + aviso)
            self.accept()
            return
        if isinstance(valor, ErroCorreio) and str(valor) == "correio.destinatarios_bloqueados" and not desbloqueado:
            bloqueados = R.destinatarios_bloqueados(self._regras, destinatarios)
            self._estado.setText(f"Fora da lista permitida: {', '.join(bloqueados)}")
            if verificar_supervisor(self):
                resposta = QMessageBox.question(
                    self,
                    "Correio",
                    "Enviar mesmo assim e acrescentar estes endereços à lista permitida?",
                )
                if resposta == QMessageBox.StandardButton.Yes:
                    for endereco in bloqueados:
                        self._regras = R.alterar("destinatarios", endereco)
                    self._enviar(desbloqueado=True)
            return
        self._estado.setText(texto_erro(valor))


class DialogoConfigurar(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurar correio")
        self.resize(720, 680)
        conta_atual = contas.carregar()
        self._endereco = QLineEdit(conta_atual[0].endereco if conta_atual else "")
        self._senha = QLineEdit()
        self._senha.setEchoMode(QLineEdit.EchoMode.Password)
        self._servidor = QLineEdit(conta_atual[0].imap.servidor if conta_atual else "")
        self._servidor.setPlaceholderText("mail.exemplo.pt (deixe vazio para o padrão do domínio)")
        self._seletor = QComboBox()
        self._seletor.currentIndexChanged.connect(self._escolher_conta)
        self._atualizar_seletor(conta_atual[0].endereco if conta_atual else None)
        self._listas: dict[str, QListWidget] = {}
        self._estado_supervisao = QLabel("")
        self._estado_supervisao.setWordWrap(True)
        self._botao_supervisao = QPushButton("")
        self._botao_supervisao.clicked.connect(lambda _=False: self._alternar_supervisao())

        raiz = QVBoxLayout(self)
        raiz.addWidget(QLabel("Conta"))
        raiz.addWidget(self._seletor)
        self._protocolo = QComboBox()
        self._protocolo.addItem("IMAP (recomendado)", "imap")
        self._protocolo.addItem("POP3", "pop3")
        self._protocolo.setCurrentIndex(1 if conta_atual and conta_atual[0].protocolo == "pop3" else 0)
        formulario = QFormLayout()
        formulario.addRow("Endereço:", self._endereco)
        formulario.addRow("Palavra-passe da conta:", self._senha)
        formulario.addRow("Servidor:", self._servidor)
        formulario.addRow("Protocolo:", self._protocolo)
        raiz.addLayout(formulario)
        guardar = QPushButton("Guardar conta")
        guardar.clicked.connect(lambda _=False: self._guardar_conta())
        raiz.addWidget(guardar)
        entrar = QHBoxLayout()
        for provedor in oauth.PROVEDORES:
            botao = QPushButton(f"Entrar com conta {oauth.PROVEDORES[provedor]['nome']}...")
            botao.clicked.connect(lambda _=False, p=provedor: self._entrar(p))
            entrar.addWidget(botao)
        raiz.addLayout(entrar)

        prefs = contas.preferencias()
        self._opcoes: dict[str, QPushButton] = {}
        for chave, texto in (
            ("html", "Mostrar a formatação (HTML)"),
            ("imagens", "Mostrar imagens"),
            ("anexos", "Permitir abrir anexos"),
        ):
            botao = interruptor(texto, prefs[chave])
            botao.toggled.connect(lambda valor, c=chave, b=botao: self._alterar_opcao(c, b, valor))
            self._opcoes[chave] = botao
            raiz.addWidget(botao)
        self._avisar = QCheckBox("Avisar quando há emails por ler")
        self._avisar.setChecked(prefs["avisar"])
        self._avisar.toggled.connect(self._alterar_preferencias)
        raiz.addWidget(self._avisar)
        raiz.addWidget(QLabel("Assinatura (acrescentada aos emails novos)"))
        self._assinatura = QPlainTextEdit(prefs["assinatura"])
        self._assinatura.setMaximumHeight(90)
        raiz.addWidget(self._assinatura)
        guardar_assinatura = QPushButton("Guardar assinatura")
        guardar_assinatura.clicked.connect(lambda _=False: self._guardar_assinatura())
        raiz.addWidget(guardar_assinatura)

        raiz.addWidget(QLabel("Supervisão"))
        raiz.addWidget(self._estado_supervisao)
        raiz.addWidget(self._botao_supervisao)

        self._secao_regras = QWidget()
        secao = QVBoxLayout(self._secao_regras)
        secao.setContentsMargins(0, 0, 0, 0)
        self._repor = QPushButton("Repor regras (apaga as listas, pede o supervisor)")
        self._repor.clicked.connect(lambda _=False: self._repor_regras())
        secao.addWidget(self._repor)
        for nome, titulo in (
            ("remetentes", "Remetentes permitidos (abrem sem palavra-passe)"),
            ("destinatarios", "Destinatários permitidos (envio sem palavra-passe)"),
            ("ligacoes", "Domínios de ligações permitidos"),
        ):
            secao.addWidget(QLabel(titulo))
            lista = QListWidget()
            self._listas[nome] = lista
            linha = QHBoxLayout()
            linha.addWidget(lista, 1)
            acrescentar = QPushButton("Acrescentar...")
            acrescentar.clicked.connect(lambda _=False, n=nome: self._acrescentar(n))
            remover = QPushButton("Remover")
            remover.clicked.connect(lambda _=False, n=nome: self._remover(n))
            coluna = QVBoxLayout()
            coluna.addWidget(acrescentar)
            coluna.addWidget(remover)
            coluna.addStretch(1)
            linha.addLayout(coluna)
            secao.addLayout(linha)
        raiz.addWidget(self._secao_regras)

        acoes = QHBoxLayout()
        for texto, acao in (
            ("Criar ou alterar palavra-passe de supervisor", self._alterar_palavra_passe),
            ("Apagar conta guardada", self._apagar_conta),
        ):
            botao = QPushButton(texto)
            botao.clicked.connect(lambda _=False, a=acao: a())
            acoes.addWidget(botao)
        raiz.addLayout(acoes)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        raiz.addWidget(fechar)

        self._atualizar_supervisao()

    def _guardar_assinatura(self) -> None:
        contas.guardar_preferencias({**contas.preferencias(), "assinatura": self._assinatura.toPlainText()})
        QMessageBox.information(self, "Correio", "Assinatura guardada.")

    def _alterar_preferencias(self, *_) -> None:
        contas.guardar_preferencias({**contas.preferencias(), "avisar": self._avisar.isChecked()})

    def _alterar_opcao(self, chave: str, botao: QPushButton, valor: bool) -> None:
        """Com supervisor definido, cada opção só muda com a palavra-passe de supervisor."""
        if self._supervisao_ativa() and not verificar_supervisor(self):
            self._sincronizar_opcoes()
            return
        contas.guardar_preferencias({**contas.preferencias(), chave: valor})
        self._sincronizar_opcoes()

    def _sincronizar_opcoes(self) -> None:
        prefs = contas.preferencias()
        for chave, botao in self._opcoes.items():
            botao.blockSignals(True)
            botao.setChecked(prefs[chave])
            botao.blockSignals(False)

    def _supervisao_ativa(self) -> bool:
        return supervisionado()

    def _atualizar_supervisao(self) -> None:
        ativa = self._supervisao_ativa()
        self._secao_regras.setVisible(ativa)
        if ativa:
            self._estado_supervisao.setText(
                "Supervisão ativa: as regras abaixo controlam que emails abrem e para quem se envia. "
                "A formatação, as imagens e os anexos ficam bloqueados até o supervisor os libertar."
            )
            self._botao_supervisao.setText("Desativar supervisão (pede o supervisor)")
            regras, integras = R.carregar()
            if not integras:
                self._estado_supervisao.setText(MENSAGENS["correio.regras_alteradas"] + " Enquanto isso, tudo está bloqueado.")
            for nome, lista in self._listas.items():
                lista.clear()
                lista.addItems(getattr(regras, nome))
        else:
            self._estado_supervisao.setText(
                "Supervisão desativada (predefinição): o correio abre tudo e envia para qualquer endereço. "
                "Ative a supervisão se quiser controlar o correio de uma criança."
            )
            self._botao_supervisao.setText("Ativar supervisão...")
        self._sincronizar_opcoes()

    def _alternar_supervisao(self) -> None:
        """Supervisão ativa = existe palavra-passe de supervisor. Ao criá-la, as opções de formatação,
        imagens e anexos ficam bloqueadas; ao desativá-la, tudo volta a ficar aberto."""
        if self._supervisao_ativa():
            if not verificar_supervisor(self):
                return
            supervisor.apagar()
            contas.guardar_preferencias({**contas.preferencias(), "html": True, "imagens": True, "anexos": True})
        else:
            nova = _palavra_passe_nova(self)
            if nova is None:
                return
            supervisor.definir(nova)
            _, integras = R.carregar()
            if not integras:
                R.guardar(R.Regras())
            contas.guardar_preferencias({**contas.preferencias(), "html": False, "imagens": False, "anexos": False})
        self._atualizar_supervisao()

    def _atualizar_seletor(self, selecionar: str | None) -> None:
        self._seletor.blockSignals(True)
        self._seletor.clear()
        self._seletor.addItem("Nova conta", None)
        for endereco in contas.listar_enderecos():
            self._seletor.addItem(endereco, endereco)
        indice = self._seletor.findData(selecionar) if selecionar else 0
        self._seletor.setCurrentIndex(max(0, indice))
        self._seletor.blockSignals(False)

    def _escolher_conta(self, indice: int) -> None:
        endereco = self._seletor.itemData(indice)
        conta = contas.carregar(endereco=endereco) if endereco else None
        self._senha.clear()
        self._endereco.setText(conta[0].endereco if conta else "")
        self._servidor.setText(conta[0].imap.servidor if conta else "")
        self._protocolo.setCurrentIndex(1 if conta and conta[0].protocolo == "pop3" else 0)

    def _entrar(self, provedor: str) -> None:
        """Entrada com conta Microsoft ou Google: abre o navegador e espera a confirmação, fora da janela."""
        if self._supervisao_ativa() and not verificar_supervisor(self):
            return
        if not oauth.configurado(provedor):
            QMessageBox.information(self, "Correio", MENSAGENS["correio.oauth_nao_configurado"])
            return
        QMessageBox.information(
            self, "Correio", f"Vai abrir o navegador para entrar com a conta {oauth.PROVEDORES[provedor]['nome']}. "
            "Depois de confirmar, volte a esta janela."
        )
        correr_em_fundo(self, lambda: oauth.entrar(provedor), lambda resultado: self._entrou(provedor, resultado))

    def _entrou(self, provedor: str, resultado: tuple) -> None:
        estado, valor = resultado
        if estado == "erro":
            QMessageBox.warning(self, "Correio", texto_erro(valor))
            return
        endereco, renovacao = valor
        try:
            contas.guardar(oauth.conta_do_provedor(provedor, endereco), renovacao)
        except (OSError, ErroCorreio) as erro:
            QMessageBox.warning(self, "Correio", texto_erro(erro))
            return
        QMessageBox.information(self, "Correio", f"Conta {endereco} guardada.")
        self._atualizar_seletor(endereco)

    def _guardar_conta(self) -> None:
        if self._supervisao_ativa() and not verificar_supervisor(self):
            return
        try:
            conta = conta_cpanel(
                self._endereco.text(), self._servidor.text().strip() or None, protocolo=self._protocolo.currentData()
            )
            contas.guardar(conta, self._senha.text())
        except ErroCorreio as erro:
            QMessageBox.warning(self, "Correio", texto_erro(erro))
            return
        QMessageBox.information(self, "Correio", "Conta guardada.")
        self._senha.clear()
        self._atualizar_seletor(conta.endereco)

    def _acrescentar(self, lista: str) -> None:
        if not verificar_supervisor(self):
            return
        entrada, ok = QInputDialog.getText(self, "Acrescentar", "Endereço ou domínio (ex.: escola.pt):")
        if not ok or not entrada.strip():
            return
        try:
            regras = R.alterar(lista, entrada)
        except ErroCorreio as erro:
            QMessageBox.warning(self, "Correio", texto_erro(erro))
            return
        self._listas[lista].clear()
        self._listas[lista].addItems(getattr(regras, lista))

    def _remover(self, lista: str) -> None:
        item = self._listas[lista].currentItem()
        if item is None or not verificar_supervisor(self):
            return
        try:
            regras = R.remover(lista, item.text())
        except ErroCorreio as erro:
            QMessageBox.warning(self, "Correio", texto_erro(erro))
            return
        self._listas[lista].clear()
        self._listas[lista].addItems(getattr(regras, lista))

    def _repor_regras(self) -> None:
        if not verificar_supervisor(self):
            return
        R.guardar(R.Regras())
        self._atualizar_supervisao()
        QMessageBox.information(self, "Correio", "Regras repostas. Acrescente de novo os endereços permitidos.")

    def _alterar_palavra_passe(self) -> None:
        if not supervisor.existe():
            nova = _palavra_passe_nova(self)
            if nova is not None:
                supervisor.definir(nova)
                QMessageBox.information(self, "Correio", "Palavra-passe de supervisor criada.")
            return
        atual, ok = QInputDialog.getText(self, "Supervisor", "Palavra-passe atual:", QLineEdit.EchoMode.Password)
        if not ok:
            return
        nova = _palavra_passe_nova(self)
        if nova is None:
            return
        try:
            R.alterar_palavra_passe(atual, nova)
        except ErroCorreio as erro:
            QMessageBox.warning(self, "Correio", texto_erro(erro))
            return
        QMessageBox.information(self, "Correio", "Palavra-passe alterada.")

    def _apagar_conta(self) -> None:
        if self._supervisao_ativa() and not verificar_supervisor(self):
            return
        endereco = self._seletor.currentData()
        if not endereco:
            QMessageBox.information(self, "Correio", "Escolha primeiro a conta a apagar.")
            return
        if QMessageBox.question(self, "Correio", f"Apagar a conta {endereco} deste computador?") != QMessageBox.StandardButton.Yes:
            return
        contas.apagar(endereco=endereco)
        self._atualizar_seletor(None)
        self._escolher_conta(self._seletor.currentIndex())
        QMessageBox.information(self, "Correio", "Conta apagada deste computador.")
