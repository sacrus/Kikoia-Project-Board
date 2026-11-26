from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from quadro import textos
from quadro.janela import JanelaQuadro
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro


def _app():
    return QApplication.instance() or QApplication([])


def _tem_tinta(imagem, x0, y0, x1, y1):
    for x in range(int(x0 * CAMADA_LARGURA), int(x1 * CAMADA_LARGURA), 3):
        for y in range(int(y0 * CAMADA_ALTURA), int(y1 * CAMADA_ALTURA), 3):
            if imagem.pixelColor(x, y).alpha() > 0:
                return True
    return False


def _janela():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.resize(800, 600)
    janela.show()
    return janela


def test_escrever_pinta_texto_a_partir_do_ponto_indicado():
    _app()
    quadro = Quadro()
    assert textos.escrever(quadro, "Olá", 0.2, 0.3, 0.1, "#e11d48")
    assert _tem_tinta(quadro.camada_carimbos, 0.2, 0.3, 0.5, 0.5)
    assert not _tem_tinta(quadro.camada_carimbos, 0.8, 0.8, 0.95, 0.95)


def test_texto_vazio_nao_escreve_nada():
    quadro = Quadro()
    assert not textos.escrever(quadro, "   ", 0.2, 0.3, 0.1, "#000000")
    assert quadro.camada_carimbos is None


def test_toque_no_quadro_abre_a_caixa_no_ponto():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "texto"
        QTest.mouseClick(tela, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(int(tela.width() * 0.2), int(tela.height() * 0.3)))
        assert tela._caixa is not None
        assert abs(tela._caixa.x_norm - 0.2) < 0.02
    finally:
        janela.close()


def test_novo_toque_move_a_caixa_sem_criar_outra():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "texto"
        tela._tocar_texto(0.2, 0.2)
        caixa = tela._caixa
        tela._tocar_texto(0.5, 0.4)
        assert tela._caixa is caixa
        assert abs(caixa.x_norm - 0.5) < 0.02
    finally:
        janela.close()


def test_setas_deslocam_a_caixa_e_nao_saem_do_quadro():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "texto"
        tela._tocar_texto(0.5, 0.5)
        caixa = tela._caixa
        antes = caixa.x_norm
        caixa.mover(caixa.PASSO, 0)
        assert caixa.x_norm > antes
        tela._tocar_texto(0.999, 0.999)
        assert caixa.x_norm + caixa.width() / tela.width() <= 1.0001
        assert caixa.y_norm + caixa.height() / tela.height() <= 1.0001
    finally:
        janela.close()


def test_certo_grava_o_texto_na_posicao_da_caixa_e_desfaz():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "texto"
        tela._tocar_texto(0.3, 0.3)
        tela._caixa.campo.setText("Olá")
        tela.confirmar_texto()
        assert tela._caixa is None
        assert _tem_tinta(janela.quadro.camada_carimbos, 0.3, 0.3, 0.5, 0.45)
        janela.desfazer()
        assert janela.quadro.camada_carimbos is None
    finally:
        janela.close()


def test_cancelar_nao_grava_nada():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "texto"
        tela._tocar_texto(0.3, 0.3)
        tela._caixa.campo.setText("Olá")
        tela.cancelar_texto()
        assert tela._caixa is None
        assert janela.quadro.camada_carimbos is None
        assert not janela.quadro.pode_desfazer()
    finally:
        janela.close()


def test_texto_vazio_ao_confirmar_nao_cria_passo_de_desfazer():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "texto"
        tela._tocar_texto(0.3, 0.3)
        tela.confirmar_texto()
        assert not janela.quadro.pode_desfazer()
    finally:
        janela.close()


def test_mudar_de_ferramenta_cancela_a_caixa():
    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "texto"
        tela._tocar_texto(0.3, 0.3)
        janela.menu._escolher_ferramenta("caneta")
        assert tela._caixa is None
    finally:
        janela.close()


def test_tamanho_muda_a_caixa_e_fica_guardado_para_a_proxima():
    from quadro.janela import TEXTO_TAMANHOS

    janela = _janela()
    try:
        tela = janela.tela
        tela.ferramenta = "texto"
        tela._tocar_texto(0.3, 0.3)
        tela._caixa.definir_tamanho(TEXTO_TAMANHOS[3])
        tela._caixa.campo.setText("X")
        tela.confirmar_texto()
        assert tela.tamanho_texto == TEXTO_TAMANHOS[3]
    finally:
        janela.close()
