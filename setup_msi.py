"""
Zinnia Axion — Windows MSI entry point (wrapper).

The MSI is defined in one place: installer/windows/build_msi.py
Use this script from the repo root so paths and imports resolve predictably.

Build (Windows):
    set INSTALLER_BACKEND_URL=https://your-backend.example.com
    python setup_msi.py bdist_msi

Output:
    dist/<name>-<version>-amd64.msi   (exact name follows cx_Freeze; see README_MSI.md)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from installer.windows.build_msi import main

if __name__ == "__main__":
    main()
