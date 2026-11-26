import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from quadro.documentos import modelo, motor_windows
from quadro.documentos.janela_documentos import DialogoDocumentos
from quadro.documentos.modelo import CaixaTextoDoc, Documento, MarcaDoc, PaginaDocumento, TracoDoc


def _imagem_teste(texto: str = "Questao 1 Estudo do Meio") -> QImage:
    img = QImage(600, 220, QImage.Format.Format_ARGB32)
    img.fill(QColor("#E5E7EB"))
    p = QPainter(img)
    p.setPen(QColor("#111827"))
    p.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
    p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, texto)
    p.end()
    return img


def test_guardar_abrir_kdoc_e_exportar_pdf(tmp_path):
    QApplication.instance() or QApplication([])
    img = _imagem_teste()
    pagina = PaginaDocumento(
        imagem=img,
        tracos=[TracoDoc("#FACC15", 0.02, "marcador", [(0.1, 0.2), (0.4, 0.2)])],
        marcas=[MarcaDoc("x", 0.5, 0.5, "#EF4444")],
        textos=[CaixaTextoDoc(0.2, 0.8, "João", "#1D4ED8")],
        texto_ocr="Questao 1",
    )
    doc = Documento(titulo="Ficha1", paginas=[pagina])

    kdoc = tmp_path / "ficha.kdoc"
    modelo.guardar_kdoc(doc, kdoc)
    lido = modelo.abrir_kdoc(kdoc)
    assert lido.titulo == "Ficha1"
    assert len(lido.paginas) == 1
    assert len(lido.paginas[0].tracos) == 1
    assert lido.paginas[0].textos[0].texto == "João"

    pdf = tmp_path / "ficha.pdf"
    modelo.exportar_pdf(doc, pdf)
    assert pdf.is_file() and pdf.stat().st_size > 1000


def test_modo_scanner_limpa_fundo_cinzento():
    QApplication.instance() or QApplication([])
    img = _imagem_teste()
    limpa = motor_windows.melhorar_foto_scanner(img)
    assert not limpa.isNull()
    canto = QColor(limpa.pixel(5, 5))
    assert canto.red() >= 245 and canto.green() >= 245 and canto.blue() >= 245


def test_ocr_windows_nativo_extrai_texto(tmp_path):
    if sys.platform != "win32":
        return
    import subprocess

    caminho = tmp_path / "ficha_ocr.jpg"
    # Gera uma imagem com texto usando GDI+ do Windows (independente de QT_QPA_PLATFORM=offscreen)
    ps = (
        "Add-Type -AssemblyName System.Drawing; "
        "$b = New-Object System.Drawing.Bitmap(700, 180); "
        "$g = [System.Drawing.Graphics]::FromImage($b); "
        "$g.Clear([System.Drawing.Color]::White); "
        "$f = New-Object System.Drawing.Font('Arial', 36, [System.Drawing.FontStyle]::Bold); "
        "$g.DrawString('Pinta as etiquetas', $f, [System.Drawing.Brushes]::Black, 40, 50); "
        f"$b.Save('{caminho}', [System.Drawing.Imaging.ImageFormat]::Jpeg); "
        "$g.Dispose(); $b.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    res = motor_windows.extrair_ocr(caminho, "pt-PT")
    assert "Pinta" in res.texto and "etiquetas" in res.texto
    assert len(res.linhas) >= 1


def test_modo_exame_bloqueia_saida_ate_palavra_passe_correta(tmp_path):
    QApplication.instance() or QApplication([])
    dlg = DialogoDocumentos()
    try:
        img_path = tmp_path / "ficha.png"
        _imagem_teste().save(str(img_path), "PNG")
        assert dlg.carregar_imagem(img_path) is True

        assert dlg.ativar_modo_exame("prof123") is True
        assert dlg._modo_exame is True
        assert dlg._btn_abrir.isEnabled() is False
        assert dlg._btn_fechar.isEnabled() is False

        # Tentar fechar com ESC ou X é bloqueado
        ev = QCloseEvent()
        dlg.closeEvent(ev)
        assert ev.isAccepted() is False

        # Palavra-passe errada não desbloqueia
        assert dlg.desbloquear_modo_exame("errada") is False
        assert dlg._modo_exame is True

        # Palavra-passe correta desbloqueia
        assert dlg.desbloquear_modo_exame("prof123") is True
        assert dlg._modo_exame is False
        assert dlg._btn_abrir.isEnabled() is True
    finally:
        dlg._modo_exame = False
        dlg.close()


def test_editor_texto_inline_em_tempo_real(tmp_path):
    QApplication.instance() or QApplication([])
    dlg = DialogoDocumentos()
    try:
        img_path = tmp_path / "ficha.png"
        _imagem_teste().save(str(img_path), "PNG")
        dlg.carregar_imagem(img_path)
        dlg._escolher_ferramenta("texto")
        dlg.canvas._rect_pagina = dlg.canvas._calcular_rect_pagina()
        dlg.canvas._editar_ou_criar_texto((0.3, 0.4))
        assert dlg.canvas._editor_inline is not None
        dlg.canvas._editor_inline.campo.setPlainText("Linha 1\nLinha 2")
        dlg.canvas.confirmar_texto_inline()
        assert dlg.canvas._editor_inline is None
        assert len(dlg._pagina_atual().textos) == 1
        assert dlg._pagina_atual().textos[0].texto == "Linha 1\nLinha 2"

        # Clicar logo abaixo (fora da caixa anterior) cria uma NOVA caixa em vez de editar a anterior
        dlg.canvas._editar_ou_criar_texto((0.3, 0.65))
        assert dlg.canvas._editor_inline is not None
        assert dlg.canvas._editor_inline.campo.toPlainText() == ""
        dlg.canvas._editor_inline.campo.setPlainText("Segunda resposta")
        dlg.canvas.confirmar_texto_inline()
        assert len(dlg._pagina_atual().textos) == 2
    finally:
        dlg.close()
