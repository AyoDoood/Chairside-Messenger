# Chairside Ready Alert - Windows Store Submission

This folder is Windows-only and intentionally lean.

Ownership and licensing:
- App source and branding are proprietary to Fieldcrest Dental PC unless otherwise stated.
- Third-party dependency notices: see `../THIRD_PARTY_NOTICES.md`.
- Ownership contact: support@fieldcrestdental.com

Safety / intended-use notice:
- This app is an operational convenience messaging tool only.
- Not intended for emergencies, life-safety alerts, patient monitoring, or clinical decision support.
- Always maintain independent clinical and emergency communication procedures.

## What this produces

- A signed or unsigned Windows executable: `ChairsideReadyAlert.exe`
- Output location after build: `dist\ChairsideReadyAlert\ChairsideReadyAlert.exe`

This format works for Microsoft Store "Win32 app (EXE/MSI)" submissions.

## Files in this folder

- `build_windows_exe.ps1` - primary build script
- `build_windows_exe.bat` - simple launcher for the PowerShell build

## Build requirements (on a Windows PC)

- Windows 10/11
- Python 3.12+ (64-bit recommended)
- Internet access (first build only, to install Python packages)

## Build steps

1. Copy this folder to a Windows machine.
2. Keep `chairside_ready_alert.py` in the same folder as the build scripts.
3. Double-click `build_windows_exe.bat` (or run PowerShell script directly).
4. After success, use:
   - `dist\ChairsideReadyAlert\ChairsideReadyAlert.exe`

## Architecture-specific builds (important)

Each build output is single-architecture and matches the Python interpreter used to build it.

- Build with x64 Python -> submit as `x64`
- Build with x86 Python -> submit as `x86`
- Build with ARM64 Python -> submit as `arm64`
- Do not mark this package as `neutral`

Examples:

- x64: `.\build_windows_exe.ps1 -PythonExe py -PythonArgs -3.12-64`
- x86: `.\build_windows_exe.ps1 -PythonExe py -PythonArgs -3.12-32`
- ARM64: `.\build_windows_exe.ps1 -PythonExe py -PythonArgs -3.12`

Verify selected Python architecture before build:

- `py -3.12-64 -c "import platform; print(platform.architecture(), platform.machine())"`

## Optional signing (recommended for distribution)

Unsigned EXEs can be submitted in some scenarios, but code-signing improves trust and install experience.

If you have a certificate:

- Sign `dist\ChairsideReadyAlert\ChairsideReadyAlert.exe` with `signtool.exe`.

## Notes for broad compatibility

- Build uses `--onedir` (more reliable than one-file self-extracting EXEs across many endpoint security setups).
- Build includes tray and icon dependencies used by the app.
- No macOS files are included.
- Current app behavior includes an inline duplicate-station-name hint to reduce confusion when two PCs share the same station label.
