"""
Windows auto-start: Task Scheduler entry at user logon (schtasks).

Uses the frozen sys.executable (e.g. ZinniaAxion.exe from the MSI) so the task always
matches the installed binary. Idempotent — deletes the same task name before create.
Fallback: Startup folder batch file if schtasks fails.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("tracker.autostart")

TASK_NAME = "Zinnia_axion"
LOG_DIR = Path.home() / ".telemetry-tracker" / "logs"


def _get_executable() -> str:
    """Return the path to the bundled .exe or the Python script."""
    if getattr(sys, "frozen", False):
        return os.path.realpath(sys.executable)
    return sys.executable


def _get_command() -> str:
    """Return the full command string for the scheduled task."""
    exe = _get_executable()
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    launcher_path = Path(__file__).resolve().parent / "launcher.py"
    return f'"{exe}" "{launcher_path}"'


def install_autostart() -> None:
    """Create a Task Scheduler entry to run the tracker at user logon."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Remove existing task first (ignore errors if it doesn't exist)
    subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
    )

    command = _get_command()

    result = subprocess.run(
        [
            "schtasks", "/Create",
            "/TN", TASK_NAME,
            "/TR", command,
            "/SC", "ONLOGON",
            "/RL", "LIMITED",
            "/F",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        logger.info("Task Scheduler entry created - tracker will auto-start on logon.")
    else:
        logger.warning(
            "schtasks /Create returned %d: %s", result.returncode, result.stderr
        )
        # Fallback: Startup folder shortcut
        _install_startup_shortcut()


def _install_startup_shortcut() -> None:
    """
    Fallback: place a .bat launcher in the user's Startup folder.
    Works even without admin privileges (per-user Startup folder).
    """
    startup_dir = Path(os.environ.get(
        "APPDATA", Path.home() / "AppData" / "Roaming"
    )) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    if not startup_dir.exists():
        logger.warning("Startup folder not found: %s", startup_dir)
        return

    legacy_bat = startup_dir / "Zinnia_axion.bat"
    if legacy_bat.exists():
        legacy_bat.unlink()
        logger.info("Removed legacy startup launcher: %s", legacy_bat)

    bat_path = startup_dir / "ZinniaAxion.bat"
    command = _get_command()

    bat_path.write_text(
        f"@echo off\r\nstart /B \"\" {command}\r\n",
        encoding="utf-8",
    )
    logger.info("Startup shortcut written to %s", bat_path)


def uninstall_autostart() -> None:
    """Remove the Task Scheduler entry and Startup shortcut."""
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        logger.info("Task Scheduler entry removed.")
    else:
        logger.info("No Task Scheduler entry found to remove.")

    # Also remove Startup shortcut if present
    startup_dir = Path(os.environ.get(
        "APPDATA", Path.home() / "AppData" / "Roaming"
    )) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    for name in ("ZinniaAxion.bat", "Zinnia_axion.bat"):
        bat_path = startup_dir / name
        if bat_path.exists():
            bat_path.unlink()
            logger.info("Startup launcher removed: %s", bat_path)


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "uninstall":
        uninstall_autostart()
    else:
        install_autostart()
