"""
MSI Installer Builder for Zinnia Axion Tracker (Windows)

This creates a native Windows MSI installer using cx_Freeze.
No external tools required - pure Python solution!

Features:
- Installs to Program Files
- Creates Start Menu shortcuts  
- Auto-starts on login
- Shows LAN ID setup on first run
- Runs silently in background

Installation:
    pip install cx_Freeze

Build MSI:
    set INSTALLER_BACKEND_URL=https://your-backend.ngrok-free.dev
    python setup_msi.py bdist_msi

Output:
    dist/Zinnia_Axion-1.0.0-amd64.msi

Usage for employees:
    1. Double-click ZinniaAxion.msi
    2. Follow installation wizard
    3. Enter LAN ID when prompted
    4. Tracker starts automatically
"""

import os
import sys
from pathlib import Path

try:
    from cx_Freeze import setup, Executable
except ImportError:
    print("=" * 70)
    print("ERROR: cx_Freeze not installed")
    print("=" * 70)
    print("\nInstall it with:")
    print("  pip install cx_Freeze")
    print("\nThen run:")
    print("  python setup_msi.py bdist_msi")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent

# Get backend URL from environment
backend_url = os.environ.get("INSTALLER_BACKEND_URL", "")
if backend_url:
    config_file = PROJECT_ROOT / "installer" / "windows" / "build_config.py"
    config_file.write_text(
        '"""\nBuild-time configuration.\n"""\n\n'
        f'BACKEND_URL = "{backend_url}"\n',
        encoding="utf-8",
    )
    print(f"✅ Backend URL configured: {backend_url}")
else:
    print("⚠️  WARNING: INSTALLER_BACKEND_URL not set")
    print("   Set it with: set INSTALLER_BACKEND_URL=https://your-backend-url")
    print("   Continuing with placeholder URL...\n")

# Files to include
include_files = [
    ("tracker/", "tracker/"),
    ("installer/windows/", "installer/windows/"),
]

# Build options
build_exe_options = {
    "packages": [
        "os", "sys", "logging", "pathlib", "tkinter", "json",
        "time", "datetime", "threading", "subprocess",
        "requests", "pynput", "psutil",
    ],
    "includes": [
        "tracker.agent",
        "tracker.platform.factory",
        "tracker.platform.base",
        "tracker.platform.windows",
        "installer.windows.setup_gui",
        "installer.windows.autostart",
        "installer.windows.build_config",
        "win32gui", "win32process", "win32api", "win32con",
        "ctypes", "ctypes.wintypes",
    ],
    "include_files": include_files,
    "excludes": [
        "matplotlib", "numpy", "pandas", "scipy", "PIL",
        "PyQt5", "PyQt6", "pytest", "flask", "streamlit",
        "sqlalchemy", "alembic", "plotly", "backend", "frontend",
    ],
    "optimize": 2,
    "build_exe": "build/exe",
}

# MSI options
bdist_msi_options = {
    "add_to_path": False,
    "initial_target_dir": r"[LocalAppDataFolder]\Zinnia\Axion",
    "upgrade_code": "{A1B2C3D4-E5F6-4321-8765-FEDCBA987654}",
    "install_icon": None,
    "summary_data": {
        "author": "Zinnia India",
        "comments": "Enterprise Productivity Intelligence Tracker",
        "keywords": "productivity,tracking,monitoring",
    },
    "target_name": "ZinniaAxion",
}

# Main executable
executables = [
    Executable(
        script="installer/windows/launcher.py",
        base="Win32GUI",  # No console window
        target_name="ZinniaAxion.exe",
        icon=None,
        shortcut_name="Zinnia Axion Tracker",
        shortcut_dir="ProgramMenuFolder",
    )
]

# Run setup
setup(
    name="Zinnia Axion",
    version="1.0.0",
    description="Enterprise Productivity Intelligence Tracker",
    long_description="Tracks employee productivity metrics in the background. "
                     "Captures app usage, keystroke counts, and idle time without "
                     "recording actual content. Respects privacy while providing "
                     "actionable insights.",
    author="Zinnia India",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)

print("\n" + "=" * 70)
print("BUILD INSTRUCTIONS")
print("=" * 70)
print("\n1. Set backend URL:")
print("   set INSTALLER_BACKEND_URL=https://your-backend.com")
print("\n2. Build MSI:")
print("   python setup_msi.py bdist_msi")
print("\n3. Distribute:")
print("   dist/ZinniaAxion-1.0.0-amd64.msi")
print("\n" + "=" * 70)
