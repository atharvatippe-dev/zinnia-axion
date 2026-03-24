# MSI Quick Start - 3 Steps ⚡

Build and distribute Windows MSI installer in 3 steps.

---

## ✅ What's Implemented

- **Automatic LAN ID detection** - Uses Windows login username
- **Zero user prompts** - No setup screens or popups
- **Auto-start enabled** - Runs on every Windows login
- **Silent operation** - Runs in background (no console)

---

## 🚀 Step 1: Build MSI (GitHub Actions)

```bash
# On macOS
cd /Users/Zinnia_India/Desktop/zinnia-axion

# Commit changes
git add .
git commit -m "MSI installer with auto LAN ID detection"
git push origin main
```

Then:
1. Go to GitHub → **Actions** tab
2. Click **"Build Windows MSI"** workflow
3. Click **"Run workflow"**
4. Enter backend URL: `https://your-backend-url.com`
5. Click **"Run workflow"**
6. Wait 2-3 minutes
7. Download **"ZinniaAxion-MSI"** artifact
8. Extract ZIP → Get `ZinniaAxion-1.0.0-amd64.msi`

---

## 📧 Step 2: Distribute to Employees

### Email Template:

```
Subject: Install Zinnia Axion Tracker

Hi team,

Please install the attached productivity tracker.

Steps:
1. Double-click: ZinniaAxion-1.0.0-amd64.msi
2. Click "Next" → "Install"
3. Done!

The tracker will start automatically and run in the background.

Thanks!
```

**Attach:** `ZinniaAxion-1.0.0-amd64.msi`

---

## ✅ Step 3: Verify Data is Coming In

1. **Wait 1-2 minutes** after employees install

2. **Check admin dashboard:**
   ```
   http://localhost:8502
   ```
   You should see employees appearing!

3. **Or check backend logs:**
   ```bash
   tail -f logs/app.log | grep "POST /track"
   ```

---

## 🎯 Employee Experience

### What they do:
1. Double-click MSI file
2. Click "Next" → "Install"
3. Click "Finish"
4. **That's it!**

### What happens automatically:
- ✅ Tracker installed
- ✅ LAN ID detected from Windows login (e.g., "john.doe")
- ✅ Tracker starts immediately
- ✅ Auto-start enabled
- ✅ Data flows to backend
- ✅ **Zero prompts or configuration needed!**

---

## 🔍 Verify It's Working

### On Employee Machine:

**Check if running:**
- Press `Ctrl+Shift+Esc` (Task Manager)
- Look for `ZinniaAxion.exe`

**Check config:**
- Navigate to: `%USERPROFILE%\.telemetry-tracker\`
- Open: `config.env`
- Should see: `USER_ID=their_windows_username`

**Check logs:**
- Open: `%USERPROFILE%\.telemetry-tracker\tracker.log`
- Should see: `Auto-detected LAN ID: their_username`

### On Backend:

**Admin Dashboard:**
```
http://localhost:8502
```
Should show employees with data.

**Backend Logs:**
```bash
grep "POST /track" logs/app.log
```
Should show requests from employees.

---

## ⚙️ What Gets Auto-Detected

```python
# Windows extracts this automatically:
LAN_ID = os.getenv("USERNAME")  # e.g., "john.doe"

# For domain-joined computers:
# COMPANY\john.doe → Becomes: "john.doe"

# For local accounts:
# John's Computer → Becomes: "John"
```

**No user input needed!** Windows login username is used automatically.

---

## 🐛 Troubleshooting

### Employee: "I don't see anything after installing"

✅ **Normal!** It runs silently in background.

Verify: Open Task Manager → Look for `ZinniaAxion.exe`

### Backend not receiving data

Check:
1. Backend URL correct? (rebuild MSI if wrong)
2. Backend running? Test in browser
3. Firewall blocking? Check employee network
4. Config file: `%USERPROFILE%\.telemetry-tracker\config.env`

### Wrong username detected

Employee can edit:
```
%USERPROFILE%\.telemetry-tracker\config.env

Change: USER_ID=correct_username
```

Then restart tracker (or restart computer).

---

## 📦 Files Created

Your project now has:

```
zinnia-axion/
├── setup_msi.py                          # MSI builder
├── .github/workflows/build-msi.yml       # GitHub Actions
├── installer/windows/
│   ├── launcher.py                       # ✅ UPDATED (auto LAN ID)
│   ├── setup_gui.py                      # GUI (not used anymore)
│   ├── autostart.py                      # Auto-start logic
│   └── build_config.py                   # Baked backend URL
├── BUILD_MSI_COMPLETE_GUIDE.md           # Full guide
└── MSI_QUICK_START.md                    # This file
```

---

## 🎉 You're Done!

MSI installer is ready to deploy with:
- ✅ Automatic LAN ID detection
- ✅ Zero user interaction
- ✅ Auto-start on login
- ✅ Silent background operation

**Build it, send it, forget it!** 🚀
