; Instalator Luny dla Windows (Inno Setup 6).
;   iscc /DAppVersion=1.0.0 /DSourceDir=..\dist\Luna packaging\luna.iss
; Instaluje bez uprawnień administratora (do folderu użytkownika); można wybrać instalację dla wszystkich.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\Luna"
#endif

[Setup]
AppId={{6F1B9C2E-3D4A-4E8B-9C7D-2A5E1F0B8C31}
AppName=Luna
AppVersion={#AppVersion}
AppVerName=Luna {#AppVersion}
AppPublisher=Luna
AppPublisherURL=https://z4k0lzakol.github.io/Luna/
AppSupportURL=https://github.com/z4k0lzakol/Luna/issues
AppUpdatesURL=https://github.com/z4k0lzakol/Luna/releases/latest
DefaultDirName={autopf}\Luna
DefaultGroupName=Luna
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE
InfoBeforeFile=installer_info.txt
OutputDir=..\dist
OutputBaseFilename=Luna-{#AppVersion}-Windows-Setup
SetupIconFile=..\luna.ico
UninstallDisplayIcon={app}\Luna.exe
UninstallDisplayName=Luna
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Luna"; Filename: "{app}\Luna.exe"
Name: "{autodesktop}\Luna"; Filename: "{app}\Luna.exe"; Tasks: desktopicon

[Registry]
; Luna na liście przeglądarek Windows (Ustawienia → Aplikacje domyślne); wybór domyślnej zostaje po stronie użytkownika
Root: HKCU; Subkey: "Software\Classes\LunaHTML"; ValueType: string; ValueName: ""; ValueData: "Luna HTML"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\LunaHTML"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\LunaHTML\Application"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Luna"
Root: HKCU; Subkey: "Software\Classes\LunaHTML\Application"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: """{app}\Luna.exe"",0"
Root: HKCU; Subkey: "Software\Classes\LunaHTML\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\Luna.exe"",0"
Root: HKCU; Subkey: "Software\Classes\LunaHTML\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Luna.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna"; ValueType: string; ValueName: ""; ValueData: "Luna"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\Luna.exe"",0"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Luna.exe"""
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Luna"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: """{app}\Luna.exe"",0"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Lekka, ciemna przeglądarka – przejrzysta jak gwieździste niebo."
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities\URLAssociations"; ValueType: string; ValueName: "http"; ValueData: "LunaHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities\URLAssociations"; ValueType: string; ValueName: "https"; ValueData: "LunaHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities\FileAssociations"; ValueType: string; ValueName: ".html"; ValueData: "LunaHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities\FileAssociations"; ValueType: string; ValueName: ".htm"; ValueData: "LunaHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "LunaHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Luna\Capabilities\StartMenu"; ValueType: string; ValueName: "StartMenuInternet"; ValueData: "Luna"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Luna"; ValueData: "Software\Clients\StartMenuInternet\Luna\Capabilities"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Luna.exe"; Description: "{cm:LaunchProgram,Luna}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Messages]
polish.WelcomeLabel2=Zainstalujesz teraz Lunę {#AppVersion} – lekką, ciemną przeglądarkę.%n%nTwoje dane (karty, zakładki, hasła) są w folderze użytkownika i zostają przy aktualizacji oraz odinstalowaniu.
