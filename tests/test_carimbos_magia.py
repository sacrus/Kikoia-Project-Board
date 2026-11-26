from PySide6.QtGui import QColor, QImage

from quadro import carimbos, magia
from quadro.modelo import CAMADA_ALTURA, CAMADA_LARGURA, Quadro


def _pixel(imagem: QImage, x: float, y: float) -> QColor:
    return imagem.pixelColor(int(x * CAMADA_LARGURA), int(y * CAMADA_ALTURA))


def _linha_preta(quadro: Quadro) -> None:
    traco = quadro.comecar_traco("#000000", 0.02, 0.5, 0.4)
    quadro.acrescentar_ponto(traco, 0.5, 0.6)


def test_carimbo_pinta_o_centro_com_a_cor_escolhida():
    quadro = Quadro()
    carimbos.tracar(quadro, "estrela", 0.5, 0.5, 0.2, "#e11d48")
    assert _pixel(quadro.camada_carimbos, 0.5, 0.5).name() == "#e11d48"
    assert _pixel(quadro.camada_carimbos, 0.02, 0.02).alpha() == 0


def test_todos_os_carimbos_desenham_alguma_coisa():
    for nome in carimbos.NOMES:
        quadro = Quadro()
        carimbos.tracar(quadro, nome, 0.5, 0.5, 0.3, "#2563eb")
        imagem = quadro.camada_carimbos
        desenhados = sum(1 for x in range(0, CAMADA_LARGURA, 8) for y in range(0, CAMADA_ALTURA, 8)
                         if imagem.pixelColor(x, y).alpha() > 0)
        assert desenhados > 0, nome


def test_carimbo_desfaz_com_o_historico():
    quadro = Quadro()
    quadro.registar()
    carimbos.tracar(quadro, "sol", 0.5, 0.5, 0.2, "#f59e0b")
    quadro.desfazer()
    assert quadro.camada_carimbos is None


def test_tingir_mistura_a_cor_com_o_fundo():
    quadro = Quadro("#ffffff")
    magia.Pincel(quadro, "tingir", "#ff0000").aplicar(0.5, 0.5, 0.05)
    verde = _pixel(quadro.camada_efeitos, 0.5, 0.5).green()
    assert 150 <= verde <= 180


def test_pixelizar_faz_blocos_uniformes():
    quadro = Quadro()
    _linha_preta(quadro)
    magia.Pincel(quadro, "pixelizar", "#000000").aplicar(0.5, 0.5, 0.04)
    imagem = quadro.camada_efeitos
    assert imagem.pixel(801, 501) == imagem.pixel(802, 502)


def test_desfocar_suaviza_a_borda_de_um_risco():
    quadro = Quadro("#ffffff")
    _linha_preta(quadro)
    magia.Pincel(quadro, "desfocar", "#000000").aplicar(0.5, 0.5, 0.05)
    cinzentos = [_pixel(quadro.camada_efeitos, (800 + dx) / CAMADA_LARGURA, 0.5).red() for dx in range(-15, -5)]
    assert any(0 < valor < 255 for valor in cinzentos)


def test_efeito_desconhecido_e_recusado():
    import pytest

    with pytest.raises(ValueError):
        magia.Pincel(Quadro(), "inventado", "#000000")


def test_carimbos_e_efeitos_sobrevivem_a_guardar_e_abrir(tmp_path):
    quadro = Quadro()
    carimbos.tracar(quadro, "casa", 0.3, 0.3, 0.2, "#16a34a")
    magia.Pincel(quadro, "tingir", "#ff0000").aplicar(0.7, 0.7, 0.05)
    caminho = tmp_path / "d.kquadro"
    quadro.guardar(caminho)
    lido = Quadro.carregar(caminho)
    assert _pixel(lido.camada_carimbos, 0.3, 0.3).name() == "#16a34a"
    assert _pixel(lido.camada_efeitos, 0.7, 0.7).red() == 255
