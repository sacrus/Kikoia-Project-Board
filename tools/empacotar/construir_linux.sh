#!/usr/bin/env bash
# Gera o executável do Kikoia Quadro Interativo para Linux (PyInstaller):
#   - Kikoia-Quadro-<versao>-Linux-x86_64.tar.gz
#   - Kikoia-Quadro-Linux-x86_64.zip (+ .sha256, compatível com a transferência automática do Teclado)
#   - kikoia-quadro_<versao>_amd64.deb (instalador Debian/Ubuntu/Linux Mint)
#
# Correr numa máquina Linux, a partir da pasta Quadro:
#   pip install -r requirements.txt pyinstaller
#   bash tools/empacotar/construir_linux.sh
# (Opcional: passar chaves API por variáveis KIKOIA_GOOGLE_CLIENT_ID=... ou SEGREDOS_JSON=/caminho/chaves.json)
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="${TMPDIR:-/tmp}/kikoia_quadro_build"
SAIDA="${SAIDA:-${HOME}/Desktop}"
mkdir -p "$SAIDA"
VERSAO="${VERSAO:-1.0.0}"
ARQUIVO_TAR="${SAIDA}/Kikoia-Quadro-${VERSAO}-Linux-x86_64.tar.gz"
ARQUIVO_ZIP="${SAIDA}/Kikoia-Quadro-Linux-x86_64.zip"
ARQUIVO_DEB="${SAIDA}/kikoia-quadro_${VERSAO}_amd64.deb"

cd "$RAIZ"
rm -rf "$TMP"
trap 'rm -f "$RAIZ/quadro/_segredos_embutidos.py"' EXIT

if [ -n "${SEGREDOS_JSON:-}" ] && [ -f "$SEGREDOS_JSON" ]; then
    python3 "$RAIZ/tools/empacotar/embutir_segredos.py" --ficheiro "$SEGREDOS_JSON"
else
    python3 "$RAIZ/tools/empacotar/embutir_segredos.py"
fi

PYTHONUTF8=1 python3 -m PyInstaller --noconfirm \
    --distpath "$TMP/dist" --workpath "$TMP/build" \
    tools/empacotar/kikoia_quadro.spec

tar -C "$TMP/dist" -czf "$ARQUIVO_TAR" KikoiaQuadro

python3 -c "
import hashlib, pathlib, zipfile
origem = pathlib.Path('$TMP/dist/KikoiaQuadro')
destino = pathlib.Path('$ARQUIVO_ZIP')
with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as zf:
    for p in sorted(origem.rglob('*')):
        if p.is_file():
            zf.write(p, p.relative_to(origem))
h = hashlib.sha256(destino.read_bytes()).hexdigest()
(destino.with_suffix('.zip.sha256')).write_text(f'{h}  {destino.name}\n', encoding='ascii')
"

echo "Pacotes gerados:"
echo "  - $ARQUIVO_TAR"
echo "  - $ARQUIVO_ZIP"

# Gerar instalador .deb (Ubuntu / Debian / Linux Mint / Pop!_OS)
if command -v dpkg-deb >/dev/null 2>&1; then
    DEB_ROOT="$TMP/deb"
    mkdir -p "$DEB_ROOT/DEBIAN" \
             "$DEB_ROOT/opt/kikoia-quadro" \
             "$DEB_ROOT/usr/bin" \
             "$DEB_ROOT/usr/share/applications" \
             "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps"

    cp -a "$TMP/dist/KikoiaQuadro/." "$DEB_ROOT/opt/kikoia-quadro/"
    ln -sf /opt/kikoia-quadro/KikoiaQuadro "$DEB_ROOT/usr/bin/kikoia-quadro"
    if [ -f "$RAIZ/Resources/Images/kikoia.png" ]; then
        cp "$RAIZ/Resources/Images/kikoia.png" "$DEB_ROOT/usr/share/icons/hicolor/256x256/apps/kikoia-quadro.png"
    fi

    cat > "$DEB_ROOT/usr/share/applications/kikoia-quadro.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Kikoia Quadro Interativo
GenericName=Quadro Interativo Educativo
Comment=Quadro interativo, documentos escolares com OCR, jogos educativos e correio acessível
Exec=/usr/bin/kikoia-quadro
Icon=kikoia-quadro
Terminal=false
Categories=Education;Graphics;Accessibility;
StartupWMClass=KikoiaQuadro
EOF

    TAM_KB="$(du -sk "$DEB_ROOT/opt" | cut -f1)"
    cat > "$DEB_ROOT/DEBIAN/control" <<EOF
Package: kikoia-quadro
Version: ${VERSAO}
Section: education
Priority: optional
Architecture: amd64
Installed-Size: ${TAM_KB}
Maintainer: Luís Patrício <info@lplogic.net>
Homepage: https://www.lplogic.net
Description: Kikoia — Quadro Interativo Educativo
 Quadro de desenho, editor de documentos escolares com OCR offline e Modo Exame,
 jogos motores/educativos e correio eletrónico acessível integrado com o Teclado Kikoia.
EOF

    cat > "$DEB_ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
exit 0
EOF
    chmod 0755 "$DEB_ROOT/DEBIAN/postinst"

    dpkg-deb --root-owner-group --build "$DEB_ROOT" "$ARQUIVO_DEB"
    echo "  - $ARQUIVO_DEB"
else
    echo "Aviso: dpkg-deb não encontrado; apenas .tar.gz e .zip foram gerados."
fi
