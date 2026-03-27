"""
utils/scheduler.py — OS-native otomatik çalıştırma
Linux  : crontab
macOS  : launchd (.plist)
Windows: schtasks
"""
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


PYTHON = sys.executable
SCRIPT = str(Path(__file__).parent.parent / "alms.py")
JOB_NAME = "ALMSScraper"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.alms.scraper.plist"


# ─── Linux: crontab ──────────────────────────────────────────
def _cron_entry(hour: int, minute: int) -> str:
    return f"{minute} {hour} * * * {PYTHON} {SCRIPT} sync --quiet\n"


def _get_crontab() -> str:
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else ""


def cron_add(hour: int, minute: int) -> bool:
    entry = _cron_entry(hour, minute)
    current = _get_crontab()
    # Önce eski ALMS satırlarını temizle
    lines = [l for l in current.splitlines(keepends=True)
             if "alms.py" not in l]
    lines.append(entry)
    new_cron = "".join(lines)
    with tempfile.NamedTemporaryFile("w", suffix=".cron", delete=False) as f:
        f.write(new_cron)
        tmp = f.name
    result = subprocess.run(["crontab", tmp])
    os.unlink(tmp)
    return result.returncode == 0


def cron_remove() -> bool:
    current = _get_crontab()
    lines = [l for l in current.splitlines(keepends=True)
             if "alms.py" not in l]
    new_cron = "".join(lines)
    with tempfile.NamedTemporaryFile("w", suffix=".cron", delete=False) as f:
        f.write(new_cron)
        tmp = f.name
    result = subprocess.run(["crontab", tmp])
    os.unlink(tmp)
    return result.returncode == 0


def cron_status() -> str | None:
    """Aktif ALMS cron satırını döndürür, yoksa None."""
    for line in _get_crontab().splitlines():
        if "alms.py" in line:
            return line.strip()
    return None


# ─── macOS: launchd ──────────────────────────────────────────
PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.alms.scraper</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>{script}</string>
    <string>sync</string>
    <string>--quiet</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>{hour}</integer>
    <key>Minute</key>
    <integer>{minute}</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


def launchd_add(hour: int, minute: int, log_path: str) -> bool:
    from utils.paths import CONFIG_DIR
    plist = PLIST_TEMPLATE.format(
        python=PYTHON, script=SCRIPT,
        hour=hour, minute=minute,
        log=log_path,
    )
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist)
    # unload önce (hata yok sayılır), sonra load
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                   capture_output=True)
    result = subprocess.run(["launchctl", "load", str(PLIST_PATH)])
    return result.returncode == 0


def launchd_remove() -> bool:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                       capture_output=True)
        PLIST_PATH.unlink()
    return True


def launchd_status() -> str | None:
    if PLIST_PATH.exists():
        return str(PLIST_PATH)
    return None


# ─── Windows: schtasks ───────────────────────────────────────
def schtasks_add(hour: int, minute: int) -> bool:
    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", JOB_NAME,
        "/TR", f'"{PYTHON}" "{SCRIPT}" sync --quiet',
        "/SC", "DAILY",
        "/ST", f"{hour:02d}:{minute:02d}",
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def schtasks_remove() -> bool:
    result = subprocess.run(
        ["schtasks", "/Delete", "/F", "/TN", JOB_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def schtasks_status() -> str | None:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", JOB_NAME, "/FO", "LIST"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "Next Run" in line or "Sonraki" in line:
                return line.strip()
    return None


# ─── Dispatcher ──────────────────────────────────────────────
def add_schedule(hour: int, minute: int, log_path: str) -> bool:
    system = platform.system()
    if system == "Linux":
        return cron_add(hour, minute)
    elif system == "Darwin":
        return launchd_add(hour, minute, log_path)
    elif system == "Windows":
        return schtasks_add(hour, minute)
    return False


def remove_schedule() -> bool:
    system = platform.system()
    if system == "Linux":
        return cron_remove()
    elif system == "Darwin":
        return launchd_remove()
    elif system == "Windows":
        return schtasks_remove()
    return False


def get_schedule_status() -> str | None:
    system = platform.system()
    if system == "Linux":
        return cron_status()
    elif system == "Darwin":
        return launchd_status()
    elif system == "Windows":
        return schtasks_status()
    return None
