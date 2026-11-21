"""JPEG XL (.jxl): importar e exportar desenhos e imagens.

Usa as ferramentas oficiais da libjxl (cjxl e djxl, licença BSD-3), que vêm na pasta «ferramentas»
ao lado do Quadro. O Quadro não precisa de plugins do Qt para ler e gravar JPEG XL.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QImage

from quadro.modelo import Quadro

EXTENSAO = ".jxl"
PASTA_FERRAMENTAS = "ferramentas"


def _pasta_ferramentas() -> Path:
    # Em desenvolvimento: Board/ferramentas. Na aplicação instalada: junto ao executável.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / PASTA_FERRAMENTAS
    return Path(__file__).resolve().parent.parent / PASTA_FERRAMENTAS


def ferramenta(nome: str) -> Path | None:
    caminho = _pasta_ferramentas() / f"{nome}.exe"
    return caminho if caminho.is_file() else None


def disponivel() -> bool:
    return ferramenta("cjxl") is not None and ferramenta("djxl") is not None


def _executar(argumentos: list[str]) -> None:
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    resultado = subprocess.run(argumentos, capture_output=True, creationflags=creationflags, timeout=120)
    if resultado.returncode != 0:
        detalhe = resultado.stderr.decode("utf-8", "replace").strip().splitlines()
        raise OSError(f"a conversão JPEG XL falhou ({detalhe[-1] if detalhe else resultado.returncode})")


def png_para_jxl(png: Path, jxl: Path) -> None:
    """Sem perdas: a imagem fica igual, com menos espaço do que o PNG."""
    cjxl = ferramenta("cjxl")
    if cjxl is None:
        raise OSError("as ferramentas JPEG XL não estão instaladas (pasta «ferramentas»)")
    _executar([str(cjxl), str(png), str(jxl), "-d", "0", "-e", "7", "--quiet"])


def jxl_para_png(jxl: Path, png: Path) -> None:
    djxl = ferramenta("djxl")
    if djxl is None:
        raise OSError("as ferramentas JPEG XL não estão instaladas (pasta «ferramentas»)")
    _executar([str(djxl), str(jxl), str(png), "--quiet"])


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
