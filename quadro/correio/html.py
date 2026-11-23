"""Filtro do HTML dos emails: só deixa etiquetas de formatação.

- Scripts, estilos, iframes, formulários e similares são removidos com o conteúdo.
- Imagens só passam quando a opção «imagens» está ligada; caso contrário cada imagem vira «[imagem bloqueada]».
- Ligações só ficam ativas se `permitir_link` aceitar o domínio. Sem essa função, todas ficam ativas.
- Atributos que não são de formatação são removidos (inclusive os on*, e os estilos com url(...)).
"""

from __future__ import annotations

import html as _html
import re
from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import urlsplit

ETIQUETAS = frozenset(
    {"b", "strong", "i", "em", "u", "p", "br", "div", "span", "ul", "ol", "li", "table", "thead", "tbody",
     "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "code", "font", "hr", "a"}
)
VAZIAS = frozenset({"br", "hr"})
DESCARTADAS_COM_CONTEUDO = frozenset(
    {"script", "style", "iframe", "object", "svg", "noscript", "head", "title", "form", "embed", "applet", "template"}
)
ATRIBUTOS_GERAIS = frozenset({"style", "align"})
ATRIBUTOS_POR_ETIQUETA = {
    "font": frozenset({"color", "size", "face"}),
    "td": frozenset({"colspan", "rowspan", "width"}),
    "th": frozenset({"colspan", "rowspan", "width"}),
    "table": frozenset({"border", "cellpadding", "cellspacing", "width"}),
    "a": frozenset({"href"}),
}
ESTILO_PROIBIDO = ("url(", "expression", "@import", "\\", "javascript")


_TAMANHO_ZERO = re.compile(r"(font-size\s*:\s*|font\s*:\s*)0*\.?0+(?:px|pt|em|%)?(?![\d.])", re.IGNORECASE)


def _tamanho_minimo(estilo: str) -> str:
    """Tamanho de letra zero (truque dos emails para texto oculto) passa a 1px: o Qt não aceita zero,
    e o texto continua praticamente invisível."""
    return _TAMANHO_ZERO.sub(lambda m: m.group(1) + "1px", estilo)


class _Filtro(HTMLParser):
    def __init__(self, permitir_link: Callable[[str], bool], imagens: bool, anexos_cid: frozenset[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.saida: list[str] = []
        self._ocultas = 0
        self._permitir_link = permitir_link
        self._imagens = imagens
        self._anexos_cid = anexos_cid

    def handle_starttag(self, tag, attrs):
        if tag in DESCARTADAS_COM_CONTEUDO:
            self._ocultas += 1
            return
        if self._ocultas:
            return
        if tag == "img":
            self.saida.append(self._imagem(dict(attrs)))
            return
        if tag not in ETIQUETAS:
            return
        self.saida.append(f"<{tag}{self._atributos(tag, attrs)}>")

    def handle_endtag(self, tag):
        if tag in DESCARTADAS_COM_CONTEUDO:
            self._ocultas = max(0, self._ocultas - 1)
            return
        if self._ocultas or tag not in ETIQUETAS or tag in VAZIAS:
            return
        self.saida.append(f"</{tag}>")

    def handle_data(self, dados):
        if not self._ocultas:
            self.saida.append(_html.escape(dados, quote=False))

    def _atributos(self, tag: str, attrs) -> str:
        permitidos = ATRIBUTOS_GERAIS | ATRIBUTOS_POR_ETIQUETA.get(tag, frozenset())
        partes = []
        for nome, valor in attrs:
            nome = nome.lower()
            if valor is None or nome not in permitidos:
                continue
            if nome == "style" and any(p in valor.lower() for p in ESTILO_PROIBIDO):
                continue
            if nome == "style":
                valor = _tamanho_minimo(valor)
            if nome == "size" and valor.strip() == "0":
                valor = "1"
            if nome == "href":
                if not self._ligacao_permitida(valor):
                    continue
            partes.append(f' {nome}="{_html.escape(valor, quote=True)}"')
        return "".join(partes)

    def _imagem(self, attrs: dict) -> str:
        """Com as imagens ligadas: as embutidas no email (cid:) e as de sites (http/https). O resto fica marcado."""
        bloqueada = "<span>[imagem bloqueada]</span>"
        if not self._imagens:
            return bloqueada
        origem = (attrs.get("src") or "").strip()
        if origem.lower().startswith("cid:"):
            nome = origem[4:]
            if nome in self._anexos_cid:
                return f'<img src="{_html.escape(CID_PREFIXO + nome, quote=True)}">'
            return "<span>[imagem em falta]</span>"
        if urlsplit(origem).scheme.lower() in ("http", "https") and urlsplit(origem).hostname:
            return f'<img src="{_html.escape(origem, quote=True)}">'
        return bloqueada

    def _ligacao_permitida(self, valor: str) -> bool:
        partes = urlsplit(valor.strip())
        if partes.scheme.lower() not in ("http", "https") or not partes.hostname:
            return False
        return self._permitir_link(partes.hostname)


CID_PREFIXO = "kikoia-cid:"


def sanitizar_html(
    texto: str,
    permitir_link: Callable[[str], bool] | None = None,
    imagens: bool = False,
    anexos_cid: frozenset[str] = frozenset(),
) -> str:
    """Devolve HTML seguro para mostrar. `permitir_link=None` deixa todas as ligações ativas.
    Com `imagens`, as imagens passam (embutidas, pelo identificador `anexos_cid`, ou de sites)."""
    filtro = _Filtro(permitir_link or (lambda _dominio: True), imagens, anexos_cid)
    filtro.feed(texto)
    filtro.close()
    return "".join(filtro.saida)
