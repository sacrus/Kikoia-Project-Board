"""Motor nativo Linux (100% offline após o 1.º uso e sem precisar de sudo) para PDF e OCR de documentos.

- PDF -> PNG: usa `PySide6.QtPdf.QPdfDocument` (integrado no PySide6, sem dependências externas),
  com fallback automático para `pdftoppm` (`poppler-utils`).
- OCR com coordenadas por linha: usa `tesseract` em modo TSV, devolvendo a mesma estrutura
  `ResultadoOCR` / `LinhaOCR` do motor Windows. Se o `tesseract` ainda não estiver instalado no
  sistema, descarrega e extrai automaticamente uma cópia local isolada em `~/.local/share/Kikoia/Quadro/ocr/`
  (com `pt-PT`, `en`, `es`, `fr`) a partir dos pacotes oficiais assinados da distribuição — sem `sudo`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QPainter

from quadro.documentos.motor_windows import ErroMotorDocumentos, LinhaOCR, ResultadoOCR

_MAPA_TESSERACT = {
    "pt-PT": "por",
    "pt": "por",
    "en": "eng",
    "es": "spa",
    "fr": "fra",
}
_PACOTES_IDIOMAS_APT = (
    "tesseract-ocr-por",
    "tesseract-ocr-eng",
    "tesseract-ocr-spa",
    "tesseract-ocr-fra",
)
_URL_TESSDATA_FAST = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/{cod}.traineddata"
_LOCK_INSTALACAO = threading.Lock()


def _pasta_ocr_local() -> Path:
    from quadro.paths import pasta_quadro

    return pasta_quadro() / "ocr"


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


def _descobrir_libs_tesseract_em_falta() -> list[str]:
    """Descobre dinamicamente `libtesseract*` e `liblept*` necessários e ainda não instalados no sistema."""
    apt_cache = shutil.which("apt-cache")
    if not apt_cache:
        return []
    em_falta: list[str] = []
    vistos: set[str] = set()
    fila = ["tesseract-ocr"]
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
            if dep.startswith(("libtesseract", "liblept")):
                if not _pacote_instalado_dpkg(dep):
                    if dep not in em_falta:
                        em_falta.append(dep)
                    fila.append(dep)
    return em_falta


def _ambiente_tesseract_local(raiz_ocr: Path) -> tuple[Path, Path, dict[str, str]] | None:
    """Devolve `(binario, pasta_tessdata, env)` se a instalação local em `raiz_ocr` estiver válida."""
    binario = raiz_ocr / "usr" / "bin" / "tesseract"
    if not (binario.is_file() and os.access(binario, os.X_OK)):
        return None
    candidatos_tessdata = sorted((raiz_ocr / "usr" / "share" / "tesseract-ocr").glob("*/tessdata"))
    if not candidatos_tessdata:
        cand_direto = raiz_ocr / "tessdata"
        if not cand_direto.is_dir():
            return None
        tessdata = cand_direto
    else:
        tessdata = candidatos_tessdata[-1]

    env = os.environ.copy()
    pastas_lib: list[str] = []
    usr_lib = raiz_ocr / "usr" / "lib"
    if usr_lib.is_dir():
        for sub in sorted(usr_lib.iterdir()):
            if sub.is_dir():
                pastas_lib.append(str(sub))
        pastas_lib.append(str(usr_lib))
    if pastas_lib:
        atual_ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = ":".join(pastas_lib + ([atual_ld] if atual_ld else []))
    env["TESSDATA_PREFIX"] = str(tessdata)
    return binario, tessdata, env


def _provisionar_tesseract_local() -> tuple[Path, Path, dict[str, str]] | None:
    """Transfere e extrai `tesseract-ocr` + bibliotecas + 4 idiomas em espaço do utilizador (sem sudo)."""
    with _LOCK_INSTALACAO:
        raiz_ocr = _pasta_ocr_local()
        existente = _ambiente_tesseract_local(raiz_ocr)
        if existente is not None:
            return existente

        apt_get = shutil.which("apt-get")
        dpkg_deb = shutil.which("dpkg-deb")
        if not (apt_get and dpkg_deb):
            return None

        pacotes = ["tesseract-ocr", *_descobrir_libs_tesseract_em_falta(), *_PACOTES_IDIOMAS_APT]
        raiz_ocr.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Usa /tmp com permissão 0755 para o download porque `apt-get download` pode usar o sandbox `_apt`,
            # que não tem acesso a `/home/<user>/.local/` (0700).
            with tempfile.TemporaryDirectory(prefix="kikoia-ocr-dl-") as tmp_str:
                tmp_dir = Path(tmp_str)
                tmp_dir.chmod(0o755)
                pasta_debs = tmp_dir / "debs"
                pasta_debs.mkdir(parents=True, exist_ok=True)
                pasta_debs.chmod(0o755)
                proc_dl = subprocess.run(
                    [apt_get, "download", *pacotes],
                    cwd=str(pasta_debs),
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if proc_dl.returncode != 0:
                    # Tenta pelo menos o núcleo + português e inglês caso algum pacote opcional falhe
                    pacotes_min = ["tesseract-ocr", *_descobrir_libs_tesseract_em_falta(), "tesseract-ocr-por", "tesseract-ocr-eng"]
                    proc_dl = subprocess.run(
                        [apt_get, "download", *pacotes_min],
                        cwd=str(pasta_debs),
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    if proc_dl.returncode != 0:
                        return None

                debs = sorted(pasta_debs.glob("*.deb"))
                if not debs:
                    return None
                extraido = tmp_dir / "root"
                extraido.mkdir(parents=True, exist_ok=True)
                for deb in debs:
                    proc_ex = subprocess.run(
                        [dpkg_deb, "-x", str(deb), str(extraido)],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if proc_ex.returncode != 0:
                        return None

                if raiz_ocr.exists():
                    shutil.rmtree(raiz_ocr)
                shutil.move(str(extraido), str(raiz_ocr))
        except (OSError, subprocess.TimeoutExpired):
            return None

        return _ambiente_tesseract_local(raiz_ocr)


def _garantir_modelo_idioma(cod_lang: str, pasta_tessdata: Path | None) -> Path | None:
    """Se faltar `<cod_lang>.traineddata`, transfere-o de `tessdata_fast` para cache do utilizador."""
    if pasta_tessdata is not None and (pasta_tessdata / f"{cod_lang}.traineddata").is_file():
        return pasta_tessdata
    destino_dir = pasta_tessdata if (pasta_tessdata is not None and os.access(pasta_tessdata, os.W_OK)) else (_pasta_ocr_local() / "tessdata")
    destino_arq = destino_dir / f"{cod_lang}.traineddata"
    if destino_arq.is_file():
        return destino_dir
    try:
        destino_dir.mkdir(parents=True, exist_ok=True)
        url = _URL_TESSDATA_FAST.format(cod=cod_lang)
        pedido = urllib.request.Request(url, headers={"User-Agent": "Kikoia-Quadro"})
        tmp = destino_arq.with_suffix(".tmp")
        with urllib.request.urlopen(pedido, timeout=30) as resp:
            dados = resp.read(25_000_000)
        if len(dados) > 100_000:
            tmp.write_bytes(dados)
            os.replace(tmp, destino_arq)
            return destino_dir
    except OSError:
        pass
    return pasta_tessdata


def _obter_motor_tesseract() -> tuple[str, Path | None, dict[str, str]]:
    """Localiza o `tesseract` do sistema ou aprovisiona automaticamente uma instalação local isolada."""
    bin_sistema = shutil.which("tesseract")
    if bin_sistema:
        env = os.environ.copy()
        return bin_sistema, None, env

    local = _ambiente_tesseract_local(_pasta_ocr_local()) or _provisionar_tesseract_local()
    if local is not None:
        bin_loc, tessdata_loc, env_loc = local
        return str(bin_loc), tessdata_loc, env_loc

    raise ErroMotorDocumentos(
        "OCR indisponível (verifique a ligação à internet no 1.º uso ou instale: sudo apt install tesseract-ocr tesseract-ocr-por)."
    )


def _escolher_idioma_tesseract(binario: str, idioma: str, pasta_tessdata: Path | None, env: dict[str, str]) -> tuple[str | None, Path | None]:
    alvo = _MAPA_TESSERACT.get(idioma, _MAPA_TESSERACT.get(idioma.split("-")[0], "por"))
    cmd_list = [binario]
    if pasta_tessdata is not None:
        cmd_list.extend(["--tessdata-dir", str(pasta_tessdata)])
    cmd_list.append("--list-langs")
    try:
        proc = subprocess.run(
            cmd_list,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        disponiveis = {
            linha.strip()
            for linha in proc.stdout.splitlines()
            if linha.strip() and not linha.lower().startswith("list of available")
        }
    except (OSError, subprocess.TimeoutExpired):
        disponiveis = set()

    if alvo in disponiveis:
        return alvo, pasta_tessdata

    # Tenta obter o modelo do idioma pedido automaticamente (ex.: `por.traineddata`)
    nova_pasta = _garantir_modelo_idioma(alvo, pasta_tessdata)
    if nova_pasta is not None and (nova_pasta / f"{alvo}.traineddata").is_file():
        return alvo, nova_pasta

    if not disponiveis:
        return alvo, pasta_tessdata
    for fallback in ("por", "eng", "spa", "fra"):
        if fallback in disponiveis:
            return fallback, pasta_tessdata
    disponiveis_sem_osd = sorted(disponiveis - {"osd", "equ"})
    return (disponiveis_sem_osd[0] if disponiveis_sem_osd else None), pasta_tessdata


def extrair_ocr_linux(caminho_imagem: Path, idioma: str = "pt-PT") -> ResultadoOCR:
    """Extrai texto e coordenadas normalizadas por linha usando Tesseract OCR offline (auto-instalável)."""
    caminho_img = Path(caminho_imagem).resolve()
    if not caminho_img.is_file():
        raise ErroMotorDocumentos("Imagem não encontrada.")

    binario, pasta_tessdata, env = _obter_motor_tesseract()

    img = QImage(str(caminho_img))
    largura = float(max(1, img.width()))
    altura = float(max(1, img.height()))

    cod_lang, dir_modelos = _escolher_idioma_tesseract(binario, idioma, pasta_tessdata, env)
    cmd = [binario, str(caminho_img), "stdout"]
    if dir_modelos is not None:
        cmd.extend(["--tessdata-dir", str(dir_modelos)])
    if cod_lang:
        cmd.extend(["-l", cod_lang])
    cmd.append("tsv")

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroMotorDocumentos(f"OCR falhou: {erro}") from erro

    if proc.returncode != 0:
        detalhe = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise ErroMotorDocumentos(detalhe[-1] if detalhe else "OCR indisponível.")

    grupos: dict[tuple[int, int, int, int], list[tuple[str, int, int, int, int]]] = {}
    ordem: list[tuple[int, int, int, int]] = []
    for idx, linha in enumerate(proc.stdout.splitlines()):
        if idx == 0 or not linha.strip():
            continue
        colunas = linha.split("\t")
        if len(colunas) < 12:
            continue
        try:
            nivel = int(colunas[0])
            page_n, block_n, par_n, line_n = int(colunas[1]), int(colunas[2]), int(colunas[3]), int(colunas[4])
            left, top, width, height = int(colunas[6]), int(colunas[7]), int(colunas[8]), int(colunas[9])
            conf = float(colunas[10])
        except ValueError:
            continue
        palavra = colunas[11].strip()
        if nivel != 5 or not palavra or conf < 0:
            continue
        chave = (page_n, block_n, par_n, line_n)
        if chave not in grupos:
            grupos[chave] = []
            ordem.append(chave)
        grupos[chave].append((palavra, left, top, width, height))

    linhas_ocr: list[LinhaOCR] = []
    for chave in ordem:
        palavras = grupos[chave]
        texto_linha = " ".join(p[0] for p in palavras).strip()
        if not texto_linha:
            continue
        min_x = min(p[1] for p in palavras)
        min_y = min(p[2] for p in palavras)
        max_x = max(p[1] + p[3] for p in palavras)
        max_y = max(p[2] + p[4] for p in palavras)
        linhas_ocr.append(
            LinhaOCR(
                texto=texto_linha,
                x=round(max(0.0, min_x) / largura, 4),
                y=round(max(0.0, min_y) / altura, 4),
                w=round(max(0.0, max_x - min_x) / largura, 4),
                h=round(max(0.0, max_y - min_y) / altura, 4),
            )
        )

    texto_total = "\n".join(l.texto for l in linhas_ocr)
    return ResultadoOCR(texto_total, linhas_ocr)


def renderizar_pdf_linux(caminho_pdf: Path, pasta_saida: Path) -> list[Path]:
    """Converte todas as páginas de um PDF em PNGs usando `PySide6.QtPdf` ou `pdftoppm`."""
    pdf = Path(caminho_pdf).resolve()
    if not pdf.is_file():
        raise ErroMotorDocumentos("Ficheiro PDF não encontrado.")
    pasta_saida.mkdir(parents=True, exist_ok=True)

    # 1. Motor integrado PySide6.QtPdf (rápido e sem processos externos)
    try:
        from PySide6.QtPdf import QPdfDocument

        doc = QPdfDocument()
        erro = doc.load(str(pdf))
        if erro == QPdfDocument.Error.None_ and doc.pageCount() > 0:
            caminhos: list[Path] = []
            try:
                for i in range(doc.pageCount()):
                    tam_pt = doc.pagePointSize(i)
                    larg_px = 1600
                    alt_px = max(1, round(larg_px * (tam_pt.height() / max(1.0, tam_pt.width()))))
                    renderizada = doc.render(i, QSize(larg_px, alt_px))
                    if renderizada.isNull():
                        continue
                    fundo = QImage(larg_px, alt_px, QImage.Format.Format_ARGB32)
                    fundo.fill(QColor("#FFFFFF"))
                    pintor = QPainter(fundo)
                    pintor.drawImage(0, 0, renderizada)
                    pintor.end()
                    destino = pasta_saida / f"pagina_{i + 1:03d}.png"
                    if fundo.save(str(destino), "PNG"):
                        caminhos.append(destino)
            finally:
                doc.close()
            if caminhos:
                return caminhos
    except ImportError:
        pass

    # 2. Fallback: pdftoppm (poppler-utils)
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise ErroMotorDocumentos(
            "Não foi possível abrir o PDF: instale PySide6-Pdf ou poppler-utils (pdftoppm)."
        )
    prefixo = pasta_saida / "pagina"
    try:
        proc = subprocess.run(
            [pdftoppm, "-png", "-r", "150", str(pdf), str(prefixo)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroMotorDocumentos(f"Falha ao abrir PDF: {erro}") from erro
    if proc.returncode != 0:
        detalhe = (proc.stderr or proc.stdout or "").strip()
        raise ErroMotorDocumentos(detalhe or "Não foi possível abrir o PDF.")
    return sorted(pasta_saida.glob("pagina*.png"))
