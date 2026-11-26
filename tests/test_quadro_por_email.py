from PySide6.QtWidgets import QApplication

from quadro.correio.modelo import conta_cpanel
from quadro.correio.regras import Regras
from quadro.janela import MIME_QUADRO, JanelaQuadro
from quadro.janela_correio import DialogoEscrever
from quadro.modelo import Quadro


def _app():
    return QApplication.instance() or QApplication([])


def test_desenho_preparado_para_email_tem_o_ficheiro_do_quadro_e_uma_imagem():
    _app()
    janela = JanelaQuadro(Quadro())
    try:
        anexos = janela.preparar_anexos_quadro()
        assert [a.nome.endswith(".kquadro") for a in anexos] == [True, False]
        assert anexos[0].tipo == MIME_QUADRO
        assert anexos[1].tipo == "image/png"
        assert all(a.dados for a in anexos)
    finally:
        janela.close()


def test_desenho_recebido_abre_no_quadro():
    _app()
    origem = JanelaQuadro(Quadro())
    destino = JanelaQuadro(Quadro())
    try:
        dados = origem.preparar_anexos_quadro()[0].dados
        resposta = destino.abrir_quadro_recebido("desenho.kquadro", dados)
        assert resposta == "Desenho do Quadro aberto."
    finally:
        origem.close()
        destino.close()


def test_ficheiro_que_nao_e_desenho_e_recusado_sem_falhar():
    _app()
    janela = JanelaQuadro(Quadro())
    try:
        resposta = janela.abrir_quadro_recebido("falso.kquadro", b"isto nao e um desenho")
        assert "não é um desenho do Quadro válido" in resposta
    finally:
        janela.close()


def test_botao_anexar_desenho_junta_os_dois_ficheiros_ao_email():
    _app()
    janela = JanelaQuadro(Quadro())
    dialogo = DialogoEscrever(
        conta_cpanel("a@portugalsat.com"), "x", Regras(), None, None,
        fornecer_quadro=janela.preparar_anexos_quadro,
    )
    try:
        assert dialogo._anexos == []
        dialogo._anexar_desenho()
        assert len(dialogo._anexos) == 2
        assert dialogo._lista_anexos.count() == 2
    finally:
        dialogo.close()
        janela.close()


def test_partilhar_sem_conta_avisa_em_vez_de_falhar(monkeypatch):
    from quadro import janela as janela_modulo

    _app()
    avisos = []
    monkeypatch.setattr(janela_modulo.QMessageBox, "information", lambda *a, **k: avisos.append(a))
    janela = JanelaQuadro(Quadro())
    try:
        janela.partilhar_por_email()
        assert avisos and "conta de correio" in avisos[0][2]
    finally:
        janela.close()


def test_partilhar_com_conta_abre_a_mensagem_com_o_desenho_anexado(monkeypatch):
    import sys

    import pytest

    from quadro import janela as janela_modulo
    from quadro.correio import contas
    from quadro.correio import supervisor as supervisor_modulo
    from quadro.correio.modelo import conta_cpanel

    if sys.platform != "win32":
        pytest.skip("DPAPI só existe no Windows")
    _app()
    monkeypatch.setattr(supervisor_modulo, "ITERACOES", 1000)
    contas.guardar(conta_cpanel("a@portugalsat.com"), "segredo-123")
    capturados = []

    class DialogoFalso:
        def __init__(self, *args, **kwargs):
            capturados.append((args, kwargs))

        def exec(self):
            return 0

    monkeypatch.setattr(janela_modulo, "DialogoEscrever", DialogoFalso)
    janela = JanelaQuadro(Quadro())
    try:
        janela.partilhar_por_email()
        inicial = capturados[0][0][4]
        assert [a.nome.endswith(".kquadro") for a in inicial.anexos] == [True, False]
    finally:
        janela.close()


def test_sem_quadro_fornecido_o_botao_fica_desativado():
    from PySide6.QtWidgets import QPushButton

    _app()
    dialogo = DialogoEscrever(conta_cpanel("a@portugalsat.com"), "x", Regras(), None, None)
    try:
        botoes = [b for b in dialogo.findChildren(QPushButton) if b.text() == "Anexar desenho do Quadro"]
        assert botoes and not botoes[0].isEnabled()
    finally:
        dialogo.close()
