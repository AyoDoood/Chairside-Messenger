@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
REM Default build uses whichever Python launcher "py" resolves to.
REM For explicit architectures, run PowerShell directly:
REM   .\build_windows_exe.ps1 -PythonExe py -PythonArgs -3.12-64
REM   .\build_windows_exe.ps1 -PythonExe py -PythonArgs -3.12-32
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_windows_exe.ps1"

if errorlevel 1 (
  echo.
  echo Build failed. Review the output above.
  pause
  exit /b 1
)

echo.
echo Build succeeded.
pause
