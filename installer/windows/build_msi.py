"""
Build script - creates a Windows .msi installer using cx_Freeze.

This creates a proper MSI installer that:
- Installs the tracker to Program Files
- Creates Start Menu shortcuts
- Sets up auto-start via Task Scheduler
- Shows LAN ID setup dialog on first run
- Runs in background automatically

Usage (from project root):
    set INSTALLER_BACKEND_URL=https://your-backend.ngrok-free.dev
    python installer/windows/build_msi.py build
    python installer/windows/build_msi.py bdist_msi

Output:
    dist/Zinnia_Axion-1.0.0-win64.msi
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add cx_Freeze to the path
try:
    from cx_Freeze import setup, Executable
except ImportError:
    print("ERROR: cx_Freeze not installed.")
    print("Install it with: pip install cx_Freeze")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LAUNCHER = PROJECT_ROOT / "installer" / "windows" / "launcher.py"

# Get backend URL from environment
backend_url = os.environ.get("INSTALLER_BACKEND_URL", "")
if not backend_url:
    print("WARNING: INSTALLER_BACKEND_URL not set.")
    print("The installer will use the placeholder URL.")
    print("Set it with: set INSTALLER_BACKEND_URL=https://your-url.ngrok-free.dev")
    print()
else:
    # Write build config
    config_file = PROJECT_ROOT / "installer" / "windows" / "build_config.py"
    config_file.write_text(
        '"""\nBuild-time configuration - values baked in by the build script.\n'
        'Do NOT edit manually; this file is overwritten by build.py.\n"""\n\n'
        f'BACKEND_URL = "{backend_url}"\n',
        encoding="utf-8",
    )
    print(f"✅ Baked backend URL: {backend_url}")

# Build options
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
        "requests",
        "pynput",
        "psutil",
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
    ],
    "include_files": [
        (str(PROJECT_ROOT / "tracker"), "tracker"),
        (str(PROJECT_ROOT / "installer" / "windows"), "installer/windows"),
    ],
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
    ],
    "optimize": 2,
}

# MSI-specific options
bdist_msi_options = {
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\Zinnia\Axion",
    "install_icon": None,  # Add icon path if you have one
    "upgrade_code": "{12345678-1234-1234-1234-123456789012}",  # Keep this constant across versions
}

# Executable configuration
executables = [
    Executable(
        script=str(LAUNCHER),
        base="Win32GUI",  # No console window
        target_name="ZinniaAxion.exe",
        icon=None,  # Add icon path if you have one
        shortcut_name="Zinnia Axion Tracker",
        shortcut_dir="ProgramMenuFolder",
    )
]

# Setup configuration
setup(
    name="Zinnia Axion",
    version="1.0.0",
    description="Enterprise Productivity Intelligence Tracker",
    author="Zinnia India",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
