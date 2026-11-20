; Installer Windows AdsBooth (Inno Setup 6). Jangan dijalankan langsung:
; pakai installer\build-windows.bat (mengisi AppVersion, SourceDir, dll.)

#ifndef AppName
  #define AppName "AdsBooth"
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\build\app"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef IconFile
  #define IconFile "icon.ico"
#endif
#define AppExe "adsbooth.exe"

[Setup]
; AppId jangan diubah antar versi: supaya update menimpa instalasi lama
AppId={{A7C78B8C-02D2-4C54-8393-AFF4584D92D3}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=AdsBooth-Setup-{#AppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Buat ikon di desktop"; GroupDescription: "Pintasan:"
Name: "autostart"; Description: "Jalankan kiosk otomatis saat Windows menyala"; GroupDescription: "Mode kiosk:"
Name: "firewall"; Description: "Izinkan tablet/HP di Wi-Fi membuka kiosk && Studio (firewall)"; GroupDescription: "Jaringan:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; folder data (config, event, foto tamu, lisensi): bisa ditulis user biasa, TIDAK dihapus saat uninstall/update
Name: "{commonappdata}\AdsBooth"; Permissions: users-modify; Flags: uninsneveruninstall

[Icons]
Name: "{group}\AdsBooth Kiosk"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{group}\AdsBooth Studio"; Filename: "{app}\{#AppExe}"; Parameters: "--studio"; WorkingDir: "{app}"
Name: "{group}\Hentikan AdsBooth"; Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; IconFilename: "{app}\{#AppExe}"
Name: "{group}\Folder data AdsBooth"; Filename: "{commonappdata}\AdsBooth"
Name: "{group}\Uninstall AdsBooth"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AdsBooth"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autodesktop}\AdsBooth Studio"; Filename: "{app}\{#AppExe}"; Parameters: "--studio"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{commonstartup}\AdsBooth Kiosk"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""AdsBooth"""; Flags: runhidden; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""AdsBooth"" dir=in action=allow program=""{app}\{#AppExe}"" enable=yes profile=private,domain,public"; Flags: runhidden; Tasks: firewall
Filename: "{app}\{#AppExe}"; Parameters: "--studio"; Description: "Buka AdsBooth Studio sekarang (atur PIN, printer, lisensi)"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "StopApp"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""AdsBooth"""; Flags: runhidden; RunOnceId: "DelFw"

[Code]
// Tutup AdsBooth yang sedang jalan sebelum file ditimpa (update)
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;
