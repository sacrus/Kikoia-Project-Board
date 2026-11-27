"""Adaptação automática de janelas e diálogos do Quadro à área útil do ecrã.

Quando o Teclado Kikoia está visível, reserva espaço no fundo do ecrã via AppBar
(Windows) ou _NET_WM_STRUT_PARTIAL (Linux), reduzindo `QScreen.availableGeometry()`.
Este módulo garante que todos os diálogos e janelas secundárias do Quadro:
  - nunca ficam escondidos por trás do teclado ao abrir;
  - redimensionam e reposicionam-se em tempo real se o teclado abrir, fechar ou
    mudar de altura (`availableGeometryChanged`);
  - regressam ao tamanho preferido assim que o teclado se esconde.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QWidget


class _AdaptadorAreaUtil(QObject):
    """Mantém uma janela/diálogo dentro de `screen().availableGeometry()`."""

    def __init__(
        self,
        janela: QWidget,
        *,
        maximizar: bool = False,
        margem: int = 12,
        ignorar_se: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(janela)
        self._janela = janela
        self._maximizar = maximizar
        self._margem = margem
        self._ignorar_se = ignorar_se
        self._tamanho_pref = janela.size()
        self._ecra_ligado: QScreen | None = None
        janela.installEventFilter(self)
        janela.destroyed.connect(self._desligar)
        self._ligar_ecra()

    def _desligar(self, *_args) -> None:
        ecra = getattr(self, "_ecra_ligado", None)
        if ecra is not None:
            try:
                ecra.availableGeometryChanged.disconnect(self._ao_mudar_area)
            except (RuntimeError, TypeError):
                pass
            self._ecra_ligado = None
        janela = getattr(self, "_janela", None)
        if janela is not None:
            try:
                janela.removeEventFilter(self)
            except RuntimeError:
                pass
            self._janela = None

    def _ecra_atual(self) -> QScreen | None:
        janela = getattr(self, "_janela", None)
        if janela is None:
            return None
        try:
            return janela.screen() or QGuiApplication.primaryScreen()
        except RuntimeError:
            return None

    def _ligar_ecra(self) -> None:
        ecra = self._ecra_atual()
        if ecra is None or ecra is self._ecra_ligado:
            return
        if self._ecra_ligado is not None:
            try:
                self._ecra_ligado.availableGeometryChanged.disconnect(self._ao_mudar_area)
            except (RuntimeError, TypeError):
                pass
        self._ecra_ligado = ecra
        ecra.availableGeometryChanged.connect(self._ao_mudar_area)

    def _ao_mudar_area(self, _area: QRect) -> None:
        try:
            self.ajustar()
        except RuntimeError:
            self._desligar()

    def _margens_moldura(self) -> tuple[int, int, int, int]:
        """Devolve (esq, topo, dir, baixo) da moldura da janela em píxeis lógicos."""
        if bool(self._janela.windowFlags() & Qt.WindowType.FramelessWindowHint):
            return (0, 0, 0, 0)
        if self._janela.isVisible():
            fg = self._janela.frameGeometry()
            g = self._janela.geometry()
            if fg.height() > g.height() or fg.width() > g.width():
                return (
                    max(0, g.left() - fg.left()),
                    max(0, g.top() - fg.top()),
                    max(0, fg.right() - g.right()),
                    max(0, fg.bottom() - g.bottom()),
                )
        # Estimativa segura antes de a janela estar visível (barra de título Windows ~32px)
        return (8, 34, 8, 8)

    def ajustar(self) -> None:
        if self._ignorar_se is not None and self._ignorar_se():
            return
        ecra = self._ecra_atual()
        if ecra is None:
            return
        self._ligar_ecra()
        area = ecra.availableGeometry()
        if area.width() <= 0 or area.height() <= 0:
            return

        esq, topo, dir_, baixo = self._margens_moldura()
        cliente = area.adjusted(esq, topo, -dir_, -baixo)
        if cliente.width() < 200 or cliente.height() < 160:
            cliente = area

        if self._maximizar:
            # Em vez de WindowMaximized (que em QDialog no Windows pode ignorar o AppBar
            # ao abrir/fechar o teclado), ocupa exatamente a área útil disponível.
            if self._janela.windowState() & Qt.WindowState.WindowMaximized:
                self._janela.setWindowState(self._janela.windowState() & ~Qt.WindowState.WindowMaximized)
            self._janela.setGeometry(cliente)
            return

        m = self._margem
        max_w = max(320, cliente.width() - m * 2)
        max_h = max(240, cliente.height() - m * 2)
        pref_w = self._tamanho_pref.width() if self._tamanho_pref.width() > 0 else 800
        pref_h = self._tamanho_pref.height() if self._tamanho_pref.height() > 0 else 600
        w = min(pref_w, max_w)
        h = min(pref_h, max_h)
        x = cliente.x() + max(0, (cliente.width() - w) // 2)
        y = cliente.y() + max(0, (cliente.height() - h) // 2)
        self._janela.setGeometry(QRect(x, y, w, h))

    def eventFilter(self, obj: QObject, evento: QEvent) -> bool:  # noqa: N802
        janela = getattr(self, "_janela", None)
        if janela is not None and obj is janela:
            tipo = evento.type()
            if tipo == QEvent.Type.Show:
                self._ligar_ecra()
                self.ajustar()
                # Reajusta no próximo ciclo quando a moldura real do SO já está calculada
                QTimer.singleShot(0, self.ajustar)
            elif tipo == QEvent.Type.ScreenChangeInternal:
                self._ligar_ecra()
                self.ajustar()
            elif tipo == QEvent.Type.Destroy:
                self._desligar()
        try:
            return super().eventFilter(obj, evento)
        except RuntimeError:
            return False


def adaptar_a_area_util(
    janela: QWidget,
    *,
    maximizar: bool = False,
    margem: int = 12,
    ignorar_se: Callable[[], bool] | None = None,
) -> _AdaptadorAreaUtil:
    """Liga `janela` à área útil do monitor (respeitando o Teclado Kikoia em tempo real)."""
    adaptador = _AdaptadorAreaUtil(janela, maximizar=maximizar, margem=margem, ignorar_se=ignorar_se)
    janela._adaptador_area_util = adaptador  # type: ignore[attr-defined]
    adaptador.ajustar()
    return adaptador
