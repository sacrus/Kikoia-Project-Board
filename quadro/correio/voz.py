"""Leitura em voz alta com a voz SAPI do Windows (através do PowerShell, sem dependências extra).

- O texto é enviado pela entrada padrão e nunca faz parte da linha de comando.
- Só há uma leitura de cada vez: uma nova leitura substitui a anterior.
- O processo fica num «job» do Windows com a opção KILL_ON_JOB_CLOSE: quando o Quadro fecha
  (mesmo que termine de forma inesperada), o sistema termina a leitura.
"""

from __future__ import annotations

import atexit
import ctypes
import subprocess
import sys
from ctypes import wintypes

from quadro.correio.modelo import ErroCorreio

_SCRIPT = (
    "[Console]::InputEncoding = [Text.Encoding]::UTF8; "
    "$texto = [Console]::In.ReadToEnd(); "
    "Add-Type -AssemblyName System.Speech; "
    "$voz = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$voz.Speak($texto)"
)
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
        _processo.kill()
        try:
            _processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    _processo = None


atexit.register(parar)


def falar(texto: str) -> subprocess.Popen | None:
    global _processo
    if sys.platform != "win32":
        raise ErroCorreio("correio.voz_so_windows")
    texto = texto.strip()
    parar()
    if not texto:
        return None
    processo = subprocess.Popen(comando(), stdin=subprocess.PIPE, creationflags=_SEM_JANELA)
    _associar_ao_job(processo)
    assert processo.stdin is not None
    processo.stdin.write(texto.encode("utf-8"))
    processo.stdin.close()
    _processo = processo
    return processo
