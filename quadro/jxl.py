"""JPEG XL (.jxl): importar e exportar desenhos e imagens.

- Windows: usa `cjxl.exe` e `djxl.exe` na pasta `ferramentas` ao lado do Quadro (ou no PATH).
- Linux: usa `cjxl` e `djxl` da pasta `ferramentas`, do sistema (`libjxl-tools`), ou aprovisiona
  automaticamente uma cópia local isolada sem `sudo` em `~/.local/share/Kikoia/Quadro/jxl/`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtGui import QImage

from quadro.modelo import Quadro

EXTENSAO = ".jxl"
PASTA_FERRAMENTAS = "ferramentas"
_LOCK_JXL = threading.Lock()
_TENTOU_PROVISIONAR = False


def _pasta_ferramentas() -> Path:
    # Em desenvolvimento: Board/ferramentas. Na aplicação instalada: junto ao executável.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / PASTA_FERRAMENTAS
    return Path(__file__).resolve().parent.parent / PASTA_FERRAMENTAS


def _pasta_jxl_local() -> Path:
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "kikoia" / "jxl"


def _pacote_instalado_dpkg(nome: str) -> bool:
    dpkg_query = shutil.which("dpkg-query")
    if not dpkg_query:
        return False
    try:
        proc = subprocess.run(
            [dpkg_query, "-W", "-f=${Status}", nome],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0 and "install ok installed" in proc.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def _descobrir_deps_jxl() -> list[str]:
    apt_cache = shutil.which("apt-cache")
    if not apt_cache:
        return []
    em_falta: list[str] = []
    vistos: set[str] = set()
    fila = ["libjxl-tools"]
    env_c = {**os.environ, "LC_ALL": "C"}
    while fila:
        atual = fila.pop(0)
        if atual in vistos:
            continue
        vistos.add(atual)
        try:
            proc = subprocess.run(
                [
                    apt_cache,
                    "depends",
                    "--no-recommends",
                    "--no-suggests",
                    "--no-conflicts",
                    "--no-breaks",
                    "--no-replaces",
                    "--no-enhances",
                    atual,
                ],
                env=env_c,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        for linha in proc.stdout.splitlines():
            limpa = linha.strip()
            if not limpa.startswith("Depends:"):
                continue
            dep = limpa.split(":", 1)[1].strip()
            if dep.startswith("<") or dep in vistos:
                continue
            if dep.startswith(("libjxl", "libhwy", "libtcmalloc", "libbrotli")):
                if not _pacote_instalado_dpkg(dep):
                    if dep not in em_falta:
                        em_falta.append(dep)
                    fila.append(dep)
    return em_falta


def _provisionar_jxl_linux() -> None:
    global _TENTOU_PROVISIONAR
    with _LOCK_JXL:
        if _TENTOU_PROVISIONAR:
            return
        _TENTOU_PROVISIONAR = True
        raiz = _pasta_jxl_local()
        if (raiz / "usr" / "bin" / "cjxl").is_file() and (raiz / "usr" / "bin" / "djxl").is_file():
            return
        apt_get = shutil.which("apt-get")
        dpkg_deb = shutil.which("dpkg-deb")
        if not (apt_get and dpkg_deb):
            return
        pacotes = ["libjxl-tools", *_descobrir_deps_jxl()]
        raiz.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="kikoia-jxl-dl-") as tmp_str:
                tmp_dir = Path(tmp_str)
                tmp_dir.chmod(0o755)
                debs_dir = tmp_dir / "debs"
                debs_dir.mkdir(parents=True, exist_ok=True)
                debs_dir.chmod(0o755)
                proc_dl = subprocess.run(
                    [apt_get, "download", *pacotes],
                    cwd=str(debs_dir),
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if proc_dl.returncode != 0:
                    return
                debs = sorted(debs_dir.glob("*.deb"))
                if not debs:
                    return
                extraido = tmp_dir / "root"
                extraido.mkdir(parents=True, exist_ok=True)
                for deb in debs:
                    proc_ex = subprocess.run(
                        [dpkg_deb, "-x", str(deb), str(extraido)],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if proc_ex.returncode != 0:
                        return
                if raiz.exists():
                    shutil.rmtree(raiz)
                shutil.move(str(extraido), str(raiz))
        except (OSError, subprocess.TimeoutExpired):
            return


def _env_execucao() -> dict[str, str]:
    env = os.environ.copy()
    if sys.platform == "win32":
        return env
    raiz = _pasta_jxl_local()
    usr_lib = raiz / "usr" / "lib"
    if usr_lib.is_dir():
        pastas = [str(sub) for sub in sorted(usr_lib.iterdir()) if sub.is_dir()] + [str(usr_lib)]
        atual = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = ":".join(pastas + ([atual] if atual else []))
    return env


def ferramenta(nome: str) -> Path | None:
    if sys.platform == "win32":
        caminho = _pasta_ferramentas() / f"{nome}.exe"
        if caminho.is_file():
            return caminho
        sistema = shutil.which(nome)
        return Path(sistema) if sistema else None

    caminho = _pasta_ferramentas() / nome
    if caminho.is_file() and os.access(caminho, os.X_OK):
        return caminho
    sistema = shutil.which(nome)
    if sistema:
        return Path(sistema)
    local_bin = _pasta_jxl_local() / "usr" / "bin" / nome
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return local_bin
    _provisionar_jxl_linux()
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return local_bin
    return None


def disponivel() -> bool:
    return ferramenta("cjxl") is not None and ferramenta("djxl") is not None


def _executar(argumentos: list[str]) -> None:
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    resultado = subprocess.run(
        argumentos,
        capture_output=True,
        creationflags=creationflags,
        env=_env_execucao(),
        timeout=120,
    )
    if resultado.returncode != 0:
        detalhe = resultado.stderr.decode("utf-8", "replace").strip().splitlines()
        raise OSError(f"a conversão JPEG XL falhou ({detalhe[-1] if detalhe else resultado.returncode})")


def png_para_jxl(png: Path, jxl_dest: Path) -> None:
    """Sem perdas: a imagem fica igual, com menos espaço do que o PNG."""
    cjxl = ferramenta("cjxl")
    if cjxl is None:
        raise OSError("as ferramentas JPEG XL não estão instaladas (pasta «ferramentas»)")
    _executar([str(cjxl), str(png), str(jxl_dest), "-d", "0", "-e", "7", "--quiet"])


def jxl_para_png(jxl_orig: Path, png: Path) -> None:
    djxl = ferramenta("djxl")
    if djxl is None:
        raise OSError("as ferramentas JPEG XL não estão instaladas (pasta «ferramentas»)")
    _executar([str(djxl), str(jxl_orig), str(png), "--quiet"])


def abrir_imagem(caminho: Path) -> QImage:
    """Abre uma imagem qualquer, incluindo JPEG XL. Devolve uma imagem nula se não conseguir."""
    if caminho.suffix.lower() != EXTENSAO:
        return QImage(str(caminho))
    temporaria = caminho.with_suffix(".convertida.png")
    try:
        jxl_para_png(caminho, temporaria)
        return QImage(str(temporaria))
    except OSError:
        return QImage()
    finally:
        temporaria.unlink(missing_ok=True)


def exportar_jxl(quadro: Quadro, caminho: Path, largura: int, altura: int) -> None:
    """Exporta o desenho em JPEG XL sem perdas (renderizado como PNG e depois convertido)."""
    from quadro.desenho import exportar_png

    temporaria = caminho.with_suffix(".convertida.png")
    try:
        exportar_png(quadro, temporaria, largura, altura)
        png_para_jxl(temporaria, caminho)
    finally:
        temporaria.unlink(missing_ok=True)
