@echo off
setlocal

REM Registers .ips/.ipst "Open with IReal Studio" for current user (no admin).
set "APP_DIR=%~dp0"
set "APP_EXE=%APP_DIR%irealstudio.exe"

if not exist "%APP_EXE%" (
    echo ERROR: irealstudio.exe not found in:
    echo   %APP_DIR%
    exit /b 1
)

REM Define ProgID for .ips files (description/icon/open command).
reg add "HKCU\Software\Classes\irealstudio.ips" /ve /d "IReal Studio Project" /f >nul
reg add "HKCU\Software\Classes\irealstudio.ips\DefaultIcon" /ve /d "\"%APP_EXE%\",0" /f >nul
reg add "HKCU\Software\Classes\irealstudio.ips\shell\open\command" /ve /d "\"%APP_EXE%\" \"%%1\"" /f >nul

REM Define ProgID for .ipst template files.
reg add "HKCU\Software\Classes\irealstudio.ipst" /ve /d "IReal Studio Template" /f >nul
reg add "HKCU\Software\Classes\irealstudio.ipst\DefaultIcon" /ve /d "\"%APP_EXE%\",0" /f >nul
reg add "HKCU\Software\Classes\irealstudio.ipst\shell\open\command" /ve /d "\"%APP_EXE%\" \"%%1\"" /f >nul

REM Associate extensions to the ProgIDs and register OpenWith entries.
reg add "HKCU\Software\Classes\.ips" /ve /d "irealstudio.ips" /f >nul
reg add "HKCU\Software\Classes\.ips\OpenWithProgids" /v "irealstudio.ips" /t REG_NONE /f >nul

reg add "HKCU\Software\Classes\.ipst" /ve /d "irealstudio.ipst" /f >nul
reg add "HKCU\Software\Classes\.ipst\OpenWithProgids" /v "irealstudio.ipst" /t REG_NONE /f >nul

echo Open With registration created for .ips and .ipst
exit /b 0
