"""Entrada com conta Microsoft ou Google (OAuth 2.0 com PKCE, sem palavra-passe da conta).

O utilizador entra no site do fornecedor, no navegador. O Quadro recebe a resposta numa porta local
(127.0.0.1) e troca-a por um token. Guarda-se só o token de renovação (cifrado, ver contas.py).
Os CLIENTE_* são os identificadores das aplicações registadas pela Kikoia nos fornecedores.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from quadro.correio.modelo import Conta, ErroCorreio, Servidor

CLIENTE_MICROSOFT = "46c00693-6c75-431b-b6c9-b662f610c1aa"
CLIENTE_GOOGLE = "826097671733-10hm8rc3ajtj7m745aam0idhg8hdfean.apps.googleusercontent.com"
TEMPO_LIMITE_LOGIN_S = 300
TEMPO_LIMITE_PEDIDO_S = 20
NOME_FICHEIRO_SEGREDO_GOOGLE = "oauth_google.json"

PROVEDORES = {
    "microsoft": {
        "cliente": CLIENTE_MICROSOFT,
        "autorizacao": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "escopos": "https://outlook.office.com/IMAP.AccessAsUser.All https://outlook.office.com/SMTP.Send offline_access openid email",
        "imap": ("outlook.office365.com", 993),
        "smtp": ("smtp.office365.com", 587),
        "smtp_ssl": False,
        "extra": {"prompt": "select_account"},
        "nome": "Microsoft",
    },
    "google": {
        "cliente": CLIENTE_GOOGLE,
        "autorizacao": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "escopos": "https://mail.google.com/ openid email",
        "imap": ("imap.gmail.com", 993),
        "smtp": ("smtp.gmail.com", 465),
        "smtp_ssl": True,
        "extra": {"access_type": "offline", "prompt": "consent"},
        "nome": "Google",
    },
}


def configurado(provedor: str) -> bool:
    return bool(PROVEDORES[provedor]["cliente"])


def _pasta_segredos() -> Path:
    raiz = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(raiz) / "Kikoia" / "Quadro"


def secreto(provedor: str) -> str | None:
    """Segredo do cliente, quando o fornecedor o exige. Fica num ficheiro local, fora do repositório:
    %LOCALAPPDATA%\\Kikoia\\Quadro\\oauth_google.json, com {"secreto": "..."}."""
    if provedor != "google":
        return None
    try:
        dados = json.loads((_pasta_segredos() / NOME_FICHEIRO_SEGREDO_GOOGLE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    valor = dados.get("secreto") if isinstance(dados, dict) else None
    return valor if isinstance(valor, str) and valor else None


def conta_do_provedor(provedor: str, endereco: str) -> Conta:
    config = PROVEDORES[provedor]
    return Conta(
        endereco=endereco,
        utilizador=endereco,
        imap=Servidor(*config["imap"]),
        smtp=Servidor(config["smtp"][0], config["smtp"][1], ssl=config["smtp_ssl"]),
        metodo=provedor,
    )


def gerar_pkce() -> tuple[str, str]:
    """Verificador secreto e o seu desafio (SHA-256), como manda o PKCE."""
    verificador = secrets.token_urlsafe(72)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verificador, desafio


def url_autorizacao(provedor: str, redirect_uri: str, desafio: str, estado: str) -> str:
    config = PROVEDORES[provedor]
    parametros = {
        "client_id": config["cliente"],
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": config["escopos"],
        "state": estado,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
        **config["extra"],
    }
    return config["autorizacao"] + "?" + urllib.parse.urlencode(parametros)


def xoauth2(usuario: str, token: str) -> str:
    """Cadeia SASL XOAUTH2 usada pelo IMAP e pelo SMTP."""
    return f"user={usuario}\x01auth=Bearer {token}\x01\x01"


def email_do_id_token(id_token: str) -> str:
    partes = id_token.split(".")
    if len(partes) < 2:
        return ""
    payload = partes[1] + "=" * (-len(partes[1]) % 4)
    try:
        dados = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (ValueError, TypeError):
        return ""
    return str(dados.get("email") or dados.get("preferred_username") or "").strip().lower()


def _pedido_token(url: str, campos: dict) -> dict:
    pedido = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(campos).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE_PEDIDO_S) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        raise ErroCorreio("correio.oauth_falhou") from erro
    except (OSError, ValueError) as erro:
        raise ErroCorreio("correio.sem_ligacao") from erro
    if not isinstance(dados, dict):
        raise ErroCorreio("correio.oauth_falhou")
    return dados


def _resposta_do_navegador(query: dict) -> tuple[str | None, str | None, str | None]:
    codigo = query.get("code", [None])[0]
    estado = query.get("state", [None])[0]
    erro = query.get("error", [None])[0]
    return codigo, estado, erro


class _Recebedor(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (nome exigido pelo http.server)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        self.server.resposta = _resposta_do_navegador(query)
        corpo = "<html><body><p>Pode fechar esta janela e voltar ao Quadro.</p></body></html>".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *_args) -> None:
        pass


def entrar(provedor: str) -> tuple[str, str]:
    """Abre o navegador, espera a confirmação e devolve (endereço, token de renovação).
    Bloqueia até ao fim da entrada: deve correr fora da janela principal."""
    if not configurado(provedor):
        raise ErroCorreio("correio.oauth_nao_configurado")
    config = PROVEDORES[provedor]
    verificador, desafio = gerar_pkce()
    estado = secrets.token_urlsafe(24)
    servidor = HTTPServer(("127.0.0.1", 0), _Recebedor)
    servidor.timeout = TEMPO_LIMITE_LOGIN_S
    servidor.resposta = None
    try:
        anfitriao = "localhost" if provedor == "microsoft" else "127.0.0.1"
        redirect_uri = f"http://{anfitriao}:{servidor.server_port}/"
        webbrowser.open(url_autorizacao(provedor, redirect_uri, desafio, estado))
        servidor.handle_request()
        resposta = servidor.resposta
    finally:
        servidor.server_close()
    if resposta is None:
        raise ErroCorreio("correio.oauth_expirou")
    codigo, estado_recebido, erro = resposta
    if erro or not codigo or estado_recebido != estado:
        raise ErroCorreio("correio.oauth_cancelado")
    campos = {
        "grant_type": "authorization_code",
        "client_id": config["cliente"],
        "code": codigo,
        "redirect_uri": redirect_uri,
        "code_verifier": verificador,
    }
    segredo = secreto(provedor)
    if segredo:
        campos["client_secret"] = segredo
    dados = _pedido_token(config["token"], campos)
    if provedor == "google" and "https://mail.google.com/" not in str(dados.get("scope", "")).split():
        raise ErroCorreio("correio.oauth_sem_correio")
    renovacao = dados.get("refresh_token")
    if not isinstance(renovacao, str) or not renovacao:
        raise ErroCorreio("correio.oauth_sem_renovacao")
    endereco = email_do_id_token(str(dados.get("id_token", "")))
    if not endereco:
        raise ErroCorreio("correio.oauth_sem_email")
    return endereco, renovacao


def renovar(provedor: str, renovacao: str) -> tuple[str, str]:
    """Obtém um token de acesso novo. Devolve (token de acesso, token de renovação a guardar)."""
    config = PROVEDORES[provedor]
    campos = {"grant_type": "refresh_token", "client_id": config["cliente"], "refresh_token": renovacao}
    segredo = secreto(provedor)
    if segredo:
        campos["client_secret"] = segredo
    dados = _pedido_token(config["token"], campos)
    acesso = dados.get("access_token")
    if not isinstance(acesso, str) or not acesso:
        raise ErroCorreio("correio.oauth_expirou")
    return acesso, str(dados.get("refresh_token") or renovacao)
