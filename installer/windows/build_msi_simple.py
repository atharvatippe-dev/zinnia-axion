"""
DEPRECATED — do not use for MSI builds.

This script previously wrapped PyInstaller + WiX. The supported path is cx_Freeze only,
defined in installer/windows/build_msi.py (run via python setup_msi.py bdist_msi).

This file is kept so old docs/links fail loudly instead of producing a divergent MSI.
"""

from __future__ import annotations

import sys


def main() -> None:
    print("=" * 72)
    print("DEPRECATED: installer/windows/build_msi_simple.py is no longer supported.")
    print()
    print("Use the canonical MSI build (cx_Freeze), from the repository root:")
    print("  set INSTALLER_BACKEND_URL=https://your-backend.example.com")
    print("  python setup_msi.py bdist_msi")
    print()
    print("Implementation: installer/windows/build_msi.py")
    print("=" * 72)
    sys.exit(2)


if __name__ == "__main__":
    main()
