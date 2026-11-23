"""Modelo do correio: contas, mensagens e erros. Não depende de nenhum fornecedor."""

from __future__ import annotations

from dataclasses import dataclass, field


class ErroCorreio(RuntimeError):
    """A mensagem é uma chave de tradução (ex.: correio.autenticacao_falhou)."""


@dataclass(frozen=True)
class Servidor:
    servidor: str
    porta: int
    ssl: bool = True


@dataclass(frozen=True)
class Conta:
    endereco: str
    utilizador: str
    imap: Servidor
    smtp: Servidor
    metodo: str = "palavra_passe"  # "palavra_passe", ou o fornecedor OAuth ("microsoft", "google")
    protocolo: str = "imap"  # "imap" ou "pop3" (o campo imap é o servidor de receção, porta 993 ou 995)


@dataclass(frozen=True)
class Anexo:
    nome: str
    tipo: str
    tamanho: int
    dados: bytes = field(default=b"", repr=False, compare=False)
    cid: str | None = None


@dataclass(frozen=True)
class Mensagem:
    uid: str
    remetente: str
    destinatarios: tuple[str, ...]
    assunto: str
    data: str
    texto: str
    anexos: tuple[Anexo, ...] = field(default_factory=tuple)
    html: str | None = None
    cc: tuple[str, ...] = field(default_factory=tuple)
    cco: tuple[str, ...] = field(default_factory=tuple)  # só existe nas cópias de emails enviados
    lida: bool = True
    marcada: bool = False  # estrela


def conta_cpanel(endereco: str, servidor: str | None = None, protocolo: str = "imap") -> Conta:
    """Conta num alojamento com cPanel: IMAP 993 (ou POP3 995) e SMTP 465, todos com SSL/TLS."""
    endereco = endereco.strip().lower()
    dominio = endereco.rsplit("@", 1)[-1]
    host = servidor or f"mail.{dominio}"
    receber = Servidor(host, 995 if protocolo == "pop3" else 993, True)
    return Conta(
        endereco=endereco,
        utilizador=endereco,
        imap=receber,
        smtp=Servidor(host, 465, True),
        protocolo=protocolo,
    )
