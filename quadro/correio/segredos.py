"""Proteção de segredos por conta de utilizador:
- Windows: DPAPI (`CryptProtectData` / `CryptUnprotectData`), ligado à conta do utilizador.
- Linux: Fernet (AES-128-CBC + HMAC-SHA256) com chave aleatória de utilizador guardada com permissões `0600`.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import os
import secrets
import sys
from ctypes import wintypes
from pathlib import Path

from quadro.correio.modelo import ErroCorreio


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _executar_windows(dados: bytes, cifrar_modo: bool) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buffer = ctypes.create_string_buffer(dados, len(dados))
    entrada = _Blob(len(dados), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    saida = _Blob()
    funcao = crypt32.CryptProtectData if cifrar_modo else crypt32.CryptUnprotectData
    if not funcao(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)):
        raise ErroCorreio("correio.segredos_falhou")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(saida.pbData, ctypes.c_void_p))


def _caminho_chave_linux() -> Path:
    from quadro.paths import pasta_kikoia

    pasta = pasta_kikoia()
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / ".chave_segredos"


def _chave_fernet_linux() -> bytes:
    caminho = _caminho_chave_linux()
    semente: bytes | None = None
    if caminho.is_file():
        try:
            bruto = caminho.read_bytes()
            if len(bruto) >= 32:
                semente = bruto[:32]
        except OSError as erro:
            raise ErroCorreio("correio.segredos_falhou") from erro
    if semente is None:
        semente = secrets.token_bytes(32)
        temporario = caminho.with_suffix(".tmp")
        try:
            fd = os.open(str(temporario), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(semente)
            os.chmod(temporario, 0o600)
            os.replace(temporario, caminho)
        except OSError as erro:
            temporario.unlink(missing_ok=True)
            raise ErroCorreio("correio.segredos_falhou") from erro
    uid_sal = f"kikoia-segredos-uid-{getattr(os, 'getuid', lambda: 0)()}".encode("utf-8")
    derivada = hashlib.pbkdf2_hmac("sha256", semente, uid_sal, 120_000, dklen=32)
    return base64.urlsafe_b64encode(derivada)


def _executar_linux(dados: bytes, cifrar_modo: bool) -> bytes:
    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError as erro:
        raise ErroCorreio("correio.segredos_falhou") from erro
    f = Fernet(_chave_fernet_linux())
    if cifrar_modo:
        return f.encrypt(dados)
    try:
        return f.decrypt(dados)
    except (InvalidToken, ValueError, TypeError) as erro:
        raise ErroCorreio("correio.segredos_falhou") from erro


def _executar(dados: bytes, cifrar: bool) -> bytes:
    if sys.platform == "win32":
        return _executar_windows(dados, cifrar)
    return _executar_linux(dados, cifrar)


def cifrar(texto: str) -> bytes:
    return _executar(texto.encode("utf-8"), cifrar=True)


def decifrar(dados: bytes) -> str:
    try:
        return _executar(dados, cifrar=False).decode("utf-8")
    except UnicodeDecodeError as erro:
        raise ErroCorreio("correio.segredos_falhou") from erro
