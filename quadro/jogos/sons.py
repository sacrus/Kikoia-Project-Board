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
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

_TAXA = 22050
_CACHE_BYTES: dict[str, bytes] = {}
_CACHE_FICHEIROS: dict[str, Path] = {}
_EFEITOS_QT: dict[str, object] = {}
_PENDENTES_QT: set[str] = set()
_QT_AUDIO_OK: bool | None = None
_PROC_SOM_LINUX: subprocess.Popen | None = None
_CMD_SOM_LINUX: list[str] | None | bool = False

# 10 notas musicais doces (Dó4 a Mi5), uma para cada dedo das duas mãos
_NOTAS_DEDOS = (
    261.63,  # 0: Mindinho Esq (Dó4)
    293.66,  # 1: Anelar Esq   (Ré4)
    329.63,  # 2: Médio Esq    (Mi4)
    349.23,  # 3: Indicador Esq(Fá4)
    392.00,  # 4: Polegar Esq  (Sol4)
    440.00,  # 5: Polegar Dir  (Lá4)
    493.88,  # 6: Indicador Dir(Si4)
    523.25,  # 7: Médio Dir    (Dó5)
    587.33,  # 8: Anelar Dir   (Ré5)
    659.25,  # 9: Mindinho Dir (Mi5)
)


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


def _gerar_acorde(indices: tuple[int, ...]) -> bytes:
    """Nota ou acorde suave tipo xilofone/marimba para os dedos pedidos (~0,48 s)."""
    dur = 0.48
    n = int(_TAXA * dur)
    freqs = [_NOTAS_DEDOS[i % len(_NOTAS_DEDOS)] for i in indices] or [440.0]
    escala = 0.72 / max(1.0, math.sqrt(len(freqs)))
    amostras: list[float] = []
    for i in range(n):
        t = i / _TAXA
        env = (1.0 - math.exp(-t * 160.0)) * math.exp(-t * 5.8)
        soma = 0.0
        for f in freqs:
            soma += (
                math.sin(2.0 * math.pi * f * t) * 0.72
                + math.sin(2.0 * math.pi * f * 2.0 * t) * 0.22
                + math.sin(2.0 * math.pi * f * 3.0 * t) * 0.06
            )
        amostras.append(soma * escala * env)
    return _empacotar_wav(amostras)


def _gerar_musica_descanso() -> bytes:
    """Breve melodia alegre e relaxante (~4,2 s) para o período de descanso entre níveis."""
    dur = 4.20
    n = int(_TAXA * dur)
    amostras = [0.0] * n
    # Melodia doce tipo caixa de música / xilofone (Dó maior)
    melodia = [
        (0.00, 0.34, 523.25),  # C5
        (0.32, 0.34, 659.25),  # E5
        (0.64, 0.34, 783.99),  # G5
        (0.96, 0.48, 659.25),  # E5
        (1.42, 0.34, 587.33),  # D5
        (1.74, 0.34, 659.25),  # E5
        (2.06, 0.50, 523.25),  # C5
        (2.58, 0.34, 659.25),  # E5
        (2.90, 0.34, 783.99),  # G5
        (3.22, 0.85, 1046.50), # C6 (final brilhante e calmo)
    ]
    # Acompanhamento suave (baixo doce)
    baixos = [
        (0.00, 1.35, 261.63),  # C4
        (1.42, 1.10, 196.00),  # G3
        (2.58, 1.50, 261.63),  # C4
    ]
    for inicio, compr, freq in melodia:
        i0 = int(inicio * _TAXA)
        i1 = min(n, int((inicio + compr) * _TAXA))
        for i in range(i0, i1):
            t = (i - i0) / _TAXA
            env = (1.0 - math.exp(-t * 120.0)) * math.exp(-t * 4.2)
            amostras[i] += (
                math.sin(2.0 * math.pi * freq * t) * 0.36
                + math.sin(2.0 * math.pi * freq * 2.0 * t) * 0.12
            ) * env
    for inicio, compr, freq in baixos:
        i0 = int(inicio * _TAXA)
        i1 = min(n, int((inicio + compr) * _TAXA))
        for i in range(i0, i1):
            t = (i - i0) / _TAXA
            env = (1.0 - math.exp(-t * 40.0)) * math.exp(-t * 2.2)
            amostras[i] += math.sin(2.0 * math.pi * freq * t) * 0.16 * env
    return _empacotar_wav(amostras)


def _obter_wav(nome: str) -> bytes:
    if nome not in _CACHE_BYTES:
        if nome == "embate":
            _CACHE_BYTES[nome] = _gerar_embate()
        elif nome == "ding":
            _CACHE_BYTES[nome] = _gerar_ding()
        elif nome == "aplausos":
            _CACHE_BYTES[nome] = _gerar_aplausos()
        elif nome == "descanso":
            _CACHE_BYTES[nome] = _gerar_musica_descanso()
        elif nome.startswith("acorde_"):
            partes = tuple(int(p) for p in nome[7:].split("_") if p.isdigit())
            _CACHE_BYTES[nome] = _gerar_acorde(partes)
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


def _comando_audio_linux() -> list[str] | None:
    global _CMD_SOM_LINUX
    if _CMD_SOM_LINUX is not False:
        return _CMD_SOM_LINUX  # type: ignore[return-value]
    for cmd in (("pw-play",), ("paplay",), ("aplay", "-q")):
        caminho = shutil.which(cmd[0])
        if caminho:
            _CMD_SOM_LINUX = [caminho, *cmd[1:]]
            return _CMD_SOM_LINUX
    _CMD_SOM_LINUX = None
    return None


def _ao_mudar_estado_qt() -> None:
    """Função de nível de módulo (nunca recolhida pelo GC do PySide6) que dispara sons assim que ficam prontos."""
    from PySide6.QtMultimedia import QSoundEffect

    for nome in list(_PENDENTES_QT):
        ef = _EFEITOS_QT.get(nome)
        if ef is None:
            _PENDENTES_QT.discard(nome)
            continue
        estado = ef.status()  # type: ignore[attr-defined]
        if estado == QSoundEffect.Status.Ready:
            _PENDENTES_QT.discard(nome)
            ef.play()  # type: ignore[attr-defined]
        elif estado == QSoundEffect.Status.Error:
            _PENDENTES_QT.discard(nome)


def _obter_ou_criar_efeito_qt(nome: str, caminho: Path) -> object | None:
    global _QT_AUDIO_OK
    if _QT_AUDIO_OK is False:
        return None
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QMediaDevices, QSoundEffect
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return None
        if _QT_AUDIO_OK is None:
            _QT_AUDIO_OK = len(QMediaDevices.audioOutputs()) > 0
            if not _QT_AUDIO_OK:
                return None
        efeito = _EFEITOS_QT.get(nome)
        if efeito is None:
            se = QSoundEffect(app)
            se.setVolume(0.90)
            se.statusChanged.connect(_ao_mudar_estado_qt)
            se.setSource(QUrl.fromLocalFile(str(caminho)))
            _EFEITOS_QT[nome] = se
            efeito = se
        return efeito
    except Exception:
        _QT_AUDIO_OK = False
        return None


def precarregar(nomes: tuple[str, ...] = ("embate", "ding", "aplausos", "descanso")) -> None:
    """Pré-carrega os efeitos sonoros em memória ao abrir o jogo para latência zero logo na 1.ª vez."""
    if sys.platform == "win32" or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    for nome in nomes:
        caminho = _obter_ficheiro_wav(nome)
        if caminho is not None:
            _obter_ou_criar_efeito_qt(nome, caminho)


def _tocar_qt_linux(nome: str, caminho: Path) -> bool:
    """Reproduz WAV em memória via QtMultimedia (baixa latência e polifónico para notas musicais)."""
    efeito = _obter_ou_criar_efeito_qt(nome, caminho)
    if efeito is None:
        return False
    try:
        from PySide6.QtMultimedia import QSoundEffect

        # Ao tocar uma nota nova, pára eventual música de descanso ainda ativa
        if nome != "descanso":
            desc = _EFEITOS_QT.get("descanso")
            if desc is not None and getattr(desc, "isPlaying", lambda: False)():
                desc.stop()  # type: ignore[attr-defined]
        if efeito.status() == QSoundEffect.Status.Ready:  # type: ignore[attr-defined]
            efeito.play()  # type: ignore[attr-defined]
        else:
            _PENDENTES_QT.add(nome)
        return True
    except Exception:
        return False


def parar() -> None:
    """Interrompe qualquer som ou música de descanso em curso."""
    global _PROC_SOM_LINUX
    _PENDENTES_QT.clear()
    if sys.platform == "win32":
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        return
    for ef in list(_EFEITOS_QT.values()):
        try:
            if getattr(ef, "isPlaying", lambda: False)():
                ef.stop()  # type: ignore[attr-defined]
        except Exception:
            pass
    if _PROC_SOM_LINUX is not None and _PROC_SOM_LINUX.poll() is None:
        try:
            _PROC_SOM_LINUX.terminate()
        except OSError:
            pass
    _PROC_SOM_LINUX = None


def _tocar(nome: str) -> None:
    global _PROC_SOM_LINUX
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    caminho = _obter_ficheiro_wav(nome)
    if caminho is None:
        return
    if sys.platform == "win32":
        try:
            import winsound

            winsound.PlaySound(
                str(caminho),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except Exception:
            pass
        return
    if _tocar_qt_linux(nome, caminho):
        return
    cmd = _comando_audio_linux()
    if cmd is None:
        return
    try:
        if _PROC_SOM_LINUX is not None and _PROC_SOM_LINUX.poll() is None:
            _PROC_SOM_LINUX.terminate()
        _PROC_SOM_LINUX = subprocess.Popen(
            [*cmd, str(caminho)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def tocar_embate() -> None:
    _tocar("embate")


def tocar_ding() -> None:
    _tocar("ding")


def tocar_aplausos() -> None:
    _tocar("aplausos")


def tocar_acorde(indices_dedos: list[int] | tuple[int, ...]) -> None:
    chave = "acorde_" + "_".join(str(i) for i in sorted(set(indices_dedos)))
    _tocar(chave)


def tocar_musica_descanso() -> None:
    _tocar("descanso")
