"""Catálogo de ações do Quadro.

Cada ação do menu tem um identificador estável (ex.: "caneta", "carimbo.figura.sol"). O catálogo é só
dados: não altera o comportamento do menu. Serve de contrato para o teclado virtual e para a app
Android, que vão desenhar as teclas a partir deste catálogo e enviar de volta o identificador escolhido.

Cada ação tem:
- id: identificador único e estável (não se muda depois de publicado);
- nome: texto para pessoas (o teclado e a app mostram ícones; o nome serve de dica e de rótulo técnico);
- icone: nome do ícone desenhado pelo Quadro (o teclado e a app não precisam de texto);
- pai: id do submenu a que pertence, ou None para o menu principal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

VERSAO_CATALOGO = 1
TAMANHOS = (1, 2, 3, 4)
FIGURAS = ("estrela", "coracao", "sol", "flor", "casa", "arvore", "peixe", "sorriso", "nuvem")
FORMAS = ("linha", "retangulo", "elipse", "poligono")
EFEITOS = ("desfocar", "tingir", "pixelizar")
CORES = ("automatica", "preto", "vermelho", "azul", "verde", "laranja", "roxo", "branco")
FERRAMENTAS = ("caneta", "borracha", "borracha_riscos", "varinha", "balde", "carimbo", "magia", "forma", "texto")


@dataclass(frozen=True)
class Acao:
    id: str
    nome: str
    icone: str
    pai: str | None = None
    ferramenta: str | None = None


def _catalogo() -> tuple[Acao, ...]:
    acoes: list[Acao] = []
    nomes_ferramenta = {
        "caneta": "Caneta",
        "borracha": "Borracha",
        "borracha_riscos": "Borracha de riscos",
        "varinha": "Varinha mágica",
        "balde": "Balde de tinta",
        "carimbo": "Carimbos",
        "magia": "Pincel mágico",
        "forma": "Formas",
        "texto": "Escrever texto",
    }
    for ferramenta in FERRAMENTAS:
        acoes.append(Acao(ferramenta, nomes_ferramenta[ferramenta], ferramenta, None, ferramenta))
    for ferramenta in ("caneta", "borracha", "borracha_riscos", "carimbo", "magia", "texto"):
        for n in TAMANHOS:
            acoes.append(Acao(f"{ferramenta}.tamanho.{n}", f"Tamanho {n}", f"tamanho-{n}", ferramenta))
    for figura in FIGURAS:
        acoes.append(Acao(f"carimbo.figura.{figura}", figura.capitalize(), f"carimbo-{figura}", "carimbo"))
    for forma in FORMAS:
        acoes.append(Acao(f"forma.{forma}", forma.capitalize(), f"forma-{forma}", "forma"))
    for efeito in EFEITOS:
        acoes.append(Acao(f"magia.{efeito}", efeito.capitalize(), f"efeito-{efeito}", "magia"))
    acoes.append(Acao("cor", "Cor", "cor"))
    for cor in CORES:
        acoes.append(Acao(f"cor.{cor}", cor.capitalize(), f"cor-{cor}", "cor"))
    acoes.extend(
        (
            Acao("desfazer", "Desfazer", "desfazer"),
            Acao("refazer", "Refazer", "refazer"),
            Acao("apagar_selecao", "Apagar seleção", "apagar"),
            Acao("jogos", "Jogos", "jogos"),
            Acao("correio", "Correio", "correio"),
            Acao("definicoes", "Definições", "definicoes"),
            Acao("importar_imagem", "Importar imagem", "imagem"),
            Acao("ocultar_menu", "Ocultar menu", "ocultar"),
            Acao("minimizar", "Minimizar", "minimizar"),
        )
    )
    return tuple(acoes)


ACOES: tuple[Acao, ...] = _catalogo()
_POR_ID = {acao.id: acao for acao in ACOES}


def acao(identificador: str) -> Acao:
    if identificador not in _POR_ID:
        raise KeyError(f"ação desconhecida: {identificador}")
    return _POR_ID[identificador]


def filhos(pai: str | None) -> tuple[Acao, ...]:
    return tuple(a for a in ACOES if a.pai == pai)


def estado(
    ferramenta: str,
    tem_selecao: bool,
    pode_desfazer: bool,
    pode_refazer: bool,
    correio_visivel: bool,
    jogos_visivel: bool = True,
) -> dict[str, dict[str, bool]]:
    """Estado de cada ação neste momento: se está ativa (selecionada) e se está disponível."""
    resultado: dict[str, dict[str, bool]] = {}
    for a in ACOES:
        ativa = a.ferramenta == ferramenta if a.ferramenta else False
        disponivel = True
        if a.id == "desfazer":
            disponivel = pode_desfazer
        elif a.id == "refazer":
            disponivel = pode_refazer
        elif a.id == "apagar_selecao":
            disponivel = tem_selecao
        elif a.id == "correio":
            disponivel = correio_visivel
        elif a.id == "jogos":
            disponivel = jogos_visivel
        resultado[a.id] = {"ativa": ativa, "disponivel": disponivel}
    return resultado


def catalogo_dados() -> dict:
    """O catálogo em formato simples (JSON), para o teclado e a app Android."""
    return {"versao": VERSAO_CATALOGO, "acoes": [asdict(a) for a in ACOES]}
