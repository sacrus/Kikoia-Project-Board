"""Janela de Documentos do Quadro Interativo: fichas escolares, PDFs, OCR offline, pintura Multiply e Modo Exame."""

from __future__ import annotations

import hashlib
import math
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from quadro import idiomas, tema_partilhado
from quadro.area_util import adaptar_a_area_util
from quadro.correio import voz
from quadro.documentos import modelo, motor_windows
from quadro.documentos.modelo import (
    EXTENSAO_DOC,
    CaixaTextoDoc,
    Documento,
    MarcaDoc,
    PaginaDocumento,
    TracoDoc,
)
from quadro.idiomas import t

_CORES_RAPIDAS = (
    "#FACC15",  # Amarelo
    "#EF4444",  # Vermelho
    "#22C55E",  # Verde
    "#2563EB",  # Azul
    "#EC4899",  # Rosa
    "#0F172A",  # Preto
)


class _SinalFundo(QObject):
    terminou = Signal(object)


def _estilo_documentos(escuro: bool) -> str:
    if escuro:
        fundo = "#131720"
        topo = "#1A202E"
        barra = "#1E2534"
        texto = "#F1F5F9"
        texto_suave = "#94A3B8"
        borda = "#2E374B"
        btn = "#262F42"
        btn_hover = "#313C54"
        editor_bg = "#0F172A"
    else:
        fundo = "#E2E8F0"
        topo = "#FFFFFF"
        barra = "#F8FAFC"
        texto = "#0F172A"
        texto_suave = "#64748B"
        borda = "#CBD5E1"
        btn = "#F1F5F9"
        btn_hover = "#E2E8F0"
        editor_bg = "#FFFFFF"

    return f"""
QDialog {{
    background-color: {fundo};
    color: {texto};
}}
QFrame#cabecalhoDoc, QFrame#barraFerrDoc {{
    background-color: {topo};
    border-bottom: 1px solid {borda};
}}
QFrame#barraFerrDoc {{
    background-color: {barra};
}}
QFrame#bannerExame {{
    background-color: #B45309;
    border-bottom: 1px solid #92400E;
}}
QLabel#textoBannerExame {{
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 700;
}}
QLabel#tituloDoc {{
    color: {texto};
    font-size: 18px;
    font-weight: 700;
}}
QLabel#estadoDoc {{
    color: {texto_suave};
    font-size: 12px;
    padding: 4px 12px;
}}
QLabel#relogioExame {{
    color: {texto};
    font-size: 13px;
    font-weight: 700;
    padding: 3px 12px;
}}
QScrollArea#areaDocScroll {{
    background-color: {fundo};
    border: none;
}}
QTextEdit#editorOCR {{
    background-color: {editor_bg};
    color: {texto};
    border: 1px solid {borda};
    border-radius: 10px;
    padding: 10px;
    font-size: 15px;
    line-height: 1.5;
}}
QPushButton {{
    background-color: {btn};
    color: {texto};
    border: 1px solid {borda};
    border-radius: 8px;
    padding: 6px 11px;
    font-size: 12.5px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {btn_hover};
}}
QPushButton:checked {{
    background-color: #2563EB;
    color: #FFFFFF;
    border-color: #2563EB;
}}
QPushButton:disabled {{
    color: {texto_suave};
}}
QPushButton[papel="primario"] {{
    background-color: #2563EB;
    color: #FFFFFF;
    border-color: #2563EB;
}}
QPushButton[papel="primario"]:hover {{
    background-color: #1D4ED8;
}}
QPushButton[papel="exame"] {{
    background-color: #D97706;
    color: #FFFFFF;
    border-color: #D97706;
}}
QPushButton[papel="exame"]:hover {{
    background-color: #B45309;
}}
QPushButton[papel="exame_ativo"] {{
    background-color: #DC2626;
    color: #FFFFFF;
    border-color: #DC2626;
}}
QPushButton[papel="exame_ativo"]:hover {{
    background-color: #B91C1C;
}}
"""


class _CampoMultilinha(QPlainTextEdit):
    """Campo de texto multilinha onde Enter muda de linha e Ctrl+Enter confirma."""

    confirmar_atalho = Signal()

    def keyPressEvent(self, evento) -> None:  # noqa: N802
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            evento.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.confirmar_atalho.emit()
            evento.accept()
            return
        super().keyPressEvent(evento)


class _EditorTextoInline(QWidget):
    """Caixa de escrita multilinha em tempo real sobre a ficha, alinhada ao píxel."""

    confirmou = Signal(str, float, float, float)  # texto, x_norm, y_norm, tam_norm
    apagou = Signal()
    tamanho_alterado = Signal(int)

    def __init__(self, canvas: CanvasDocumento, x_px: int, y_px: int, texto_inicial: str, cor: str, tam_px: int, editando_existente: bool = False) -> None:
        super().__init__(canvas)
        self._canvas = canvas
        self._cor = cor
        self._tam_px = max(11, tam_px)
        self._arrastando = False
        self._offset_drag = QPointF()

        # Barra flutuante compacta de controlos (estilo Quadro Interativo)
        self._barra = QFrame()
        self._barra.setStyleSheet(
            "QFrame { background: rgba(15, 23, 42, 225); border: 1px solid #3B82F6; border-radius: 8px; }"
            " QPushButton { background: rgba(255,255,255,24); color: #FFFFFF; border: none; border-radius: 5px; padding: 2px 7px; font-size: 11px; font-weight: 700; }"
            " QPushButton:hover { background: #2563EB; }"
        )
        lay_b = QHBoxLayout(self._barra)
        lay_b.setContentsMargins(4, 3, 4, 3)
        lay_b.setSpacing(4)

        self._pega = QLabel("✥")
        self._pega.setStyleSheet("color: #93C5FD; font-size: 13px; font-weight: 700; padding: 0 4px;")
        self._pega.setCursor(Qt.CursorShape.SizeAllCursor)

        btn_menos = QPushButton("A−")
        btn_menos.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_menos.clicked.connect(lambda: self._ajustar_tamanho_utilizador(-3))
        btn_mais = QPushButton("A+")
        btn_mais.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mais.clicked.connect(lambda: self._ajustar_tamanho_utilizador(3))
        btn_ok = QPushButton("✓")
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(self.confirmar)
        btn_del = QPushButton("✕")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.clicked.connect(self.apagou.emit)

        lay_b.addWidget(self._pega)
        lay_b.addWidget(btn_menos)
        lay_b.addWidget(btn_mais)
        lay_b.addWidget(btn_ok)
        lay_b.addWidget(btn_del)

        # Campo multilinha transparente sobre a ficha (Enter muda de linha!)
        self.campo = _CampoMultilinha(texto_inicial)
        self.campo.setPlaceholderText(t("doc.inserir_texto"))
        self.campo.setFrameShape(QFrame.Shape.NoFrame)
        self.campo.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.campo.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.campo.document().setDocumentMargin(0)
        self.campo.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.campo.confirmar_atalho.connect(self.confirmar)
        self.campo.textChanged.connect(self._ajustar_dimensoes)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(3)
        raiz.addWidget(self._barra, 0, Qt.AlignmentFlag.AlignLeft)
        raiz.addWidget(self.campo)

        self._aplicar_estilo_campo()
        self._ajustar_dimensoes()
        self.adjustSize()

        # Alinha exatamente o canto superior esquerdo do texto com (x_px, y_px)
        desloc_y = self._barra.sizeHint().height() + 3 + 2
        desloc_x = 2
        if not editando_existente:
            # Ao clicar numa linha para criar texto novo, centra verticalmente a primeira linha no clique
            y_px = y_px - int(self._tam_px * 0.55)
        self.move(max(0, x_px - desloc_x), max(0, y_px - desloc_y))
        self.show()
        self.campo.setFocus()
        if editando_existente:
            cursor = self.campo.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.campo.setTextCursor(cursor)

    def definir_cor(self, cor: str) -> None:
        self._cor = cor if cor != "#FACC15" else "#1D4ED8"
        self._aplicar_estilo_campo()

    def definir_tamanho_px(self, tam_px: int) -> None:
        self._tam_px = max(11, min(72, tam_px))
        self._aplicar_estilo_campo()
        self._ajustar_dimensoes()

    def _ajustar_tamanho_utilizador(self, delta: int) -> None:
        self.definir_tamanho_px(self._tam_px + delta)
        self.tamanho_alterado.emit(self._tam_px)

    def _aplicar_estilo_campo(self) -> None:
        fonte = QFont("Segoe UI")
        fonte.setPixelSize(self._tam_px)
        fonte.setBold(True)
        self.campo.setFont(fonte)
        self.campo.setStyleSheet(
            f"QPlainTextEdit {{ background: rgba(255, 255, 255, 185); color: {self._cor}; "
            f"border: 1.5px dashed #2563EB; border-radius: 4px; padding: 0px; }}"
        )

    def _ajustar_dimensoes(self) -> None:
        fm = QFontMetrics(self.campo.font())
        texto = self.campo.toPlainText()
        linhas = texto.splitlines() if texto else [self.campo.placeholderText()]
        if texto.endswith("\n"):
            linhas.append("")
        larg_txt = max((fm.horizontalAdvance(l) for l in linhas), default=140)
        larg = max(180, larg_txt + 24)
        max_larg = max(200, self._canvas.width() - self.x() - 10)
        alt = max(fm.lineSpacing() + 8, len(linhas) * fm.lineSpacing() + 8)
        self.campo.setFixedSize(min(larg, max_larg), alt)
        self.adjustSize()

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self._arrastando = True
            self._offset_drag = evento.position()
            evento.accept()
            return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if self._arrastando:
            novo = self.mapToParent(evento.position().toPoint()) - self._offset_drag.toPoint()
            self.move(max(0, min(self._canvas.width() - 60, novo.x())), max(0, min(self._canvas.height() - 40, novo.y())))
            evento.accept()
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        self._arrastando = False
        super().mouseReleaseEvent(evento)

    def confirmar(self) -> None:
        r = self._canvas._rect_pagina
        if r.width() <= 0 or r.height() <= 0:
            self.apagou.emit()
            return
        # Usa exatamente o canto superior esquerdo do viewport (onde o texto começa a ser desenhado)
        pos_viewport = self.campo.viewport().mapTo(self._canvas, self.campo.viewport().rect().topLeft())
        x_norm = max(0.0, min(0.98, (pos_viewport.x() - r.x()) / r.width()))
        y_norm = max(0.0, min(0.98, (pos_viewport.y() - r.y()) / r.height()))
        tam_norm = max(0.010, min(0.080, self._tam_px / r.height()))
        self.confirmou.emit(self.campo.toPlainText().rstrip(), x_norm, y_norm, tam_norm)


class CanvasDocumento(QWidget):
    """Folha interativa da ficha escolar dentro de uma área com scroll e zoom ajustável."""

    alterou = Signal()
    zoom_alterado = Signal(int)
    tamanho_texto_alterado = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pagina: PaginaDocumento | None = None
        self.ferramenta = "marcador"  # "marcador", "caneta", "texto", "x", "visto", "circulo", "borracha"
        self.cor = "#FACC15"
        self.tamanho_ferramenta = 22  # 6..50 (adapta traço, letra, marcas e borracha)
        self.tamanho_texto_norm: float | None = None  # tamanho escolhido pelo utilizador (persiste até mudar ou novo doc)
        self.zoom = 1.0  # 1.0 = largura confortável de leitura (~960 px)
        self._largura_base = 960.0
        self._traco_ativo: TracoDoc | None = None
        self._editor_inline: _EditorTextoInline | None = None
        self._texto_em_edicao: CaixaTextoDoc | None = None
        self._rect_pagina = QRectF()
        self._atualizar_dimensao()

    def definir_pagina(self, pagina: PaginaDocumento | None) -> None:
        self.confirmar_texto_inline()
        self.pagina = pagina
        self._traco_ativo = None
        self._atualizar_dimensao()
        self.update()

    def confirmar_texto_inline(self) -> None:
        if self._editor_inline is not None:
            self._editor_inline.confirmar()

    def repor_tamanho_texto_padrao(self) -> None:
        self.tamanho_texto_norm = None
        self.tamanho_ferramenta = 22

    def atualizar_estilo_texto_inline(self) -> None:
        if self._editor_inline is not None:
            self._editor_inline.definir_cor(self.cor)
            r = self._rect_pagina
            if r.height() > 0:
                tam_norm = self.tamanho_texto_norm if self.tamanho_texto_norm is not None else (self.tamanho_ferramenta / 1000.0)
                self._editor_inline.definir_tamanho_px(max(11, int(round(tam_norm * r.height()))))

    def definir_zoom(self, fator: float) -> None:
        self.zoom = max(0.45, min(2.5, fator))
        self._atualizar_dimensao()
        self.zoom_alterado.emit(int(round(self.zoom * 100)))
        self.update()

    def _atualizar_dimensao(self) -> None:
        margem = 24
        if self.pagina is not None and not self.pagina.imagem.isNull():
            iw = max(1.0, float(self.pagina.imagem.width()))
            ih = max(1.0, float(self.pagina.imagem.height()))
            rw = self._largura_base * self.zoom
            rh = rw * (ih / iw)
        else:
            rw = 760.0 * self.zoom
            rh = 1020.0 * self.zoom
        self.setFixedSize(int(rw + margem * 2), int(rh + margem * 2))

    def _calcular_rect_pagina(self) -> QRectF:
        margem = 24.0
        return QRectF(margem, margem, max(100.0, self.width() - margem * 2), max(100.0, self.height() - margem * 2))

    def wheelEvent(self, evento) -> None:  # noqa: N802
        if evento.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = 0.12 if evento.angleDelta().y() > 0 else -0.12
            self.definir_zoom(self.zoom + delta)
            evento.accept()
            return
        super().wheelEvent(evento)

    def _para_norm(self, pos: QPointF) -> tuple[float, float] | None:
        r = self._rect_pagina
        if r.width() <= 0 or r.height() <= 0 or not r.contains(pos):
            return None
        return ((pos.x() - r.x()) / r.width(), (pos.y() - r.y()) / r.height())

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._rect_pagina = self._calcular_rect_pagina()

        if self.pagina is None:
            p.setPen(QColor("#64748B"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, t("doc.sem_ficha"))
            p.end()
            return

        # Sombra discreta da folha de papel
        sombra = self._rect_pagina.adjusted(4, 5, 4, 5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(15, 23, 42, 45))
        p.drawRoundedRect(sombra, 4, 4)

        modelo.renderizar_pagina(p, self.pagina, self._rect_pagina)
        p.setPen(QPen(QColor("#94A3B8"), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self._rect_pagina)
        p.end()

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() != Qt.MouseButton.LeftButton or self.pagina is None:
            return
        if self._editor_inline is not None:
            self.confirmar_texto_inline()
            if self.ferramenta == "texto":
                # Primeiro clique fora confirma o texto atual; novo clique abre outro se desejado
                return
        pt = self._para_norm(evento.position())
        if pt is None:
            return

        escala = self.tamanho_ferramenta / 1000.0
        if self.ferramenta in ("marcador", "caneta"):
            self.pagina.guardar_estado()
            esp = escala if self.ferramenta == "marcador" else max(0.0025, escala * 0.35)
            traco = TracoDoc(self.cor, esp, self.ferramenta, [pt])
            self.pagina.tracos.append(traco)
            self._traco_ativo = traco
            self.alterou.emit()
            self.update()
        elif self.ferramenta in ("x", "visto", "circulo"):
            self.pagina.guardar_estado()
            tam_marca = max(0.018, escala * 1.8)
            self.pagina.marcas.append(MarcaDoc(self.ferramenta, pt[0], pt[1], self.cor, tam_marca))
            self.alterou.emit()
            self.update()
        elif self.ferramenta == "texto":
            self._editar_ou_criar_texto(pt)
        elif self.ferramenta == "borracha":
            self._apagar_perto(pt)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if self.pagina is None:
            return
        pt = self._para_norm(evento.position())
        if pt is None:
            return
        if self._traco_ativo is not None:
            self._traco_ativo.pontos.append(pt)
            self.update()
        elif self.ferramenta == "borracha" and (evento.buttons() & Qt.MouseButton.LeftButton):
            self._apagar_perto(pt)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self._traco_ativo = None

    def _rect_do_texto(self, tx: CaixaTextoDoc) -> QRectF:
        """Calcula o retângulo exato em píxeis ocupado por um texto renderizado na página."""
        r = self._rect_pagina
        px = r.x() + tx.x * r.width()
        py = r.y() + tx.y * r.height()
        tam_px = max(11, int(tx.tamanho * r.height()))
        fonte = QFont("Segoe UI")
        fonte.setPixelSize(tam_px)
        fonte.setBold(True)
        fm = QFontMetrics(fonte)
        linhas = tx.texto.splitlines() or [""]
        larg = max((fm.horizontalAdvance(l) for l in linhas), default=24)
        alt = max(fm.lineSpacing(), len(linhas) * fm.lineSpacing())
        return QRectF(px - 3.0, py - 2.0, larg + 6.0, alt + 4.0)

    def _editar_ou_criar_texto(self, pt: tuple[float, float]) -> None:
        if self.pagina is None:
            return
        r = self._rect_pagina
        clique_px = QPointF(r.x() + pt[0] * r.width(), r.y() + pt[1] * r.height())
        existente = None
        for tx in reversed(self.pagina.textos):
            if self._rect_do_texto(tx).contains(clique_px):
                existente = tx
                break

        self._texto_em_edicao = existente
        if existente is not None:
            self.pagina.guardar_estado()
            self.pagina.textos.remove(existente)
            x_px = int(r.x() + existente.x * r.width())
            y_px = int(r.y() + existente.y * r.height())
            tam_px = max(12, int(existente.tamanho * r.height()))
            cor_txt = existente.cor
            texto_ini = existente.texto
            self.update()
        else:
            x_px = int(clique_px.x())
            y_px = int(clique_px.y())
            tam_norm = self.tamanho_texto_norm if self.tamanho_texto_norm is not None else (self.tamanho_ferramenta / 1000.0)
            tam_px = max(11, int(round(tam_norm * r.height())))
            cor_txt = self.cor if self.cor != "#FACC15" else "#1D4ED8"
            texto_ini = ""

        editor = _EditorTextoInline(self, x_px, y_px, texto_ini, cor_txt, tam_px, editando_existente=existente is not None)
        editor.confirmou.connect(self._ao_confirmar_texto_inline)
        editor.apagou.connect(self._ao_apagar_texto_inline)
        editor.tamanho_alterado.connect(self._ao_alterar_tamanho_texto_inline)
        self._editor_inline = editor

    def _ao_alterar_tamanho_texto_inline(self, tam_px: int) -> None:
        r = self._rect_pagina
        if r.height() <= 0:
            return
        self.tamanho_texto_norm = max(0.010, min(0.080, tam_px / r.height()))
        val_slider = max(8, min(50, int(round(self.tamanho_texto_norm * 1000.0))))
        self.tamanho_ferramenta = val_slider
        self.tamanho_texto_alterado.emit(val_slider)

    def _ao_confirmar_texto_inline(self, texto: str, x_norm: float, y_norm: float, tam_norm: float) -> None:
        editor = self._editor_inline
        self._editor_inline = None
        cor_txt = editor._cor if editor is not None else "#1D4ED8"
        if editor is not None:
            editor.deleteLater()
        if self.pagina is not None and texto:
            if self._texto_em_edicao is None:
                self.pagina.guardar_estado()
                self.tamanho_texto_norm = tam_norm
            self.pagina.textos.append(CaixaTextoDoc(x_norm, y_norm, texto, cor_txt, tam_norm))
            self.alterou.emit()
        self._texto_em_edicao = None
        self.update()

    def _ao_apagar_texto_inline(self) -> None:
        editor = self._editor_inline
        self._editor_inline = None
        if editor is not None:
            editor.deleteLater()
        self._texto_em_edicao = None
        self.alterou.emit()
        self.update()

    def _apagar_perto(self, pt: tuple[float, float]) -> None:
        """Apaga apenas traços, marcas e textos feitos pelo aluno (nunca a ficha original)."""
        if self.pagina is None:
            return
        raio = max(0.015, self.tamanho_ferramenta / 650.0)
        alterado = False

        novos_tracos = [
            tr for tr in self.pagina.tracos
            if not any(math.hypot(px - pt[0], py - pt[1]) <= raio for px, py in tr.pontos)
        ]
        if len(novos_tracos) != len(self.pagina.tracos):
            if not alterado:
                self.pagina.guardar_estado()
                alterado = True
            self.pagina.tracos = novos_tracos

        novas_marcas = [m for m in self.pagina.marcas if math.hypot(m.x - pt[0], m.y - pt[1]) > raio * 1.2]
        if len(novas_marcas) != len(self.pagina.marcas):
            if not alterado:
                self.pagina.guardar_estado()
                alterado = True
            self.pagina.marcas = novas_marcas

        novos_textos = [tx for tx in self.pagina.textos if math.hypot(tx.x - pt[0], tx.y - pt[1]) > raio * 1.5]
        if len(novos_textos) != len(self.pagina.textos):
            if not alterado:
                self.pagina.guardar_estado()
                alterado = True
            self.pagina.textos = novos_textos

        if alterado:
            self.alterou.emit()
            self.update()


class DialogoDocumentos(QDialog):
    """Janela principal de Documentos: fichas escolares, PDFs, OCR offline, leitura em voz alta e Modo Exame."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        idiomas.carregar_partilhado()
        self.setWindowTitle(t("doc.titulo"))
        self.resize(1160, 740)
        self._escuro = tema_partilhado.e_escuro()
        self.documento = Documento()
        self._idx_pagina = 0

        # Estado do Modo Exame (hash SHA-256 da palavra-passe definida pelo professor)
        self._modo_exame = False
        self._hash_exame: str | None = None
        self._pedindo_senha_exame = False
        self._geometria_normal = None
        self._timer_vigia_exame = QTimer(self)
        self._timer_vigia_exame.setInterval(250)
        self._timer_vigia_exame.timeout.connect(self._vigiar_foco_exame)

        # --- Banner de Modo Exame (visível apenas quando bloqueado) ---
        self._banner_exame = QFrame()
        self._banner_exame.setObjectName("bannerExame")
        self._banner_exame.setVisible(False)
        lay_ban = QHBoxLayout(self._banner_exame)
        lay_ban.setContentsMargins(16, 6, 16, 6)
        lbl_ban = QLabel(t("doc.exame_ativo_banner"))
        lbl_ban.setObjectName("textoBannerExame")
        lay_ban.addWidget(lbl_ban)
        lay_ban.addStretch(1)

        # --- Cabeçalho ---
        cab = QFrame()
        cab.setObjectName("cabecalhoDoc")
        cab_lay = QHBoxLayout(cab)
        cab_lay.setContentsMargins(14, 10, 14, 10)
        cab_lay.setSpacing(8)

        lbl_tit = QLabel(t("def.documentos"))
        lbl_tit.setObjectName("tituloDoc")

        self._btn_abrir = QPushButton(t("doc.abrir"))
        self._btn_abrir.setProperty("papel", "primario")
        self._btn_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_abrir.clicked.connect(self._abrir_ficheiro)

        self._btn_guardar = QPushButton(t("doc.guardar"))
        self._btn_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_guardar.clicked.connect(self._guardar_kdoc)

        self._btn_pdf = QPushButton(t("doc.exportar_pdf"))
        self._btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pdf.clicked.connect(self._exportar_pdf)

        self._btn_ant = QPushButton(t("doc.pagina_ant"))
        self._btn_ant.clicked.connect(lambda: self._ir_pagina(self._idx_pagina - 1))
        self._lbl_pag = QLabel(t("doc.pagina", atual=0, total=0))
        self._btn_seg = QPushButton(t("doc.pagina_seg"))
        self._btn_seg.clicked.connect(lambda: self._ir_pagina(self._idx_pagina + 1))

        # Controlos de zoom do documento (para leitura confortável de provas/PDFs A4)
        self._btn_zoom_menos = QPushButton("−")
        self._btn_zoom_menos.setFixedWidth(32)
        self._btn_zoom_menos.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_zoom_menos.clicked.connect(lambda: self.canvas.definir_zoom(self.canvas.zoom - 0.15))
        self._lbl_zoom = QLabel("100%")
        self._lbl_zoom.setMinimumWidth(44)
        self._lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._btn_zoom_mais = QPushButton("+")
        self._btn_zoom_mais.setFixedWidth(32)
        self._btn_zoom_mais.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_zoom_mais.clicked.connect(lambda: self.canvas.definir_zoom(self.canvas.zoom + 0.15))

        self._btn_exame = QPushButton(t("doc.modo_exame"))
        self._btn_exame.setProperty("papel", "exame")
        self._btn_exame.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_exame.clicked.connect(self._alternar_modo_exame)

        self._btn_fechar = QPushButton(t("geral.fechar"))
        self._btn_fechar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_fechar.clicked.connect(self._tentar_fechar)

        cab_lay.addWidget(lbl_tit)
        cab_lay.addSpacing(8)
        cab_lay.addWidget(self._btn_abrir)
        cab_lay.addWidget(self._btn_guardar)
        cab_lay.addWidget(self._btn_pdf)
        cab_lay.addStretch(1)
        cab_lay.addWidget(self._btn_ant)
        cab_lay.addWidget(self._lbl_pag)
        cab_lay.addWidget(self._btn_seg)
        cab_lay.addSpacing(12)
        cab_lay.addWidget(self._btn_zoom_menos)
        cab_lay.addWidget(self._lbl_zoom)
        cab_lay.addWidget(self._btn_zoom_mais)
        cab_lay.addStretch(1)
        cab_lay.addWidget(self._btn_exame)
        cab_lay.addWidget(self._btn_fechar)

        # --- Barra de ferramentas de preenchimento + OCR ---
        barra = QFrame()
        barra.setObjectName("barraFerrDoc")
        barra_lay = QHBoxLayout(barra)
        barra_lay.setContentsMargins(14, 8, 14, 8)
        barra_lay.setSpacing(6)

        self._botoes_ferr: dict[str, QPushButton] = {}
        for fid, chave in (
            ("marcador", "doc.ferr_marcador"),
            ("caneta", "doc.ferr_caneta"),
            ("texto", "doc.ferr_texto"),
            ("x", "doc.ferr_x"),
            ("visto", "doc.ferr_visto"),
            ("circulo", "doc.ferr_circulo"),
            ("borracha", "doc.ferr_borracha"),
        ):
            b = QPushButton(t(chave))
            b.setCheckable(True)
            b.setChecked(fid == "marcador")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, f=fid: self._escolher_ferramenta(f))
            self._botoes_ferr[fid] = b
            barra_lay.addWidget(b)

        barra_lay.addSpacing(6)
        self._botoes_cor: list[tuple[str, QPushButton]] = []
        for cor in _CORES_RAPIDAS:
            bc = QPushButton()
            bc.setFixedSize(26, 26)
            bc.setCursor(Qt.CursorShape.PointingHandCursor)
            bc.clicked.connect(lambda _=False, c=cor: self._escolher_cor(c))
            self._botoes_cor.append((cor, bc))
            barra_lay.addWidget(bc)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(8, 50)
        self._slider.setValue(22)
        self._slider.setFixedWidth(92)
        self._slider.valueChanged.connect(self._mudar_espessura)
        self._lbl_tam_ferr = QLabel("22")
        self._lbl_tam_ferr.setMinimumWidth(24)
        self._lbl_tam_ferr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        barra_lay.addWidget(self._slider)
        barra_lay.addWidget(self._lbl_tam_ferr)

        btn_desfazer = QPushButton(t("doc.desfazer"))
        btn_desfazer.clicked.connect(self._desfazer)
        barra_lay.addWidget(btn_desfazer)

        barra_lay.addStretch(1)

        self._btn_scanner = QPushButton(t("doc.scanner"))
        self._btn_scanner.clicked.connect(self._aplicar_scanner)
        self._btn_ocr = QPushButton(t("doc.ocr"))
        self._btn_ocr.clicked.connect(self._executar_ocr)
        self._btn_ler = QPushButton(t("doc.ler_voz"))
        self._btn_ler.clicked.connect(self._ler_voz)
        self._btn_parar_voz = QPushButton(t("doc.parar_voz"))
        self._btn_parar_voz.clicked.connect(lambda: voz.parar())

        barra_lay.addWidget(self._btn_scanner)
        barra_lay.addWidget(self._btn_ocr)
        barra_lay.addWidget(self._btn_ler)
        barra_lay.addWidget(self._btn_parar_voz)

        # --- Área principal: Canvas com scroll/zoom + Painel lateral de Texto Extraído (OCR) ---
        self.canvas = CanvasDocumento()
        self.canvas.zoom_alterado.connect(lambda pct: self._lbl_zoom.setText(f"{pct}%"))
        self.canvas.tamanho_texto_alterado.connect(self._sincronizar_slider_tamanho)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("areaDocScroll")
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self.canvas)

        self._painel_ocr = QWidget()
        lay_ocr = QVBoxLayout(self._painel_ocr)
        lay_ocr.setContentsMargins(6, 8, 12, 8)
        lay_ocr.setSpacing(6)
        lbl_ocr = QLabel(t("doc.painel_ocr"))
        lbl_ocr.setStyleSheet("font-weight: 700;")
        self._editor_ocr = QTextEdit()
        self._editor_ocr.setObjectName("editorOCR")
        self._editor_ocr.textChanged.connect(self._sincronizar_texto_ocr)
        lay_ocr.addWidget(lbl_ocr)
        lay_ocr.addWidget(self._editor_ocr, 1)
        self._painel_ocr.setVisible(False)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(self._scroll)
        divisor.addWidget(self._painel_ocr)
        divisor.setStretchFactor(0, 3)
        divisor.setStretchFactor(1, 2)

        # Rodapé: estado à esquerda + relógio discreto à direita (visível em Modo Exame)
        self._estado = QLabel(t("doc.sem_ficha"))
        self._estado.setObjectName("estadoDoc")
        self._relogio = QLabel("")
        self._relogio.setObjectName("relogioExame")
        self._relogio.setVisible(False)
        self._timer_relogio = QTimer(self)
        self._timer_relogio.setInterval(1000)
        self._timer_relogio.timeout.connect(self._atualizar_relogio)

        rodape = QHBoxLayout()
        rodape.setContentsMargins(0, 0, 4, 2)
        rodape.addWidget(self._estado, 1)
        rodape.addWidget(self._relogio)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._banner_exame)
        raiz.addWidget(cab)
        raiz.addWidget(barra)
        raiz.addWidget(divisor, 1)
        raiz.addLayout(rodape)

        self._atualizar_botoes_cor()
        self._atualizar_navegacao()
        self.setStyleSheet(_estilo_documentos(self._escuro))
        self._encerrado = False
        self._sinais_fundo: list[_SinalFundo] = []
        self._adaptador_area = adaptar_a_area_util(self, maximizar=True, ignorar_se=lambda: self._modo_exame)
        self._ecra_exame = self.screen() or QGuiApplication.primaryScreen()
        if self._ecra_exame is not None:
            self._ecra_exame.availableGeometryChanged.connect(self._ao_mudar_area_exame)

    # --- Ferramentas e páginas ----------------------------------------------------

    def _pagina_atual(self) -> PaginaDocumento | None:
        if 0 <= self._idx_pagina < len(self.documento.paginas):
            return self.documento.paginas[self._idx_pagina]
        return None

    def _escolher_ferramenta(self, fid: str) -> None:
        self.canvas.confirmar_texto_inline()
        self.canvas.ferramenta = fid
        for k, b in self._botoes_ferr.items():
            b.setChecked(k == fid)

    def _escolher_cor(self, cor: str) -> None:
        self.canvas.cor = cor
        self._atualizar_botoes_cor()
        self.canvas.atualizar_estilo_texto_inline()

    def _atualizar_botoes_cor(self) -> None:
        for cor, btn in self._botoes_cor:
            borda = "3px solid #2563EB" if cor == self.canvas.cor else "1.5px solid #94A3B8"
            btn.setStyleSheet(f"QPushButton {{ background: {cor}; border: {borda}; border-radius: 13px; padding: 0; }}")

    def _mudar_espessura(self, val: int) -> None:
        self.canvas.tamanho_ferramenta = val
        self.canvas.tamanho_texto_norm = val / 1000.0
        self._lbl_tam_ferr.setText(str(val))
        self.canvas.atualizar_estilo_texto_inline()

    def _sincronizar_slider_tamanho(self, val: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(max(self._slider.minimum(), min(self._slider.maximum(), val)))
        self._slider.blockSignals(False)
        self._lbl_tam_ferr.setText(str(val))

    def _repor_tamanho_novo_documento(self) -> None:
        self.canvas.repor_tamanho_texto_padrao()
        self._sincronizar_slider_tamanho(self.canvas.tamanho_ferramenta)

    def _atualizar_relogio(self) -> None:
        self._relogio.setText(QTime.currentTime().toString("HH:mm"))

    def _desfazer(self) -> None:
        p = self._pagina_atual()
        if p is not None and p.desfazer():
            self.canvas.update()

    def _ir_pagina(self, idx: int) -> None:
        if not self.documento.paginas:
            return
        self._idx_pagina = max(0, min(len(self.documento.paginas) - 1, idx))
        p = self._pagina_atual()
        self.canvas.definir_pagina(p)
        self._editor_ocr.blockSignals(True)
        self._editor_ocr.setPlainText(p.texto_ocr if p else "")
        self._editor_ocr.blockSignals(False)
        if p and p.texto_ocr:
            self._painel_ocr.setVisible(True)
        self._atualizar_navegacao()

    def _atualizar_navegacao(self) -> None:
        total = len(self.documento.paginas)
        atual = self._idx_pagina + 1 if total else 0
        self._lbl_pag.setText(t("doc.pagina", atual=atual, total=total))
        self._btn_ant.setEnabled(atual > 1)
        self._btn_seg.setEnabled(atual < total)
        tem = total > 0
        self._btn_guardar.setEnabled(tem)
        self._btn_pdf.setEnabled(tem and not self._modo_exame)
        self._btn_scanner.setEnabled(tem and not self._modo_exame)
        self._btn_ocr.setEnabled(tem)
        self._btn_ler.setEnabled(tem)

    def _sincronizar_texto_ocr(self) -> None:
        p = self._pagina_atual()
        if p is not None:
            p.texto_ocr = self._editor_ocr.toPlainText()

    # --- Abrir / Guardar / Exportar PDF -------------------------------------------

    def carregar_imagem(self, caminho: Path) -> bool:
        img = QImage(str(caminho))
        if img.isNull():
            return False
        self._repor_tamanho_novo_documento()
        self.documento = Documento(titulo=caminho.stem, paginas=[PaginaDocumento(imagem=img)])
        self._ir_pagina(0)
        self._estado.setText(caminho.name)
        return True

    def _abrir_ficheiro(self) -> None:
        if self._modo_exame:
            QMessageBox.warning(self, t("doc.modo_exame"), t("doc.exame_bloqueado"))
            return
        caminho_str, _ = QFileDialog.getOpenFileName(
            self,
            t("doc.abrir"),
            "",
            "Fichas e Documentos (*.pdf *.png *.jpg *.jpeg *.bmp *.webp *.kdoc);;Todos (*.*)",
        )
        if not caminho_str:
            return
        caminho = Path(caminho_str)
        ext = caminho.suffix.lower()
        if ext == EXTENSAO_DOC:
            try:
                self._repor_tamanho_novo_documento()
                self.documento = modelo.abrir_kdoc(caminho)
                self._ir_pagina(0)
                self._estado.setText(caminho.name)
            except Exception as erro:
                QMessageBox.warning(self, t("def.documentos"), str(erro))
        elif ext == ".pdf":
            self._estado.setText(t("doc.a_processar_pdf"))
            self._correr_fundo(
                lambda: motor_windows.renderizar_pdf(caminho, Path(tempfile.mkdtemp(prefix="kikoia_pdf_"))),
                lambda res: self._pdf_pronto(caminho.stem, res),
            )
        else:
            if not self.carregar_imagem(caminho):
                QMessageBox.warning(self, t("def.documentos"), "Não foi possível abrir a imagem.")

    def _pdf_pronto(self, titulo: str, resultado: tuple) -> None:
        estado, valor = resultado
        if estado == "erro":
            self._estado.setText(str(valor))
            return
        paginas = [PaginaDocumento(imagem=QImage(str(p))) for p in valor if not QImage(str(p)).isNull()]
        if not paginas:
            self._estado.setText("PDF sem páginas.")
            return
        self._repor_tamanho_novo_documento()
        self.documento = Documento(titulo=titulo, paginas=paginas)
        self._ir_pagina(0)
        self._estado.setText(f"{titulo}.pdf ({len(paginas)} pág.)")

    def _guardar_kdoc(self) -> None:
        self.canvas.confirmar_texto_inline()
        if not self.documento.paginas:
            return
        destino, _ = QFileDialog.getSaveFileName(self, t("doc.guardar"), f"{self.documento.titulo}{EXTENSAO_DOC}", f"Documento Kikoia (*{EXTENSAO_DOC})")
        if not destino:
            return
        modelo.guardar_kdoc(self.documento, Path(destino))
        self._estado.setText(t("doc.guardado"))

    def _exportar_pdf(self) -> None:
        self.canvas.confirmar_texto_inline()
        if self._modo_exame or not self.documento.paginas:
            return
        destino, _ = QFileDialog.getSaveFileName(self, t("doc.exportar_pdf"), f"{self.documento.titulo}.pdf", "PDF (*.pdf)")
        if not destino:
            return
        try:
            modelo.exportar_pdf(self.documento, Path(destino))
            self._estado.setText(t("doc.pdf_exportado"))
        except Exception as erro:
            QMessageBox.warning(self, t("doc.exportar_pdf"), str(erro))

    # --- Modo Scanner, OCR Offline Windows e Leitura em Voz Alta ------------------

    def _aplicar_scanner(self) -> None:
        p = self._pagina_atual()
        if p is None or p.imagem.isNull():
            return
        p.imagem = motor_windows.melhorar_foto_scanner(p.imagem)
        self.canvas.update()
        self._estado.setText(t("doc.scanner_ok"))

    def _executar_ocr(self) -> None:
        p = self._pagina_atual()
        if p is None or p.imagem.isNull():
            return
        self._estado.setText(t("doc.a_extrair_ocr"))
        self._btn_ocr.setEnabled(False)
        tmp = Path(tempfile.mkdtemp(prefix="kikoia_ocr_")) / "pagina.jpg"
        p.imagem.convertToFormat(QImage.Format.Format_RGB32).save(str(tmp), "JPEG", 95)
        lingua = idiomas.atual()
        self._correr_fundo(
            lambda: motor_windows.extrair_ocr(tmp, lingua),
            lambda res: self._ocr_pronto(p, res),
        )

    def _ocr_pronto(self, pagina: PaginaDocumento, resultado: tuple) -> None:
        self._btn_ocr.setEnabled(True)
        estado, valor = resultado
        if estado == "erro":
            self._estado.setText(str(valor))
            return
        pagina.texto_ocr = valor.texto
        pagina.linhas_ocr = [{"texto": l.texto, "x": l.x, "y": l.y, "w": l.w, "h": l.h} for l in valor.linhas]
        if self._pagina_atual() is pagina:
            self._editor_ocr.blockSignals(True)
            self._editor_ocr.setPlainText(pagina.texto_ocr)
            self._editor_ocr.blockSignals(False)
            self._painel_ocr.setVisible(True)
        self._estado.setText(t("doc.ocr_concluido", n=len(valor.linhas)))

    def _ler_voz(self) -> None:
        p = self._pagina_atual()
        if p is None:
            return
        texto = self._editor_ocr.toPlainText().strip() or p.texto_ocr.strip()
        if not texto:
            self._executar_ocr()
            return
        try:
            voz.ler(texto)
        except Exception as erro:
            self._estado.setText(str(erro))

    # --- 🔒 Modo Exame (bloqueio por palavra-passe do professor) -------------------

    @staticmethod
    def _hash_pw(pw: str) -> str:
        return hashlib.sha256(pw.encode("utf-8")).hexdigest()

    def ativar_modo_exame(self, palavra_passe: str) -> bool:
        """Ativa o Modo Exame em Full Screen (cobrindo a barra de tarefas) + relógio discreto."""
        if not palavra_passe.strip():
            return False
        self._hash_exame = self._hash_pw(palavra_passe)
        self._modo_exame = True
        self._geometria_normal = self.geometry()
        self._banner_exame.setVisible(True)
        self._btn_abrir.setEnabled(False)
        self._btn_pdf.setEnabled(False)
        self._btn_scanner.setEnabled(False)
        self._btn_fechar.setEnabled(False)
        self._btn_exame.setText(t("doc.desbloquear_exame"))
        self._btn_exame.setProperty("papel", "exame_ativo")
        self._btn_exame.style().unpolish(self._btn_exame)
        self._btn_exame.style().polish(self._btn_exame)
        self._atualizar_relogio()
        self._relogio.setVisible(True)
        self._timer_relogio.start()
        self._timer_vigia_exame.start()
        self._aplicar_geometria_exame()
        return True

    def _aplicar_geometria_exame(self) -> None:
        """Full screen real + sempre no topo (cobre notificações e impede Alt+Tab).
        Se o Teclado Kikoia estiver a reservar espaço no fundo (AppBar > 110 px),
        respeita apenas a faixa do teclado sem expor a barra de tarefas."""
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        ecra = self.screen() or QGuiApplication.primaryScreen()
        if ecra is not None:
            total = ecra.geometry()
            util = ecra.availableGeometry()
            faixa_fundo = total.bottom() - util.bottom()
            if faixa_fundo > 110:
                if self.isFullScreen():
                    self.showNormal()
                self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                self.setGeometry(total.x(), total.y(), total.width(), util.bottom() - total.y() + 1)
                self.show()
            elif sys.platform != "win32":
                # Em XWayland/Mutter no Linux, QDialog.showFullScreen() pode ser ignorado pelo gestor;
                # usa janela sem moldura ocupando a totalidade do monitor.
                if self.isFullScreen():
                    self.showNormal()
                self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                self.setGeometry(total)
                self.show()
            else:
                self.showFullScreen()
        else:
            self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def _vigiar_foco_exame(self) -> None:
        """Em Modo Exame, se Alt+Tab ou uma notificação roubar o foco para outra app, recupera-o logo."""
        if not self._modo_exame or self._pedindo_senha_exame:
            return
        if not self.isActiveWindow():
            self.raise_()
            self.activateWindow()

    def desbloquear_modo_exame(self, palavra_passe: str) -> bool:
        """Desbloqueia o Modo Exame se a palavra-passe coincidir."""
        if not self._modo_exame:
            return True
        if self._hash_exame != self._hash_pw(palavra_passe):
            return False
        self._modo_exame = False
        self._hash_exame = None
        self._banner_exame.setVisible(False)
        self._timer_relogio.stop()
        self._timer_vigia_exame.stop()
        self._relogio.setVisible(False)
        self._btn_abrir.setEnabled(True)
        self._btn_fechar.setEnabled(True)
        self._btn_exame.setText(t("doc.modo_exame"))
        self._btn_exame.setProperty("papel", "exame")
        self._btn_exame.style().unpolish(self._btn_exame)
        self._btn_exame.style().polish(self._btn_exame)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        if self.isFullScreen():
            self.showNormal()
        self.show()
        self._adaptador_area.ajustar()
        self._atualizar_navegacao()
        return True

    def _alternar_modo_exame(self) -> None:
        if not self._modo_exame:
            pw, ok = QInputDialog.getText(self, t("doc.modo_exame"), t("doc.exame_pedir_pw"), QLineEdit.EchoMode.Password)
            if ok and pw.strip():
                self.ativar_modo_exame(pw)
        else:
            self._pedindo_senha_exame = True
            try:
                pw, ok = QInputDialog.getText(self, t("doc.modo_exame"), t("doc.exame_confirmar_pw"), QLineEdit.EchoMode.Password)
            finally:
                self._pedindo_senha_exame = False
            if ok:
                if not self.desbloquear_modo_exame(pw):
                    QMessageBox.warning(self, t("doc.modo_exame"), t("doc.exame_pw_errada"))

    def _ao_mudar_area_exame(self, _area) -> None:
        if not self._encerrado and self._modo_exame:
            self._aplicar_geometria_exame()

    def _encerrar_recursos(self) -> None:
        """Para temporizadores, desliga sinais de ecrã e impede callbacks de threads após fechar."""
        if self._encerrado:
            return
        self._encerrado = True
        self.canvas.confirmar_texto_inline()
        self._timer_relogio.stop()
        self._timer_vigia_exame.stop()
        voz.parar()
        if self._ecra_exame is not None:
            try:
                self._ecra_exame.availableGeometryChanged.disconnect(self._ao_mudar_area_exame)
            except (RuntimeError, TypeError):
                pass
            self._ecra_exame = None
        if hasattr(self, "_adaptador_area") and self._adaptador_area is not None:
            self._adaptador_area._desligar()

    def _tentar_fechar(self) -> None:
        if self._modo_exame:
            QMessageBox.warning(self, t("doc.modo_exame"), t("doc.exame_bloqueado"))
            return
        self.accept()

    def done(self, resultado: int) -> None:  # noqa: N802
        if self._modo_exame:
            self._estado.setText(t("doc.exame_bloqueado"))
            return
        self._encerrar_recursos()
        super().done(resultado)

    def reject(self) -> None:
        # Bloqueia fechar com tecla ESC durante o Modo Exame!
        if self._modo_exame:
            self._estado.setText(t("doc.exame_bloqueado"))
            return
        self._encerrar_recursos()
        super().reject()

    def closeEvent(self, evento) -> None:  # noqa: N802
        # Bloqueia fechar com X ou Alt+F4 durante o Modo Exame!
        if self._modo_exame:
            evento.ignore()
            self._estado.setText(t("doc.exame_bloqueado"))
            return
        self._encerrar_recursos()
        super().closeEvent(evento)

    def _correr_fundo(self, trabalho, ao_terminar) -> None:
        sinal = _SinalFundo(self)
        self._sinais_fundo.append(sinal)

        def _entregar(res) -> None:
            try:
                self._sinais_fundo.remove(sinal)
            except ValueError:
                pass
            if not self._encerrado:
                ao_terminar(res)

        sinal.terminou.connect(_entregar, Qt.ConnectionType.QueuedConnection)

        def _exec() -> None:
            try:
                res = ("ok", trabalho())
            except Exception as erro:
                res = ("erro", str(erro))
            if self._encerrado:
                return
            try:
                sinal.terminou.emit(res)
            except RuntimeError:
                pass

        threading.Thread(target=_exec, daemon=True, name="quadro-doc").start()
