"""Catálogo de jogos do Quadro.

Os metadados (`index.json` e `game.json`) vêm da pasta `Resources/` do repositório Kikoia-Project-Board.
Os jogos não são alojados aqui: cada um é transferido da fonte oficial, só quando o utilizador o pede,
e só é instalado se o SHA-256 coincidir com o valor registado no `game.json`.

Para testes sem internet, a variável `KIKOIA_RECURSOS_QUADRO` pode apontar para uma pasta local.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

REPOSITORIO_RECURSOS = "https://raw.githubusercontent.com/sacrus/Kikoia-Project-Board/main/Resources/"
VARIAVEL_RECURSOS = "KIKOIA_RECURSOS_QUADRO"
TIMEOUT_S = 20
LIMITE_METADADOS = 1_000_000
LIMITE_IMAGEM = 10_000_000
TAMANHO_BLOCO = 64 * 1024
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_NOME_FICHEIRO = re.compile(r"[A-Za-z0-9._-]{1,120}")
TIPOS_INSTALACAO = ("executavel", "instalador", "integrado")
_MODULO = re.compile(r"[a-z0-9_]{1,40}")
DISPOSITIVOS_CONTROLO = ("rato", "teclado", "caneta", "toque")
NIVEIS_CONTROLO = ("necessario", "aconselhado", "suportado")
_SINONIMOS_NIVEL = {"obrigatorio": "necessario"}


class ErroCatalogo(RuntimeError):
    """A mensagem é uma chave de tradução, ou texto técnico já traduzido."""


@dataclass(frozen=True)
class Instalacao:
    tipo: str
    url: str
    ficheiro: str
    sha256: str
    executavel: str | None = None
    modulo: str | None = None


@dataclass
class Jogo:
    id: str
    pasta: str
    nome: str
    descricao: str
    autores: list[str]
    copyright: str
    licenca: str
    licenca_url: str
    site: str
    fonte_oficial: str
    screenshots: list[str] = field(default_factory=list)
    instalacao_windows: Instalacao | None = None
    controlos: dict[str, str] = field(default_factory=dict)
    categoria: str = ""
    publico: str = ""


@dataclass(frozen=True)
class ResumoJogo:
    id: str
    pasta: str
    nome: str


def base_recursos() -> str:
    return os.environ.get(VARIAVEL_RECURSOS) or REPOSITORIO_RECURSOS


def pasta_jogos(dados: Path | None = None) -> Path:
    if dados is not None:
        return dados
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Kikoia" / "Quadro" / "jogos"


def pasta_cache() -> Path:
    return pasta_jogos().parent / "cache"


def _e_url(base: str) -> bool:
    return base.startswith(("https://", "http://"))


def _caminho_seguro(relativo: str) -> str:
    partes = relativo.split("/")
    if not relativo or relativo.startswith("/") or any(p in ("", ".", "..") for p in partes):
        raise ErroCatalogo("catalogo.caminho_invalido")
    return relativo


def _ler(base: str, relativo: str, limite: int, baixar: Callable | None = None) -> bytes:
    relativo = _caminho_seguro(relativo)
    if baixar is not None:
        return baixar(base, relativo, limite)
    if _e_url(base):
        pedido = urllib.request.Request(
            urllib.parse.urljoin(base, relativo), headers={"User-Agent": "Kikoia-Quadro"}
        )
        try:
            with urllib.request.urlopen(pedido, timeout=TIMEOUT_S) as resposta:
                dados = resposta.read(limite + 1)
        except urllib.error.HTTPError as erro:
            raise ErroCatalogo("catalogo.sem_recursos") from erro
        except OSError as erro:
            raise ErroCatalogo("catalogo.sem_rede") from erro
    else:
        try:
            dados = (Path(base) / relativo).read_bytes()
        except OSError as erro:
            raise ErroCatalogo("catalogo.sem_recursos") from erro
    if len(dados) > limite:
        raise ErroCatalogo("catalogo.ficheiro_grande")
    return dados


def _json(base: str, relativo: str, baixar: Callable | None = None) -> dict:
    try:
        dados = json.loads(_ler(base, relativo, LIMITE_METADADOS, baixar).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroCatalogo("catalogo.metadados_invalidos") from erro
    if not isinstance(dados, dict):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    return dados


def _texto(dados: dict, chave: str) -> str:
    valor = dados.get(chave)
    if not isinstance(valor, str) or not valor.strip():
        raise ErroCatalogo("catalogo.metadados_invalidos")
    return valor


def _https(valor: str) -> str:
    if not valor.startswith("https://"):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    return valor


def carregar_indice(base: str | None = None, baixar: Callable | None = None) -> list[ResumoJogo]:
    base = base or base_recursos()
    dados = _json(base, "index.json", baixar)
    jogos = dados.get("jogos")
    if not isinstance(jogos, list):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    resumos = []
    for item in jogos:
        if not isinstance(item, dict):
            raise ErroCatalogo("catalogo.metadados_invalidos")
        id_ = _texto(item, "id")
        if not _ID.fullmatch(id_):
            raise ErroCatalogo("catalogo.metadados_invalidos")
        resumos.append(ResumoJogo(id_, _caminho_seguro(_texto(item, "pasta")), _texto(item, "nome")))
    return resumos


def carregar_jogo(resumo: ResumoJogo, base: str | None = None, baixar: Callable | None = None) -> Jogo:
    base = base or base_recursos()
    dados = _json(base, f"{resumo.pasta}/game.json", baixar)
    if dados.get("id") != resumo.id:
        raise ErroCatalogo("catalogo.metadados_invalidos")
    autores = dados.get("autores")
    if not isinstance(autores, list) or not all(isinstance(a, str) and a for a in autores):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    screenshots = dados.get("screenshots", [])
    if not isinstance(screenshots, list):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    jogo = Jogo(
        id=resumo.id,
        pasta=resumo.pasta,
        nome=_texto(dados, "nome"),
        descricao=_texto(dados, "descricao"),
        autores=autores,
        copyright=_texto(dados, "copyright"),
        licenca=_texto(dados, "licenca"),
        licenca_url=_https(_texto(dados, "licenca_url")),
        site=_https(_texto(dados, "site")),
        fonte_oficial=_https(_texto(dados, "fonte_oficial")),
        screenshots=[_caminho_seguro(s) for s in screenshots if isinstance(s, str)],
        instalacao_windows=_instalacao(dados.get("instalacao", {}).get("windows")),
        controlos=_controlos(dados.get("controlos")),
        categoria=str(dados.get("categoria") or "").strip(),
        publico=str(dados.get("publico") or "").strip(),
    )
    return jogo


def _controlos(dados: object) -> dict[str, str]:
    """Lê e valida os dispositivos de entrada (rato, teclado, caneta, toque) e respetivo nível."""
    if dados is None:
        return {}
    if not isinstance(dados, dict):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    resultado: dict[str, str] = {}
    for chave, valor in dados.items():
        if chave not in DISPOSITIVOS_CONTROLO or not isinstance(valor, str):
            raise ErroCatalogo("catalogo.metadados_invalidos")
        nivel = _SINONIMOS_NIVEL.get(valor.strip().lower(), valor.strip().lower())
        if nivel not in NIVEIS_CONTROLO:
            raise ErroCatalogo("catalogo.metadados_invalidos")
        resultado[chave] = nivel
    return resultado


def _instalacao(dados: object) -> Instalacao | None:
    if dados is None:
        return None
    if not isinstance(dados, dict):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    tipo = _texto(dados, "tipo")
    if tipo not in TIPOS_INSTALACAO:
        raise ErroCatalogo("catalogo.metadados_invalidos")
    if tipo == "integrado":
        modulo = _texto(dados, "modulo")
        if not _MODULO.fullmatch(modulo):
            raise ErroCatalogo("catalogo.metadados_invalidos")
        return Instalacao(tipo="integrado", url="", ficheiro="", sha256="", modulo=modulo)
    ficheiro = _texto(dados, "ficheiro")
    sha256 = _texto(dados, "sha256")
    if not _NOME_FICHEIRO.fullmatch(ficheiro):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    if not _SHA256.fullmatch(sha256):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    executavel = dados.get("executavel")
    if executavel is not None and (not isinstance(executavel, str) or not _NOME_FICHEIRO.fullmatch(executavel)):
        raise ErroCatalogo("catalogo.metadados_invalidos")
    return Instalacao(tipo, _https(_texto(dados, "fonte")), ficheiro, sha256, executavel)


def miniatura(jogo: Jogo, cache: Path, base: str | None = None, baixar: Callable | None = None) -> Path | None:
    """Descarrega a primeira imagem do jogo para a cache, na primeira vez que é precisa."""
    if not jogo.screenshots:
        return None
    relativo = jogo.screenshots[0]
    destino = cache / jogo.id / Path(relativo).name
    if destino.is_file():
        return destino
    dados = _ler(base or base_recursos(), f"{jogo.pasta}/{relativo}", LIMITE_IMAGEM, baixar)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)
    return destino


def instalado(jogo: Jogo, pasta: Path | None = None) -> Path | None:
    if jogo.instalacao_windows is None or jogo.instalacao_windows.tipo == "integrado":
        return None
    caminho = pasta_jogos(pasta) / jogo.id / jogo.instalacao_windows.ficheiro
    return caminho if caminho.is_file() else None


def _pastas_instalacao_windows(jogo: Jogo) -> list[Path]:
    """Pastas onde um programa instalado no Windows pode estar (Program Files, AppData e Registo)."""
    candidatas: list[Path] = []
    nomes_pasta = [jogo.nome, f"{jogo.nome}-Qt", jogo.id]
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        raiz = os.environ.get(var)
        if raiz:
            for nome in nomes_pasta:
                candidatas.append(Path(raiz) / nome)
                candidatas.append(Path(raiz) / nome / "bin")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for nome in nomes_pasta:
            candidatas.append(Path(local) / "Programs" / nome)
            candidatas.append(Path(local) / "Programs" / nome / "bin")
            candidatas.append(Path(local) / nome)
            candidatas.append(Path(local) / nome / "bin")

    if sys.platform == "win32":
        try:
            import winreg

            alvo = jogo.id.lower()
            nome_alvo = jogo.nome.lower()
            raizes = (
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            )
            for hive, sub in raizes:
                try:
                    with winreg.OpenKey(hive, sub) as chave:
                        total = winreg.QueryInfoKey(chave)[0]
                        for i in range(total):
                            try:
                                nome_sub = winreg.EnumKey(chave, i)
                                with winreg.OpenKey(chave, nome_sub) as item:
                                    display = ""
                                    try:
                                        display = str(winreg.QueryValueEx(item, "DisplayName")[0]).lower()
                                    except OSError:
                                        pass
                                    if alvo not in display and nome_alvo not in display and alvo not in nome_sub.lower():
                                        continue
                                    for campo in ("InstallLocation", "DisplayIcon"):
                                        try:
                                            val = str(winreg.QueryValueEx(item, campo)[0]).strip().strip('"').split(",")[0]
                                        except OSError:
                                            continue
                                        if not val:
                                            continue
                                        p = Path(val)
                                        pasta_cand = p.parent if p.suffix.lower() == ".exe" else p
                                        candidatas.append(pasta_cand)
                                        candidatas.append(pasta_cand / "bin")
                            except OSError:
                                continue
                except OSError:
                    continue
        except Exception:
            pass
    return candidatas


def executavel_instalado(jogo: Jogo, pastas_extra: list[Path] | None = None) -> Path | None:
    """Devolve o executável do jogo já instalado no sistema (ex.: GCompris.exe), se encontrado."""
    inst = jogo.instalacao_windows
    if inst is None or inst.tipo != "instalador":
        return None
    nome_exe = inst.executavel or (f"{jogo.nome}.exe" if jogo.id == "gcompris" else None)
    if not nome_exe:
        return None
    pastas = list(pastas_extra) if pastas_extra is not None else _pastas_instalacao_windows(jogo)
    for pasta in pastas:
        candidato = pasta / nome_exe
        if candidato.is_file():
            return candidato
    return None


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as ficheiro:
        for bloco in iter(lambda: ficheiro.read(TAMANHO_BLOCO), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _baixar_ficheiro(url: str, destino: Path, progresso: Callable[[int, int], None] | None) -> None:
    pedido = urllib.request.Request(url, headers={"User-Agent": "Kikoia-Quadro"})
    with urllib.request.urlopen(pedido, timeout=TIMEOUT_S) as resposta, open(destino, "wb") as ficheiro:
        total = int(resposta.headers.get("Content-Length") or 0)
        recebido = 0
        while True:
            bloco = resposta.read(TAMANHO_BLOCO)
            if not bloco:
                break
            ficheiro.write(bloco)
            recebido += len(bloco)
            if progresso is not None:
                progresso(recebido, total)


def transferir(
    jogo: Jogo,
    pasta: Path | None = None,
    progresso: Callable[[int, int], None] | None = None,
    baixar: Callable | None = None,
) -> Path:
    """Transfere o jogo da fonte oficial, verifica o SHA-256 e guarda-o. Nada fica guardado se falhar."""
    instalacao = jogo.instalacao_windows
    if instalacao is None:
        raise ErroCatalogo("catalogo.sem_windows")
    baixar = baixar or _baixar_ficheiro
    destino_dir = pasta_jogos(pasta) / jogo.id
    destino_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=destino_dir, prefix=".descarga-") as tmp_texto:
            temporario = Path(tmp_texto) / instalacao.ficheiro
            baixar(instalacao.url, temporario, progresso)
            if _sha256(temporario) != instalacao.sha256:
                raise ErroCatalogo("catalogo.verificacao_falhou")
            destino = destino_dir / instalacao.ficheiro
            shutil.move(str(temporario), str(destino))
    except OSError as erro:
        raise ErroCatalogo("catalogo.sem_rede") from erro
    return destino


def abrir(caminho: Path, tipo: str) -> None:
    """Executa o jogo (executável) ou o instalador oficial. Só funciona no Windows."""
    if sys.platform != "win32":
        raise ErroCatalogo("catalogo.so_windows")
    if tipo == "instalador":
        os.startfile(str(caminho))  # type: ignore[attr-defined]
        return
    subprocess.Popen(
        [str(caminho)],
        cwd=str(caminho.parent),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
