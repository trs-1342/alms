> 🇹🇷 [Türkçe](https://github.com/trs-1342/alms/blob/main/README.md) &nbsp;|&nbsp; 🇬🇧 **English**

---

# ALMS Downloader

One-command access to IGU (Istanbul Gelisim University) ALMS and OBIS systems.
Automatically downloads course materials and displays exam schedules.

<!-- ═══════════════════════════════════════════════════════════════
     PHOTO 1 — Main menu screenshot
     Where to capture : run  alms  in terminal (no arguments)
     File             : assets/foto-1.png
     ═══════════════════════════════════════════════════════════════ -->
![Main Menu](assets/foto-1.png)

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
alms                # Open menu
alms sync           # Download new files
alms download       # Pick files interactively
alms obis --sinav   # View exam schedule
alms update         # Install updates
alms --version      # Version + update check
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
| `alms export` | Export course index |
| `alms open` | Open download folder |
| `alms obis --setup` | Set up OBIS session |
| `alms obis --sinav` | Exam schedule |
| `alms obis notlar` | Course grades |
| `alms obis devamsizlik` | Attendance |
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

## Automatic Downloads

Configured from menu option **[12] Auto-run**.

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

MIT

## Developer

[My Web Site](https://hattab.vercel.app)
[GitHub](https://github.com/trs-1342)
