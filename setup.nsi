; https://stackoverflow.com/questions/29560977/nsis-detect-if-directory-exists-during-installation
; https://nsis.sourceforge.io/Reference/IfFileExists

# FileFunc.nsh — required for:
# * ${GetSize}
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"
; {{{
# From https://nsis.sourceforge.io/Managing_Sections_on_Runtime:
#!define SF_USELECTED  0
#!define SF_SELECTED   1
#!define SF_SECGRP     2
#!define SF_BOLD       8
#!define SF_RO         16
#!define SF_EXPAND     32
################################
# 
#!macro SecSelect SecId
#  Push $0
#  IntOp $0 ${SF_SELECTED} | ${SF_RO}
#  SectionSetFlags ${SecId} $0
#  SectionSetInstTypes ${SecId} 1
#  Pop $0
#!macroend
# 
#!define SelectSection '!insertmacro SecSelect'
##################################
# 
#!macro SecUnSelect SecId
#  Push $0
#  IntOp $0 ${SF_USELECTED} | ${SF_RO}
#  SectionSetFlags ${SecId} $0
#  SectionSetText  ${SecId} ""
#  Pop $0
#!macroend
# 
#!define UnSelectSection '!insertmacro SecUnSelect'
; }}}

Name "mister_viz Installer"
OutFile "mister_viz Installer.exe"
RequestExecutionLevel admin
Unicode True

InstallDir $PROGRAMFILES\mister_viz

InstallDirRegKey HKLM "Software\Interlaced\mister_viz" "Install_Dir"


Page custom nsDialogsPage
Page Components
Page InstFiles

Var Dialog
Var Label
Function nsDialogsPage
	nsDialogs::Create 1018
	Pop $Dialog

	${If} $Dialog == error
		Abort
	${EndIf}

	${NSD_CreateLabel} 0 0 100% 100% "\
Important: To use this program, you must install a custom version$\r$\n\
of the main MiSTer program on your MiSTer.$\r$\n\
$\r$\n\
This custom MiSTer program can be found at:$\r$\n\
https://github.com/jaysonlarose/Main_MiSTer_inputsocket$\r$\n\
$\r$\n\
You must also add the following directives to MiSTer.ini:$\r$\n\
input_socket_enabled=1$\r$\n\
input_socket_bindport=22101$\r$\n\
input_socket_bindhost=$\r$\n\
"
	Pop $Label

	nsDialogs::Show
FunctionEnd

Section "Visual Studio Runtime"
	SetOutPath "$INSTDIR"
	File "/home/jayson/Downloads/VC_redist.x64.exe"
	ExecWait "$INSTDIR\VC_redist.x64.exe /install /passive"
	Delete "$INSTDIR\VC_redist.x64.exe"
SectionEnd
Section "Core Files (Required)"
	SectionIn RO
	SetOutPath $INSTDIR
	File /r "dist/mister_viz/*"
	WriteRegStr HKLM Software\Interlaced\mister_viz "Install_Dir" "$INSTDIR"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\mister_viz" "DisplayName" "mister_viz"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\mister_viz" "UninstallString" '"$INSTDIR\uninstall.exe"'
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\mister_viz" "NoModify" 1
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\mister_viz" "NoRepair" 1
	# Calculate size of $INSTDIR for the uninstaller
	${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
	IntFmt $0 "0x%08X" $0
	WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\mister_viz" "EstimatedSize" "$0"
	WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Create resource directory for current user" section_createres
	SetOutPath "$PROFILE\mister_viz"
	File /r "resources/*.*"
SectionEnd

Section "Start Menu Shortcuts"

  CreateDirectory "$SMPROGRAMS\mister_viz"
  CreateShortcut "$SMPROGRAMS\mister_viz\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  CreateShortcut "$SMPROGRAMS\mister_viz\mister_viz.lnk" "$INSTDIR\mister_viz.exe"
SectionEnd


;--------------------------------

; Uninstaller

Section "Uninstall"
  
  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\mister_viz"
  DeleteRegKey HKLM SOFTWARE\mister_viz

  ; Remove shortcuts, if any
  Delete "$SMPROGRAMS\mister_viz\*.lnk"

  ; Remove directories
  RMDir "$SMPROGRAMS\mister_viz"
  RMDir /r "$INSTDIR"

SectionEnd


Function .onInit
	; if %HOME%\mister_viz already exists, make the "Create resource directory" section disabled by default
	IfFileExists $PROFILE\mister_viz\*.* 0 continue

	SectionGetFlags ${section_createres} $0
	IntOp $1 1 ~
	IntOp $0 $0 & $1
	SectionSetFlags ${section_createres} $0

	continue:

FunctionEnd

