"""Gera temporariamente `quadro/_segredos_embutidos.py` apenas durante o empacotamento.

Lê as 5 chaves de API (Google, Microsoft, Openverse) a partir de:
  1. Variáveis de ambiente `KIKOIA_<CHAVE_MAIUSCULA>` (útil em Linux/WSL/Docker/CI);
  2. Um ficheiro JSON privado passado em `--ficheiro` (opcional);
  3. O cofre local da máquina de build (`quadro.segredos_app.ler()`).

O ficheiro gerado está no `.gitignore` e é apagado automaticamente pelo script de
empacotamento logo após o PyInstaller terminar. Nenhum segredo é impresso no terminal.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from quadro.segredos_app import CHAVES, ler as ler_cofre_local  # noqa: E402

DESTINO = RAIZ / "quadro" / "_segredos_embutidos.py"


def _recolher_valores(ficheiro: Path | None = None) -> dict[str, str]:
    valores: dict[str, str] = {}

    # 1. Cofre local da máquina de build (DPAPI no Windows / Fernet no Linux)
    try:
        for k, v in ler_cofre_local().items():
            if k in CHAVES and isinstance(v, str) and v.strip():
                valores[k] = v.strip()
    except Exception:
        pass

    # 2. Ficheiro JSON privado opcional (sobrepõe o cofre local)
    if ficheiro is not None and ficheiro.is_file():
        dados = json.loads(ficheiro.read_text(encoding="utf-8-sig"))
        if isinstance(dados, dict):
            for k in CHAVES:
                v = dados.get(k)
                if isinstance(v, str) and v.strip():
                    valores[k] = v.strip()

    # 3. Variáveis de ambiente KIKOIA_<CHAVE> (maior prioridade)
    for k in CHAVES:
        v = os.environ.get(f"KIKOIA_{k.upper()}", "").strip()
        if v:
            valores[k] = v

    return valores


def gerar(destino: Path = DESTINO, valores: dict[str, str] | None = None) -> int:
    dados = _recolher_valores() if valores is None else {k: v.strip() for k, v in valores.items() if k in CHAVES and v.strip()}
    if not dados:
        destino.unlink(missing_ok=True)
        return 0

    bruto = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    mascara = secrets.token_bytes(32)
    cifrado = bytes(b ^ mascara[i % len(mascara)] for i, b in enumerate(bruto))

    m_b64 = base64.b64encode(mascara).decode("ascii")
    c_b64 = base64.b64encode(cifrado).decode("ascii")

    codigo = (
        '"""Módulo temporário gerado apenas em tempo de build (fora do Git)."""\n'
        "from __future__ import annotations\n\n"
        "import base64\n"
        "import json\n\n"
        f"_M = {m_b64!r}\n"
        f"_C = {c_b64!r}\n\n\n"
        "def ler() -> dict[str, str]:\n"
        "    m = base64.b64decode(_M)\n"
        "    c = base64.b64decode(_C)\n"
        "    bruto = bytes(b ^ m[i % len(m)] for i, b in enumerate(c))\n"
        "    dados = json.loads(bruto.decode('utf-8'))\n"
        "    return dados if isinstance(dados, dict) else {}\n"
    )
    destino.write_text(codigo, encoding="utf-8")
    return len(dados)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera quadro/_segredos_embutidos.py para o build.")
    parser.add_argument("--ficheiro", type=Path, default=None, help="Ficheiro JSON privado opcional com chaves API.")
    args = parser.parse_args()
    valores = _recolher_valores(args.ficheiro)
    qtd = gerar(DESTINO, valores)
    print(f"Segredos embutidos para o build: {qtd}/{len(CHAVES)} chaves configuradas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
