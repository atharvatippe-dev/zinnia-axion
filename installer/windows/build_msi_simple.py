"""
Alternative MSI builder using PyInstaller + WiX Toolset automation.

This is a simpler approach that:
1. Builds .exe with PyInstaller (existing build.py)
2. Wraps it in MSI using Python-based WiX wrapper

Requirements:
    pip install pyinstaller
    
Note: This script generates a WiX .wxs file and calls candle.exe/light.exe
      You need WiX Toolset installed: https://wixtoolset.org/
      
Usage:
    set INSTALLER_BACKEND_URL=https://your-backend.ngrok-free.dev
    python installer/windows/build_msi_simple.py
    
Output:
    dist/ZinniaAxion.msi
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

# First, build the .exe using existing build.py
print("=" * 70)
print("STEP 1: Building .exe with PyInstaller")
print("=" * 70)

build_script = PROJECT_ROOT / "installer" / "windows" / "build.py"
result = subprocess.run([sys.executable, str(build_script)], cwd=str(PROJECT_ROOT))
if result.returncode != 0:
    print("ERROR: Failed to build .exe")
    sys.exit(1)

exe_path = DIST_DIR / "Zinnia_axion.exe"
if not exe_path.exists():
    print(f"ERROR: .exe not found at {exe_path}")
    sys.exit(1)

print(f"\n✅ .exe built successfully: {exe_path}")
print(f"   Size: {exe_path.stat().st_size / (1024*1024):.1f} MB")

# Generate WiX source file
print("\n" + "=" * 70)
print("STEP 2: Generating WiX source (.wxs)")
print("=" * 70)

wxs_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Product 
    Id="*" 
    Name="Zinnia Axion Tracker" 
    Language="1033" 
    Version="1.0.0.0" 
    Manufacturer="Zinnia India" 
    UpgradeCode="{uuid.uuid4()}">
    
    <Package 
      InstallerVersion="200" 
      Compressed="yes" 
      InstallScope="perUser" 
      Description="Zinnia Axion - Enterprise Productivity Intelligence Tracker"
      Comments="Tracks productivity metrics in the background" />

    <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />
    <MediaTemplate EmbedCab="yes" />

    <Feature Id="ProductFeature" Title="Zinnia Axion" Level="1">
      <ComponentGroupRef Id="ProductComponents" />
    </Feature>

    <Icon Id="icon.ico" SourceFile="installer/windows/icon.ico" />
    <Property Id="ARPPRODUCTICON" Value="icon.ico" />
    
    <!-- Custom action to run setup on first launch -->
    <CustomAction 
      Id="LaunchApplication" 
      FileKey="ZinniaAxionEXE" 
      ExeCommand="" 
      Execute="immediate" 
      Impersonate="yes" 
      Return="asyncNoWait" />

    <InstallExecuteSequence>
      <Custom Action="LaunchApplication" After="InstallFinalize">NOT Installed</Custom>
    </InstallExecuteSequence>

  </Product>

  <Fragment>
    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="LocalAppDataFolder">
        <Directory Id="ZinniaFolder" Name="Zinnia">
          <Directory Id="INSTALLFOLDER" Name="Axion" />
        </Directory>
      </Directory>
      
      <Directory Id="ProgramMenuFolder">
        <Directory Id="ApplicationProgramsFolder" Name="Zinnia Axion" />
      </Directory>
      
      <Directory Id="StartupFolder" />
    </Directory>
  </Fragment>

  <Fragment>
    <ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER">
      <Component Id="ZinniaAxionEXE" Guid="{uuid.uuid4()}">
        <File Id="ZinniaAxionEXE" Source="dist/Zinnia_axion.exe" KeyPath="yes" />
        
        <!-- Start Menu Shortcut -->
        <Shortcut 
          Id="ApplicationStartMenuShortcut" 
          Name="Zinnia Axion Tracker" 
          Description="Enterprise Productivity Tracker"
          Directory="ApplicationProgramsFolder" 
          WorkingDirectory="INSTALLFOLDER" 
          Icon="icon.ico" 
          IconIndex="0" 
          Advertise="yes" />
        
        <!-- Startup Folder Shortcut (auto-start) -->
        <Shortcut 
          Id="ApplicationStartupShortcut" 
          Name="Zinnia Axion Tracker" 
          Description="Enterprise Productivity Tracker"
          Directory="StartupFolder" 
          WorkingDirectory="INSTALLFOLDER" 
          Icon="icon.ico" 
          IconIndex="0" 
          Advertise="yes" />
        
        <!-- Remove Start Menu folder on uninstall -->
        <RemoveFolder Id="ApplicationProgramsFolder" Directory="ApplicationProgramsFolder" On="uninstall" />
        
        <!-- Registry key for Add/Remove Programs -->
        <RegistryValue 
          Root="HKCU" 
          Key="Software\\Zinnia\\Axion" 
          Name="installed" 
          Type="integer" 
          Value="1" 
          KeyPath="no" />
      </Component>
    </ComponentGroup>
  </Fragment>
</Wix>
"""

wxs_file = BUILD_DIR / "zinnia_axion.wxs"
BUILD_DIR.mkdir(exist_ok=True)
wxs_file.write_text(wxs_content, encoding="utf-8")
print(f"✅ WiX source generated: {wxs_file}")

# Check if WiX is installed
print("\n" + "=" * 70)
print("STEP 3: Checking WiX Toolset installation")
print("=" * 70)

wix_paths = [
    Path(r"C:\Program Files (x86)\WiX Toolset v3.11\bin"),
    Path(r"C:\Program Files\WiX Toolset v3.11\bin"),
    Path(r"C:\Program Files (x86)\WiX Toolset v4.0\bin"),
    Path(r"C:\Program Files\WiX Toolset v4.0\bin"),
]

candle_exe = None
light_exe = None

for wix_path in wix_paths:
    if (wix_path / "candle.exe").exists():
        candle_exe = wix_path / "candle.exe"
        light_exe = wix_path / "light.exe"
        break

if not candle_exe:
    print("❌ ERROR: WiX Toolset not found!")
    print("\nPlease install WiX Toolset:")
    print("  1. Download from: https://wixtoolset.org/releases/")
    print("  2. Install WiX Toolset v3.11 or later")
    print("  3. Re-run this script")
    print("\nAlternatively, use build_msi.py with cx_Freeze (no WiX required):")
    print("  pip install cx_Freeze")
    print("  python installer/windows/build_msi.py bdist_msi")
    sys.exit(1)

print(f"✅ WiX found: {candle_exe.parent}")

# Compile with candle.exe
print("\n" + "=" * 70)
print("STEP 4: Compiling with candle.exe")
print("=" * 70)

wixobj_file = BUILD_DIR / "zinnia_axion.wixobj"
result = subprocess.run(
    [str(candle_exe), "-out", str(wixobj_file), str(wxs_file)],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print("❌ Candle.exe failed:")
    print(result.stderr)
    sys.exit(1)

print(f"✅ Compiled: {wixobj_file}")

# Link with light.exe
print("\n" + "=" * 70)
print("STEP 5: Linking with light.exe")
print("=" * 70)

msi_file = DIST_DIR / "ZinniaAxion.msi"
result = subprocess.run(
    [
        str(light_exe),
        "-ext", "WixUIExtension",
        "-out", str(msi_file),
        str(wixobj_file),
    ],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print("❌ Light.exe failed:")
    print(result.stderr)
    sys.exit(1)

print(f"✅ MSI created: {msi_file}")
print(f"   Size: {msi_file.stat().st_size / (1024*1024):.1f} MB")

print("\n" + "=" * 70)
print("✅ BUILD COMPLETE!")
print("=" * 70)
print(f"\nMSI Installer: {msi_file}")
print("\nYou can now distribute this .msi file to employees.")
print("On installation:")
print("  1. MSI installs to %LOCALAPPDATA%\\Zinnia\\Axion")
print("  2. Creates Start Menu shortcut")
print("  3. Adds to Startup folder (auto-start on login)")
print("  4. First run shows LAN ID setup dialog")
print("  5. Tracker runs in background automatically")
