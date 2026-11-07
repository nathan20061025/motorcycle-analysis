; Inno Setup script (free: https://jrsoftware.org/isinfo.php). Compile after building dist\TrafficAnalysis:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\TrafficSetup.iss
; Output: installer\Output\TrafficSetup.exe
[Setup]
AppName=Motorcycle Traffic Analysis
AppVersion=0.1.0
AppPublisher=Traffic Project
DefaultDirName={autopf}\TrafficAnalysis
DefaultGroupName=Traffic Analysis
OutputDir=Output
OutputBaseFilename=TrafficSetup
Compression=lzma2/fast
SolidCompression=no
DiskSpanning=no
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayName=Motorcycle Traffic Analysis

[Files]
Source: "..\dist\TrafficAnalysis\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Traffic Analysis"; Filename: "{app}\TrafficAnalysis.exe"
Name: "{autodesktop}\Traffic Analysis"; Filename: "{app}\TrafficAnalysis.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; Flags: unchecked

[Run]
Filename: "{app}\TrafficAnalysis.exe"; Description: "Start Traffic Analysis now"; Flags: nowait postinstall skipifsilent
