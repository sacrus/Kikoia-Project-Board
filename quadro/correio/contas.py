"""Conta de correio guardada no computador e preferências do correio.

A palavra-passe fica cifrada com o DPAPI (ver segredos.py). Os restantes dados ficam em JSON.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from quadro.correio import oauth, segredos
from quadro.correio.modelo import Conta, ErroCorreio, Servidor

# Tudo ligado por omissão. Com uma palavra-passe de supervisor, as opções «html», «imagens» e «anexos»
# começam desligadas, e só o supervisor as liga (ver janela_correio.py).
PREFERENCIAS_OMISSAO = {
    "bolha": True,
    "avisar": True,
    "intervalo_min": 5,
    "html": True,
    "imagens": True,
    "anexos": True,
    "assinatura": "",
}


def pasta(base: Path | None = None) -> Path:
    if base is not None:
        base.mkdir(parents=True, exist_ok=True)
        return base
    raiz = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    destino = Path(raiz) / "Kikoia" / "Quadro" / "correio"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _escrever(caminho: Path, dados: dict) -> None:
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(temporario, caminho)


def _ler(caminho: Path) -> dict | None:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def _pasta_contas(base: Path | None = None) -> Path:
    destino = pasta(base) / "contas"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _pasta_de_conta(endereco: str, base: Path | None = None) -> Path:
    nome = re.sub(r"[^a-z0-9@._-]", "_", endereco.strip().lower())
    return _pasta_contas(base) / nome


def _migrar(base: Path | None = None) -> None:
    """Versões anteriores guardavam uma só conta na pasta do correio. Passa-a para a pasta de contas."""
    legado = pasta(base) / "conta.json"
    if not legado.is_file():
        return
    dados = _ler(legado)
    if dados is None or not isinstance(dados.get("endereco"), str):
        return
    destino = _pasta_de_conta(dados["endereco"], base)
    destino.mkdir(parents=True, exist_ok=True)
    os.replace(legado, destino / "conta.json")
    if (pasta(base) / "senha.bin").is_file():
        os.replace(pasta(base) / "senha.bin", destino / "senha.bin")


def listar_enderecos(base: Path | None = None) -> list[str]:
    """Endereços das contas guardadas, por ordem alfabética."""
    _migrar(base)
    enderecos = []
    for pasta_conta in _pasta_contas(base).iterdir():
        dados = _ler(pasta_conta / "conta.json") if pasta_conta.is_dir() else None
        if dados and isinstance(dados.get("endereco"), str) and (pasta_conta / "senha.bin").is_file():
            enderecos.append(dados["endereco"])
    return sorted(enderecos, key=str.lower)


def guardar(conta: Conta, palavra_passe: str, base: Path | None = None) -> None:
    pasta_conta = _pasta_de_conta(conta.endereco, base)
    pasta_conta.mkdir(parents=True, exist_ok=True)
    _escrever(
        pasta_conta / "conta.json",
        {
            "endereco": conta.endereco,
            "utilizador": conta.utilizador,
            "metodo": conta.metodo,
            "protocolo": conta.protocolo,
            "imap": {"servidor": conta.imap.servidor, "porta": conta.imap.porta, "ssl": conta.imap.ssl},
            "smtp": {"servidor": conta.smtp.servidor, "porta": conta.smtp.porta, "ssl": conta.smtp.ssl},
        },
    )
    (pasta_conta / "senha.bin").write_bytes(segredos.cifrar(palavra_passe))


def carregar(base: Path | None = None, endereco: str | None = None) -> tuple[Conta, str] | None:
    """A conta pedida (ou a primeira guardada, se não for indicada). None se não houver conta."""
    _migrar(base)
    if endereco is None:
        enderecos = listar_enderecos(base)
        if not enderecos:
            return None
        endereco = enderecos[0]
    pasta_conta = _pasta_de_conta(endereco, base)
    dados = _ler(pasta_conta / "conta.json")
    senha_ficheiro = pasta_conta / "senha.bin"
    if dados is None or not senha_ficheiro.is_file():
        return None
    try:
        conta = Conta(
            endereco=str(dados["endereco"]),
            utilizador=str(dados["utilizador"]),
            imap=Servidor(str(dados["imap"]["servidor"]), int(dados["imap"]["porta"]), bool(dados["imap"].get("ssl", True))),
            smtp=Servidor(str(dados["smtp"]["servidor"]), int(dados["smtp"]["porta"]), bool(dados["smtp"].get("ssl", True))),
            metodo=str(dados.get("metodo", "palavra_passe")),
            protocolo=str(dados.get("protocolo", "imap")) if dados.get("protocolo") in ("imap", "pop3") else "imap",
        )
    except (KeyError, TypeError, ValueError):
        return None
    try:
        segredo = segredos.decifrar(senha_ficheiro.read_bytes())
    except (OSError, ErroCorreio):
        return None
    if conta.metodo in oauth.PROVEDORES:
        return _com_token(conta, segredo, senha_ficheiro)
    return conta, segredo


def _com_token(conta: Conta, renovacao: str, senha_ficheiro: Path) -> tuple[Conta, str]:
    """Conta OAuth: troca o token de renovação por um token de acesso. Se falhar, devolve token vazio
    (o login then recusa, e o utilizador vê a mensagem de autenticação)."""
    try:
        acesso, nova = oauth.renovar(conta.metodo, renovacao)
    except ErroCorreio:
        return conta, ""
    if nova != renovacao:
        senha_ficheiro.write_bytes(segredos.cifrar(nova))
    return conta, acesso


def apagar(base: Path | None = None, endereco: str | None = None) -> None:
    """Apaga a conta indicada (ou a primeira, se não for indicada). As outras contas não são tocadas."""
    _migrar(base)
    if endereco is None:
        enderecos = listar_enderecos(base)
        if not enderecos:
            return
        endereco = enderecos[0]
    pasta_conta = _pasta_de_conta(endereco, base)
    for nome in ("conta.json", "senha.bin"):
        (pasta_conta / nome).unlink(missing_ok=True)
    try:
        pasta_conta.rmdir()
    except OSError:
        pass


def preferencias(base: Path | None = None) -> dict:
    dados = _ler(pasta(base) / "preferencias.json") or {}
    resultado = dict(PREFERENCIAS_OMISSAO)
    for chave in PREFERENCIAS_OMISSAO:
        if chave in dados and type(dados[chave]) is type(PREFERENCIAS_OMISSAO[chave]):
            resultado[chave] = dados[chave]
    resultado["intervalo_min"] = max(1, min(60, int(resultado["intervalo_min"])))
    return resultado


def guardar_preferencias(valores: dict, base: Path | None = None) -> None:
    _escrever(pasta(base) / "preferencias.json", {**PREFERENCIAS_OMISSAO, **valores})
