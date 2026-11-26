"""Modelo de dados de Documentos (.kdoc) e exportação para PDF multipágina."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtPrintSupport import QPrinter

EXTENSAO_DOC = ".kdoc"


@dataclass
class TracoDoc:
    cor: str
    espessura: float  # proporcional à largura da página (0.003 .. 0.04)
    modo: str  # "marcador" (Multiply translúcido) ou "caneta" (opaco)
    pontos: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class MarcaDoc:
    tipo: str  # "x", "visto", "circulo"
    x: float
    y: float
    cor: str
    tamanho: float = 0.04


@dataclass
class CaixaTextoDoc:
    x: float
    y: float
    texto: str
    cor: str = "#1D4ED8"
    tamanho: float = 0.024  # proporcional à altura da página


@dataclass
class PaginaDocumento:
    imagem: QImage
    tracos: list[TracoDoc] = field(default_factory=list)
    marcas: list[MarcaDoc] = field(default_factory=list)
    textos: list[CaixaTextoDoc] = field(default_factory=list)
    texto_ocr: str = ""
    linhas_ocr: list[dict] = field(default_factory=list)
    historico: list[dict] = field(default_factory=list)

    def guardar_estado(self) -> None:
        self.historico.append(self._snapshot())
        if len(self.historico) > 40:
            self.historico.pop(0)

    def desfazer(self) -> bool:
        if not self.historico:
            return False
        snap = self.historico.pop()
        self.tracos = [TracoDoc(t["cor"], t["espessura"], t["modo"], [tuple(p) for p in t["pontos"]]) for t in snap["tracos"]]
        self.marcas = [MarcaDoc(**m) for m in snap["marcas"]]
        self.textos = [CaixaTextoDoc(**tx) for tx in snap["textos"]]
        return True

    def _snapshot(self) -> dict:
        return {
            "tracos": [{"cor": t.cor, "espessura": t.espessura, "modo": t.modo, "pontos": [list(p) for p in t.pontos]} for t in self.tracos],
            "marcas": [{"tipo": m.tipo, "x": m.x, "y": m.y, "cor": m.cor, "tamanho": m.tamanho} for m in self.marcas],
            "textos": [{"x": tx.x, "y": tx.y, "texto": tx.texto, "cor": tx.cor, "tamanho": tx.tamanho} for tx in self.textos],
        }


@dataclass
class Documento:
    titulo: str = "Novo Documento"
    paginas: list[PaginaDocumento] = field(default_factory=list)


def _imagem_para_b64(img: QImage) -> str:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return base64.b64encode(bytes(buf.data())).decode("ascii")


def _b64_para_imagem(texto: str) -> QImage:
    img = QImage()
    img.loadFromData(base64.b64decode(texto.encode("ascii")), "PNG")
    return img


def guardar_kdoc(doc: Documento, caminho: Path) -> None:
    payload = {
        "versao": 1,
        "titulo": doc.titulo,
        "paginas": [
            {
                "imagem_png": _imagem_para_b64(p.imagem),
                "texto_ocr": p.texto_ocr,
                "linhas_ocr": p.linhas_ocr,
                **p._snapshot(),
            }
            for p in doc.paginas
        ],
    }
    Path(caminho).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def abrir_kdoc(caminho: Path) -> Documento:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    paginas: list[PaginaDocumento] = []
    for item in dados.get("paginas", []):
        img = _b64_para_imagem(item["imagem_png"])
        p = PaginaDocumento(
            imagem=img,
            tracos=[TracoDoc(t["cor"], float(t["espessura"]), t["modo"], [(float(a), float(b)) for a, b in t["pontos"]]) for t in item.get("tracos", [])],
            marcas=[MarcaDoc(m["tipo"], float(m["x"]), float(m["y"]), m["cor"], float(m.get("tamanho", 0.04))) for m in item.get("marcas", [])],
            textos=[CaixaTextoDoc(float(tx["x"]), float(tx["y"]), tx["texto"], tx.get("cor", "#1D4ED8"), float(tx.get("tamanho", 0.024))) for tx in item.get("textos", [])],
            texto_ocr=str(item.get("texto_ocr", "")),
            linhas_ocr=list(item.get("linhas_ocr", [])),
        )
        paginas.append(p)
    return Documento(titulo=str(dados.get("titulo", Path(caminho).stem)), paginas=paginas)


def renderizar_pagina(painter: QPainter, pagina: PaginaDocumento, retangulo: QRectF) -> None:
    """Desenha uma página completa (ficha + pintura Multiply + marcas + textos) num retângulo alvo."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # 1. Ficha original de fundo
    if not pagina.imagem.isNull():
        painter.drawImage(retangulo, pagina.imagem)
    else:
        painter.fillRect(retangulo, QColor("#FFFFFF"))

    w = retangulo.width()
    h = retangulo.height()
    x0 = retangulo.x()
    y0 = retangulo.y()

    # 2. Traços (marcador translúcido em Multiply preserva os contornos pretos do desenho!)
    for traco in pagina.tracos:
        if not traco.pontos:
            continue
        painter.save()
        cor = QColor(traco.cor)
        if traco.modo == "marcador":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            cor.setAlpha(155)
        pen = QPen(cor, max(2.0, traco.espessura * w), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if len(traco.pontos) == 1:
            px, py = traco.pontos[0]
            painter.drawPoint(QPointF(x0 + px * w, y0 + py * h))
        else:
            path = QPainterPath()
            path.moveTo(x0 + traco.pontos[0][0] * w, y0 + traco.pontos[0][1] * h)
            for px, py in traco.pontos[1:]:
                path.lineTo(x0 + px * w, y0 + py * h)
            painter.drawPath(path)
        painter.restore()

    # 3. Marcas rápidas (X, Visto, Círculo)
    for m in pagina.marcas:
        cx = x0 + m.x * w
        cy = y0 + m.y * h
        r = max(10.0, m.tamanho * w * 0.5)
        pen = QPen(QColor(m.cor), max(2.5, r * 0.22), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if m.tipo == "x":
            painter.drawLine(QPointF(cx - r, cy - r), QPointF(cx + r, cy + r))
            painter.drawLine(QPointF(cx + r, cy - r), QPointF(cx - r, cy + r))
        elif m.tipo == "visto":
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx - r * 0.2, cy + r * 0.85))
            painter.drawLine(QPointF(cx - r * 0.2, cy + r * 0.85), QPointF(cx + r * 1.05, cy - r * 0.8))
        elif m.tipo == "circulo":
            painter.drawEllipse(QPointF(cx, cy), r * 1.15, r * 0.85)

    # 4. Caixas de texto editáveis (suporta múltiplas linhas e origem top-left exata ao píxel)
    for tx in pagina.textos:
        px = x0 + tx.x * w
        py = y0 + tx.y * h
        tam_px = max(11, int(tx.tamanho * h))
        fonte = QFont("Segoe UI")
        fonte.setPixelSize(tam_px)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.setPen(QColor(tx.cor))
        caixa = QRectF(px, py, max(40.0, x0 + w - px - 6.0), max(24.0, y0 + h - py - 4.0))
        painter.drawText(caixa, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, tx.texto)

    painter.restore()


def exportar_pdf(doc: Documento, caminho: Path) -> None:
    """Exporta todas as páginas preenchidas do documento para um PDF multipágina limpo."""
    if not doc.paginas:
        return
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(caminho))

    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Não foi possível criar o ficheiro PDF.")
    try:
        for idx, pagina in enumerate(doc.paginas):
            if idx > 0:
                printer.newPage()
            alvo = QRectF(printer.pageRect(QPrinter.Unit.DevicePixel))
            if not pagina.imagem.isNull():
                iw, ih = float(pagina.imagem.width()), float(pagina.imagem.height())
                escala = min(alvo.width() / max(1.0, iw), alvo.height() / max(1.0, ih))
                rw, rh = iw * escala, ih * escala
                rect = QRectF(alvo.x() + (alvo.width() - rw) / 2, alvo.y() + (alvo.height() - rh) / 2, rw, rh)
            else:
                rect = alvo
            renderizar_pagina(painter, pagina, rect)
    finally:
        painter.end()
