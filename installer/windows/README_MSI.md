# Windows MSI Installer Guide

This guide explains how to build and distribute the Zinnia Axion tracker as a Windows MSI installer.

## Overview

The MSI installer provides a professional Windows installation experience:

- **Double-click installation** - No Python required on employee machines
- **Program Files installation** - Installs to `%LOCALAPPDATA%\Zinnia\Axion`
- **Start Menu shortcut** - Easy access via Windows Start Menu
- **Auto-start on login** - Tracker starts automatically when Windows boots
- **First-run setup** - Prompts for LAN ID on first launch
- **Silent background operation** - Runs without console window
- **Clean uninstallation** - Standard Windows "Add/Remove Programs"

## Prerequisites

### On Build Machine (Your Computer)

```bash
# Install cx_Freeze (MSI builder)
pip install cx_Freeze

# Verify installation
python -c "import cx_Freeze; print(f'cx_Freeze {cx_Freeze.version} installed')"
```

### On Employee Machines

**Nothing required!** The MSI is a standalone installer.

## Building the MSI

### Step 1: Set Backend URL

```cmd
set INSTALLER_BACKEND_URL=https://your-backend.ngrok-free.dev
```

Or for production:
```cmd
set INSTALLER_BACKEND_URL=https://axion.company.com
```

### Step 2: Build MSI

```cmd
python setup_msi.py bdist_msi
```

### Step 3: Find Output

```
dist/ZinniaAxion-1.0.0-amd64.msi
```

Size: ~15-25 MB (includes Python runtime + dependencies)

## Alternative Build Methods

### Method 1: cx_Freeze (Recommended)

**File:** `setup_msi.py` (root directory)

```cmd
python setup_msi.py bdist_msi
```

**Pros:**
- Pure Python - no external tools
- Works on any Windows machine
- Creates proper MSI with all features
- Easy to customize

**Cons:**
- Larger file size (~20 MB)
- Includes Python runtime

### Method 2: Advanced MSI with cx_Freeze

**File:** `installer/windows/build_msi.py`

```cmd
python installer/windows/build_msi.py build
python installer/windows/build_msi.py bdist_msi
```

More control over build options.

### Method 3: PyInstaller + WiX (Expert)

**File:** `installer/windows/build_msi_simple.py`

```cmd
python installer/windows/build_msi_simple.py
```

**Requirements:**
- PyInstaller: `pip install pyinstaller`
- WiX Toolset: https://wixtoolset.org/releases/

**Pros:**
- Smaller file size
- More control over MSI features

**Cons:**
- Requires WiX Toolset installation
- More complex setup

## Distribution

### Internal Distribution

1. **Network Share:**
   ```
   \\company-server\software\ZinniaAxion.msi
   ```

2. **Email:**
   - Zip the MSI
   - Send via corporate email
   - Include installation instructions

3. **Software Portal:**
   - Upload to company software portal
   - Employees download and install

### Silent Installation (IT Admin)

Deploy via Group Policy or SCCM:

```cmd
msiexec /i ZinniaAxion.msi /quiet /norestart
```

With custom properties:
```cmd
msiexec /i ZinniaAxion.msi /quiet BACKEND_URL=https://axion.company.com
```

## Employee Installation

### GUI Installation

1. Double-click `ZinniaAxion.msi`
2. Click "Next" through wizard
3. Choose installation location (default: `%LOCALAPPDATA%\Zinnia\Axion`)
4. Click "Install"
5. Setup window appears asking for LAN ID
6. Enter name/employee ID
7. Click "Save & Start"
8. Tracker runs in background

### Verification

Check Task Manager:
- Process: `ZinniaAxion.exe`
- Description: Zinnia Axion Tracker

Check Start Menu:
- Folder: "Zinnia Axion"
- Shortcut: "Zinnia Axion Tracker"

Check auto-start:
- `shell:startup` → Should have "Zinnia Axion Tracker" shortcut

## Uninstallation

### User Method

1. Open "Add/Remove Programs"
2. Search for "Zinnia Axion"
3. Click "Uninstall"

### Admin Method

```cmd
msiexec /x ZinniaAxion.msi /quiet
```

Or using product code:
```cmd
msiexec /x {A1B2C3D4-E5F6-4321-8765-FEDCBA987654} /quiet
```

## Configuration

### Build-Time Configuration

Set during MSI build (baked into installer):

| Variable | Description | Example |
|----------|-------------|---------|
| `INSTALLER_BACKEND_URL` | Backend API URL | `https://axion.company.com` |

### Runtime Configuration

Set after installation (employee can modify):

Location: `%USERPROFILE%\.telemetry-tracker\config.env`

```env
USER_ID=john.doe
BACKEND_URL=https://axion.company.com
POLL_INTERVAL_SEC=10
BATCH_INTERVAL_SEC=60
WINDOW_TITLE_MODE=redacted
```

## Troubleshooting

### Build Errors

**"cx_Freeze not found"**
```cmd
pip install cx_Freeze
```

**"Module not found"**
- Check `build_exe_options` in `setup_msi.py`
- Add missing package to `packages` or `includes`

**"Build failed"**
- Run with verbose output:
  ```cmd
  python setup_msi.py bdist_msi --verbose
  ```

### Installation Errors

**"Installation failed"**
- Check Windows Event Viewer
- Run MSI with logging:
  ```cmd
  msiexec /i ZinniaAxion.msi /l*v install.log
  ```

**"Tracker not starting"**
- Check log file: `%USERPROFILE%\.telemetry-tracker\tracker.log`
- Verify backend URL is accessible
- Check firewall settings

### Runtime Errors

**"Can't connect to backend"**
- Check `config.env` file
- Verify `BACKEND_URL` is correct
- Test URL in browser
- Check corporate firewall/proxy

**"LAN ID not detected"**
- Manually edit `config.env`
- Set `USER_ID=your_name`
- Restart tracker

## Advanced: Customization

### Custom Icon

1. Create `installer/windows/icon.ico` (256x256 px)
2. Update `setup_msi.py`:
   ```python
   executables = [
       Executable(
           script="installer/windows/launcher.py",
           base="Win32GUI",
           target_name="ZinniaAxion.exe",
           icon="installer/windows/icon.ico",  # Add this
       )
   ]
   ```

### Custom Install Location

Update `setup_msi.py`:
```python
bdist_msi_options = {
    "initial_target_dir": r"[ProgramFilesFolder]\Zinnia\Axion",  # System-wide
    # or
    "initial_target_dir": r"[LocalAppDataFolder]\Zinnia\Axion",  # Per-user
}
```

### Version Updates

Update `setup_msi.py`:
```python
setup(
    name="Zinnia Axion",
    version="1.1.0",  # Increment this
    ...
)
```

**Important:** Keep `upgrade_code` constant across versions!

### Add License Agreement

Create `LICENSE.rtf` and update `setup_msi.py`:
```python
bdist_msi_options = {
    "license_file": "LICENSE.rtf",
    ...
}
```

## File Structure

```
zinnia-axion/
├── setup_msi.py                          # Main MSI builder
├── installer/
│   └── windows/
│       ├── launcher.py                   # Entry point
│       ├── setup_gui.py                  # LAN ID prompt
│       ├── autostart.py                  # Auto-start logic
│       ├── build_config.py               # Baked config
│       ├── build_msi.py                  # Alternative builder
│       ├── build_msi_simple.py           # WiX-based builder
│       └── README_MSI.md                 # This file
├── tracker/
│   ├── agent.py                          # Main tracker
│   └── platform/
│       └── windows.py                    # Windows-specific code
└── dist/
    └── ZinniaAxion-1.0.0-amd64.msi      # Output
```

## Best Practices

1. **Test before distribution**
   - Install on clean Windows VM
   - Verify all features work
   - Check auto-start behavior

2. **Version control**
   - Increment version for each release
   - Tag releases in git
   - Keep upgrade code constant

3. **Security**
   - Sign MSI with code signing certificate
   - Use HTTPS for backend URL
   - Validate backend SSL certificate

4. **Documentation**
   - Include installation guide
   - Provide troubleshooting steps
   - Document uninstallation process

5. **Support**
   - Monitor installation success rate
   - Collect error logs
   - Provide IT helpdesk with FAQ

## Support

For issues:
1. Check `%USERPROFILE%\.telemetry-tracker\tracker.log`
2. Review Windows Event Viewer
3. Run MSI with logging: `msiexec /i ZinniaAxion.msi /l*v install.log`
4. Contact IT support with log files

---

**Last Updated:** March 2026  
**Version:** 1.0.0
