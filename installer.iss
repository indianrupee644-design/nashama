[Setup]
AppName=Nashama
AppVersion=1.0
AppPublisher=Nashama
DefaultDirName={autopf}\Nashama
DefaultGroupName=Nashama
DisableProgramGroupPage=yes
OutputBaseFilename=Nashama_Setup
OutputDir=output
SetupIconFile=nashama.ico
UninstallDisplayIcon={app}\Nashama.exe
WizardStyle=modern
Compression=lzma2
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce

[Files]
Source: "dist\Nashama.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Nashama"; Filename: "{app}\Nashama.exe"
Name: "{autodesktop}\Nashama"; Filename: "{app}\Nashama.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Nashama.exe"; Description: "Launch Nashama"; Flags: nowait postinstall skipifsilent
