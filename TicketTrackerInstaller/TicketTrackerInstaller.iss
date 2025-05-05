[Setup]
AppName=Ticket Tracker
AppVersion=1.0.0
DefaultDirName={pf}\Ticket Tracker
DefaultGroupName=Ticket Tracker
OutputDir=installer
OutputBaseFilename=TicketTrackerInstaller
Compression=lzma
SolidCompression=yes
SetupIconFile=sntt.ico

[Files]
Source: "dist\TicketTracker.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "appdata.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "settings.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "sntt.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Ticket Tracker"; Filename: "{app}\TicketTracker.exe"
Name: "{commondesktop}\Ticket Tracker"; Filename: "{app}\TicketTracker.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
