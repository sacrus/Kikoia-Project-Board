"""Testes da adaptação automática de janelas/diálogos do Quadro à área útil (Teclado Kikoia)."""

from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QDialog

from quadro.area_util import adaptar_a_area_util


class _EcraFalso:
    def __init__(self, area: QRect) -> None:
        self._area = area

    def availableGeometry(self) -> QRect:  # noqa: N802
        return self._area

    class _SinalFalso:
        def connect(self, _cb) -> None:
            pass

        def disconnect(self, _cb) -> None:
            pass

    availableGeometryChanged = _SinalFalso()


def test_dialogo_normal_encolhe_e_centra_acima_do_teclado():
    QApplication.instance() or QApplication([])
    dlg = QDialog()
    dlg.resize(880, 680)
    adapt = adaptar_a_area_util(dlg)
    # Simula ecrã 1366x768 com Teclado Kikoia a ocupar 310 px no fundo -> área útil 1366x458
    adapt._ecra_atual = lambda: _EcraFalso(QRect(0, 0, 1366, 458))  # type: ignore[method-assign]
    adapt.ajustar()
    assert dlg.geometry().bottom() <= 458
    assert dlg.width() <= 880
    assert dlg.height() < 458
    dlg.close()


def test_dialogo_maximizado_ocupa_area_util_acima_do_teclado():
    QApplication.instance() or QApplication([])
    dlg = QDialog()
    dlg.resize(1160, 740)
    adapt = adaptar_a_area_util(dlg, maximizar=True)
    adapt._ecra_atual = lambda: _EcraFalso(QRect(0, 0, 1920, 640))  # type: ignore[method-assign]
    adapt.ajustar()
    assert dlg.geometry().bottom() <= 640
    assert dlg.geometry().width() >= 1880
    # Quando o teclado fecha (área útil aumenta para 1032), expande automaticamente
    adapt._ecra_atual = lambda: _EcraFalso(QRect(0, 0, 1920, 1032))  # type: ignore[method-assign]
    adapt.ajustar()
    assert dlg.geometry().height() > 950
    assert dlg.geometry().bottom() <= 1032
    dlg.close()
