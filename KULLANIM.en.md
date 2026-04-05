> 🇹🇷 [Türkçe](https://github.com/trs-1342/alms/blob/main/KULLANIM.md) &nbsp;|&nbsp; 🇬🇧 **English**

---

# ALMS Downloader — Usage Guide

---

## Quick Start

```bash
alms setup          # First-time setup (done once)
alms                # Open menu
alms sync           # Download new files
alms obis --sinav   # View exam schedule
```

---

## All Commands

### `alms` — Menu
```
alms
```
Opens the interactive menu. All features are accessible from here.

---

### `alms setup` — Setup
```
alms setup
alms setup --reconfigure credentials   # Update credentials only
alms setup --reconfigure schedule      # Update automation schedule only
```
Configures username, password, and settings on first run.
Re-running shows reconfiguration options.

---

### `alms sync` — Sync

<!-- ═══════════════════════════════════════════════════════════════
     PHOTO 2 — Sync progress bar screenshot
     Where to capture : while  alms sync  is running (████░░ bar visible)
     File             : assets/foto-2.png
     ═══════════════════════════════════════════════════════════════ -->
![Sync Progress](assets/foto-2.png)

```
alms sync                              # Download new files
alms sync --course FIZ108              # Single course
alms sync --courses FIZ108,MAT106      # Multiple courses
alms sync -f pdf                       # PDFs only
alms sync -f video                     # Videos only
alms sync --week 7                     # Week 7 only
alms sync --all                        # Re-download everything
alms sync --force                      # Same as --all
alms sync --quiet                      # Silent mode (for cron/scheduler)
alms sync -v                           # Verbose logs
```

**Filters can be combined:**
```bash
alms sync --course FIZ108 -f pdf --week 3
```

---

### `alms download` — File Picker
```
alms download
```
Opens the interactive file selection screen.

**Keyboard Shortcuts:**

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate |
| `SPACE` | Select / deselect |
| `G` | Select entire group |
| `A` | Select all |
| `N` | Clear selection |
| `F` | Filter (course code or filename) |
| `ESC` | Clear filter |
| `ENTER` | Confirm and download |
| `Q` | Cancel |

**File indicators:**

| Symbol | Meaning |
|--------|---------|
| `●` | Selected |
| `◉` | Already downloaded |
| `○` | Not selected |

---

### `alms list` — Course List
```
alms list
```
Shows enrolled courses and progress percentages.

---

### `alms today` — Daily Schedule
```
alms today
```
Shows today's and upcoming activities (assignments, exams).

---

### `alms status` — System Status
```
alms status
```
Displays:
- App version and build
- Whether an update is available
- ALMS token status (minutes remaining)
- Download folder and file count
- Automation schedule
- Network connectivity
- OBIS session status

---

### `alms open` — Open Folder
```
alms open
```
Opens the download folder in the system file manager.

---

### `alms stats` — Statistics
```
alms stats
```
Shows number of downloaded files and size per course.

---

### `alms log` — Activity Log
```
alms log
```
Shows the last 30 sync/download records.

---

### `alms export` — Export
```
alms export
```
Exports the course list and downloaded file index.
Format: Markdown or JSON.
Output: `~/ALMS/alms_index_DATE.md` or `.json`

---

### `alms obis` — OBIS Integration

<!-- ═══════════════════════════════════════════════════════════════
     PHOTO 3 — Exam schedule screenshot
     Where to capture : alms obis --sinav output (date + time list)
     File             : assets/foto-3.png
     ═══════════════════════════════════════════════════════════════ -->
![Exam Schedule](assets/foto-3.png)

```
alms obis --setup              # Set up OBIS session (done once)
alms obis --setup --force      # Force session refresh
alms obis --sinav              # View exam schedule
alms obis sinav                # Same
alms obis notlar               # View course grades
alms obis devamsizlik          # View attendance
```

**OBIS setup:**
1. Log into `obis.gelisim.edu.tr` in your browser
2. `F12` → `Storage` → `Cookies` → `obis.gelisim.edu.tr`
3. Copy the `ASP.NET_SessionId` value
4. Run `alms obis --setup` and paste it

Any of these token formats are accepted:
```
m1qijfitlaoatp0mddt2bmtd
ASP.NET_SessionId:"m1qijfitlaoatp0mddt2bmtd"
ASP.NET_SessionId=m1qijfitlaoatp0mddt2bmtd
```

Example exam schedule output:
```
📅  April 18, 2026  ← 17 days away
──────────────────────────────────────────────────────────────────────
  YZM102     BASIC PROGRAMMING II          MIDTERM  11:00

📅  April 20, 2026  ← 19 days away
──────────────────────────────────────────────────────────────────────
  MAT106     MATHEMATICS II                MIDTERM  17:00
```

---

### `alms update` — Update
```
alms update
```
Performs a safe update:
1. Backs up config files
2. `git pull origin main`
3. Updates dependencies
4. Saves version info
5. Refreshes automation schedule
6. Rolls back automatically on failure

---

### `alms --version` — Version Info
```
alms --version
```
Example output:
```
  ALMS Downloader v2.0.0 (build: ea4674a)
  Updated     : 2026-04-05
  Changes     : cross-platform fixes, auto-install
  Checking for updates...
  ✅ Up to date
```
If an update is available:
```
  ⬆️  3 updates available → v2.1.0 — run: alms update
```

---

### `alms logout` — Logout
```
alms logout
```
Securely deletes saved credentials and sessions.
Use when your ALMS password changes, then run `alms setup`.

---

### `alms config` — View Settings
```
alms config
```
Displays current settings in JSON format (sensitive values hidden).

---

## Automatic Downloads

Configure via menu option **[12] Auto-run**.

| Platform | Method | Log |
|----------|--------|-----|
| Linux | crontab | `~/.config/alms/cron.log` |
| macOS | launchd | `~/Library/Application Support/alms/cron.log` |
| Windows | Task Scheduler | `%APPDATA%\alms\cron.log` |

**Update check during automation:**
Every time the menu opens, updates are checked in the background.
If an update is available, you'll be prompted before the menu appears:
```
⬆️  3 updates available  v2.0.0 → v2.1.0
Update now? [Y/N]:
```

---

## File Structure

```
~/ALMS/                                      # Download folder
├── FIZ108/
│   ├── Hafta_01/
│   └── Hafta_07/
└── YZM102/

~/.config/alms/                              # Config (Linux)
~/Library/Application Support/alms/         # Config (macOS)
%APPDATA%\alms\                              # Config (Windows)
├── credentials.enc              # Encrypted credentials
├── config.json                  # Settings
├── manifest.json                # Download registry
├── version.json                 # Version info
├── obis_session                 # Encrypted OBIS token
├── alms.log                     # Application log
└── cron.log                     # Automation log
```

---

## Security

| Feature | Status |
|---------|--------|
| Credential encryption | AES-256 (Fernet), machine-specific |
| OBIS token encryption | AES-256 (Fernet) |
| SSL verification | Always enabled |
| Log sanitization | Tokens/passwords never written to logs |
| Config permissions | `chmod 700` (directory), `chmod 600` (files) |

---

## Troubleshooting

**`alms` command not found:**
```bash
# macOS (zsh)
source ~/.zprofile   # or open a new terminal

# Linux (bash)
source ~/.bashrc

# Linux (zsh)
source ~/.zshrc

# Windows
# Open a new CMD or PowerShell window
```

**macOS — `alms` runs but shows package errors (requests, cryptography):**
```bash
# The venv wrapper may be missing. Re-run setup:
./setup.sh
```

**macOS — lock file stuck after crash:**
```bash
rm ~/Library/Application\ Support/alms/.alms.lock 2>/dev/null
```

**OBIS session expired:**
```bash
alms obis --setup
```

**Token expired:**
```bash
alms logout
alms setup
```

**Update failed:**
```bash
# Manual update
cd /path/to/alms
git pull origin main
.venv/bin/python -m pip install -r requirements.txt
```

**Linux — missing dependency:**
```bash
.venv/bin/pip install -r requirements.txt
```

**Windows — missing dependency:**
```bat
.venv\Scripts\pip.exe install -r requirements.txt
```
