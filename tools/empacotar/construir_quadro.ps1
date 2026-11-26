# Gera o Quadro Interativo para Windows: executavel (PyInstaller), instalador (Inno Setup)
# e o .zip que a transferencia do teclado usa (Kikoia-Quadro-Windows.zip, com KikoiaQuadro.exe na raiz).
#
# Uso (a partir da pasta Board):  powershell -ExecutionPolicy Bypass -File tools\empacotar\construir_quadro.ps1 -Versao 1.0.0
# Pre-requisitos: Python com PySide6 e PyInstaller; Inno Setup 6; pasta ferramentas\ com cjxl.exe e djxl.exe (+ DLLs).

param(
    [Parameter(Mandatory = $true)] [string] $Versao,
    [string] $Iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"
$raiz = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $raiz
$dist = Join-Path $raiz "dist"
$app = Join-Path $dist "KikoiaQuadro"

if (-not (Test-Path (Join-Path $raiz "ferramentas\cjxl.exe"))) { throw "Falta ferramentas\cjxl.exe (JPEG XL)." }
if (-not (Test-Path $Iscc)) { throw "Inno Setup nao encontrado em: $Iscc" }

$modSegredos = Join-Path $raiz "quadro\_segredos_embutidos.py"
try {
    Write-Host "1/4 Executavel (PyInstaller)..."
    $env:PYTHONUTF8 = "1"
    py (Join-Path $PSScriptRoot "embutir_segredos.py")
    $extraArgs = @()
    if (Test-Path $modSegredos) {
        $extraArgs += @("--hidden-import", "quadro._segredos_embutidos")
    }
    py -m PyInstaller --noconfirm --clean --windowed --name KikoiaQuadro --paths . `
        --distpath $dist --workpath (Join-Path $raiz "build") --specpath (Join-Path $raiz "build") `
        @extraArgs `
        (Join-Path $PSScriptRoot "quadro_principal.py")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }
} finally {
    Remove-Item -Force -ErrorAction SilentlyContinue $modSegredos
}

Write-Host "2/4 Ferramentas JPEG XL (libjxl, licenca BSD-3)..."
$ferr = Join-Path $app "ferramentas"
New-Item -ItemType Directory -Force -Path $ferr | Out-Null
Copy-Item (Join-Path $raiz "ferramentas\*") $ferr -Force
Copy-Item (Join-Path $PSScriptRoot "LICENCA-libjxl.txt") $app -Force

Write-Host "3/4 Instalador (Inno Setup)..."
& $Iscc "/DOrigem=$app" "/DSaida=$dist" "/DVersao=$Versao" (Join-Path $PSScriptRoot "kikoia_quadro.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou." }

Write-Host "4/4 Pacote para transferencia (zip com SHA-256)..."
$zip = Join-Path $dist "Kikoia-Quadro-Windows.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $app "*") -DestinationPath $zip
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash  Kikoia-Quadro-Windows.zip" | Set-Content (Join-Path $dist "Kikoia-Quadro-Windows.zip.sha256") -Encoding ASCII

Write-Host "Concluido."
Write-Host "  Instalador: $dist\Kikoia-Quadro-Windows-Setup-$Versao.exe"
Write-Host "  Pacote:     $zip"
Write-Host "  SHA-256:    $hash"
