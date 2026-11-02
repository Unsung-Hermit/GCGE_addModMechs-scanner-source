@echo off
setlocal EnableDelayedExpansion
set "HERE=%~dp0"
cd /d "%HERE%"

set "SCANNER="
if exist "%HERE%scan_modmechs.exe" set "SCANNER=%HERE%scan_modmechs.exe"
if not defined SCANNER if exist "%HERE%Tools\scan_modmechs.exe" set "SCANNER=%HERE%Tools\scan_modmechs.exe"

if defined SCANNER (
  "%SCANNER%" one
  set "EC=!ERRORLEVEL!"
) else (
  set "SCRIPT="
  if exist "%HERE%scan_modmechs.py" set "SCRIPT=%HERE%scan_modmechs.py"
  if not defined SCRIPT if exist "%HERE%Tools\scan_modmechs.py" set "SCRIPT=%HERE%Tools\scan_modmechs.py"
  if not defined SCRIPT (
    echo ERROR: scan_modmechs.exe / scan_modmechs.py not found next to this bat or in Tools\.
    echo Copy Scan_One_Mod.bat, Tools\ ^(scan_modmechs.exe, repak, UAssetGUI, snapshot .txt^),
    echo and gui_config.ini into the target mod's Paks folder, then run again.
    echo.
    pause
    exit /b 1
  )

  set "PY="
  where py >nul 2>&1 && set "PY=py -3"
  if not defined PY where python >nul 2>&1 && set "PY=python"
  if not defined PY (
    echo ERROR: scan_modmechs.exe not found, and Python 3 is not on PATH.
    echo Use the distributed Tools\scan_modmechs.exe ^(no Python needed^), or install Python 3.
    echo.
    pause
    exit /b 1
  )

  %PY% "!SCRIPT!" one
  set "EC=!ERRORLEVEL!"
)

echo.
if !EC! neq 0 (
  echo Scan_One_Mod failed with exit code !EC!.
) else (
  echo Done. Updated "%HERE%gui_config.ini"
  echo Copy it back to GCGE_addModMechs\Resources\gui_config.ini ^(overwrite^).
)
echo.
pause
exit /b !EC!
