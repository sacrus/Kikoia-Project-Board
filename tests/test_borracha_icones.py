from PySide6.QtWidgets import QApplication

from quadro import carimbos, formas, magia
from quadro.janela import CARIMBO_DIAMETROS, CARIMBO_TAMANHOS, JanelaQuadro
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro


def _app():
    return QApplication.instance() or QApplication([])


def _alfa(imagem, x, y):
    return imagem.pixelColor(int(x * CAMADA_LARGURA), int(y * CAMADA_ALTURA)).alpha()


def test_borracha_de_pixels_apaga_carimbo_e_efeito_no_centro():
    quadro = Quadro()
    carimbos.tracar(quadro, "estrela", 0.5, 0.5, 0.2, "#e11d48")
    magia.Pincel(quadro, "tingir", "#ff0000").aplicar(0.5, 0.5, 0.05)
    assert _alfa(quadro.camada_carimbos, 0.5, 0.5) > 0
    quadro.apagar_pixels(0.5, 0.5, 0.06)
    assert _alfa(quadro.camada_carimbos, 0.5, 0.5) == 0
    assert _alfa(quadro.camada_efeitos, 0.5, 0.5) == 0


def test_borracha_de_pixels_nao_apaga_a_imagem_importada():
    from PySide6.QtGui import QColor, QImage

    from quadro import camadas

    imagem = QImage(40, 40, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#ff0000"))
    quadro = Quadro()
    quadro.definir_camada_base(camadas.preparar_imagem(imagem))
    quadro.apagar_pixels(0.5, 0.5, 0.2)
    assert _alfa(quadro.camada_base, 0.5, 0.5) == 255


def test_borracha_pela_janela_desfaz_os_pixels():
    _app()
    janela = JanelaQuadro(Quadro())
    janela.show()
    tela = janela.tela
    tela.ferramenta = "borracha"
    carimbos.tracar(janela.quadro, "sol", 0.5, 0.5, 0.2, "#f59e0b")
    tela._registado = False
    tela._apagar(0.5, 0.5)
    assert _alfa(janela.quadro.camada_carimbos, 0.5, 0.5) == 0
    janela.desfazer()
    assert _alfa(janela.quadro.camada_carimbos, 0.5, 0.5) > 0
    janela.close()


def test_limpar_quadro_retira_carimbos_e_efeitos():
    quadro = Quadro()
    carimbos.tracar(quadro, "casa", 0.5, 0.5, 0.2, "#16a34a")
    magia.Pincel(quadro, "pixelizar", "#000000").aplicar(0.3, 0.3, 0.05)
    quadro.limpar()
    assert not quadro.tem_pixels()


def test_icones_sem_texto_existem_para_formas_efeitos_e_carimbos():
    _app()
    for tipo in formas.TIPOS:
        assert not formas.icone(tipo).isNull()
    for efeito in magia.EFEITOS:
        assert not magia.icone(efeito).isNull()
    for nome in carimbos.NOMES:
        assert not carimbos.icone(nome).isNull()


def test_tamanhos_de_carimbo_sao_crescentes_e_com_bolinha_correspondente():
    assert list(CARIMBO_TAMANHOS) == sorted(CARIMBO_TAMANHOS)
    assert len(CARIMBO_TAMANHOS) == len(CARIMBO_DIAMETROS)
