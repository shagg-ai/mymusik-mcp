Unicode true
ManifestDPIAware true
RequestExecutionLevel user
!include "MUI2.nsh"

Name "MyMusik MCP"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\MyMusik MCP"
InstallDirRegKey HKCU "Software\MyMusik\MCP" "InstallDir"
SetCompressor /SOLID lzma
!define MUI_ICON "mymusik.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\MyMusik Setup.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open MyMusik pairing setup"
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\MyMusikMCP"
Section
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD}\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortCut "$SMPROGRAMS\MyMusik MCP Setup.lnk" "$INSTDIR\MyMusik Setup.exe"
  WriteRegStr HKCU "Software\MyMusik\MCP" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "MyMusik MCP"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "MyMusik"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\MyMusik Setup.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$SMPROGRAMS\MyMusik MCP Setup.lnk"
  !include "${REMOVE_FILES}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "Software\MyMusik\MCP"
  DeleteRegKey /ifempty HKCU "Software\MyMusik"
SectionEnd
