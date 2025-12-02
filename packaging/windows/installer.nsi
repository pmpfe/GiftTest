; NSIS Installer Script for GiftTestPractice
; Tested with NSIS 3.x

!include "MUI2.nsh"
!include "x64.nsh"

; Basic configuration
Name "Gift Test Practice"
OutFile "GiftTestPractice-Setup.exe"
InstallDir "$PROGRAMFILES\GiftTestPractice"
InstallDirRegKey HKCU "Software\GiftTestPractice" ""

; MUI Settings
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; Version info
VIProductVersion "1.0.0.0"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductName" "Gift Test Practice"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductVersion" "1.0.0"
VIAddVersionKey /LANG=${LANG_ENGLISH} "CompanyName" "GiftTest"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileVersion" "1.0.0"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileDescription" "Interactive GIFT Test Practice Application"
VIAddVersionKey /LANG=${LANG_ENGLISH} "LegalCopyright" "© 2024"

; Installation sections
Section "Install"
  SetOutPath "$INSTDIR"
  File /r "dist-windows\*.*"
  
  ; Create start menu shortcuts
  CreateDirectory "$SMPROGRAMS\GiftTestPractice"
  CreateShortCut "$SMPROGRAMS\GiftTestPractice\Gift Test Practice.lnk" "$INSTDIR\GiftTestPractice.exe"
  CreateShortCut "$SMPROGRAMS\GiftTestPractice\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  
  ; Create desktop shortcut
  CreateShortCut "$DESKTOP\Gift Test Practice.lnk" "$INSTDIR\GiftTestPractice.exe"
  
  ; Registry settings
  WriteRegStr HKCU "Software\GiftTestPractice" "" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GiftTestPractice" \
    "DisplayName" "Gift Test Practice"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GiftTestPractice" \
    "DisplayVersion" "1.0.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GiftTestPractice" \
    "UninstallString" "$INSTDIR\uninstall.exe"
  
  ; Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\*.*"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\GiftTestPractice\*.*"
  RMDir "$SMPROGRAMS\GiftTestPractice"
  Delete "$DESKTOP\Gift Test Practice.lnk"
  DeleteRegKey HKCU "Software\GiftTestPractice"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GiftTestPractice"
SectionEnd
