from PySide6.QtGui import QColor, QImage

from quadro import camadas
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro


def _quadrado(quadro: Quadro, x0: float, y0: float, x1: float, y1: float) -> None:
    lados = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    for inicio, fim in lados:
        traco = quadro.comecar_traco("#000000", 0.01, *inicio)
        quadro.acrescentar_ponto(traco, *fim)


def _cor_em(imagem: QImage, x: float, y: float) -> QColor:
    return imagem.pixelColor(int(x * CAMADA_LARGURA), int(y * CAMADA_ALTURA))


def test_balde_pinta_dentro_do_contorno_e_nao_fora():
    quadro = Quadro()
    _quadrado(quadro, 0.3, 0.3, 0.6, 0.6)
    assert camadas.preencher(quadro, 0.45, 0.45, "#e11d48")
    assert _cor_em(quadro.camada_preench, 0.45, 0.45).name() == "#e11d48"
    assert _cor_em(quadro.camada_preench, 0.05, 0.05).alpha() == 0


def test_balde_nao_atravessa_o_contorno():
    quadro = Quadro()
    _quadrado(quadro, 0.3, 0.3, 0.6, 0.6)
    camadas.preencher(quadro, 0.45, 0.45, "#2563eb")
    assert _cor_em(quadro.camada_preench, 0.9, 0.9).alpha() == 0


def test_desfazer_retira_o_preenchimento():
    quadro = Quadro()
    _quadrado(quadro, 0.3, 0.3, 0.6, 0.6)
    quadro.registar()
    camadas.preencher(quadro, 0.45, 0.45, "#16a34a")
    assert quadro.camada_preench is not None
    quadro.desfazer()
    assert quadro.camada_preench is None


def test_preenchimento_e_imagem_sobrevivem_a_guardar_e_abrir(tmp_path):
    quadro = Quadro("#e8f4ea")
    imagem = QImage(40, 20, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#ff0000"))
    quadro.definir_camada_base(camadas.preparar_imagem(imagem))
    _quadrado(quadro, 0.3, 0.3, 0.6, 0.6)
    camadas.preencher(quadro, 0.45, 0.45, "#7c3aed")
    caminho = tmp_path / "d.kquadro"
    quadro.guardar(caminho)

    lido = Quadro.carregar(caminho)
    assert lido.camada_base is not None
    assert _cor_em(lido.camada_base, 0.5, 0.5).name() == "#ff0000"
    assert _cor_em(lido.camada_preench, 0.45, 0.45).name() == "#7c3aed"


def test_imagem_importada_mantem_as_proporcoes():
    imagem = QImage(100, 50, QImage.Format.Format_ARGB32)
    imagem.fill(QColor("#00ff00"))
    preparada = camadas.preparar_imagem(imagem)
    assert (preparada.width(), preparada.height()) == (CAMADA_LARGURA, CAMADA_ALTURA)
    assert preparada.pixelColor(5, 5).alpha() == 0
    assert preparada.pixelColor(CAMADA_LARGURA // 2, CAMADA_ALTURA // 2).name() == "#00ff00"


def test_quadro_antigo_sem_camadas_continua_a_abrir(tmp_path):
    caminho = tmp_path / "antigo.kquadro"
    caminho.write_text('{"formato": "kikoia-quadro", "versao": 1, "fundo": "#ffffff", "tracos": []}', encoding="utf-8")
    quadro = Quadro.carregar(caminho)
    assert quadro.camada_base is None
    assert quadro.camada_preench is None

