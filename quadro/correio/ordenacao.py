"""Ordenação da lista de mensagens (feita no computador, sobre as mensagens já carregadas)."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from quadro.correio.modelo import Mensagem

CRITERIOS = (
    ("recentes", "Mais recentes primeiro"),
    ("antigas", "Mais antigas primeiro"),
    ("remetente", "Remetente (A–Z)"),
    ("assunto", "Assunto (A–Z)"),
    ("nao_lidas", "Por ler primeiro"),
)
_MINIMO = datetime.min.replace(tzinfo=timezone.utc)


def _data(mensagem: Mensagem) -> datetime:
    try:
        data = parsedate_to_datetime(mensagem.data)
    except (TypeError, ValueError, IndexError):
        return _MINIMO
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data


def ordenar(mensagens: list[Mensagem], criterio: str) -> list[Mensagem]:
    if criterio == "antigas":
        return sorted(mensagens, key=_data)
    if criterio == "remetente":
        return sorted(mensagens, key=lambda m: m.remetente.lower())
    if criterio == "assunto":
        return sorted(mensagens, key=lambda m: m.assunto.lower())
    if criterio == "nao_lidas":
        return sorted(mensagens, key=lambda m: (m.lida, -_data(m).timestamp()))
    return sorted(mensagens, key=_data, reverse=True)
