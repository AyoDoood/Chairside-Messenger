# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this app is

Chairside Ready Alert is a LAN-based alert/messaging tool for dental offices. Staff at different workstations (Room 1, Room 2, Doctor, Lab, etc.) send one-click alerts to each other. It is a single-file Python GUI app (`chairside_ready_alert.py`) using Tkinter for the UI and raw TCP/UDP sockets for peer-to-peer networking — no server required.

## Running the app

```bash
python3 chairside_ready_alert.py
```

Requires Python 3.11+ with Tkinter. Optional dependencies (for system tray): `pystray`, `pillow`, `pyobjc-framework-Cocoa` (macOS), `cairosvg`, `certifi`.

There is **no test suite, no linter config, and no CI** in this repo. Verification is manual: run the app, ideally on two machines (or two loopback instances on different ports) and exchange alerts.

## Architecture

**Single-file app.** All application logic lives in `chairside_ready_alert.py`. Key classes:

- `ChairsideReadyAlertApp` (chairside_ready_alert.py:1134) — the Tkinter main window and top-level controller.
- `ConfigStore` (chairside_ready_alert.py:442) — reads/writes `chairside_ready_alert_config.json` from a platform-appropriate user data directory (`~/Library/Application Support/ChairsideReadyAlert/` on macOS, `%LOCALAPPDATA%\ChairsideReadyAlert\` on Windows). Atomic writes via temp file + `os.replace`. See this class for the canonical config shape and defaults.
- `LanDiscovery` (chairside_ready_alert.py:503) — UDP broadcast/listen on port 50506 for zero-config peer discovery. Peers broadcast JSON beacons every 2.5s; stale after 12s.
- `MessageServer` (chairside_ready_alert.py:637) and `MessageClient` (chairside_ready_alert.py:807) — TCP messaging layer; peers connect to each other on port 50505 (default) to send alert messages. The `is_server` config flag is now vestigial; the app is fully peer-to-peer.
- System tray — `pystray` + `pillow`; loaded lazily with a fallback repair path if missing.

**Threading model (important).** The Tkinter UI runs on the main thread. `LanDiscovery`, `MessageServer`, and `MessageClient` each run on background threads and post events through a `queue.Queue` drained by a `root.after(...)` poll on the UI thread. Any new background work must use the same queue — direct Tk calls from a non-main thread will crash on macOS.

**Themes**: `Modern Blue`, `Sage Clinic`, `Rose Quartz` — defined as dicts in `THEMES`.

**Alert sounds**: 15 synthesized sounds generated at runtime (no audio files needed). Sample rate: 22050 Hz, output via `wave` + platform audio.

**Auto-update**: checks `version.json` on GitHub, downloads individual files listed in `UPDATE_ALLOWED_FILES`. Only those files can be updated; arbitrary files are rejected. The manifest URL can be overridden by setting the `CHAIRSIDE_UPDATE_MANIFEST_URL` env var or by adding `update_manifest_url` to the config file; otherwise `UPDATE_MANIFEST_URL_BUILTIN` (chairside_ready_alert.py:119) is used.

**Single-instance lock**: `chairside_messenger.instance.lock` in the user data directory, using `fcntl.flock` (macOS/Linux) or `msvcrt.locking` (Windows). A second launch focuses the existing window via a local TCP IPC on port 59661.

## Repo layout traps

- **`dental_messenger.py`** still sits in the repo root — it is the pre-rename legacy copy and is not referenced by installers or `version.json`. Do not edit it; it is slated for deletion. All changes belong in `chairside_ready_alert.py`.
- **Duplicated Windows installer.** `Chairside Ready Alert Windows Installer/` contains its own copies of `install_chairside_ready_alert.ps1`, `Install Chairside Ready Alert.bat`, and a sample `chairside_ready_alert_config.json`. The **root copies are canonical** (referenced by `version.json`); the subfolder is a packaging bundle. When changing the installer, update both or the bundle will drift.

## Installers

- **macOS**: `install_chairside_ready_alert_macos.sh` (called by `Install Chairside Ready Alert macOS.command`). Installs to `~/Library/Application Support/ChairsideReadyAlert/`, creates a `.app` bundle on the Desktop. Targets python.org Python 3.12.
- **Windows**: `install_chairside_ready_alert.ps1` (called by `Install Chairside Ready Alert.bat`). Installs to `%LOCALAPPDATA%\ChairsideReadyAlert\`, creates a Desktop shortcut.
- **Windows EXE build** (`Windows Store Submission/`): PyInstaller `--onedir` build. Run `build_windows_exe.bat` on Windows. Output: `dist\ChairsideReadyAlert\ChairsideReadyAlert.exe`.
- **Hosted Windows EXE build** (`.github/workflows/build-windows.yml`): builds all three Microsoft Store architectures (x64, x86, ARM64) on GitHub-hosted runners. Triggered by pushing a `v*` tag or via `workflow_dispatch` from the Actions tab. Each build is uploaded as an artifact named `ChairsideReadyAlert-<arch>`. The ARM64 leg runs on `windows-11-arm`, which is free for public repos but may incur runner-minute charges on private repos.

## Releasing — version sync checklist

When cutting a release, these three must agree:

1. `APP_VERSION` in `chairside_ready_alert.py` (line 116).
2. `version` in `version.json`.
3. `release_notes` in `version.json` (updated to describe this release).

The `sha256` fields in `version.json` are intentionally empty (verified by HTTPS, not hash). `version.json.example` is a template — do not publish credentials or real URLs there.

After bumping these three, push a `v<version>` tag (e.g. `v1.0.5`) to trigger `.github/workflows/build-windows.yml` and produce x64/x86/ARM64 EXEs as Actions artifacts for Microsoft Store submission.

## Ownership

Proprietary to Fieldcrest Dental PC. Not intended for emergencies or clinical decision support.
