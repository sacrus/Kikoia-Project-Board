"""Motor nativo Windows 10/11 (100% offline e gratuito) para OCR, renderização de PDF e limpeza de fotos.

Usa diretamente as APIs WinRT integradas no Windows 10/11:
- `Windows.Media.Ocr.OcrEngine` para extração de texto (OCR) com coordenadas por linha.
- `Windows.Data.Pdf.PdfDocument` para converter páginas de PDF em imagens PNG de alta qualidade.
Não requer bibliotecas externas nem chaves de API.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QColor, QImage

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_SCRIPT_OCR = r"""
param([string]$ImgPath, [string]$LangTag)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImgPath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$w = [double]$bitmap.PixelWidth
$h = [double]$bitmap.PixelHeight

$engine = $null
if ($LangTag) {
    try {
        $lang = [Windows.Globalization.Language]::new($LangTag)
        if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($lang)) {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
        }
    } catch {}
}
if ($null -eq $engine) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if ($null -eq $engine) {
    throw "Nenhum pacote de idioma OCR instalado no Windows."
}

$res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$linhas = @()
foreach ($line in $res.Lines) {
    $minX = 1e9; $minY = 1e9; $maxX = 0.0; $maxY = 0.0
    foreach ($word in $line.Words) {
        $r = $word.BoundingRect
        if ($r.X -lt $minX) { $minX = $r.X }
        if ($r.Y -lt $minY) { $minY = $r.Y }
        if (($r.X + $r.Width) -gt $maxX) { $maxX = $r.X + $r.Width }
        if (($r.Y + $r.Height) -gt $maxY) { $maxY = $r.Y + $r.Height }
    }
    if ($minX -gt 1e8) { $minX = 0; $minY = 0 }
    $linhas += [PSCustomObject]@{
        texto = $line.Text
        x = [Math]::Round($minX / [Math]::Max(1.0, $w), 4)
        y = [Math]::Round($minY / [Math]::Max(1.0, $h), 4)
        w = [Math]::Round(([Math]::Max(0.0, $maxX - $minX)) / [Math]::Max(1.0, $w), 4)
        h = [Math]::Round(([Math]::Max(0.0, $maxY - $minY)) / [Math]::Max(1.0, $h), 4)
    }
}
$out = [PSCustomObject]@{
    texto = ($linhas | ForEach-Object { $_.texto }) -join "`n"
    linhas = $linhas
}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$out | ConvertTo-Json -Depth 4 -Compress
"""

_SCRIPT_PDF = r"""
param([string]$PdfPath, [string]$OutDir)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFolder, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime]
$null = [Windows.Data.Pdf.PdfPageRenderOptions, Windows.Data.Pdf, ContentType=WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
$asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
})[0]
function AwaitOp($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}
function AwaitAct($WinRtTask) {
    $netTask = $asTaskAction.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$pdfFile = AwaitOp ([Windows.Storage.StorageFile]::GetFileFromPathAsync($PdfPath)) ([Windows.Storage.StorageFile])
$pdfDoc = AwaitOp ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($pdfFile)) ([Windows.Data.Pdf.PdfDocument])
$outFolder = AwaitOp ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync($OutDir)) ([Windows.Storage.StorageFolder])

$caminhos = @()
for ($i = 0; $i -lt $pdfDoc.PageCount; $i++) {
    $page = $pdfDoc.GetPage($i)
    $nome = ("pagina_{0:D3}.png" -f ($i + 1))
    $imgFile = AwaitOp ($outFolder.CreateFileAsync($nome, [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
    $stream = AwaitOp ($imgFile.OpenAsync([Windows.Storage.FileAccessMode]::ReadWrite)) ([Windows.Storage.Streams.IRandomAccessStream])
    $opts = [Windows.Data.Pdf.PdfPageRenderOptions]::new()
    $opts.DestinationWidth = [uint32]1600
    AwaitAct ($page.RenderToStreamAsync($stream, $opts))
    $stream.Dispose()
    $page.Dispose()
    $caminhos += $imgFile.Path
}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
ConvertTo-Json -InputObject $caminhos -Compress
"""


@dataclass(frozen=True)
class LinhaOCR:
    texto: str
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class ResultadoOCR:
    texto: str
    linhas: list[LinhaOCR]


class ErroMotorDocumentos(RuntimeError):
    """Erro ao processar PDF ou OCR."""


def _executar_powershell(script: str, argumentos: list[str], timeout_s: int = 45) -> str:
    if sys.platform != "win32":
        raise ErroMotorDocumentos("Esta funcionalidade nativa só está disponível no Windows.")
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script, *argumentos]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroMotorDocumentos(f"Falha ao executar motor do Windows: {erro}") from erro
    if proc.returncode != 0:
        detalhe = (proc.stderr or proc.stdout or "").strip().splitlines()
        msg = detalhe[-1] if detalhe else "erro desconhecido"
        raise ErroMotorDocumentos(msg)
    return proc.stdout.strip()


def extrair_ocr(caminho_imagem: Path, idioma: str = "pt-PT") -> ResultadoOCR:
    """Extrai texto e coordenadas de uma imagem (Windows.Media.Ocr no Windows; Tesseract no Linux)."""
    if sys.platform != "win32":
        from quadro.documentos.motor_linux import extrair_ocr_linux

        return extrair_ocr_linux(caminho_imagem, idioma)
    import tempfile

    caminho_img = Path(caminho_imagem).resolve()
    if not caminho_img.is_file():
        raise ErroMotorDocumentos("Imagem não encontrada.")
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", encoding="utf-8", delete=False) as f:
        f.write(_SCRIPT_OCR)
        script_path = Path(f.name)
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(script_path), "-ImgPath", str(caminho_img), "-LangTag", idioma,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            creationflags=_NO_WINDOW,
        )
        if proc.returncode != 0:
            detalhe = (proc.stderr or proc.stdout or "").strip()
            raise ErroMotorDocumentos(detalhe or "OCR indisponível.")
        saida = proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroMotorDocumentos(f"OCR falhou: {erro}") from erro
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass

    if not saida:
        return ResultadoOCR("", [])
    try:
        dados = json.loads(saida)
    except ValueError as erro:
        raise ErroMotorDocumentos("Resposta OCR inválida.") from erro

    linhas_raw = dados.get("linhas") or []
    if isinstance(linhas_raw, dict):
        linhas_raw = [linhas_raw]
    linhas = [
        LinhaOCR(
            texto=str(item.get("texto", "")),
            x=float(item.get("x", 0.0)),
            y=float(item.get("y", 0.0)),
            w=float(item.get("w", 0.0)),
            h=float(item.get("h", 0.0)),
        )
        for item in linhas_raw
        if isinstance(item, dict) and item.get("texto")
    ]
    return ResultadoOCR(str(dados.get("texto", "")), linhas)


def renderizar_pdf(caminho_pdf: Path, pasta_saida: Path) -> list[Path]:
    """Converte todas as páginas de um PDF em PNGs (Windows.Data.Pdf no Windows; QtPdf/pdftoppm no Linux)."""
    if sys.platform != "win32":
        from quadro.documentos.motor_linux import renderizar_pdf_linux

        return renderizar_pdf_linux(caminho_pdf, pasta_saida)
    import tempfile

    pdf = Path(caminho_pdf).resolve()
    if not pdf.is_file():
        raise ErroMotorDocumentos("Ficheiro PDF não encontrado.")
    pasta_saida.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", encoding="utf-8", delete=False) as f:
        f.write(_SCRIPT_PDF)
        script_path = Path(f.name)
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(script_path), "-PdfPath", str(pdf), "-OutDir", str(pasta_saida.resolve()),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=_NO_WINDOW,
        )
        if proc.returncode != 0:
            detalhe = (proc.stderr or proc.stdout or "").strip()
            raise ErroMotorDocumentos(detalhe or "Não foi possível abrir o PDF.")
        saida = proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroMotorDocumentos(f"Falha ao abrir PDF: {erro}") from erro
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass

    if not saida:
        return []
    dados = json.loads(saida)
    if isinstance(dados, str):
        dados = [dados]
    return [Path(p) for p in dados if isinstance(p, str) and Path(p).is_file()]


def melhorar_foto_scanner(imagem: QImage) -> QImage:
    """Modo Scanner offline: branqueia fundo cinzento/amarelado de fotos e reforça nitidez do texto."""
    if imagem.isNull():
        return imagem
    img = imagem.convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    # Estima o nível de brilho do papel amostrando uma grelha leve (muito rápido)
    amostras: list[int] = []
    passo_x = max(1, w // 32)
    passo_y = max(1, h // 32)
    for y in range(0, h, passo_y):
        for x in range(0, w, passo_x):
            c = QColor(img.pixel(x, y))
            amostras.append((c.red() * 3 + c.green() * 6 + c.blue()) // 10)
    amostras.sort()
    ponto_branco = amostras[int(len(amostras) * 0.80)] if amostras else 210
    ponto_branco = max(135, min(240, ponto_branco))
    ponto_preto = max(20, int(ponto_branco * 0.25))
    intervalo = max(40.0, float(ponto_branco - ponto_preto))

    # Tabela de lookup (0..255) para velocidade instantânea
    lut = [0] * 256
    for v in range(256):
        norm = (v - ponto_preto) / intervalo
        if norm <= 0.0:
            lut[v] = 0
        elif norm >= 1.0:
            lut[v] = 255
        else:
            # Curva ligeira para manter traços nítidos e papel limpo
            lut[v] = int((norm ** 0.92) * 255)

    ptr = img.bits()
    total_bytes = w * h * 4
    buf = bytearray(ptr[:total_bytes])
    for i in range(0, total_bytes, 4):
        # BGRA em little-endian (Format_ARGB32)
        b = lut[buf[i]]
        g = lut[buf[i + 1]]
        r = lut[buf[i + 2]]
        # Se for quase neutro e claro (sombra do papel), aproxima de branco puro
        if r > 218 and g > 218 and b > 218 and max(r, g, b) - min(r, g, b) < 22:
            buf[i] = 255
            buf[i + 1] = 255
            buf[i + 2] = 255
        else:
            buf[i] = b
            buf[i + 1] = g
            buf[i + 2] = r
    return QImage(bytes(buf), w, h, img.bytesPerLine(), QImage.Format.Format_ARGB32).copy()
