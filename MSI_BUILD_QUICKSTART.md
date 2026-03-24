# Windows MSI Installer - Quick Start Guide

Build a professional Windows MSI installer for the Zinnia Axion tracker in 3 simple steps.

## Overview

The MSI installer allows employees to install the tracker with a simple double-click:
- ✅ **No Python required** on employee machines
- ✅ **Auto-starts on login** via Windows Startup
- ✅ **Prompts for LAN ID** on first run
- ✅ **Runs silently** in background (no console window)
- ✅ **Standard uninstall** via Windows Settings

---

## Quick Start (3 Steps)

### Step 1: Install Build Tools

On your build machine (needs to be Windows or Windows VM):

```cmd
pip install cx_Freeze
```

### Step 2: Set Backend URL

```cmd
set INSTALLER_BACKEND_URL=https://your-backend-url.com
```

For example:
```cmd
set INSTALLER_BACKEND_URL=https://abc123.ngrok-free.dev
```

Or for production:
```cmd
set INSTALLER_BACKEND_URL=https://axion.company.com
```

### Step 3: Build MSI

```cmd
python setup_msi.py bdist_msi
```

**Output:** `dist/ZinniaAxion-1.0.0-amd64.msi` (15-25 MB)

---

## Distribution

### Send to Employees

1. **Email the MSI:**
   - Zip: `dist/ZinniaAxion-1.0.0-amd64.msi`
   - Email to employees
   - Include installation instructions

2. **Network Share:**
   ```
   \\company-server\software\ZinniaAxion.msi
   ```

3. **Company Software Portal:**
   - Upload to internal software portal
   - Employees download and install

---

## Employee Installation

### What Employees Do:

1. **Double-click** `ZinniaAxion.msi`
2. **Click "Next"** through installation wizard
3. **Click "Install"** (installs to `%LOCALAPPDATA%\Zinnia\Axion`)
4. **Enter LAN ID** when prompted (e.g., "john.doe" or "JOHN123")
5. **Click "Save & Start"**
6. **Done!** Tracker runs in background

### What Happens:

- ✅ Tracker installed to user's AppData folder
- ✅ Start Menu shortcut created
- ✅ Auto-start enabled (runs on Windows login)
- ✅ Config saved to `%USERPROFILE%\.telemetry-tracker\config.env`
- ✅ Tracker starts sending data to backend

---

## Verification

### Check if Tracker is Running

**Task Manager:**
1. Press `Ctrl+Shift+Esc`
2. Look for `ZinniaAxion.exe`

**Start Menu:**
1. Press Windows key
2. Search "Zinnia Axion"
3. Should see "Zinnia Axion Tracker" shortcut

**Log File:**
```
%USERPROFILE%\.telemetry-tracker\tracker.log
```

---

## Uninstallation

### Employee Method:

1. Open **Settings** → **Apps** → **Apps & features**
2. Search for **"Zinnia Axion"**
3. Click **"Uninstall"**

### IT Admin Method (Silent):

```cmd
msiexec /x ZinniaAxion.msi /quiet
```

---

## Advanced Options

### Silent Installation (IT Deployment)

Deploy via Group Policy or SCCM:

```cmd
msiexec /i ZinniaAxion.msi /quiet /norestart
```

### Custom Configuration

After installation, employees can edit:
```
%USERPROFILE%\.telemetry-tracker\config.env
```

Example:
```env
USER_ID=john.doe
BACKEND_URL=https://axion.company.com
POLL_INTERVAL_SEC=10
BATCH_INTERVAL_SEC=60
```

### Rebuild with New Backend URL

If backend URL changes:

```cmd
set INSTALLER_BACKEND_URL=https://new-backend-url.com
python setup_msi.py bdist_msi
```

Distribute new MSI to employees.

---

## Troubleshooting

### Build Issues

**"cx_Freeze not found"**
```cmd
pip install cx_Freeze
```

**"Build failed"**
```cmd
python setup_msi.py bdist_msi --verbose
```

### Installation Issues

**"Installation failed"**
- Check Windows Event Viewer
- Run with logging:
  ```cmd
  msiexec /i ZinniaAxion.msi /l*v install.log
  ```

### Runtime Issues

**"Tracker not sending data"**
1. Check log: `%USERPROFILE%\.telemetry-tracker\tracker.log`
2. Verify backend URL in config.env
3. Test backend URL in browser
4. Check firewall/proxy settings

**"LAN ID not detected"**
- Manually edit config.env
- Set `USER_ID=your_name`
- Restart tracker from Start Menu

---

## File Locations

### On Build Machine:

```
zinnia-axion/
├── setup_msi.py                    # MSI builder script
├── dist/
│   └── ZinniaAxion-1.0.0-amd64.msi # Output MSI
└── installer/windows/
    ├── launcher.py                 # Entry point
    ├── setup_gui.py                # LAN ID prompt
    └── autostart.py                # Auto-start logic
```

### On Employee Machine (After Installation):

```
%LOCALAPPDATA%\Zinnia\Axion\
├── ZinniaAxion.exe                 # Tracker executable
└── lib/                            # Python runtime + dependencies

%USERPROFILE%\.telemetry-tracker\
├── config.env                      # User configuration
├── tracker.log                     # Log file
└── buffer.json                     # Offline buffer

Start Menu\Programs\
└── Zinnia Axion\
    └── Zinnia Axion Tracker.lnk   # Shortcut

shell:startup\
└── Zinnia Axion Tracker.lnk       # Auto-start shortcut
```

---

## Comparison with .exe

| Feature | MSI Installer | Standalone .exe |
|---------|---------------|-----------------|
| **Installation** | Windows installer wizard | Manual copy to folder |
| **Start Menu** | ✅ Automatic | ❌ Manual shortcut |
| **Auto-start** | ✅ Automatic | ❌ Manual Task Scheduler |
| **Uninstall** | ✅ Standard Windows uninstall | ❌ Manual deletion |
| **Updates** | ✅ MSI upgrade support | ❌ Manual replacement |
| **IT Deployment** | ✅ Group Policy / SCCM | ❌ Manual scripting |
| **User Experience** | ✅ Professional | ⚠️ Technical |

**Recommendation:** Use MSI for enterprise deployment.

---

## Next Steps

1. **Build MSI** using steps above
2. **Test on clean Windows VM** before distribution
3. **Distribute to pilot group** (5-10 employees)
4. **Monitor backend** for incoming data
5. **Roll out company-wide** after successful pilot

---

## Support

For detailed documentation:
- Full guide: `installer/windows/README_MSI.md`
- Tracker docs: `README.md`
- Backend setup: `SYSTEM_DESIGN_DOCUMENT.md`

For issues:
- Check tracker log: `%USERPROFILE%\.telemetry-tracker\tracker.log`
- Review installation log: `msiexec /i ZinniaAxion.msi /l*v install.log`
- Contact IT support with log files

---

**Version:** 1.0.0  
**Last Updated:** March 2026  
**Build Time:** ~30 seconds  
**MSI Size:** 15-25 MB
