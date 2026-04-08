# Windows MSI — Zinnia Axion Tracker

Single canonical build: **cx_Freeze**, implemented in **`installer/windows/build_msi.py`**.

## One command (local or CI)

From the **repository root** on Windows:

```cmd
set INSTALLER_BACKEND_URL=https://your-production-backend.example.com
python setup_msi.py bdist_msi
```

- **`setup_msi.py`** — thin wrapper (discoverability at repo root).  
- **`installer/windows/build_msi.py`** — **source of truth** for packages, excludes, MSI metadata, install path, upgrade code, `ZinniaAxion.exe`, and shortcuts.

Equivalent (same code path):

```cmd
python installer\windows\build_msi.py bdist_msi
```

## Prerequisites (build machine)

```cmd
pip install cx_Freeze
pip install -r requirements.txt
pip install pywin32 psutil pynput
```

Employees who install the MSI do **not** need Python.

## Backend URL (baked into the MSI)

1. Set **`INSTALLER_BACKEND_URL`** in the environment before building.  
2. The build overwrites **`installer/windows/build_config.py`** with `BACKEND_URL = "<your url>"`.  
3. That module is frozen into **`ZinniaAxion.exe`**.  
4. On **first run**, **`launcher.py`** calls **`setup_gui.write_config()`** with that baked URL and the Windows username as **`USER_ID`**, writing:

`%USERPROFILE%\.telemetry-tracker\config.env`

If **`INSTALLER_BACKEND_URL`** is unset, the build prints a warning and uses whatever **`build_config.py`** already contains (often the repo placeholder). **Production builds should always set the variable.**

## Build output

MSI appears under **`dist/`**. The exact filename is produced by cx_Freeze from **`name`** and **`version`** in `build_msi.py` (currently **`ZinniaAxion`** / **`1.0.0`**), e.g.:

`dist\ZinniaAxion-1.0.0-amd64.msi`

Use `dir dist\*.msi` after a build to confirm.

## What gets installed

| Item | Value |
|------|--------|
| Default install directory | `%LOCALAPPDATA%\Zinnia\Axion` (per-user, no admin for default path) |
| Main executable | `ZinniaAxion.exe` |
| Start Menu shortcut | **Zinnia Axion Tracker** |
| Upgrade identity | Fixed **`upgrade_code`** in `build_msi.py` (do not change between releases you want to upgrade in place) |

Bundled next to the runtime: **`tracker/`** tree and **`installer/windows/`** (launcher dependencies, autostart, `build_config`).

## First run and runtime config

- **No setup wizard** in the default MSI flow: the launcher creates **`config.env`** automatically if missing or empty.  
- **`USER_ID`** defaults to the Windows account name; **`BACKEND_URL`** comes from the baked **`build_config`**.  
- Optional GUI: `python -m installer.windows.setup_gui` (manual use).

## Autostart

After config exists, the launcher calls **`installer.windows.autostart.install_autostart()`**:

1. Prefer **Task Scheduler** task name **`Zinnia_axion`**, command = quoted path to **`ZinniaAxion.exe`**.  
2. If **`schtasks`** fails, fallback: **`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ZinniaAxion.bat`**.

## Tracker and backend

- **`tracker.agent`** loads **`BACKEND_URL`**, **`USER_ID`**, intervals, etc. from the environment after **`launcher.py`** loads **`config.env`**.  
- Events are posted to **`{BACKEND_URL}/track`**.

## Verify an install

1. **Task Manager** — process **`ZinniaAxion.exe`**.  
2. **`schtasks /Query /TN Zinnia_axion`** — scheduled task present.  
3. **`%USERPROFILE%\.telemetry-tracker\config.env`** — contains expected **`BACKEND_URL`** and **`USER_ID`**.  
4. **`%USERPROFILE%\.telemetry-tracker\tracker.log`** — launcher/agent logging.  
5. Backend receives **`POST /track`** (check server logs or DB).

## CI

**`.github/workflows/build-msi.yml`** runs the same command: **`python setup_msi.py bdist_msi`**, with **`INSTALLER_BACKEND_URL`** from workflow dispatch input or a default for tag builds.

## Deprecated / non-MSI paths

| Script | Status |
|--------|--------|
| **`installer/windows/build_msi_simple.py`** | **Deprecated** — exits with instructions to use **`setup_msi.py`**. |
| **`installer/windows/build.py`** | Optional **PyInstaller** `Zinnia_axion.exe` only; **not** the MSI pipeline. |

## Troubleshooting

- **`cx_Freeze` missing** — `pip install cx_Freeze`.  
- **Missing module at runtime** — add package or module to **`packages`** / **`includes`** in **`build_msi.py`** only.  
- **Verbose build** — `python setup_msi.py bdist_msi --verbose`  
- **MSI log** — `msiexec /i Your.msi /l*v install.log`

---

**Last updated:** April 2026  
