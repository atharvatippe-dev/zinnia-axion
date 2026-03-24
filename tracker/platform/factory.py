"""
Factory that returns the correct PlatformCollector for the current OS.
"""

from __future__ import annotations

import sys
import logging

from tracker.platform.base import PlatformCollector

logger = logging.getLogger("tracker.platform")


def get_collector() -> PlatformCollector:
    """
    Detect the current OS and return the appropriate collector.

    Raises RuntimeError if the platform is unsupported.
    """
    system = sys.platform

    if system == "darwin":
        from tracker.platform.macos import MacOSCollector
        logger.info("Detected macOS — using MacOSCollector.")
        return MacOSCollector()

    elif system == "win32":
        from tracker.platform.windows import WindowsCollector
        logger.info("Detected Windows — using WindowsCollector.")
        return WindowsCollector()

    elif system == "linux":
        from tracker.platform.linux import LinuxCollector
        logger.info("Detected Linux — using LinuxCollector.")
        return LinuxCollector()

    else:
        raise RuntimeError(
            f"Unsupported platform: {system}. "
            "Implement a PlatformCollector subclass in tracker/platform/."
        )
