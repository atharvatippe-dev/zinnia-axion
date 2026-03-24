# Complete MSI Build & Distribution Guide

**FULLY AUTOMATIC** - Zero employee interaction required!

---

## What You'll Get

A Windows MSI installer that:
- ✅ **Auto-detects LAN ID** from Windows login (no prompts!)
- ✅ **Starts automatically** on installation
- ✅ **Auto-starts on every Windows login**
- ✅ **Sends data to backend** immediately
- ✅ **Zero user interaction** required

---

## Build Steps (On macOS → Use GitHub Actions)

Since you're on macOS, the easiest way is to use GitHub Actions to build the MSI automatically.

### Step 1: Push Code to GitHub

```bash
cd /Users/Zinnia_India/Desktop/zinnia-axion

# Add all files
git add .

# Commit changes
git commit -m "Add automatic LAN ID detection for MSI installer"

# Push to GitHub
git push origin main
```

### Step 2: Go to GitHub Actions

1. Open your repository on GitHub: `https://github.com/YOUR_USERNAME/zinnia-axion`
2. Click the **"Actions"** tab at the top
3. Click **"Build Windows MSI"** workflow (on the left)
4. Click **"Run workflow"** button (on the right)

### Step 3: Enter Backend URL

In the popup that appears:
- **Backend URL field:** Enter your backend URL
- Examples:
  - `https://abc123.ngrok-free.dev` (for testing)
  - `https://axion.yourcompany.com` (for production)
  - `https://your-ecs-alb.amazonaws.com` (AWS deployment)

Click **"Run workflow"**

### Step 4: Wait for Build (2-3 minutes)

Watch the workflow run:
- Green checkmark ✅ = Success
- Red X ❌ = Failed (check logs)

### Step 5: Download MSI

Once complete:
1. Click on the completed workflow run
2. Scroll down to **"Artifacts"** section
3. Click **"ZinniaAxion-MSI"** to download
4. Extract the ZIP file
5. You'll get: `ZinniaAxion-1.0.0-amd64.msi`

**File size:** ~15-25 MB

---

## Alternative: Build on Windows VM

If you have access to a Windows machine or VM:

### On Windows:

```cmd
# 1. Install cx_Freeze
pip install cx_Freeze

# 2. Set backend URL
set INSTALLER_BACKEND_URL=https://your-backend-url.com

# 3. Navigate to project
cd C:\path\to\zinnia-axion

# 4. Build MSI
python setup_msi.py bdist_msi

# Output: dist\ZinniaAxion-1.0.0-amd64.msi
```

---

## Test the MSI (Critical!)

Before distributing to all employees, test on a clean Windows machine:

### Test Steps:

1. **Copy MSI to test Windows machine**
   ```
   ZinniaAxion-1.0.0-amd64.msi
   ```

2. **Double-click MSI**
   - Installation wizard appears
   - Click "Next" → "Install"
   - Installation completes
   - **No prompts should appear!**

3. **Verify tracker is running**
   - Press `Ctrl+Shift+Esc` (Task Manager)
   - Look for `ZinniaAxion.exe`
   - Should be running!

4. **Check LAN ID was auto-detected**
   - Navigate to: `%USERPROFILE%\.telemetry-tracker\`
   - Open: `config.env`
   - Should see: `USER_ID=your_windows_username`

5. **Check log file**
   - Open: `%USERPROFILE%\.telemetry-tracker\tracker.log`
   - Should see:
     ```
     Auto-detected LAN ID: your_windows_username
     Config auto-created with LAN ID: your_windows_username
     Starting Zinnia Axion Agent.
     ```

6. **Verify data reaches backend**
   - Wait 60 seconds
   - Check backend logs or admin dashboard
   - Should see data from test user

7. **Test auto-start**
   - Restart Windows
   - After login, check Task Manager
   - `ZinniaAxion.exe` should be running automatically

### If all tests pass ✅ → Ready to distribute!

---

## Distribute to Employees

### Option 1: Email Distribution

```bash
# On macOS, prepare email:
cd ~/Downloads  # or wherever you saved the MSI

# Zip it (optional, for email size)
zip ZinniaAxion.zip ZinniaAxion-1.0.0-amd64.msi
```

**Email template:**

```
Subject: Install Zinnia Axion Productivity Tracker

Hi team,

Please install the Zinnia Axion tracker on your Windows computer.

INSTALLATION STEPS:
1. Download the attached file: ZinniaAxion-1.0.0-amd64.msi
2. Double-click the file
3. Click "Next" and then "Install"
4. That's it! The tracker will start automatically.

The tracker runs in the background and will automatically start when you log in to Windows.

If you have any issues, please contact IT support.

Thanks!
```

### Option 2: Network Share

```cmd
# On Windows file server:
copy ZinniaAxion-1.0.0-amd64.msi \\company-server\software\

# Tell employees:
"Install from: \\company-server\software\ZinniaAxion-1.0.0-amd64.msi"
```

### Option 3: Company Software Portal

Upload `ZinniaAxion-1.0.0-amd64.msi` to your company's software distribution portal (if you have one).

### Option 4: IT Mass Deployment (Silent Install)

For IT admins to deploy via Group Policy or SCCM:

```cmd
# Silent installation (no UI at all)
msiexec /i \\server\share\ZinniaAxion-1.0.0-amd64.msi /quiet /norestart

# With logging
msiexec /i \\server\share\ZinniaAxion-1.0.0-amd64.msi /quiet /norestart /l*v C:\install.log
```

---

## Employee Experience

### What employees see:

1. **Double-click MSI**
   - Windows installation wizard appears

2. **Click "Next" → "Install"**
   - Progress bar shows installation

3. **Installation completes**
   - Click "Finish"
   - **That's it! No other prompts!**

### What happens automatically:

1. ✅ Tracker installed to `%LOCALAPPDATA%\Zinnia\Axion`
2. ✅ Start Menu shortcut created
3. ✅ Auto-start enabled (runs on login)
4. ✅ LAN ID auto-detected from Windows username
5. ✅ Tracker starts sending data to backend
6. ✅ Config saved to `%USERPROFILE%\.telemetry-tracker\config.env`

### What employees DON'T see:

- ❌ No "Enter your name" popup
- ❌ No configuration screens
- ❌ No visible windows or consoles
- ❌ No further action needed

**Perfect for enterprise deployment!**

---

## Verify Deployment Success

### From Admin Dashboard:

1. Wait 1-2 minutes after employees install
2. Open admin dashboard
3. Check for new users appearing
4. Verify data is flowing

### From Backend Logs:

```bash
# Check backend logs for new users
grep "POST /track" logs/app.log | tail -20
```

You should see:
```
POST /track - 200 - user_id: john.doe
POST /track - 200 - user_id: jane.smith
POST /track - 200 - user_id: mike.jones
```

---

## Troubleshooting

### Employee: "I don't see anything after installing"

**This is normal!** The tracker runs silently in the background.

To verify it's working:
1. Press `Ctrl+Shift+Esc`
2. Look for `ZinniaAxion.exe`
3. If present → Working correctly!

### Employee: "Is it really running?"

Check the log file:
1. Press `Win+R`
2. Type: `%USERPROFILE%\.telemetry-tracker`
3. Open `tracker.log`
4. Should see recent activity

### Backend not receiving data

**Check:**
1. Backend URL is correct in MSI (rebuild if wrong)
2. Backend is running and accessible
3. Firewall allows outbound HTTPS
4. Check employee's `config.env` file has correct BACKEND_URL

**Debug:**
```
# On employee machine:
%USERPROFILE%\.telemetry-tracker\config.env

# Should contain:
BACKEND_URL=https://your-backend-url.com
USER_ID=john.doe  # (their Windows username)
```

### Wrong username detected

If auto-detection picks up wrong username:

**Option 1: Employee can edit config**
```
1. Navigate to: %USERPROFILE%\.telemetry-tracker\
2. Open: config.env
3. Change: USER_ID=correct_username
4. Restart tracker (or restart computer)
```

**Option 2: Rebuild MSI with manual prompt**
- Revert launcher.py changes
- Use setup GUI instead

---

## Updating/Reinstalling

### To update tracker:

1. Build new MSI with updated version:
   ```python
   # In setup_msi.py, change:
   version="1.1.0"  # Increment version
   ```

2. Distribute new MSI

3. Employees install new version
   - Old version uninstalled automatically
   - Config preserved (LAN ID not lost)
   - Tracker updated

### To uninstall:

**Employees:**
1. Settings → Apps → Apps & features
2. Search "Zinnia Axion"
3. Click "Uninstall"

**IT (Silent):**
```cmd
msiexec /x ZinniaAxion-1.0.0-amd64.msi /quiet
```

---

## Configuration Reference

### Build-Time (Baked into MSI):

```cmd
set INSTALLER_BACKEND_URL=https://your-backend-url.com
```

This URL is **permanently baked** into the MSI.

### Runtime (Auto-Created):

File: `%USERPROFILE%\.telemetry-tracker\config.env`

```env
USER_ID=john.doe                          # Auto-detected from Windows login
BACKEND_URL=https://your-backend-url.com  # From MSI build
POLL_INTERVAL_SEC=10
BATCH_INTERVAL_SEC=60
BUFFER_FILE=C:\Users\john\.telemetry-tracker\buffer.json
WINDOW_TITLE_MODE=redacted
```

Employees can edit this file if needed (rare).

---

## Security & Privacy

### What gets captured:

✅ **App name** (e.g., "Visual Studio Code")
✅ **Keystroke count** (number only, not content!)
✅ **Mouse click count**
✅ **Mouse movement distance**
✅ **Idle time**
✅ **Timestamp**

### What does NOT get captured:

❌ **Keystroke content** (what was typed)
❌ **Screenshots**
❌ **Clipboard data**
❌ **File contents**
❌ **URLs** (unless in window title, which can be redacted)
❌ **Passwords**
❌ **Personal data**

### Privacy mode:

Window titles are **redacted by default** (configured in launcher):
- `WINDOW_TITLE_MODE=redacted`
- Only keeps classification keywords (e.g., "youtube", "zoom")
- Strips email subjects, document names, etc.

---

## Complete Build Checklist

Before distributing to all employees:

- [ ] Backend is running and accessible
- [ ] Backend URL is correct (test in browser)
- [ ] MSI built with correct backend URL
- [ ] Tested MSI on clean Windows machine
- [ ] Verified LAN ID auto-detection works
- [ ] Verified tracker starts automatically
- [ ] Verified data reaches backend
- [ ] Verified auto-start works (after reboot)
- [ ] Prepared employee communication
- [ ] IT support team briefed
- [ ] Pilot test with 5-10 employees
- [ ] Monitor for 24-48 hours
- [ ] Roll out company-wide

---

## Quick Command Reference

### Build MSI (GitHub Actions):
```
1. Push code to GitHub
2. Go to Actions → Build Windows MSI
3. Enter backend URL
4. Run workflow
5. Download artifact
```

### Build MSI (Windows):
```cmd
pip install cx_Freeze
set INSTALLER_BACKEND_URL=https://your-backend-url.com
python setup_msi.py bdist_msi
```

### Distribute:
```
Email: Send ZinniaAxion-1.0.0-amd64.msi
Network: \\server\share\ZinniaAxion-1.0.0-amd64.msi
Silent: msiexec /i ZinniaAxion.msi /quiet
```

### Verify:
```
Task Manager → ZinniaAxion.exe
%USERPROFILE%\.telemetry-tracker\tracker.log
Admin Dashboard → Check for users
```

---

**You're ready to deploy! 🚀**

The MSI will automatically detect Windows usernames and start sending productivity data to your backend with zero employee interaction required.
