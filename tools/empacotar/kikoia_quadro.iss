; Instalador do Quadro Interativo (Windows). Compilado por construir_quadro.ps1, que passa Origem, Saida e Versao.

#ifndef Origem
  #error Definir Origem: pasta do executavel (dist\KikoiaQuadro)
#endif
#ifndef Saida
  #define Saida "."
#endif
#ifndef Versao
  #define Versao "1.0.0"
#endif

#define NomeApp "Kikoia Quadro Interativo"

[Setup]
; Identificador fixo deste produto: nao mudar entre versoes.
AppId={{5D2E8C1A-7B3F-4E61-9A0C-2F8D4B6E1C73}
AppName={#NomeApp}
AppVersion={#Versao}
AppVerName={#NomeApp} {#Versao}
AppPublisher=Luís Patrício
AppPublisherURL=https://www.lplogic.net
AppSupportURL=https://github.com/sacrus/Kikoia-Project-Board
AppUpdatesURL=https://github.com/sacrus/Kikoia-Project-Board/releases
DefaultDirName={autopf}\Kikoia Quadro Interativo
DefaultGroupName={#NomeApp}
DisableProgramGroupPage=yes
; Instala para o utilizador, sem pedir administrador.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#Saida}
OutputBaseFilename=Kikoia-Quadro-Windows-Setup-{#Versao}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\KikoiaQuadro.exe
UninstallDisplayName={#NomeApp}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "portugues"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "ingles"; MessagesFile: "compiler:Default.isl"
Name: "espanol"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "frances"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "atalho_ambiente"; Description: "Criar atalho no ambiente de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "{#Origem}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#NomeApp}"; Filename: "{app}\KikoiaQuadro.exe"
Name: "{autodesktop}\{#NomeApp}"; Filename: "{app}\KikoiaQuadro.exe"; Tasks: atalho_ambiente
Name: "{group}\Desinstalar {#NomeApp}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\KikoiaQuadro.exe"; Description: "Abrir o Quadro Interativo"; Flags: nowait postinstall skipifsilent

[Code]
// O teclado procura o Quadro em %LOCALAPPDATA%\Kikoia\Quadro (ficheiro atual.json). Ao instalar,
// registamos aqui o local da instalacao: o teclado passa a encontrar o Quadro sem perguntar.
procedure RegistarInstalacao();
var
  Pasta, Ficheiro, Conteudo, Exe: String;
begin
  Pasta := ExpandConstant('{localappdata}\Kikoia\Quadro');
  ForceDirectories(Pasta);
  Exe := ExpandConstant('{app}\KikoiaQuadro.exe');
  StringChangeEx(Exe, '\', '\\', True);
  Conteudo := '{"versao": "{#Versao}", "exe": "' + Exe + '"}';
  Ficheiro := Pasta + '\atual.json';
  SaveStringToFile(Ficheiro, Conteudo, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RegistarInstalacao();
end;
