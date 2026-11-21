"""Proteção de segredos com o DPAPI do Windows: só a conta do utilizador que os guardou os consegue ler."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from quadro.correio.modelo import ErroCorreio


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _executar(dados: bytes, cifrar: bool) -> bytes:
    if sys.platform != "win32":
        raise ErroCorreio("correio.segredos_so_windows")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buffer = ctypes.create_string_buffer(dados, len(dados))
    entrada = _Blob(len(dados), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    saida = _Blob()
    funcao = crypt32.CryptProtectData if cifrar else crypt32.CryptUnprotectData
    if not funcao(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)):
        raise ErroCorreio("correio.segredos_falhou")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(saida.pbData, ctypes.c_void_p))


def cifrar(texto: str) -> bytes:
    return _executar(texto.encode("utf-8"), cifrar=True)


def decifrar(dados: bytes) -> str:
    return _executar(dados, cifrar=False).decode("utf-8")
