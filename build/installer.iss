; Inno Setup 6: programma di installazione di Sonar (Sonar-Setup-<versione>.exe).
; Compilato da build\BUILD_WINDOWS.cmd con: ISCC.exe /DAppVersion=1.0.0 build\installer.iss
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6E4B1C2A-5F3D-4D1E-9C7B-2A8F0E5D3B91}
AppName=Sonar
AppVersion={#AppVersion}
AppVerName=Sonar {#AppVersion}
AppPublisher=Ivan Murano, Laura Ripoli
AppPublisherURL=https://github.com/ivan-murano/sonar
DefaultDirName={autopf}\Sonar
DefaultGroupName=Sonar
DisableProgramGroupPage=yes
; installazione per l'utente corrente, senza diritti di amministratore e senza domande
PrivilegesRequired=lowest
ShowLanguageDialog=auto
DisableDirPage=yes
DisableReadyPage=yes
CloseApplications=yes
LicenseFile=..\LICENSE.txt
OutputDir=output
OutputBaseFilename=Sonar-Setup-{#AppVersion}
; lzma2/max: ultra64 con archivio solido da ~550 MB esaurisce la memoria del compilatore (processo a 32 bit)
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Sonar.exe
UninstallDisplayName=Sonar

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\Sonar\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Sonar"; Filename: "{app}\Sonar.exe"
Name: "{group}\{cm:UninstallProgram,Sonar}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Sonar"; Filename: "{app}\Sonar.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Sonar.exe"; Description: "{cm:LaunchProgram,Sonar}"; Flags: nowait postinstall skipifsilent
