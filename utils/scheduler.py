"""
utils/scheduler.py — Linux crontab ile otomatik çalıştırma
"""
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


def _resolve_python() -> str:
    """
    .venv Python'unu bul — yoksa sys.executable kullan.
    Menüden değil, dosya sistemi üzerinden bulur (cron için güvenli).
    """
    script_dir = Path(__file__).parent.parent
    for candidate in [
        script_dir / ".venv" / "bin" / "python",
        script_dir / ".venv" / "bin" / "python3",
        script_dir / "venv"  / "bin" / "python",
        script_dir / "venv"  / "bin" / "python3",
    ]:
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return sys.executable


PYTHON   = _resolve_python()
SCRIPT   = str(Path(__file__).parent.parent / "alms.py")
WORK_DIR = str(Path(__file__).parent.parent)
JOB_NAME = "ALMSScraper"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.alms.scraper.plist"


def _wrapper_script_path() -> Path:
    """Cron için shell wrapper script yolu."""
    from utils.paths import CONFIG_DIR
    return CONFIG_DIR / "alms_cron.sh"


def _write_wrapper(courses: list[str] | None = None) -> Path:
    """
    Cron'dan çağrılacak shell wrapper yaz.
    Shell script yaklaşımı: ortam değişkenleri, hata yakalama, log — hepsi net.
    """
    course_args = f" --courses {','.join(courses)}" if courses else ""
    log_file    = Path.home() / ".config" / "alms" / "cron.log"

    script = f"""#!/bin/bash
# ALMS otomatik indirme — cron wrapper
# Oluşturuldu: scheduler.py tarafından

export HOME="{Path.home()}"
export PATH="/usr/local/bin:/usr/bin:/bin"

PYTHON="{PYTHON}"
SCRIPT="{SCRIPT}"
LOG="{log_file}"
LOCK="{Path.home()}/.config/alms/.cron.lock"

# Zaten çalışıyor mu?
if [ -f "$LOCK" ]; then
    PID=$(cat "$LOCK" 2>/dev/null)
    if kill -0 "$PID" 2>/dev/null; then
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [SKIP] Zaten çalışıyor (PID=$PID)" >> "$LOG"
        exit 0
    fi
fi

# Lock al
echo $$ > "$LOCK"
trap "rm -f '$LOCK'" EXIT

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [START] ALMS sync başlıyor{course_args}" >> "$LOG"

"$PYTHON" "$SCRIPT" sync --quiet{course_args} >> "$LOG" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [OK] Sync tamamlandı" >> "$LOG"
else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [ERROR] Sync başarısız (exit=$EXIT_CODE)" >> "$LOG"
fi
"""
    path = _wrapper_script_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script)
    path.chmod(0o755)
    return path


# ─── Linux: cron servisi kontrolü ───────────────────────────
def _ensure_cron_running() -> None:
    """
    Linux'ta cronie/cron servisinin çalıştığından emin ol.
    Çalışmıyorsa başlatmayı dener, kullanıcıyı bilgilendirir.
    """
    if platform.system() != "Linux":
        return

    for svc in ("cronie", "cron", "crond"):
        result = subprocess.run(
            ["systemctl", "is-active", svc],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return  # Zaten çalışıyor

        # Servis var mı?
        check = subprocess.run(
            ["systemctl", "list-unit-files", f"{svc}.service"],
            capture_output=True, text=True,
        )
        if svc not in check.stdout:
            continue

        # Var ama çalışmıyor — başlat
        print(f"\n  ⚠️  {svc} servisi çalışmıyor. Başlatılıyor...")
        start = subprocess.run(
            ["sudo", "systemctl", "start", svc],
            capture_output=True,
        )
        enable = subprocess.run(
            ["sudo", "systemctl", "enable", svc],
            capture_output=True,
        )
        if start.returncode == 0:
            print(f"  ✅ {svc} başlatıldı ve otomatik başlangıca eklendi.")
        else:
            print(f"  ❌ {svc} başlatılamadı. Manuel çalıştır:")
            print(f"     sudo systemctl start {svc}")
            print(f"     sudo systemctl enable {svc}")
        return

    # Hiç cron servisi bulunamadı
    print("\n  ⚠️  Cron servisi bulunamadı.")
    print("     Arch/Manjaro : sudo pacman -S cronie && sudo systemctl enable --now cronie")
    print("     Ubuntu/Debian: sudo apt install cron")
    print("     Fedora       : sudo dnf install cronie && sudo systemctl enable --now cronie")



def _cron_entry(hour: int, minute: int, wrapper: Path) -> str:
    return f"{minute} {hour} * * * {wrapper}\n"


def _get_crontab() -> str:
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else ""


def cron_add(hour: int, minute: int, courses: list[str] | None = None) -> bool:
    wrapper = _write_wrapper(courses)
    entry   = _cron_entry(hour, minute, wrapper)
    current = _get_crontab()

    # Eski ALMS satırlarını temizle (wrapper path veya eski alms.py yolu)
    lines = [
        l for l in current.splitlines(keepends=True)
        if "alms" not in l.lower()
    ]
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
    lines = [
        l for l in current.splitlines(keepends=True)
        if "alms" not in l.lower()
    ]
    new_cron = "".join(lines)
    with tempfile.NamedTemporaryFile("w", suffix=".cron", delete=False) as f:
        f.write(new_cron)
        tmp = f.name
    result = subprocess.run(["crontab", tmp])
    os.unlink(tmp)

    # Wrapper script de sil
    wp = _wrapper_script_path()
    if wp.exists():
        wp.unlink()

    return result.returncode == 0


def cron_status() -> str | None:
    for line in _get_crontab().splitlines():
        if "alms" in line.lower():
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
    <string>--quiet</string>{course_args}
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


def launchd_add(hour: int, minute: int, log_path: str,
                courses: list[str] | None = None) -> bool:
    course_args = ""
    if courses:
        course_args = "".join(
            f"\n    <string>--courses</string>\n    <string>{','.join(courses)}</string>"
        )
    plist = PLIST_TEMPLATE.format(
        python=PYTHON, script=SCRIPT,
        hour=hour, minute=minute,
        log=log_path,
        course_args=course_args,
    )
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist)
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    result = subprocess.run(["launchctl", "load", str(PLIST_PATH)])
    return result.returncode == 0


def launchd_remove() -> bool:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink()
    return True


def launchd_status() -> str | None:
    if PLIST_PATH.exists():
        return str(PLIST_PATH)
    return None


# ─── Windows: schtasks ───────────────────────────────────────
def schtasks_add(hour: int, minute: int,
                 courses: list[str] | None = None) -> bool:
    course_args = f" --courses {','.join(courses)}" if courses else ""
    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", JOB_NAME,
        "/TR", f'"{PYTHON}" "{SCRIPT}" sync --quiet{course_args}',
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
def add_schedule(hour: int, minute: int, log_path: str,
                 courses: list[str] | None = None) -> bool:
    system = platform.system()
    if system == "Linux":
        return cron_add(hour, minute, courses)
    elif system == "Darwin":
        return launchd_add(hour, minute, log_path, courses)
    elif system == "Windows":
        return schtasks_add(hour, minute, courses)
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
