> 🇹🇷 [Türkçe](https://github.com/trs-1342/alms/blob/main/README.md) &nbsp;|&nbsp; 🇬🇧 **English**

---

# ALMS Downloader

One-command access to IGU (Istanbul Gelisim University) ALMS and OBIS systems.
Automatically downloads course materials, displays exam schedules, and supports offline mode.

<!-- ═══════════════════════════════════════════════════════════════
     PHOTO 1 — Main menu screenshot
     Where to capture : run  alms  in terminal (no arguments)
     File             : assets/foto-1-en.png
     ═══════════════════════════════════════════════════════════════ -->
![Main Menu](assets/foto-1-en.png)

---

```
~/ALMS/
├── FIZ108/
│   ├── Hafta_01/  →  fizik_2_1_hafta.pdf
│   └── Hafta_07/  →  Fizik_2_Bolum_6.pdf
├── YZM102/
│   └── Hafta_04/  →  Pointers2.pdf
└── MAT106/
    └── Hafta_03/  →  mat_3_hafta.pdf
```

---

## Installation

### macOS

```bash
git clone https://github.com/trs-1342/alms
cd alms
chmod +x setup.sh && ./setup.sh
alms setup
```

> `setup.sh` automatically installs missing tools:
> - **Homebrew** if missing → installed automatically
> - **Python 3.10+** if missing → `brew install python3`
> - **git** if missing → `brew install git`
>
> No administrator password required (Homebrew runs at user level).

### Linux

```bash
git clone https://github.com/trs-1342/alms
cd alms
chmod +x setup.sh && ./setup.sh
alms setup
```

> `setup.sh` automatically installs missing tools (sudo required):
> - **Python 3.10+** if missing → installed via `pacman`/`apt`/`dnf`
> - **git** if missing → installed via package manager
> - **cronie/cron** if missing → installed and started for automation
>
> Enter your sudo password when prompted; press `Ctrl+C` then `Enter` to skip.

### Windows

```bat
git clone https://github.com/trs-1342/alms
cd alms
setup.bat
alms setup
```

> `setup.bat` automatically installs missing tools:
> - **Python 3.10+** if missing → `winget install Python.Python.3.12`
>
> **Administrator privileges are required for Task Scheduler (auto-download).**
> Right-click → "Run as administrator".

### Windows — Portable (Lab / No admin rights)

For environments where **administrator password is required** (e.g. university lab computers):

```bat
git clone https://github.com/trs-1342/alms
cd alms
setup_portable.bat
alms.bat setup
```

> - Downloads Python into the project folder (`portable\python\`) — no system-wide installation
> - No administrator privileges required at any step
> - Internet connection needed (~15 MB download)
> - If you move the folder, re-run `setup_portable.bat`

---

### Manual Installation

Use these steps if the automated setup fails.

#### macOS — Manual

```bash
# 1. Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Apple Silicon (M1/M2/M3) PATH setup:
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# 2. Install tools
brew install python3 git

# 3. Clone the project
git clone https://github.com/trs-1342/alms
cd alms

# 4. Virtual environment and packages
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt

# 5. Create alms command
mkdir -p ~/.local/bin
echo '#!/usr/bin/env bash' > ~/.local/bin/alms
echo "exec \"$(pwd)/.venv/bin/python\" \"$(pwd)/alms.py\" \"\$@\"" >> ~/.local/bin/alms
chmod +x ~/.local/bin/alms

# 6. Add to PATH (zsh)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile

# 7. First-time setup
alms setup
```

#### Linux — Manual

```bash
# 1. Install tools (Arch example; adapt for apt/dnf)
sudo pacman -S python git cronie
sudo systemctl enable --now cronie

# 2. Clone the project
git clone https://github.com/trs-1342/alms
cd alms

# 3. Virtual environment and packages
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create alms command
mkdir -p ~/.local/bin
echo '#!/usr/bin/env bash' > ~/.local/bin/alms
echo "exec \"$(pwd)/.venv/bin/python\" \"$(pwd)/alms.py\" \"\$@\"" >> ~/.local/bin/alms
chmod +x ~/.local/bin/alms

# 5. PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 6. First-time setup
alms setup
```

#### Windows — Manual

```bat
:: 1. Install Python (winget)
winget install Python.Python.3.12 --accept-package-agreements

:: 2. Install Git (if missing)
winget install Git.Git --accept-package-agreements

:: Open a new terminal, then:

:: 3. Clone the project
git clone https://github.com/trs-1342/alms
cd alms

:: 4. Virtual environment and packages
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\pip.exe install -r requirements.txt

:: 5. Create alms.bat
echo @echo off > alms.bat
echo "%CD%\.venv\Scripts\python.exe" "%CD%\alms.py" %%* >> alms.bat

:: 6. First-time setup
alms.bat setup
```

---

## Basic Usage

```bash
alms                        # Open menu
alms sync                   # Download new files
alms download               # Pick files interactively
alms obis --sinav           # View exam schedule
alms konular                # View exam topics (community)
alms cache --guncelle       # Save OBIS data for offline use
alms notify-check           # Check for new announcements/exams/topics
alms update                 # Install updates
alms --version              # Version + update check
```

Full usage guide: **[USAGE.md](https://github.com/trs-1342/alms/blob/main/KULLANIM.en.md)**

---

## Command Reference

| Command | Description |
|---------|-------------|
| `alms` | Interactive menu |
| `alms setup` | First-time setup |
| `alms sync` | Download new files |
| `alms sync --courses FIZ108,MAT106` | Download specific courses |
| `alms sync -f pdf` | PDFs only |
| `alms sync --quiet` | Silent mode (automation) |
| `alms download` | File picker |
| `alms list` | List enrolled courses |
| `alms today` | Upcoming activities |
| `alms status` | System status |
| `alms stats` | Statistics |
| `alms log` | Activity log |
| `alms export` | Export course index + OBIS data |
| `alms open` | Open download folder |
| `alms obis --setup` | Set up OBIS session |
| `alms obis sinav` | Exam schedule |
| `alms obis notlar` | Course grades (assignments/midterm/final/letter) |
| `alms obis transkript` | Transcript + semester GPA and cumulative GPA |
| `alms obis program` | Weekly course schedule |
| `alms obis devamsizlik` | Attendance status |
| `alms obis duyurular` | OBIS announcements (full content) |
| `alms takvim` | ALMS activity timeline |
| `alms konular` | List exam topics |
| `alms konular --ekle` | Add a new exam topic |
| `alms konular --oyla <id>` | Vote on a topic |
| `alms cache` | Offline cache status |
| `alms cache --guncelle` | Fetch and cache all OBIS data |
| `alms cache --temizle` | Clear the cache |
| `alms notify-check` | Check for new announcements/exams/topics |
| `alms notify-check --quiet` | Silent check (for automation) |
| `alms update` | Install updates |
| `alms --version` | Version info |
| `alms logout` | Delete saved credentials |

---

## OBIS Setup

Done **once** after logging into OBIS in your browser:

```bash
alms obis --setup
# F12 → Storage → Cookies → copy the ASP.NET_SessionId value and paste it
```

The session token remains valid until you log out.

---

## Offline Mode

Access OBIS data without an internet connection (exam day, off-campus, etc.):

```bash
# While connected, save data locally
alms cache --guncelle

# When offline, view cached data
alms obis sinav          # shows from cache
alms obis devamsizlik    # shows from cache
alms obis program        # shows from cache
alms obis notlar         # shows from cache
alms obis transkript     # shows from cache
```

What gets cached:
- Exam schedule
- Course grades (assignments/midterm/final/letter)
- Transcript & GPA
- Weekly course schedule
- Attendance status
- Announcements

> Cache is stored as JSON in `~/.config/alms/cache/`.
> Each command automatically refreshes the cache when connected.

---

## Exam Topics (Community)

<!-- ═══════════════════════════════════════════════════════════════
     PHOTO 4 — Exam topics list
     Where to capture : alms konular  (with a few topics entered)
     File             : assets/foto-4-en.png
     ═══════════════════════════════════════════════════════════════ -->
![Exam Topics](assets/foto-4-en.png)

Community-shared exam topics via Firebase. No extra setup needed — Firebase connects automatically once `alms setup` is done.

```bash
alms konular                    # List all topics
alms konular --ekle             # Add a new topic
alms konular --vize             # Midterm topics only
alms konular --final            # Final topics only
alms konular --ders FIZ108      # Topics for a specific course
alms konular --oyla <id>        # Vote correct / incorrect on a topic
```

- Each student can add one topic per 30 minutes (spam protection)
- Student numbers are never stored in plain text (SHA-256 hash)
- Votes are immutable; trust score indicates reliability

---

## Notification Automation

Sends a desktop notification when new announcements, exams, or exam topics are added.
Runs as a **separate** scheduler from the file download automation.

```bash
alms notify-check           # Manual check (shows new items if any)
alms notify-check --quiet   # Silent check — sends notification only
```

Configure automatic scheduling via menu **Settings → Notification Automation**:
- Choose check frequency (e.g. every 1 hour)
- Linux: crontab, macOS: launchd, Windows: Task Scheduler

---

## Automatic Downloads

Configure via menu **Settings → Auto Run**.

| Platform | Method | Log |
|----------|--------|-----|
| Linux | crontab | `~/.config/alms/cron.log` |
| macOS | launchd | `~/Library/Application Support/alms/cron.log` |
| Windows | Task Scheduler | `%APPDATA%\alms\cron.log` |

---

## Security

- Credentials encrypted with **AES-256**, machine-specific key
- OBIS token stored encrypted
- SSL verification always enabled
- Tokens and passwords are never written to logs
- Firebase: student number stored as SHA-256 hash, never in plain text

---

## Update System

```bash
alms update
```

- Config files are backed up first
- `git pull` + dependency update
- Automatic rollback on failure
- Update notification shown on menu launch

Version is determined from git tags (`v2.0`) or commit count.

---

## Dependencies

```
requests>=2.31.0,<3.0.0
cryptography>=42.0.0,<45.0.0
beautifulsoup4>=4.12.0,<5.0.0
```

Installed automatically by `setup.sh` / `setup.bat`.

---

## License

Source-Available License (Custom License)

⚠️ This is NOT an open-source project.
Its use for security purposes without explicit permission is strictly prohibited.

## Developer

[My Web Site](https://hattab.vercel.app) <br/>
[GitHub](https://github.com/trs-1342)
