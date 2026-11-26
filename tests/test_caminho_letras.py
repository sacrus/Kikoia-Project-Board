from PySide6.QtWidgets import QApplication

from quadro.jogos import caligrafia, sons
from quadro.jogos.caminho_letras import AreaCaminhoLetras, DialogoCaminhoLetras


def test_caligrafia_gera_tracos_para_letras_e_numeros():
    for letra in ("a", "b", "e", "l", "m", "o", "s", "z"):
        tracos = caligrafia.tracos_do_caractere(letra)
        assert tracos and len(tracos[0]) >= 10
    for numero in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
        tracos = caligrafia.tracos_do_caractere(numero)
        assert tracos and len(tracos[0]) >= 5


def test_sons_geram_wav_valido():
    for nome in ("embate", "ding", "aplausos"):
        wav = sons._obter_wav(nome)
        assert wav.startswith(b"RIFF")
        assert len(wav) > 1000
        ficheiro = sons._obter_ficheiro_wav(nome)
        assert ficheiro is not None and ficheiro.is_file()


def test_falhar_ou_levantar_volta_ao_inicio():
    from PySide6.QtCore import QPointF

    app = QApplication.instance() or QApplication([])
    area = AreaCaminhoLetras()
    area.som_ativo = False
    area.resize(900, 600)
    area.iniciar_nivel(1, sequencia_fixa=["a"])
    traco = area._tracos[0]

    # Avança parcialmente
    area._iniciar_traco(traco.pontos[0])
    for pt in traco.pontos[1:12]:
        area._mover_traco(pt)
    assert traco.progresso > 0

    # Sair da estrada -> volta ao início (progresso = 0)
    area._mover_traco(QPointF(10.0, 10.0))
    assert traco.progresso == 0
    assert area._a_desenhar is False

    # Avança parcialmente e levanta a caneta -> volta ao início
    area._iniciar_traco(traco.pontos[0])
    for pt in traco.pontos[1:10]:
        area._mover_traco(pt)
    assert traco.progresso > 0
    area._terminar_traco()
    assert traco.progresso == 0


def test_caneta_ativa_rejeicao_de_palma():
    app = QApplication.instance() or QApplication([])
    area = AreaCaminhoLetras()
    assert area._caneta_prioritaria() is False
    area._caneta_em_proximidade = True
    assert area._caneta_prioritaria() is True


def test_jogo_progride_de_niveis_e_aumenta_caracteres():
    app = QApplication.instance() or QApplication([])
    area = AreaCaminhoLetras()
    area.som_ativo = False
    area.resize(900, 600)

    area.iniciar_nivel(1)
    assert len(area._sequencia) == 1
    assert len(area._tracos) >= 1

    area.iniciar_nivel(4)
    assert len(area._sequencia) == 2

    area.iniciar_nivel(7)
    assert len(area._sequencia) == 3

    # Simula percorrer o primeiro traco ate ao fim num nivel de 1 letra
    area.iniciar_nivel(1, sequencia_fixa=["a"])
    traco = area._tracos[0]
    area._iniciar_traco(traco.pontos[0])
    for pt in traco.pontos[1:]:
        area._mover_traco(pt)
    assert area._celebrando is True
    assert area.estrelas == 1


def test_dialogo_caminho_letras_abre():
    app = QApplication.instance() or QApplication([])
    dlg = DialogoCaminhoLetras()
    try:
        assert dlg.area.nivel == 1
    finally:
        dlg.close()
