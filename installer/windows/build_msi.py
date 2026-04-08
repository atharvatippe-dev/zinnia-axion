"""
Canonical Windows MSI build for Zinnia Axion (cx_Freeze).

SOURCE OF TRUTH
---------------
This module is the only place that defines cx_Freeze options (packages, excludes,
MSI metadata, install directory, upgrade code, executable/shortcut names). CI and
local builds must run the same entry point so the MSI is always identical in behavior.

Entry points (equivalent):
  - Repository root (recommended):  python setup_msi.py bdist_msi
  - Direct:                          python installer/windows/build_msi.py bdist_msi

Run from the repository root (or use setup_msi.py, which chdirs to the root).

BACKEND URL BAKING
------------------
Set INSTALLER_BACKEND_URL before building. This overwrites installer/windows/build_config.py
with BACKEND_URL = "<your url>". That module is frozen into the exe; launcher.py reads it
on first run when creating %USERPROFILE%\\.telemetry-tracker\\config.env.

If INSTALLER_BACKEND_URL is unset, the existing build_config.py in the repo is left as-is
(typically a placeholder) and a warning is printed.

INSTALL LOCATION
----------------
Per-user install under %%LOCALAPPDATA%%\\Zinnia\\Axion — no elevation for default path,
suitable for enterprise rollouts where users lack admin rights.

UPGRADE CODE
------------
Must stay constant across MSI releases so Windows recognizes upgrades/replacements.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Product / MSI identity (keep upgrade_code stable across versions) ---
MSI_APP_NAME = "ZinniaAxion"  # cx_Freeze `name` → dist MSI filename prefix (no spaces)
MSI_VERSION = "1.0.0"
EXE_NAME = "ZinniaAxion.exe"
SHORTCUT_NAME = "Zinnia Axion Tracker"
UPGRADE_CODE = "{A1B2C3D4-E5F6-4321-8765-FEDCBA987654}"
# Per-user default install dir in the WiX/cx_Freeze sense:
INITIAL_TARGET_DIR = r"[LocalAppDataFolder]\Zinnia\Axion"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LAUNCHER_SCRIPT = PROJECT_ROOT / "installer" / "windows" / "launcher.py"
BUILD_CONFIG_PATH = PROJECT_ROOT / "installer" / "windows" / "build_config.py"


def _bake_backend_url() -> None:
    """Write build_config.py from INSTALLER_BACKEND_URL when set."""
    backend_url = os.environ.get("INSTALLER_BACKEND_URL", "").strip()
    if not backend_url:
        print(
            "[WARNING] INSTALLER_BACKEND_URL is not set.\n"
            "          The MSI will use whatever BACKEND_URL is already in\n"
            "          installer/windows/build_config.py (often a placeholder).\n"
            "          For production: set INSTALLER_BACKEND_URL before building.\n"
        )
        return

    BUILD_CONFIG_PATH.write_text(
        '"""\n'
        "Build-time configuration — written by installer/windows/build_msi.py\n"
        "when INSTALLER_BACKEND_URL is set. Do not edit for production installs;\n"
        "change the env var and rebuild the MSI instead.\n"
        '"""\n\n'
        f'BACKEND_URL = "{backend_url}"\n',
        encoding="utf-8",
    )
    print(f"[OK] Baked BACKEND_URL into build_config.py: {backend_url}")


def _cx_freeze_setup() -> None:
    try:
        from cx_Freeze import Executable, setup
    except ImportError:
        print("ERROR: cx_Freeze is not installed. Install with: pip install cx_Freeze")
        sys.exit(1)

    # Bundled source trees sit next to the frozen exe; launcher adds BUNDLE_DIR to sys.path.
    include_files = [
        (str(PROJECT_ROOT / "tracker"), "tracker"),
        (str(PROJECT_ROOT / "installer" / "windows"), "installer/windows"),
    ]

    build_exe_options = {
        "packages": [
            "os",
            "sys",
            "logging",
            "pathlib",
            "tkinter",
            "json",
            "time",
            "datetime",
            "threading",
            "subprocess",
            "requests",
            "pynput",
            "psutil",
            "dotenv",
            "win32gui",
            "win32process",
            "win32api",
            "win32con",
            "ctypes",
        ],
        "includes": [
            "tracker.agent",
            "tracker.platform.factory",
            "tracker.platform.base",
            "tracker.platform.windows",
            "installer.windows.setup_gui",
            "installer.windows.autostart",
            "installer.windows.build_config",
            "win32gui",
            "win32process",
            "win32api",
            "win32con",
            "ctypes",
            "ctypes.wintypes",
        ],
        "include_files": include_files,
        "excludes": [
            "matplotlib",
            "numpy",
            "pandas",
            "scipy",
            "PIL",
            "PyQt5",
            "PyQt6",
            "pytest",
            "flask",
            "streamlit",
            "sqlalchemy",
            "alembic",
            "plotly",
            "backend",
            "frontend",
        ],
        "optimize": 2,
    }

    bdist_msi_options = {
        "add_to_path": False,
        "initial_target_dir": INITIAL_TARGET_DIR,
        "upgrade_code": UPGRADE_CODE,
        "install_icon": None,
        "summary_data": {
            "author": "Zinnia India",
            "comments": "Enterprise Productivity Intelligence Tracker",
            "keywords": "productivity,tracking,monitoring",
        },
    }

    executables = [
        Executable(
            script=str(LAUNCHER_SCRIPT),
            base="Win32GUI",
            target_name=EXE_NAME,
            icon=None,
            shortcut_name=SHORTCUT_NAME,
            shortcut_dir="ProgramMenuFolder",
        )
    ]

    setup(
        name=MSI_APP_NAME,
        version=MSI_VERSION,
        description="Enterprise Productivity Intelligence Tracker",
        long_description=(
            "Tracks employee productivity metrics in the background. "
            "Captures app usage, keystroke counts, and idle time without "
            "recording actual content."
        ),
        author="Zinnia India",
        options={
            "build_exe": build_exe_options,
            "bdist_msi": bdist_msi_options,
        },
        executables=executables,
    )


def main() -> None:
    """Prepare config and invoke cx_Freeze setuptools integration (uses sys.argv)."""
    os.chdir(PROJECT_ROOT)
    _bake_backend_url()
    _cx_freeze_setup()


if __name__ == "__main__":
    main()
