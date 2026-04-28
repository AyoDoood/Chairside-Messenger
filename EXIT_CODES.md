# Chairside Ready Alert — Process Exit Codes

This page documents the process exit codes returned by the Chairside Ready Alert executable for the Microsoft Store submission.

## Overview

Chairside Ready Alert is a portable Win32 application. The executable (`ChairsideReadyAlert.exe`) is the application itself, not a traditional installer — running it launches the program directly. There are no install or uninstall steps that the executable performs on its own; deployment, update, and removal are handled entirely by the Microsoft Store.

Because the executable is the application, it uses standard process exit codes rather than installer-specific codes.

## Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| `0` | Normal termination. The user closed the main window or selected **Close** from the system tray menu. |
| Non-zero | Abnormal termination. The process was terminated by the operating system, killed externally, or exited due to an uncaught exception. The specific value is whatever the Python runtime or operating system supplies and is not interpreted by the application. |

## Notes for Certification

- The application does not display its own dialogs, modify the system, or write to its install directory at startup. User configuration is stored under `%LOCALAPPDATA%\ChairsideReadyAlert\`.
- The application does not require any command-line switches to run silently; launching the executable with no arguments brings up the main window normally.
- No installer-style return codes (such as `1602` for user cancel or `3010` for reboot required) are produced, because there is no installation phase.

## Contact

For questions about this documentation or the Microsoft Store submission, contact: **support@fieldcrestdental.com**
