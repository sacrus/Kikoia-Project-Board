from PySide6.QtWidgets import QApplication

from quadro.jogos import sons
from quadro.jogos.dedos_musicais import AreaDedosMusicais, DialogoDedosMusicais, config_para_nivel


def test_progressao_velocidade_e_dedos():
    c1 = config_para_nivel(1)
    c4 = config_para_nivel(4)
    c7 = config_para_nivel(7)
    assert c1.max_dedos == 1
    assert c4.min_dedos == 2
    assert c7.max_dedos == 3
    assert c7.tempo_s < c4.tempo_s < c1.tempo_s


def test_sons_musicais_e_descanso():
    wav_acorde = sons._obter_wav("acorde_2_7")
    assert wav_acorde.startswith(b"RIFF")
    assert len(wav_acorde) > 1000
    wav_desc = sons._obter_wav("descanso")
    assert wav_desc.startswith(b"RIFF")
    assert len(wav_desc) > 10000


def test_acertar_nivel_entra_em_descanso_e_errar_reinicia_nivel():
    app = QApplication.instance() or QApplication([])
    area = AreaDedosMusicais()
    area.som_ativo = False
    area.resize(960, 620)
    area.iniciar_nivel(1)

    assert area.estado == "ativo"
    assert area.ronda_atual == 1

    # Errar um dedo -> entra em estado erro (volta ao início do nível 1)
    errado = next(i for i in range(10) if i not in area._alvos)
    area._processar_toque_em(area._pads[errado].centro_pad)
    assert area.estado == "erro"

    # Recomeça nível 1 e completa todas as 5 rondas
    area.iniciar_nivel(1)
    for _ in range(5):
        alvos = list(area._alvos)
        for idx in alvos:
            area._processar_toque_em(area._pads[idx].centro_pad)
    assert area.estado == "descanso"
    assert area._tempo_descanso > 0.0

    # Reiniciar volta sempre ao Nível 1
    area.nivel = 4
    area.reiniciar_jogo()
    assert area.nivel == 1
    assert area.estado == "pronto"


def test_dialogo_dedos_musicais_abre():
    app = QApplication.instance() or QApplication([])
    dlg = DialogoDedosMusicais()
    try:
        assert dlg.area.nivel == 1
        dlg.iniciar_ecra_completo()
        assert dlg._ecra_completo is True
        dlg._alternar_ecra_completo()
        assert dlg._ecra_completo is False
    finally:
        dlg.close()


def test_modo_so_direita_e_teclado_nao_rebentam():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    app = QApplication.instance() or QApplication([])
    area = AreaDedosMusicais()
    area.som_ativo = False
    area.resize(960, 620)
    area.definir_modo_maos("so_direita")
    area.iniciar_nivel(1)

    # No modo "so_direita" existem apenas 5 pads (indices 5..9); clicar neles nao pode dar IndexError
    alvo_idx = next(iter(area._alvos))
    assert 5 <= alvo_idx <= 9
    pad = area._pad_por_indice(alvo_idx)
    assert pad is not None
    area._processar_toque_em(pad.centro_pad)
    assert area.ronda_atual == 2

    # Também funciona por tecla do teclado (0..9 / letras)
    alvo_tecla = {5: Qt.Key.Key_6, 6: Qt.Key.Key_7, 7: Qt.Key.Key_8, 8: Qt.Key.Key_9, 9: Qt.Key.Key_0}[next(iter(area._alvos))]
    ev = QKeyEvent(QKeyEvent.Type.KeyPress, alvo_tecla, Qt.KeyboardModifier.NoModifier)
    area.keyPressEvent(ev)
    assert area.ronda_atual == 3
