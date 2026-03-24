"""
Launcher - entry point for the bundled Zinnia Axion .exe (Windows).

Flow (Fully Automatic - No User Prompts):
  1. Check if %USERPROFILE%\\.telemetry-tracker\\config.env exists
  2. If not → auto-detect LAN ID from Windows USERNAME (first launch)
  3. Create config.env automatically with detected LAN ID
  4. Load config.env into environment
  5. Install Task Scheduler auto-start entry (idempotent)
  6. Start the Zinnia Axion Agent

The tracker automatically uses the employee's Windows login username (LAN ID)
without requiring any user input. Perfect for silent enterprise deployment.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_LOG_DIR = Path.home() / ".telemetry-tracker"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "tracker.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(_LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("tracker.launcher")

# When bundled with PyInstaller, files are in a temp dir.
# _MEIPASS is set by PyInstaller; fall back to script dir for dev.
if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(BUNDLE_DIR))

CONFIG_DIR = Path.home() / ".telemetry-tracker"
CONFIG_FILE = CONFIG_DIR / "config.env"


def _load_config_env() -> None:
    """Read config.env and inject into os.environ."""
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _install_autostart() -> None:
    """Install a Windows Task Scheduler entry so the tracker starts on logon."""
    try:
        from installer.windows.autostart import install_autostart
        install_autostart()
    except Exception as exc:
        logger.warning("Could not install auto-start: %s", exc)


def main() -> None:
    # Step 1: Auto-create config on first launch (no GUI prompt)
    if not CONFIG_FILE.exists() or CONFIG_FILE.stat().st_size == 0:
        logger.info("No config found - auto-detecting LAN ID from Windows login.")
        
        # Auto-detect LAN ID from Windows USERNAME environment variable
        auto_lan_id = os.getenv("USERNAME") or os.getenv("USER") or "default"
        logger.info(f"Auto-detected LAN ID: {auto_lan_id}")
        
        # Create config automatically (no user prompt needed)
        from installer.windows.setup_gui import write_config
        try:
            from installer.windows.build_config import BACKEND_URL as DEFAULT_BACKEND_URL
        except ImportError:
            DEFAULT_BACKEND_URL = os.environ.get(
                "INSTALLER_BACKEND_URL", "https://your-backend-url.ngrok-free.dev"
            )
        
        write_config(auto_lan_id, DEFAULT_BACKEND_URL)
        logger.info(f"Config auto-created with LAN ID: {auto_lan_id}")

    # Step 2: Load config
    _load_config_env()
    logger.info("Config loaded. User ID: %s", os.environ.get("USER_ID", "unknown"))

    # Step 3: Install auto-start (idempotent - safe to call multiple times)
    _install_autostart()

    # Step 4: Start the tracker
    from tracker.agent import main as tracker_main
    tracker_main()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in launcher")
        sys.exit(1)
