#!/usr/bin/env bash
# Gera o executável do Kikoia Quadro Interativo para Linux (PyInstaller) e um pacote .zip
# (compatível com a transferência automática do Teclado) + .tar.gz.
# Correr numa máquina Linux, a partir da pasta Quadro:
#   pip install -r requirements.txt pyinstaller
#   bash tools/empacotar/construir_linux.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="${TMPDIR:-/tmp}/kikoia_quadro_build"
SAIDA="${HOME}/Desktop"
mkdir -p "$SAIDA"
VERSAO="${VERSAO:-1.0.0}"
ARQUIVO_TAR="${SAIDA}/Kikoia-Quadro-${VERSAO}-Linux-x86_64.tar.gz"
ARQUIVO_ZIP="${SAIDA}/Kikoia-Quadro-Linux-x86_64.zip"

cd "$RAIZ"
rm -rf "$TMP"
trap 'rm -f "$RAIZ/quadro/_segredos_embutidos.py"' EXIT
python3 "$RAIZ/tools/empacotar/embutir_segredos.py"
PYTHONUTF8=1 python3 -m PyInstaller --noconfirm \
    --distpath "$TMP/dist" --workpath "$TMP/build" \
    tools/empacotar/kikoia_quadro.spec

tar -C "$TMP/dist" -czf "$ARQUIVO_TAR" KikoiaQuadro
python3 -c "
import pathlib, zipfile
origem = pathlib.Path('$TMP/dist/KikoiaQuadro')
with zipfile.ZipFile('$ARQUIVO_ZIP', 'w', zipfile.ZIP_DEFLATED) as zf:
    for p in sorted(origem.rglob('*')):
        if p.is_file():
            zf.write(p, p.relative_to(origem))
"
echo "Pacotes gerados:"
echo "  - $ARQUIVO_TAR"
echo "  - $ARQUIVO_ZIP"
