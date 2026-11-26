from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from quadro.janela import Tela
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro


def _tela():
    QApplication.instance() or QApplication([])
    tela = Tela(Quadro())
    tela.resize(CAMADA_LARGURA, CAMADA_ALTURA)
    return tela


def _imagem_vermelha():
    imagem = QImage(20, 20, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#ff0000"))
    return imagem


def test_carimbo_so_fica_no_quadro_ao_confirmar():
    tela = _tela()
    tela._abrir_carimbo(0.5, 0.5)
    assert tela._colocacao is not None
    assert tela.quadro.camada_carimbos is None
    tela.confirmar_colocacao()
    assert tela._colocacao is None
    assert tela.quadro.camada_carimbos is not None
    assert tela.quadro.camada_carimbos.pixelColor(CAMADA_LARGURA // 2, CAMADA_ALTURA // 2).alpha() > 0


def test_carimbo_cancelado_nao_deixa_nada():
    tela = _tela()
    tela._abrir_carimbo(0.5, 0.5)
    tela.cancelar_colocacao()
    assert tela._colocacao is None
    assert tela.quadro.camada_carimbos is None


def test_carimbo_movido_antes_de_confirmar_fica_na_nova_posicao():
    tela = _tela()
    tela._abrir_carimbo(0.2, 0.2)
    tela._colocacao.definir_posicao(0.5, 0.5)
    tela.confirmar_colocacao()
    camada = tela.quadro.camada_carimbos
    assert camada.pixelColor(CAMADA_LARGURA // 2, CAMADA_ALTURA // 2).alpha() > 0
    assert camada.pixelColor(int(0.2 * CAMADA_LARGURA), int(0.2 * CAMADA_ALTURA)).alpha() == 0


def test_mudar_de_ferramenta_cancela_o_carimbo_por_colocar():
    tela = _tela()
    tela._abrir_carimbo(0.5, 0.5)
    tela.ao_mudar_ferramenta("caneta")
    assert tela._colocacao is None


def test_imagem_fica_aberta_ao_mudar_de_ferramenta():
    tela = _tela()
    tela.iniciar_imagem(_imagem_vermelha())
    tela.ao_mudar_ferramenta("caneta")
    assert tela._colocacao is not None


def test_imagem_colocada_na_posicao_e_tamanho_escolhidos():
    tela = _tela()
    tela.iniciar_imagem(_imagem_vermelha())
    assert tela.quadro.camada_base is None
    tela._colocacao.definir_posicao(0.25, 0.25)
    tela.confirmar_colocacao()
    base = tela.quadro.camada_base
    assert base is not None
    assert base.pixelColor(int(0.25 * CAMADA_LARGURA), int(0.25 * CAMADA_ALTURA)).alpha() > 0
    assert base.pixelColor(int(0.75 * CAMADA_LARGURA), int(0.75 * CAMADA_ALTURA)).alpha() == 0


def test_imagem_redimensionada_ocupa_mais_area():
    tela = _tela()
    tela.iniciar_imagem(_imagem_vermelha())
    tela._colocacao.definir_posicao(0.5, 0.5)
    tamanho_antes = tela._colocacao.tamanho
    tela._colocacao.redimensionar(2)
    assert tela._colocacao.tamanho > tamanho_antes
    tela.confirmar_colocacao()
    base = tela.quadro.camada_base
    assert base.pixelColor(int(0.5 * CAMADA_LARGURA), int(0.5 * CAMADA_ALTURA)).alpha() > 0
    assert base.pixelColor(int(0.5 * CAMADA_LARGURA) + 300, int(0.5 * CAMADA_ALTURA)).alpha() > 0


def test_imagem_cancelada_nao_altera_o_quadro():
    tela = _tela()
    tela.iniciar_imagem(_imagem_vermelha())
    tela.cancelar_colocacao()
    assert tela.quadro.camada_base is None
