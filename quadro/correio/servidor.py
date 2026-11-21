"""Ligações IMAP e SMTP com TLS obrigatório e verificação do certificado."""

from __future__ import annotations

import base64
import imaplib
import poplib
import re
import smtplib
import ssl
import time
import unicodedata
from dataclasses import dataclass, replace
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, getaddresses, make_msgid, parseaddr
from html.parser import HTMLParser

from quadro.correio import oauth
from quadro.correio.modelo import Anexo, Conta, ErroCorreio, Mensagem

TEMPO_LIMITE_S = 20


def contexto_seguro() -> ssl.SSLContext:
    return ssl.create_default_context()


class _TextoHtml(HTMLParser):
    BLOCOS = ("p", "div", "br", "li", "tr", "h1", "h2", "h3")

    def __init__(self) -> None:
        super().__init__()
        self.partes: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._ignorar += 1
        elif tag in self.BLOCOS:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._ignorar:
            self._ignorar -= 1

    def handle_data(self, dados):
        if not self._ignorar:
            self.partes.append(dados)


def _html_para_texto(html: str) -> str:
    parser = _TextoHtml()
    parser.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "".join(parser.partes)).strip()


def mensagem_de_bytes(uid: str, bruto: bytes) -> Mensagem:
    """Converte uma mensagem MIME em texto simples e lista de anexos (sem HTML nem imagens)."""
    original = BytesParser(policy=policy.default).parsebytes(bruto)
    texto: str | None = None
    html: str | None = None
    anexos: list[Anexo] = []
    for parte in original.walk():
        if parte.is_multipart():
            continue
        tipo = parte.get_content_type()
        nome = parte.get_filename()
        if tipo in ("text/plain", "text/html") and not nome and parte.get_content_disposition() != "attachment":
            conteudo = parte.get_content()
            if tipo == "text/plain" and texto is None:
                texto = conteudo
            elif tipo == "text/html" and html is None:
                html = conteudo
            continue
        dados = parte.get_payload(decode=True) or b""
        cid = str(parte.get("Content-ID", "")).strip().strip("<>") or None
        anexos.append(Anexo(nome or "sem-nome", tipo, len(dados), dados, cid))
    if texto is None and html is not None:
        texto = _html_para_texto(html)
    destinatarios = tuple(endereco.lower() for _, endereco in getaddresses([str(h) for h in original.get_all("To", [])]) if endereco)
    return Mensagem(
        uid=uid,
        remetente=parseaddr(str(original.get("From", "")))[1].lower(),
        destinatarios=destinatarios,
        assunto=str(original.get("Subject", "")),
        data=str(original.get("Date", "")),
        texto=texto or "",
        anexos=tuple(anexos),
        html=html,
        cc=_enderecos(original.get_all("Cc", [])),
        cco=_enderecos(original.get_all("Bcc", [])),
    )


def _enderecos(cabecalhos) -> tuple[str, ...]:
    return tuple(endereco.lower() for _, endereco in getaddresses([str(h) for h in cabecalhos]) if endereco)


@dataclass(frozen=True)
class Pasta:
    nome: str  # nome IMAP completo, ex.: "INBOX", "INBOX.Spam"
    especial: str | None = None  # "lixo", "spam", "enviados", "rascunhos" ou None
    nao_lidas: int = 0


_LINHA_LIST = re.compile(r'\((?P<flags>[^)]*)\)\s+(?:"(?P<delim>[^"]*)"|NIL)\s+(?P<nome>.+)')
_MARCAS_ESPECIAIS = (("lixo", "\\trash"), ("spam", "\\junk"), ("enviados", "\\sent"), ("rascunhos", "\\drafts"))
_NOMES_ESPECIAIS = {"trash": "lixo", "lixo": "lixo", "junk": "spam", "spam": "spam", "sent": "enviados", "drafts": "rascunhos"}


def _pasta_de_linha(linha: str) -> Pasta | None:
    correspondencia = _LINHA_LIST.match(linha)
    if correspondencia is None:
        return None
    flags = correspondencia.group("flags").lower()
    if "\\noselect" in flags:
        return None
    nome = correspondencia.group("nome").strip()
    if nome.startswith('"') and nome.endswith('"'):
        nome = nome[1:-1]
    especial = next((valor for valor, marca in _MARCAS_ESPECIAIS if marca in flags), None)
    if especial is None:
        delimitador = correspondencia.group("delim") or "."
        simples = nome.split(delimitador)[-1].lower()
        especial = _NOMES_ESPECIAIS.get(simples)
    return Pasta(nome, especial)


def _nome_imap(pasta: str) -> str:
    """Nome de pasta pronto para um comando IMAP (entre aspas se tiver espaços ou caracteres especiais)."""
    if re.fullmatch(r"[A-Za-z0-9._-]+", pasta):
        return pasta
    return '"' + pasta.replace("\\", "\\\\").replace('"', '\\"') + '"'


class ClienteImap:
    """Uso: with ClienteImap(conta, senha) as correio: correio.listar()."""

    def __init__(self, conta: Conta, palavra_passe: str, tempo_limite: float = TEMPO_LIMITE_S) -> None:
        self._conta = conta
        self._palavra_passe = palavra_passe
        self._tempo_limite = tempo_limite
        self._ligacao: imaplib.IMAP4_SSL | None = None

    def __enter__(self) -> ClienteImap:
        servidor = self._conta.imap
        try:
            self._ligacao = imaplib.IMAP4_SSL(
                servidor.servidor, servidor.porta, ssl_context=contexto_seguro(), timeout=self._tempo_limite
            )
        except OSError as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        try:
            if self._conta.metodo in oauth.PROVEDORES:
                token = self._palavra_passe
                self._ligacao.authenticate(
                    "XOAUTH2", lambda _resposta: oauth.xoauth2(self._conta.utilizador, token).encode("utf-8")
                )
            else:
                self._ligacao.login(self._conta.utilizador, self._palavra_passe)
        except imaplib.IMAP4.error as erro:
            self.sair()
            raise ErroCorreio("correio.autenticacao_falhou") from erro
        return self

    def __exit__(self, *_) -> None:
        self.sair()

    def sair(self) -> None:
        if self._ligacao is None:
            return
        try:
            self._ligacao.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
        self._ligacao = None

    def listar_pastas(self) -> list[Pasta]:
        """Todas as pastas da conta (a caixa de entrada primeiro). Sem pastas legíveis, só a caixa de entrada."""
        assert self._ligacao is not None, "use dentro de with"
        try:
            _, dados = self._ligacao.list()
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        pastas = [p for p in (_pasta_de_linha(l.decode("utf-8", "replace")) for l in dados or [] if isinstance(l, bytes)) if p]
        pastas = [replace(p, nao_lidas=self._nao_lidas_da_pasta(p.nome)) for p in pastas]
        pastas.sort(key=lambda p: (p.nome.upper() != "INBOX", p.nome.lower()))
        return pastas or [Pasta("INBOX")]

    def _nao_lidas_da_pasta(self, pasta: str) -> int:
        """Quantas mensagens por ler tem a pasta. Sem resposta do servidor, conta como zero."""
        try:
            estado, dados = self._ligacao.status(_nome_imap(pasta), "(UNSEEN)")
        except (imaplib.IMAP4.error, OSError):
            return 0
        if estado != "OK" or not dados or not isinstance(dados[0], bytes):
            return 0
        encontrado = re.search(r"UNSEEN (\d+)", dados[0].decode("utf-8", "replace"))
        return int(encontrado.group(1)) if encontrado else 0

    def listar(self, limite: int = 30, pasta: str = "INBOX", termo: str | None = None) -> list[Mensagem]:
        """As mensagens mais recentes da pasta (ou as que contêm o termo), sem as marcar como lidas."""
        assert self._ligacao is not None, "use dentro de with"
        try:
            self._ligacao.select(_nome_imap(pasta), readonly=True)
            if termo:
                _, dados = self._ligacao.uid("SEARCH", None, *_criterio_pesquisa(termo))
            else:
                _, dados = self._ligacao.uid("SEARCH", None, "ALL")
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        uids = dados[0].split()[-limite:] if dados and dados[0] else []
        return [self.obter(uid.decode()) for uid in reversed(uids)]

    def marcar(self, uid: str, pasta: str, lida: bool | None = None, marcada: bool | None = None) -> None:
        assert self._ligacao is not None, "use dentro de with"
        try:
            self._ligacao.select(_nome_imap(pasta), readonly=False)
            if lida is not None:
                self._ligacao.uid("STORE", uid, "+FLAGS" if lida else "-FLAGS", "(\\Seen)")
            if marcada is not None:
                self._ligacao.uid("STORE", uid, "+FLAGS" if marcada else "-FLAGS", "(\\Flagged)")
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro

    def mover(self, uid: str, origem: str, destino: str) -> None:
        assert self._ligacao is not None, "use dentro de with"
        try:
            self._ligacao.select(_nome_imap(origem), readonly=False)
            estado, _ = self._ligacao.uid("COPY", uid, _nome_imap(destino))
            if estado != "OK":
                raise ErroCorreio("correio.mover_falhou")
            self._ligacao.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
            self._ligacao.expunge()
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro

    def guardar_em_pasta(self, especial: str, mensagem: bytes, flags: str) -> None:
        """Guarda uma mensagem na pasta de um tipo (ex.: «rascunhos»)."""
        assert self._ligacao is not None, "use dentro de with"
        pasta = next((p.nome for p in self.listar_pastas() if p.especial == especial), None)
        if pasta is None:
            raise ErroCorreio("correio.sem_pasta_" + especial)
        try:
            estado, _ = self._ligacao.append(_nome_imap(pasta), flags, imaplib.Time2Internaldate(time.time()), mensagem)
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        if estado != "OK":
            raise ErroCorreio("correio.sem_pasta_" + especial)

    def guardar_em_enviados(self, mensagem: bytes) -> None:
        assert self._ligacao is not None, "use dentro de with"
        enviados = next((p.nome for p in self.listar_pastas() if p.especial == "enviados"), None)
        if enviados is None:
            raise ErroCorreio("correio.sem_pasta_enviados")
        try:
            estado, _ = self._ligacao.append(_nome_imap(enviados), "(\\Seen)", imaplib.Time2Internaldate(time.time()), mensagem)
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        if estado != "OK":
            raise ErroCorreio("correio.sem_pasta_enviados")

    def apagar(self, uid: str, pasta: str, lixo: str | None) -> None:
        """Move a mensagem para o lixo. Se já está no lixo (ou não há lixo), apaga-a de vez."""
        assert self._ligacao is not None, "use dentro de with"
        definitivo = lixo is None or lixo == pasta
        try:
            self._ligacao.select(_nome_imap(pasta), readonly=False)
            if not definitivo:
                estado, _ = self._ligacao.uid("COPY", uid, _nome_imap(lixo))
                if estado != "OK":
                    raise ErroCorreio("correio.apagar_falhou")
            self._ligacao.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
            self._ligacao.expunge()
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro

    def nao_lidas(self) -> int:
        """Quantas mensagens da caixa de entrada ainda não foram lidas. Não as marca como lidas."""
        assert self._ligacao is not None, "use dentro de with"
        try:
            self._ligacao.select("INBOX", readonly=True)
            _, dados = self._ligacao.uid("SEARCH", None, "UNSEEN")
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        return len(dados[0].split()) if dados and dados[0] else 0

    def obter(self, uid: str) -> Mensagem:
        assert self._ligacao is not None, "use dentro de with"
        try:
            estado, dados = self._ligacao.uid("FETCH", uid, "(FLAGS BODY.PEEK[])")
        except (imaplib.IMAP4.error, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        if estado != "OK" or not dados or not isinstance(dados[0], tuple):
            raise ErroCorreio("correio.mensagem_nao_encontrada")
        cabecalho = dados[0][0].decode("ascii", "replace") if isinstance(dados[0][0], bytes) else ""
        bandeiras = re.search(r"FLAGS \(([^)]*)\)", cabecalho)
        flags = bandeiras.group(1).lower() if bandeiras else ""
        return replace(mensagem_de_bytes(uid, dados[0][1]), lida="\\seen" in flags, marcada="\\flagged" in flags)


def _criterio_pesquisa(termo: str) -> list[str]:
    """Pesquisa no texto inteiro, sem distinguir maiúsculas nem acentos (o IMAP simples só aceita ASCII)."""
    limpo = unicodedata.normalize("NFKD", termo).encode("ascii", "ignore").decode("ascii").replace('"', "").strip()
    return ["TEXT", f'"{limpo}"'] if limpo else ["ALL"]


def _sem_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()


class ClientePop3:
    """Receção por POP3. O POP3 não tem pastas, marcas nem cópia de Enviados no servidor: essas operações
    são recusadas com uma mensagem clara, e o estado de leitura não existe (todas as mensagens contam como lidas).
    Uso: with ClientePop3(conta, senha) as correio: correio.listar()."""

    def __init__(self, conta: Conta, palavra_passe: str, tempo_limite: float = TEMPO_LIMITE_S) -> None:
        self._conta = conta
        self._palavra_passe = palavra_passe
        self._tempo_limite = tempo_limite
        self._ligacao: poplib.POP3_SSL | None = None
        self._numeros: dict[str, int] = {}

    def __enter__(self) -> ClientePop3:
        servidor = self._conta.imap
        try:
            self._ligacao = poplib.POP3_SSL(servidor.servidor, servidor.porta, context=contexto_seguro(), timeout=self._tempo_limite)
        except OSError as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        try:
            if self._conta.metodo in oauth.PROVEDORES:
                sasl = oauth.xoauth2(self._conta.utilizador, self._palavra_passe)
                self._ligacao._shortcmd("AUTH XOAUTH2 " + base64.b64encode(sasl.encode("utf-8")).decode("ascii"))
            else:
                self._ligacao.user(self._conta.utilizador)
                self._ligacao.pass_(self._palavra_passe)
        except poplib.error_proto as erro:
            self.sair()
            raise ErroCorreio("correio.autenticacao_falhou") from erro
        except OSError as erro:
            self.sair()
            raise ErroCorreio("correio.sem_ligacao") from erro
        return self

    def __exit__(self, *_) -> None:
        self.sair()

    def sair(self) -> None:
        """Ao sair, o POP3 confirma os apagamentos pedidos nesta sessão."""
        if self._ligacao is None:
            return
        try:
            self._ligacao.quit()
        except (poplib.error_proto, OSError):
            pass
        self._ligacao = None

    def listar_pastas(self) -> list[Pasta]:
        return [Pasta("INBOX")]

    def _pares(self) -> list[tuple[int, str]]:
        try:
            _, linhas, _ = self._ligacao.uidl()
        except (poplib.error_proto, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro
        pares = []
        for linha in linhas:
            partes = linha.decode("ascii", "replace").split()
            if len(partes) == 2 and partes[0].isdigit():
                pares.append((int(partes[0]), partes[1]))
        return pares

    def _obter_numero(self, numero: int, uid: str) -> Mensagem:
        try:
            _, linhas, _ = self._ligacao.retr(numero)
        except (poplib.error_proto, OSError) as erro:
            raise ErroCorreio("correio.mensagem_nao_encontrada") from erro
        return mensagem_de_bytes(uid, b"\r\n".join(linhas))

    def listar(self, limite: int = 30, pasta: str = "INBOX", termo: str | None = None) -> list[Mensagem]:
        pares = self._pares()
        self._numeros = {uid: numero for numero, uid in pares}
        if not termo:
            return [self._obter_numero(numero, uid) for numero, uid in reversed(pares[-limite:])]
        procurado = _sem_acentos(termo.strip())
        encontradas = []
        for numero, uid in reversed(pares[-200:]):
            mensagem = self._obter_numero(numero, uid)
            if procurado in _sem_acentos(f"{mensagem.assunto} {mensagem.remetente} {mensagem.texto}"):
                encontradas.append(mensagem)
                if len(encontradas) >= limite:
                    break
        return encontradas

    def obter(self, uid: str) -> Mensagem:
        numero = self._numeros.get(uid)
        if numero is None:
            raise ErroCorreio("correio.mensagem_nao_encontrada")
        return self._obter_numero(numero, uid)

    def nao_lidas(self) -> int:
        return 0

    def apagar(self, uid: str, pasta: str, lixo: str | None) -> None:
        numero = self._numeros.get(uid)
        if numero is None:
            raise ErroCorreio("correio.mensagem_nao_encontrada")
        try:
            self._ligacao.dele(numero)
        except (poplib.error_proto, OSError) as erro:
            raise ErroCorreio("correio.sem_ligacao") from erro

    def marcar(self, *_args, **_kwargs) -> None:
        raise ErroCorreio("correio.pop3_sem_marcas")

    def mover(self, *_args, **_kwargs) -> None:
        raise ErroCorreio("correio.pop3_sem_pastas")

    def guardar_em_pasta(self, especial: str, mensagem: bytes, flags: str) -> None:
        raise ErroCorreio("correio.pop3_sem_pastas")

    def guardar_em_enviados(self, mensagem: bytes) -> None:
        raise ErroCorreio("correio.pop3_sem_enviados")


def cliente_de(conta: Conta, palavra_passe: str, tempo_limite: float = TEMPO_LIMITE_S):
    """O cliente de receção certo para a conta (IMAP ou POP3)."""
    if conta.protocolo == "pop3":
        return ClientePop3(conta, palavra_passe, tempo_limite)
    return ClienteImap(conta, palavra_passe, tempo_limite)


def guardar_em_enviados(conta: Conta, palavra_passe: str, mensagem: EmailMessage, tempo_limite: float = TEMPO_LIMITE_S) -> None:
    """Guarda uma cópia do email enviado na pasta «Enviados» do servidor (com o cabeçalho Bcc)."""
    with cliente_de(conta, palavra_passe, tempo_limite) as correio:
        correio.guardar_em_enviados(mensagem.as_bytes())


def contar_nao_lidas(conta: Conta, palavra_passe: str, tempo_limite: float = TEMPO_LIMITE_S) -> int:
    with cliente_de(conta, palavra_passe, tempo_limite) as correio:
        return correio.nao_lidas()


def _tipo_mime(tipo: str) -> tuple[str, str]:
    if "/" in tipo:
        principal, subtipo = tipo.split("/", 1)
        return principal or "application", subtipo or "octet-stream"
    return "application", "octet-stream"


def montar_mensagem(
    endereco: str,
    destinatarios: list[str],
    assunto: str,
    texto: str,
    html: str | None = None,
    cc: list[str] | tuple = (),
    cco: list[str] | tuple = (),
    anexos: tuple[Anexo, ...] = (),
    imagens: tuple[Anexo, ...] = (),
    com_bcc: bool = False,
) -> EmailMessage:
    """Mensagem com texto simples e, se houver formatação, a versão HTML (o cliente escolhe a que pode mostrar).
    `imagens` são as imagens do próprio texto (referidas no HTML como cid:) e `anexos` os ficheiros anexados.
    O cabeçalho Bcc só entra com `com_bcc` (a cópia guardada em Enviados); a mensagem enviada não o tem."""
    mensagem = EmailMessage()
    mensagem["From"] = endereco
    mensagem["To"] = ", ".join(destinatarios)
    if cc:
        mensagem["Cc"] = ", ".join(cc)
    if com_bcc and cco:
        mensagem["Bcc"] = ", ".join(cco)
    mensagem["Subject"] = assunto
    mensagem["Date"] = formatdate(localtime=True)
    mensagem["Message-ID"] = make_msgid(domain=endereco.split("@")[-1])
    mensagem.set_content(texto)
    if html is not None:
        mensagem.add_alternative(html, subtype="html")
        if imagens:
            corpo_html = mensagem.get_body(preferencelist=("html",))
            for imagem in imagens:
                principal, subtipo = _tipo_mime(imagem.tipo)
                corpo_html.add_related(imagem.dados, maintype=principal, subtype=subtipo, cid=f"<{imagem.cid}>")
    for anexo in anexos:
        principal, subtipo = _tipo_mime(anexo.tipo)
        mensagem.add_attachment(anexo.dados, maintype=principal, subtype=subtipo, filename=anexo.nome)
    return mensagem


def _ligar_smtp(servidor, tempo_limite: float) -> smtplib.SMTP:
    """Porta com SSL direto (465) ou com STARTTLS (587, a usada pela Microsoft)."""
    if servidor.ssl:
        return smtplib.SMTP_SSL(servidor.servidor, servidor.porta, context=contexto_seguro(), timeout=tempo_limite)
    smtp = smtplib.SMTP(servidor.servidor, servidor.porta, timeout=tempo_limite)
    try:
        smtp.ehlo()
        smtp.starttls(context=contexto_seguro())
        smtp.ehlo()
    except (smtplib.SMTPException, OSError):
        smtp.close()
        raise
    return smtp


def enviar(
    conta: Conta,
    palavra_passe: str,
    destinatarios: list[str],
    assunto: str,
    texto: str,
    tempo_limite: float = TEMPO_LIMITE_S,
    html: str | None = None,
    cc: list[str] | tuple = (),
    cco: list[str] | tuple = (),
    anexos: tuple[Anexo, ...] = (),
    imagens: tuple[Anexo, ...] = (),
) -> EmailMessage:
    """Envia para todos os destinatários (para, cc e cco). Devolve a cópia com o cabeçalho Bcc, para Enviados."""
    if not destinatarios and not cc and not cco:
        raise ErroCorreio("correio.sem_destinatarios")
    if not destinatarios:
        destinatarios, cc = list(cc), []
    argumentos = dict(html=html, cc=cc, cco=cco, anexos=anexos, imagens=imagens)
    mensagem = montar_mensagem(conta.endereco, destinatarios, assunto, texto, **argumentos)
    copia = montar_mensagem(conta.endereco, destinatarios, assunto, texto, com_bcc=True, **argumentos)
    todos = list(destinatarios) + list(cc) + list(cco)
    servidor = conta.smtp
    try:
        with _ligar_smtp(servidor, tempo_limite) as smtp:
            if conta.metodo in oauth.PROVEDORES:
                smtp.auth("XOAUTH2", lambda _resposta=None: oauth.xoauth2(conta.utilizador, palavra_passe))
            else:
                smtp.login(conta.utilizador, palavra_passe)
            recusados = smtp.send_message(mensagem, from_addr=conta.endereco, to_addrs=todos)
        if recusados:
            raise ErroCorreio("correio.destinatarios_recusados")
    except smtplib.SMTPAuthenticationError as erro:
        raise ErroCorreio("correio.autenticacao_falhou") from erro
    except (smtplib.SMTPException, OSError) as erro:
        raise ErroCorreio("correio.envio_falhou") from erro
    return copia
