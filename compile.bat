@echo off
:: compile.bat – Build IReal Studio for Windows using Nuitka (standalone mode).
::
:: Usage:
::   compile.bat [--console]
::
:: Options:
::   --console   Build with a visible console window (useful for debugging
::               startup crashes – shows Python tracebacks in a terminal).
::               Without this flag the app runs silently as a GUI application.
::
:: Requirements:
::   uv must be installed (https://github.com/astral-sh/uv)
::   A C compiler reachable by Nuitka (MinGW-w64 or MSVC).
::   Nuitka will download MinGW-w64 automatically if --assume-yes-for-downloads
::   is set and no compiler is found.
::
:: Output:
::   dist\irealstudio-windows\    – standalone directory with irealstudio.exe
::   dist\irealstudio-windows.zip – ready-to-ship archive

setlocal EnableDelayedExpansion

:: ── configuration ──────────────────────────────────────────────────────────
set DIST_DIR=dist\irealstudio-windows
set ARCHIVE=dist\irealstudio-windows.zip
:: ────────────────────────────────────────────────────────────────────────────

:: ── parse arguments ─────────────────────────────────────────────────────────
:: Pass --console to build with a visible console window for debugging.
:: Without --console the app runs silently (no console window).
set CONSOLE_MODE=disable
:parse_args
if "%~1"=="--console" (
    set CONSOLE_MODE=force
    shift
    goto parse_args
)
:: ────────────────────────────────────────────────────────────────────────────

echo.
echo ===================================================
echo  IReal Studio – Windows build
echo ===================================================
echo.

:: Ensure uv is available
where uv >nul 2>&1
if errorlevel 1 (
    echo ERROR: uv not found on PATH.
    echo Install it from https://github.com/astral-sh/uv and re-run.
    exit /b 1
)

:: Install / sync project dependencies (including nuitka[onefile] dev group)
echo [1/4] Installing dependencies with uv...
uv sync --all-groups
if errorlevel 1 (
    echo ERROR: uv sync failed.
    exit /b 1
)

:: Resolve the accessible_output3 lib directory so Nuitka can bundle the DLLs
:: (NVDA/JAWS/ZoomText etc.) at the path load_library() expects at runtime:
::   <exe_dir>\accessible_output3\lib\<dll>
for /f "tokens=*" %%i in ('uv run python -c "import os,accessible_output3; print(os.path.join(os.path.dirname(accessible_output3.__file__),'lib'))"') do set AO3_LIB=%%i
if not defined AO3_LIB (
    echo ERROR: Could not resolve accessible_output3 lib path.
    exit /b 1
)
if not exist "!AO3_LIB!" (
    echo ERROR: accessible_output3 lib directory not found: !AO3_LIB!
    exit /b 1
)

:: Remove previous build artifacts so the output is clean
echo [2/4] Cleaning previous build output...
if exist dist\main.dist   rmdir /s /q dist\main.dist
if exist "%DIST_DIR%"     rmdir /s /q "%DIST_DIR%"
if exist "%ARCHIVE%"      del /f /q "%ARCHIVE%"

:: Build the standalone executable with Nuitka
echo [3/4] Building with Nuitka (standalone)...
uv run python -m nuitka ^
    --mode=standalone ^
    --output-file=irealstudio.exe ^
    --output-dir=dist ^
    --windows-console-mode=!CONSOLE_MODE! ^
    --assume-yes-for-downloads ^
    --follow-imports ^
    --include-data-dir=locales=locales ^
    "--include-data-dir=!AO3_LIB!=accessible_output3/lib" ^
    --include-module=mido.backends.rtmidi ^
    --nofollow-import-to=unittest ^
    --nofollow-import-to=doctest ^
    --nofollow-import-to=pdb ^
    --nofollow-import-to=tkinter ^
    --nofollow-import-to=test ^
    main.py

if errorlevel 1 (
    echo ERROR: Nuitka build failed.
    exit /b 1
)

:: Nuitka names the standalone output dir after the script: main.dist
:: Rename it to irealstudio-windows
echo [4/4] Packaging...
if not exist dist\main.dist (
    echo ERROR: dist\main.dist not found – Nuitka did not produce expected output.
    exit /b 1
)
rename dist\main.dist irealstudio-windows
powershell -NoProfile -Command ^
    "Compress-Archive -Path 'dist\irealstudio-windows' -DestinationPath '%ARCHIVE%' -Force"

echo.
echo ===================================================
echo  Build complete!
echo  Standalone dir : %DIST_DIR%
echo  Archive        : %ARCHIVE%
echo ===================================================
endlocal
