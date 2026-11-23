"""Efeitos sonoros sintetizados (WAV) para os jogos integrados do Quadro.

Gera os ficheiros WAV uma única vez numa pasta temporária local e reproduz-os
com `winsound.PlaySound(..., SND_FILENAME | SND_ASYNC)` no Windows, evitando
os problemas de `SND_MEMORY | SND_ASYNC` no Windows 10/11.
"""

from __future__ import annotations

import io
import math
import os
import random
import struct
import sys
import tempfile
import wave
from pathlib import Path

_TAXA = 22050
_CACHE_BYTES: dict[str, bytes] = {}
_CACHE_FICHEIROS: dict[str, Path] = {}


def _empacotar_wav(amostras: list[float]) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_TAXA)
        dados = bytearray()
        for v in amostras:
            clamped = max(-1.0, min(1.0, v))
            dados.extend(struct.pack("<h", int(clamped * 32000)))
        w.writeframes(bytes(dados))
    return buf.getvalue()


def _gerar_embate() -> bytes:
    """Som 'boing/thud' bem audível e divertido de colisão com obstáculo (~0,32 s)."""
    dur = 0.32
    n = int(_TAXA * dur)
    amostras: list[float] = []
    fase = 0.0
    rng = random.Random(7)
    for i in range(n):
        t = i / _TAXA
        freq = 320.0 * math.exp(-t * 6.5) + 85.0
        fase += 2.0 * math.pi * freq / _TAXA
        env = math.exp(-t * 7.5) * (1.0 - math.exp(-t * 160.0))
        ruido = (rng.uniform(-1.0, 1.0) * 0.30 * math.exp(-t * 45.0)) if t < 0.06 else 0.0
        amostras.append((math.sin(fase) * 0.78 + math.sin(fase * 2.0) * 0.22) * env + ruido)
    return _empacotar_wav(amostras)


def _gerar_ding() -> bytes:
    """Sino cristalino curto ao concluir uma letra intermédia (~0,35 s)."""
    dur = 0.35
    n = int(_TAXA * dur)
    amostras: list[float] = []
    for i in range(n):
        t = i / _TAXA
        env = math.exp(-t * 8.0) * (1.0 - math.exp(-t * 180.0))
        v = (
            math.sin(2.0 * math.pi * 880.0 * t) * 0.58
            + math.sin(2.0 * math.pi * 1318.5 * t) * 0.32
            + math.sin(2.0 * math.pi * 1760.0 * t) * 0.16
        ) * env
        amostras.append(v)
    return _empacotar_wav(amostras)


def _gerar_aplausos() -> bytes:
    """Fanfarra alegre (Dó-Mi-Sol-Dó) acompanhada de aplausos bem audíveis (~1,6 s)."""
    dur = 1.60
    n = int(_TAXA * dur)
    amostras = [0.0] * n

    notas = [
        (0.00, 0.15, 523.25),   # C5
        (0.14, 0.15, 659.25),   # E5
        (0.28, 0.17, 783.99),   # G5
        (0.44, 0.65, 1046.50),  # C6
    ]
    for inicio, compr, freq in notas:
        i0 = int(inicio * _TAXA)
        i1 = min(n, int((inicio + compr) * _TAXA))
        for i in range(i0, i1):
            t = (i - i0) / _TAXA
            env = (1.0 - math.exp(-t * 95.0)) * math.exp(-t * 3.4)
            amostras[i] += (
                math.sin(2.0 * math.pi * freq * t) * 0.42
                + math.sin(2.0 * math.pi * freq * 2.0 * t) * 0.16
            ) * env

    rng = random.Random(42)
    for _ in range(58):
        inicio = rng.uniform(0.20, 1.38)
        i0 = int(inicio * _TAXA)
        dur_palma = rng.uniform(0.05, 0.09)
        i1 = min(n, i0 + int(dur_palma * _TAXA))
        amp = rng.uniform(0.08, 0.16)
        prev = 0.0
        for i in range(i0, i1):
            t = (i - i0) / _TAXA
            env = math.exp(-t * 34.0) * (1.0 - math.exp(-t * 300.0))
            branco = rng.uniform(-1.0, 1.0)
            filtrado = (branco - prev * 0.62) * 0.65
            prev = branco
            amostras[i] += filtrado * amp * env

    return _empacotar_wav(amostras)


def _obter_wav(nome: str) -> bytes:
    if nome not in _CACHE_BYTES:
        if nome == "embate":
            _CACHE_BYTES[nome] = _gerar_embate()
        elif nome == "ding":
            _CACHE_BYTES[nome] = _gerar_ding()
        elif nome == "aplausos":
            _CACHE_BYTES[nome] = _gerar_aplausos()
        else:
            return b""
    return _CACHE_BYTES[nome]


def _obter_ficheiro_wav(nome: str) -> Path | None:
    caminho = _CACHE_FICHEIROS.get(nome)
    if caminho is not None and caminho.is_file():
        return caminho
    dados = _obter_wav(nome)
    if not dados:
        return None
    pasta = Path(tempfile.gettempdir()) / "kikoia_sons"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{nome}_v2.wav"
    if not destino.is_file() or destino.stat().st_size != len(dados):
        destino.write_bytes(dados)
    _CACHE_FICHEIROS[nome] = destino
    return destino


def _tocar(nome: str) -> None:
    if sys.platform != "win32":
        return
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    caminho = _obter_ficheiro_wav(nome)
    if caminho is None:
        return
    try:
        import winsound

        winsound.PlaySound(
            str(caminho),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
    except Exception:
        pass


def tocar_embate() -> None:
    _tocar("embate")


def tocar_ding() -> None:
    _tocar("ding")


def tocar_aplausos() -> None:
    _tocar("aplausos")
