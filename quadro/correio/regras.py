"""Regras do correio para crianças e adultos.

- Remetentes permitidos: as mensagens abrem sem palavra-passe; as restantes ficam bloqueadas.
- Destinatários permitidos: o utilizador só envia para estes; os outros precisam de palavra-passe.
- Ligações: só abrem texto de domínios aprovados; as restantes ficam marcadas como bloqueadas.
- Anexos: de remetentes permitidos, exceto ficheiros executáveis. Tudo o resto precisa de palavra-passe.

Entradas com "@" são endereços exatos. Entradas sem "@" são domínios, e incluem os subdomínios.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import urlsplit

from quadro.correio import servidor, supervisor
from quadro.correio.html import sanitizar_html
from quadro.correio.modelo import Conta, ErroCorreio, Mensagem

NOME_FICHEIRO = "regras-correio.json"
LIMITE_ENTRADAS = 500
EXTENSOES_EXECUTAVEIS = frozenset(
    {".exe", ".bat", ".cmd", ".com", ".scr", ".msi", ".msp", ".ps1", ".vbs", ".js", ".jar",
     ".lnk", ".reg", ".dll", ".hta", ".pif", ".wsf"}
)
_ENDERECO = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
_DOMINIO = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}")
_LIGACAO = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)


@dataclass
class Regras:
    remetentes: list[str] = field(default_factory=list)
    destinatarios: list[str] = field(default_factory=list)
    ligacoes: list[str] = field(default_factory=list)

    def para_dados(self) -> dict:
        return {
            "remetentes": sorted(set(self.remetentes)),
            "destinatarios": sorted(set(self.destinatarios)),
            "ligacoes": sorted(set(self.ligacoes)),
        }

    @classmethod
    def de_dados(cls, dados: object) -> Regras:
        if not isinstance(dados, dict):
            raise ErroCorreio("correio.regras_invalidas")
        listas = {}
        for chave in ("remetentes", "destinatarios", "ligacoes"):
            valor = dados.get(chave, [])
            if not isinstance(valor, list) or len(valor) > LIMITE_ENTRADAS:
                raise ErroCorreio("correio.regras_invalidas")
            listas[chave] = [normalizar(v, ligacao=(chave == "ligacoes")) for v in valor if isinstance(v, str)]
        return cls(listas["remetentes"], listas["destinatarios"], listas["ligacoes"])


def normalizar(entrada: str, ligacao: bool = False) -> str:
    valor = entrada.strip().lower()
    if ligacao:
        if _DOMINIO.fullmatch(valor):
            return valor
    elif _ENDERECO.fullmatch(valor) or _DOMINIO.fullmatch(valor):
        return valor
    raise ErroCorreio("correio.entrada_invalida")


def pertence(endereco: str, lista: list[str]) -> bool:
    """Endereço exato, ou domínio e os seus subdomínios. «evilescola.pt» não pertence a «escola.pt»."""
    endereco = endereco.strip().lower().rstrip(".")
    dominio = endereco.rsplit("@", 1)[-1]
    for entrada in lista:
        if "@" in entrada:
            if endereco == entrada:
                return True
        elif dominio == entrada or dominio.endswith("." + entrada):
            return True
    return False


# --- ficheiro assinado -----------------------------------------------------------


def caminho(pasta: Path | None = None) -> Path:
    return supervisor.pasta_dados(pasta) / NOME_FICHEIRO


def _assinatura(corpo: str, chave: bytes) -> str:
    return hmac.new(chave, corpo.encode("utf-8"), hashlib.sha256).hexdigest()


def guardar(regras: Regras, pasta: Path | None = None) -> None:
    chave = supervisor.chave_integridade(pasta)
    if chave is None:
        raise ErroCorreio("supervisor.nao_definido")
    corpo = json.dumps(regras.para_dados(), ensure_ascii=False, sort_keys=True)
    destino = caminho(pasta)
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(json.dumps({"corpo": corpo, "assinatura": _assinatura(corpo, chave)}), encoding="utf-8")
    temporario.replace(destino)


def carregar(pasta: Path | None = None) -> tuple[Regras, bool]:
    """Devolve (regras, íntegras). Se o ficheiro foi alterado à mão, as regras ficam vazias (tudo bloqueado)."""
    destino = caminho(pasta)
    if not destino.exists():
        return Regras(), True
    try:
        dados = json.loads(destino.read_text(encoding="utf-8"))
        corpo = dados["corpo"]
        assinatura = dados["assinatura"]
    except (OSError, ValueError, KeyError, TypeError):
        return Regras(), False
    chave = supervisor.chave_integridade(pasta)
    if chave is None or not isinstance(corpo, str) or not hmac.compare_digest(_assinatura(corpo, chave), str(assinatura)):
        return Regras(), False
    try:
        return Regras.de_dados(json.loads(corpo)), True
    except (ValueError, ErroCorreio):
        return Regras(), False


def alterar(lista: str, entrada: str, pasta: Path | None = None) -> Regras:
    """Acrescenta um endereço ou domínio a uma lista. Só deve ser chamada depois de verificar o supervisor."""
    regras, integras = carregar(pasta)
    if not integras:
        raise ErroCorreio("correio.regras_alteradas")
    valor = normalizar(entrada, ligacao=(lista == "ligacoes"))
    getattr(regras, lista).append(valor)
    guardar(regras, pasta)
    return regras


def remover(lista: str, entrada: str, pasta: Path | None = None) -> Regras:
    regras, integras = carregar(pasta)
    if not integras:
        raise ErroCorreio("correio.regras_alteradas")
    setattr(regras, lista, [v for v in getattr(regras, lista) if v != entrada.strip().lower()])
    guardar(regras, pasta)
    return regras


def alterar_palavra_passe(atual: str, nova: str, pasta: Path | None = None) -> None:
    """Altera a palavra-passe e volta a assinar as regras com a nova chave."""
    regras, integras = carregar(pasta)
    supervisor.definir(nova, pasta, palavra_atual=atual)
    if integras and caminho(pasta).exists():
        guardar(regras, pasta)


# --- leitura ----------------------------------------------------------------------


def _executavel(nome: str) -> bool:
    return Path(nome).suffix.lower() in EXTENSOES_EXECUTAVEIS


@dataclass(frozen=True)
class AnexoVisto:
    nome: str
    tipo: str
    tamanho: int
    executavel: bool
    permitido: bool


@dataclass(frozen=True)
class Visao:
    uid: str
    remetente: str
    assunto: str
    data: str
    remetente_permitido: bool
    aberta: bool
    texto: str | None
    anexos: tuple[AnexoVisto, ...]
    html: str | None = None


def ver(
    regras: Regras,
    mensagem: Mensagem,
    desbloqueada: bool = False,
    supervisionado: bool = True,
    html_ativo: bool = False,
    imagens: bool = True,
    anexos_ativos: bool = True,
) -> Visao:
    """Como `_ver_base`, e com a formatação HTML filtrada quando `html_ativo` está ligado.
    `imagens` e `anexos_ativos` são as opções do correio (ver contas.preferencias)."""
    base = _ver_base(regras, mensagem, desbloqueada, supervisionado, anexos_ativos)
    if not (html_ativo and base.aberta and mensagem.html):
        return base
    permitir = None if not supervisionado else (lambda dominio: pertence(dominio, regras.ligacoes))
    cids = frozenset(a.cid for a in mensagem.anexos if a.cid)
    return replace(base, html=sanitizar_html(mensagem.html, permitir, imagens=imagens, anexos_cid=cids))


def sanitizar(texto: str, regras: Regras) -> str:
    def substituir(encontrado: re.Match) -> str:
        url = encontrado.group(0).rstrip(".,;:)")
        alvo = url if url.lower().startswith(("http://", "https://")) else "http://" + url
        host = urlsplit(alvo).hostname or ""
        return url if host and pertence(host, regras.ligacoes) else "[ligação bloqueada]"

    return _LIGACAO.sub(substituir, texto)


def _ver_base(
    regras: Regras,
    mensagem: Mensagem,
    desbloqueada: bool = False,
    supervisionado: bool = True,
    anexos_ativos: bool = True,
) -> Visao:
    """Decide o que mostrar. `desbloqueada` é True quando o supervisor introduziu a palavra-passe.
    Sem supervisão, tudo está aberto (os anexos só dependem da opção «anexos»)."""
    if not supervisionado:
        return Visao(
            uid=mensagem.uid,
            remetente=mensagem.remetente,
            assunto=mensagem.assunto,
            data=mensagem.data,
            remetente_permitido=True,
            aberta=True,
            texto=mensagem.texto,
            anexos=tuple(
                AnexoVisto(a.nome, a.tipo, a.tamanho, executavel=_executavel(a.nome), permitido=anexos_ativos)
                for a in mensagem.anexos
            ),
        )
    remetente_ok = pertence(mensagem.remetente, regras.remetentes)
    aberta = remetente_ok or desbloqueada
    anexos = tuple(
        AnexoVisto(
            nome=a.nome,
            tipo=a.tipo,
            tamanho=a.tamanho,
            executavel=_executavel(a.nome),
            permitido=desbloqueada or (remetente_ok and anexos_ativos),
        )
        for a in mensagem.anexos
    )
    return Visao(
        uid=mensagem.uid,
        remetente=mensagem.remetente,
        assunto=mensagem.assunto,
        data=mensagem.data,
        remetente_permitido=remetente_ok,
        aberta=aberta,
        texto=sanitizar(mensagem.texto, regras) if aberta else None,
        anexos=anexos,
    )


# --- envio ------------------------------------------------------------------------


def destinatarios_bloqueados(regras: Regras, destinatarios: list[str]) -> list[str]:
    return [d for d in destinatarios if not pertence(d, regras.destinatarios)]


def enviar(
    conta: Conta,
    palavra_passe_conta: str,
    regras: Regras,
    destinatarios: list[str],
    assunto: str,
    texto: str,
    desbloqueado: bool = False,
    supervisionado: bool = True,
    html: str | None = None,
    cc: list[str] | tuple = (),
    cco: list[str] | tuple = (),
    anexos: tuple = (),
    imagens: tuple = (),
):
    """Envia só para destinatários permitidos (para, cc e cco), a não ser que o supervisor tenha desbloqueado o envio.
    Sem supervisão, envia para qualquer destinatário. Devolve a cópia para a pasta Enviados."""
    todos = list(destinatarios) + list(cc) + list(cco)
    if supervisionado and destinatarios_bloqueados(regras, todos) and not desbloqueado:
        raise ErroCorreio("correio.destinatarios_bloqueados")
    return servidor.enviar(
        conta, palavra_passe_conta, destinatarios, assunto, texto,
        html=html, cc=cc, cco=cco, anexos=anexos, imagens=imagens,
    )
