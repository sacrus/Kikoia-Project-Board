import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def pasta_local_isolada(monkeypatch, tmp_path):
    """Os testes não tocam nas contas, regras e segredos reais do utilizador (%LOCALAPPDATA% / $XDG_DATA_HOME)."""
    from quadro import idiomas

    pasta_local = str(tmp_path / "local")
    monkeypatch.setenv("LOCALAPPDATA", pasta_local)
    monkeypatch.setenv("XDG_DATA_HOME", pasta_local)
    idiomas.definir("pt-PT", guardar=False)


def pytest_sessionfinish(session, exitstatus):
    import gc

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        for janela in app.topLevelWidgets():
            janela.close()
            janela.deleteLater()
        app.processEvents()
    gc.collect()
