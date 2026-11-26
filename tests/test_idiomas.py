import json
from pathlib import Path

from PySide6.QtWidgets import QApplication

from quadro import idiomas
from quadro.janela import DialogoDefinicoes, JanelaQuadro
from quadro.modelo import Quadro

PASTA = Path(__file__).resolve().parent.parent / "data" / "idiomas"


def test_todos_os_quatro_idiomas_tem_as_mesmas_chaves():
    base = set(json.loads((PASTA / "pt-PT.json").read_text(encoding="utf-8")).keys())
    assert len(base) >= 100
    for codigo in ("en", "es", "fr"):
        chaves = set(json.loads((PASTA / f"{codigo}.json").read_text(encoding="utf-8")).keys())
        assert chaves == base


def test_definicoes_muda_idioma_ao_vivo_e_guarda_partilhado(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    idiomas.definir("pt-PT", guardar=False)
    QApplication.instance() or QApplication([])
    janela = JanelaQuadro(Quadro())
    dlg = DialogoDefinicoes(janela)
    try:
        assert dlg.windowTitle() == "Definições"
        idx_en = dlg._combo_idioma.findData("en")
        dlg._combo_idioma.setCurrentIndex(idx_en)
        assert idiomas.atual() == "en"
        assert dlg.windowTitle() == "Settings"
        assert idiomas.ler_partilhado()["idioma"] == "en"
    finally:
        idiomas.definir("pt-PT", guardar=False)
        dlg.close()
        janela.close()
