"""Testes de compatibilidade Linux do Quadro Interativo (XDG, segredos, PDF, OCR, voz, sons, JXL e catálogo)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from quadro import catalogo, jxl, paths, segredos_app
from quadro.correio import regras, segredos, voz
from quadro.correio.modelo import ErroCorreio
from quadro.documentos import modelo, motor_windows
from quadro.documentos.modelo import Documento, PaginaDocumento

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="testes específicos de Linux")


def test_paths_usa_xdg_data_home_quando_localappdata_ausente(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert paths.pasta_kikoia() == tmp_path / "xdg" / "Kikoia"
    assert paths.pasta_quadro() == tmp_path / "xdg" / "Kikoia" / "Quadro"


def test_segredos_linux_ida_e_volta_e_recusa_adulteracao():
    cifrado = segredos.cifrar("palavra-secreta-linux-2026")
    assert b"palavra-secreta" not in cifrado
    assert segredos.decifrar(cifrado) == "palavra-secreta-linux-2026"

    with pytest.raises(ErroCorreio):
        segredos.decifrar(b"dados-corrompidos")

    segredos_app.gravar({"openverse_client_id": "id-123", "openverse_client_secret": "sec-456"})
    assert segredos_app.obter("openverse_client_id") == "id-123"
    assert segredos_app.obter("openverse_client_secret") == "sec-456"


def test_renderizar_pdf_linux_converte_paginas_em_png(tmp_path):
    QApplication.instance() or QApplication([])
    img1 = QImage(400, 300, QImage.Format.Format_ARGB32)
    img1.fill(QColor("#FFFFFF"))
    img2 = QImage(400, 300, QImage.Format.Format_ARGB32)
    img2.fill(QColor("#F1F5F9"))

    doc = Documento(titulo="TestePDF", paginas=[PaginaDocumento(imagem=img1), PaginaDocumento(imagem=img2)])
    pdf_path = tmp_path / "ficha_duas_paginas.pdf"
    modelo.exportar_pdf(doc, pdf_path)
    assert pdf_path.is_file()

    saida = tmp_path / "paginas_png"
    geradas = motor_windows.renderizar_pdf(pdf_path, saida)
    assert len(geradas) == 2
    for p in geradas:
        lida = QImage(str(p))
        assert not lida.isNull()
        assert lida.width() >= 800


def test_ocr_linux_interpreta_tsv_do_tesseract(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    img_path = tmp_path / "ficha.png"
    img = QImage(500, 200, QImage.Format.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    img.save(str(img_path), "PNG")

    tsv_falso = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t50\t40\t120\t30\t95.2\tOlá\n"
        "5\t1\t1\t1\t1\t2\t180\t40\t150\t30\t93.1\tEscola\n"
        "5\t1\t1\t1\t2\t1\t50\t90\t200\t28\t91.0\tExercício\n"
    )

    class _Proc:
        def __init__(self, stdout: str):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    def _run_falso(cmd, *args, **kwargs):
        if "--list-langs" in cmd:
            return _Proc("List of available languages (2):\npor\neng\n")
        return _Proc(tsv_falso)

    monkeypatch.setattr(shutil, "which", lambda nome: "/usr/bin/tesseract" if nome == "tesseract" else None)
    import subprocess
    monkeypatch.setattr(subprocess, "run", _run_falso)

    res = motor_windows.extrair_ocr(img_path, "pt-PT")
    assert res.texto == "Olá Escola\nExercício"
    assert len(res.linhas) == 2
    assert res.linhas[0].texto == "Olá Escola"
    assert 0.0 < res.linhas[0].x < 1.0 and 0.0 < res.linhas[0].w <= 1.0


def test_voz_linux_alias_ler_e_sem_texto_no_comando(monkeypatch, tmp_path):
    assert voz.ler is voz.falar
    assert voz.falar("   ") is None

    monkeypatch.setattr(voz, "_procurar_voz_piper", lambda idioma: None)
    monkeypatch.setattr(shutil, "which", lambda nome: "/usr/bin/espeak-ng" if nome == "espeak-ng" else None)
    cmd = voz.comando_linux("pt-PT")
    assert cmd == ["/usr/bin/espeak-ng", "--stdin", "-v", "pt-pt"]


def test_jxl_linux_encontra_binario_do_sistema(monkeypatch, tmp_path):
    bin_falso = tmp_path / "cjxl"
    bin_falso.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda nome: str(bin_falso) if nome == "cjxl" else None)
    assert jxl.ferramenta("cjxl") == bin_falso


def test_regras_correio_bloqueiam_extensoes_executaveis_linux():
    for ext in (".sh", ".appimage", ".deb", ".rpm", ".desktop", ".run", ".bin"):
        assert ext in regras.EXTENSOES_EXECUTAVEIS


def test_catalogo_linux_deteta_binarios_nativos(monkeypatch, tmp_path):
    raiz = Path(__file__).resolve().parent.parent / "Resources"
    resumos = catalogo.carregar_indice(str(raiz))
    jogos_por_id = {r.id: catalogo.carregar_jogo(r, str(raiz)) for r in resumos if r.id in ("gcompris", "simon-blackbox")}

    bin_gcompris = tmp_path / "gcompris-qt"
    bin_gcompris.write_text("#!/bin/sh\n", encoding="utf-8")
    bin_puzzle = tmp_path / "sgt-blackbox"
    bin_puzzle.write_text("#!/bin/sh\n", encoding="utf-8")

    def _which(nome: str):
        if nome == "gcompris-qt":
            return str(bin_gcompris)
        if nome == "sgt-blackbox":
            return str(bin_puzzle)
        return None

    monkeypatch.setattr(shutil, "which", _which)
    assert catalogo.executavel_instalado(jogos_por_id["gcompris"]) == bin_gcompris
    assert catalogo.executavel_instalado(jogos_por_id["simon-blackbox"]) == bin_puzzle


def test_transferir_linux_gcompris_verifica_sha_e_extrai(tmp_path):
    import hashlib

    raiz = Path(__file__).resolve().parent.parent / "Resources"
    resumos = catalogo.carregar_indice(str(raiz))
    gcompris = next(catalogo.carregar_jogo(r, str(raiz)) for r in resumos if r.id == "gcompris")

    # Simula auto-extrator CPack oficial do GCompris
    script_falso = (
        "#!/bin/sh\n"
        "for a in \"$@\"; do\n"
        "  case \"$a\" in --prefix=*) DEST=\"${a#--prefix=}\" ;; esac\n"
        "done\n"
        "mkdir -p \"$DEST/bin\"\n"
        "printf '#!/bin/sh\\nexit 0\\n' > \"$DEST/bin/gcompris-qt.sh\"\n"
        "chmod +x \"$DEST/bin/gcompris-qt.sh\"\n"
    ).encode("utf-8")
    sha = hashlib.sha256(script_falso).hexdigest()
    gcompris.instalacao_linux = catalogo.InstalacaoLinux(
        tipo="pacote_oficial",
        fonte="https://download.kde.org/gcompris.sh",
        ficheiro="gcompris.sh",
        sha256=sha,
        executavel="gcompris-qt.sh",
    )

    pasta_jogos = tmp_path / "jogos"
    exe = catalogo.transferir_linux(
        gcompris,
        pasta=pasta_jogos,
        baixar=lambda url, dest, prog: dest.write_bytes(script_falso),
    )
    assert exe == pasta_jogos / "gcompris" / "bin" / "gcompris-qt.sh"
    assert exe.is_file()


def test_abrir_anexo_correio_usa_qdesktopservices_no_linux(monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from quadro.correio.modelo import Anexo, Mensagem, conta_cpanel
    from quadro.correio.regras import Regras
    from quadro.janela_correio import DialogoCorreio

    QApplication.instance() or QApplication([])
    abertos = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: (abertos.append(url.toLocalFile()), True)[1])

    dlg = DialogoCorreio()
    try:
        msg = Mensagem(
            uid="1",
            remetente="prof@escola.pt",
            destinatarios=("aluno@escola.pt",),
            assunto="Ficha",
            data="Mon, 16 Nov 2026 10:00:00 +0000",
            texto="Olá",
            anexos=(Anexo("ficha.pdf", "application/pdf", 4, b"%PDF"),),
        )
        dlg._conta = conta_cpanel("aluno@escola.pt")
        dlg._regras = Regras(remetentes=["prof@escola.pt"])
        dlg._mensagens = [msg]
        dlg._recarregar_lista()
        dlg._lista.setCurrentRow(0)
        dlg._anexos.setCurrentRow(0)
        dlg._abrir_anexo()
        assert len(abertos) == 1 and abertos[0].endswith("ficha.pdf")
    finally:
        dlg.close()
