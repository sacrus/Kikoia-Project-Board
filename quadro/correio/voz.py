"""Leitura em voz alta no Quadro Interativo (Correio e Documentos).

- Windows: voz SAPI através do PowerShell (sem dependências extra), num Job Object com KILL_ON_JOB_CLOSE.
- Linux: voz neural Piper (reutilizando vozes instaladas pelo Teclado Kikoia ou no Quadro) com fallback
  para `spd-say` / `espeak-ng` / `espeak`.
- Em ambos os sistemas, o texto é enviado pela entrada padrão (`stdin`) e nunca faz parte da linha de comando.
- Só há uma leitura de cada vez: uma nova leitura substitui a anterior.
"""

from __future__ import annotations

import atexit
import ctypes
import os
import shutil
import signal
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

from quadro.correio.modelo import ErroCorreio

_SCRIPT = (
    "[Console]::InputEncoding = [Text.Encoding]::UTF8; "
    "$texto = [Console]::In.ReadToEnd(); "
    "Add-Type -AssemblyName System.Speech; "
    "$voz = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$voz.Speak($texto)"
)

_SCRIPT_PIPER_LINUX = """
import sys, numpy as np, sounddevice as sd
from piper import PiperVoice, SynthesisConfig
modelo, config = sys.argv[1], sys.argv[2]
texto = sys.stdin.buffer.read().decode("utf-8", "replace").strip()
if texto:
    voz = PiperVoice.load(modelo, config)
    cfg = SynthesisConfig(length_scale=1.35, noise_scale=0.4)
    blocos, taxa = [], 22050
    for b in voz.synthesize(texto, syn_config=cfg):
        taxa = b.sample_rate
        blocos.append(b.audio_float_array)
    if blocos:
        sil = np.zeros(int(taxa * 0.25), dtype=np.float32)
        sd.play(np.concatenate([sil, *blocos, sil]), taxa)
        sd.wait()
"""

_PASTAS_PIPER = {
    "pt-PT": ("piper-pt_PT", "pt_PT-tugao-medium.onnx", "pt_PT-tugao-medium.onnx.json"),
    "en": ("piper-en", "en_US-amy-medium.onnx", "en_US-amy-medium.onnx.json"),
    "es": ("piper-es", "es_ES-sharvard-medium.onnx", "es_ES-sharvard-medium.onnx.json"),
    "fr": ("piper-fr", "fr_FR-siwis-medium.onnx", "fr_FR-siwis-medium.onnx.json"),
}
_VOZES_ESPEAK = {
    "pt-PT": "pt-pt",
    "en": "en",
    "es": "es",
    "fr": "fr",
}

_SEM_JANELA = 0x08000000
_processo: subprocess.Popen | None = None
_job = None


class _IOCounters(ctypes.Structure):
    _fields_ = [(nome, ctypes.c_ulonglong) for nome in ("r", "rb", "ro", "w", "wb", "wo")]


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits),
        ("IoInfo", _IOCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def comando() -> list[str]:
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT]


def _procurar_voz_piper(idioma: str) -> tuple[Path, Path] | None:
    try:
        import piper  # noqa: F401
        import sounddevice  # noqa: F401
    except ImportError:
        return None
    xdg = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    from quadro.paths import pasta_quadro

    raizes = [xdg / "teclado" / "vozes", pasta_quadro() / "vozes"]
    for cod in (idioma, "pt-PT", "en", "es", "fr"):
        info = _PASTAS_PIPER.get(cod)
        if not info:
            continue
        sub, nome_mod, nome_cfg = info
        for raiz in raizes:
            mod = raiz / sub / nome_mod
            cfg = raiz / sub / nome_cfg
            if mod.is_file() and cfg.is_file():
                return mod, cfg
    return None


def comando_linux(idioma: str | None = None) -> list[str] | None:
    """Devolve o comando de síntese de voz disponível no Linux (sem o texto nos argumentos)."""
    if idioma is None:
        from quadro import idiomas

        idioma = idiomas.atual()
    par_piper = _procurar_voz_piper(idioma)
    if par_piper is not None:
        mod, cfg = par_piper
        return [sys.executable, "-c", _SCRIPT_PIPER_LINUX, str(mod), str(cfg)]
    voz_esp = _VOZES_ESPEAK.get(idioma, "pt-pt")
    for bin_esp in ("espeak-ng", "espeak"):
        caminho = shutil.which(bin_esp)
        if caminho:
            return [caminho, "--stdin", "-v", voz_esp]
    spd = shutil.which("spd-say")
    if spd:
        return [spd, "--wait", "--pipe-mode", "-l", voz_esp.split("-")[0]]
    return None


def _job_com_limpeza() -> int | None:
    """Um job que termina os processos associados quando o último handle deste programa fecha."""
    global _job
    if _job is not None:
        return _job
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # 9 = ExtendedLimit
        return None
    _job = job
    return job


def _associar_ao_job(processo: subprocess.Popen) -> None:
    job = _job_com_limpeza()
    if job is None:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.AssignProcessToJobObject(job, processo._handle)  # se falhar, parar() continua a funcionar


def parar() -> None:
    global _processo
    if _processo is not None and _processo.poll() is None:
        if sys.platform != "win32":
            try:
                os.killpg(os.getpgid(_processo.pid), signal.SIGTERM)
            except OSError:
                _processo.kill()
        else:
            _processo.kill()
        try:
            _processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _processo.kill()
    _processo = None


atexit.register(parar)


def falar(texto: str) -> subprocess.Popen | None:
    global _processo
    texto = texto.strip()
    parar()
    if not texto:
        return None
    if sys.platform == "win32":
        processo = subprocess.Popen(comando(), stdin=subprocess.PIPE, creationflags=_SEM_JANELA)
        _associar_ao_job(processo)
    else:
        cmd = comando_linux()
        if cmd is None:
            raise ErroCorreio("correio.voz_indisponivel")
        processo = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    assert processo.stdin is not None
    processo.stdin.write(texto.encode("utf-8"))
    processo.stdin.close()
    _processo = processo
    return processo


# Alias usado pelo módulo de Documentos (`janela_documentos.py`).
ler = falar
