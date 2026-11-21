"""Dados iniciais para escrever uma mensagem: responder, responder a todos, encaminhar e editar rascunhos.

Não depende da interface: devolve um Rascunho que a janela de escrita preenche.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quadro.correio.modelo import Anexo, Mensagem


@dataclass(frozen=True)
class Rascunho:
    para: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    assunto: str = ""
    texto: str = ""
    anexos: tuple[Anexo, ...] = field(default_factory=tuple)


def _com_prefixo(prefixo: str, assunto: str) -> str:
    """«Re: …» ou «Fwd: …», sem repetir o prefixo se a mensagem já o tiver."""
    base = prefixo.rstrip(": ").lower()
    atual = assunto.lstrip().lower()
    if atual.startswith(base + ":"):
        return assunto
    return f"{prefixo}{assunto}"


def citar(mensagem: Mensagem) -> str:
    linhas = (mensagem.texto or "").splitlines() or [""]
    return f"\n\nEm {mensagem.data}, {mensagem.remetente} escreveu:\n" + "\n".join(f"> {linha}" for linha in linhas)


def responder(mensagem: Mensagem, endereco_proprio: str, todos: bool = False) -> Rascunho:
    proprio = endereco_proprio.lower()
    cc: list[str] = []
    if todos:
        for endereco in mensagem.destinatarios + mensagem.cc:
            limpo = endereco.lower()
            if limpo and limpo != proprio and limpo != mensagem.remetente.lower() and limpo not in cc:
                cc.append(limpo)
    return Rascunho(
        para=(mensagem.remetente,),
        cc=tuple(cc),
        assunto=_com_prefixo("Re: ", mensagem.assunto),
        texto=citar(mensagem),
    )


def encaminhar(mensagem: Mensagem) -> Rascunho:
    cabecalho = (
        "---------- Mensagem encaminhada ----------\n"
        f"De: {mensagem.remetente}\n"
        f"Data: {mensagem.data}\n"
        f"Assunto: {mensagem.assunto}\n"
        f"Para: {', '.join(mensagem.destinatarios)}\n\n"
    )
    return Rascunho(
        assunto=_com_prefixo("Fwd: ", mensagem.assunto),
        texto=cabecalho + (mensagem.texto or ""),
        anexos=tuple(a for a in mensagem.anexos if a.dados),
    )


def editar(mensagem: Mensagem) -> Rascunho:
    """Um rascunho guardado: abre com o mesmo conteúdo, para continuar a escrever."""
    return Rascunho(
        para=mensagem.destinatarios,
        cc=mensagem.cc,
        assunto=mensagem.assunto,
        texto=mensagem.texto or "",
        anexos=tuple(a for a in mensagem.anexos if a.dados),
    )
