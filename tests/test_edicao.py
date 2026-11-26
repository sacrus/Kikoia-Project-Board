from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from quadro.janela import JanelaQuadro
from quadro.modelo import Quadro, distancia_ao_traco


def _app():
    return QApplication.instance() or QApplication([])


def _risco(quadro, cor, x0, y0, x1, y1):
    quadro.registar()
    traco = quadro.comecar_traco(cor, 0.01, x0, y0)
    quadro.acrescentar_ponto(traco, x1, y1)
    return traco


def test_desfazer_retira_os_riscos_do_mais_recente_para_o_mais_antigo():
    quadro = Quadro()
    _risco(quadro, "#000000", 0.1, 0.1, 0.2, 0.2)
    _risco(quadro, "#e11d48", 0.3, 0.3, 0.4, 0.4)
    _risco(quadro, "#2563eb", 0.5, 0.5, 0.6, 0.6)

    assert quadro.desfazer()
    assert [t.cor for t in quadro.tracos] == ["#000000", "#e11d48"]
    assert quadro.desfazer()
    assert [t.cor for t in quadro.tracos] == ["#000000"]
    assert quadro.desfazer()
    assert quadro.tracos == []
    assert not quadro.desfazer()


def test_refazer_volta_a_colocar_os_riscos_por_ordem():
    quadro = Quadro()
    _risco(quadro, "#000000", 0.1, 0.1, 0.2, 0.2)
    _risco(quadro, "#e11d48", 0.3, 0.3, 0.4, 0.4)
    quadro.desfazer()
    quadro.desfazer()
    assert quadro.refazer()
    assert [t.cor for t in quadro.tracos] == ["#000000"]
    assert quadro.refazer()
    assert [t.cor for t in quadro.tracos] == ["#000000", "#e11d48"]
    assert not quadro.refazer()


def test_nova_alteracao_apaga_o_refazer():
    quadro = Quadro()
    _risco(quadro, "#000000", 0.1, 0.1, 0.2, 0.2)
    quadro.desfazer()
    _risco(quadro, "#e11d48", 0.3, 0.3, 0.4, 0.4)
    assert not quadro.pode_refazer()


def test_desfazer_repoe_a_cor_de_fundo():
    quadro = Quadro("#ffffff")
    quadro.registar()
    quadro.fundo = "#222222"
    quadro.desfazer()
    assert quadro.fundo == "#ffffff"


def test_distancia_mede_ao_segmento_e_nao_so_aos_pontos():
    quadro = Quadro()
    traco = quadro.comecar_traco("#000000", 0.01, 0.0, 0.5)
    quadro.acrescentar_ponto(traco, 1.0, 0.5)
    assert abs(distancia_ao_traco(traco, 0.5, 0.52)) < 0.03
    assert distancia_ao_traco(traco, 0.5, 0.9) > 0.3


def test_traco_em_devolve_o_mais_recente_sobreposto():
    quadro = Quadro()
    _risco(quadro, "#000000", 0.1, 0.5, 0.9, 0.5)
    _risco(quadro, "#e11d48", 0.1, 0.5, 0.9, 0.5)
    escolhido = quadro.traco_em(0.5, 0.5, 0.01)
    assert escolhido.cor == "#e11d48"
    assert quadro.traco_em(0.5, 0.9, 0.01) is None


def test_area_seleciona_os_riscos_que_la_passam():
    quadro = Quadro()
    dentro = _risco(quadro, "#000000", 0.2, 0.2, 0.3, 0.3)
    _risco(quadro, "#000000", 0.8, 0.8, 0.9, 0.9)
    assert quadro.tracos_na_area(0.1, 0.1, 0.4, 0.4) == [dentro]


def test_remover_e_mudar_cor_sao_desfazíveis():
    quadro = Quadro()
    traco = _risco(quadro, "#000000", 0.1, 0.1, 0.2, 0.2)
    quadro.registar()
    quadro.mudar_cor([traco], "#2563eb")
    assert quadro.tracos[0].cor == "#2563eb"
    quadro.desfazer()
    assert quadro.tracos[0].cor == "#000000"
    quadro.registar()
    quadro.remover([quadro.tracos[0]])
    assert quadro.tracos == []
    quadro.desfazer()
    assert len(quadro.tracos) == 1


def _carregar_esc(janela):
    for atalho in janela.findChildren(QShortcut):
        if atalho.key() == QKeySequence(Qt.Key.Key_Escape):
            atalho.activated.emit()
            return
    raise AssertionError("atalho Esc não encontrado")


def test_menu_escondido_e_mostrado_pela_tecla_esc():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    janela.ocultar_menu()
    assert janela.menu.isHidden()
    assert not janela._aviso.isHidden()

    _carregar_esc(janela)
    assert not janela.menu.isHidden()
    assert janela._aviso.isHidden()
    janela.close()


def test_esc_com_menu_visivel_nao_fecha_o_programa():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    _carregar_esc(janela)
    assert janela.isVisible()
    janela.close()


def test_desfazer_pela_janela_atualiza_o_menu():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    _risco(janela.quadro, "#000000", 0.1, 0.1, 0.2, 0.2)
    janela.tela.alterou.emit()
    assert janela.menu._desfazer_botao.isEnabled()
    janela.desfazer()
    assert not janela.menu._desfazer_botao.isEnabled()
    assert janela.menu._refazer_botao.isEnabled()
    janela.close()


def test_varinha_seleciona_um_risco_e_apaga_a_selecao():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    _risco(janela.quadro, "#000000", 0.1, 0.5, 0.9, 0.5)
    janela.tela.ferramenta = "varinha"
    janela.tela.alterou.emit()
    tela = janela.tela
    alvo = QPointF(tela.width() * 0.5, tela.height() * 0.5)
    QTest.mousePress(tela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, alvo.toPoint())
    QTest.mouseRelease(tela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, alvo.toPoint())
    assert len(tela.selecao) == 1
    janela.apagar_selecao()
    assert janela.quadro.tracos == []
    janela.desfazer()
    assert len(janela.quadro.tracos) == 1
    janela.close()
