"""
utils/scheduler.py — Linux crontab ile otomatik çalıştırma
"""
import os
import platform
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


def _resolve_python() -> str:
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

# Cron satırlarını tanımlamak için sabit etiket
_CRON_TAG       = "# ALMS-SCHEDULER"
_REBOOT_TAG     = "# ALMS-REBOOT"
_NOTIFY_TAG     = "# ALMS-NOTIFY"

# Bildirim otomasyonu için sabitler
_NOTIFY_JOB_NAME = "ALMSNotifier"
_NOTIFY_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.alms.notifier.plist"


def _wrapper_script_path() -> Path:
    from utils.paths import CONFIG_DIR
    return CONFIG_DIR / "alms_cron.sh"


def _write_wrapper(courses: list[str] | None = None) -> Path:
    """
    Cron wrapper script'i yaz.
    - Başlangıç ve bitiş bildirimleri (DISPLAY/DBUS ile)
    - İlerleme yüzdesi log'a
    - Lock mekanizması
    """
    course_args = (f" --courses {shlex.quote(','.join(courses))}" if courses else "")
    from utils.paths import CONFIG_DIR
    log_file = CONFIG_DIR / "cron.log"
    home        = Path.home()

    script = f"""#!/bin/bash
# ALMS otomatik indirme — cron wrapper
# Oluşturuldu: scheduler.py tarafından

export HOME="{home}"
export PATH="/usr/local/bin:/usr/bin:/bin"

# Masaüstü bildirimi için DBUS/DISPLAY bul
find_display() {{
    for pid in $(pgrep -u "$USER" -x Xorg 2>/dev/null || pgrep -u "$USER" -x Xwayland 2>/dev/null); do
        local d=$(cat /proc/"$pid"/environ 2>/dev/null | tr '\\0' '\\n' | grep '^DISPLAY=' | cut -d= -f2)
        [ -n "$d" ] && echo "$d" && return
    done
    echo ":0"
}}

find_dbus() {{
    local uid=$(id -u)
    local bus="/run/user/$uid/bus"
    [ -S "$bus" ] && echo "unix:path=$bus" && return
    for pid in $(pgrep -u "$USER" dbus-daemon 2>/dev/null | head -1); do
        cat /proc/"$pid"/environ 2>/dev/null | tr '\\0' '\\n' | grep '^DBUS_SESSION_BUS_ADDRESS=' | cut -d= -f2- && return
    done
}}

send_notify() {{
    local title="$1"
    local msg="$2"
    local disp=$(find_display)
    local dbus=$(find_dbus)
    export DISPLAY="$disp"
    [ -n "$dbus" ] && export DBUS_SESSION_BUS_ADDRESS="$dbus"
    notify-send --app-name="ALMS" --urgency=normal "$title" "$msg" 2>/dev/null || true
}}

PYTHON="{PYTHON}"
SCRIPT="{SCRIPT}"
LOG="{log_file}"
LOCK="{home}/.config/alms/.cron.lock"

# Log 1MB'ı geçince eski logu arşivle
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 1048576 ]; then
    mv "$LOG" "$LOG.old"
fi

# Atomik lock (flock) — TOCTOU race condition önleme
exec 9>"$LOCK"
flock -n 9 || {{ echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [SKIP] Zaten çalışıyor" >> "$LOG"; exit 0; }}
echo $$ >&9
trap "rm -f '$LOCK'" EXIT

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [START] ALMS sync başlıyor{course_args}" >> "$LOG"

# Başlangıç bildirimi
send_notify "ALMS Sync Başladı" "Ders materyalleri indiriliyor...{course_args}"

# Sync çalıştır — çıktıyı geçici dosyaya al (yüzde hesabı için)
TMPOUT=$(mktemp)
"$PYTHON" "$SCRIPT" sync --quiet{course_args} 2>&1 | tee "$TMPOUT" >> "$LOG"
EXIT_CODE=${{PIPESTATUS[0]}}

# Sonuç özeti çıkar
OK_COUNT=$(grep -c "✅\\|indirildi" "$TMPOUT" 2>/dev/null || echo "0")
FAIL_COUNT=$(grep -c "❌\\|başarısız" "$TMPOUT" 2>/dev/null || echo "0")
rm -f "$TMPOUT"

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [OK] Sync tamamlandı" >> "$LOG"
    # Bitiş bildirimi
    if grep -q "indirildi" "$LOG" 2>/dev/null; then
        LAST_RESULT=$(tail -20 "$LOG" | grep "Sync tamamlandı" | tail -1 || echo "")
        send_notify "ALMS Sync Tamamlandı ✅" "İndirme başarıyla tamamlandı"
    else
        send_notify "ALMS Sync Tamamlandı" "Yeni dosya bulunamadı"
    fi
else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [ERROR] Sync başarısız (exit=$EXIT_CODE)" >> "$LOG"
    send_notify "ALMS Sync Başarısız ❌" "Hata oluştu, log: $LOG"
fi
"""
    path = _wrapper_script_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script)
    path.chmod(0o755)
    return path


# ─── Linux: cron servisi kontrolü ───────────────────────────
def _ensure_cron_running() -> None:
    if platform.system() != "Linux":
        return
    for svc in ("cronie", "cron", "crond"):
        result = subprocess.run(
            ["systemctl", "is-active", svc],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return
        check = subprocess.run(
            ["systemctl", "list-unit-files", f"{svc}.service"],
            capture_output=True, text=True,
        )
        if svc not in check.stdout:
            continue
        print(f"\n  ⚠️  {svc} servisi çalışmıyor. Başlatılıyor...")
        start = subprocess.run(["sudo", "systemctl", "start", svc], capture_output=True)
        subprocess.run(["sudo", "systemctl", "enable", svc], capture_output=True)
        if start.returncode == 0:
            print(f"  ✅ {svc} başlatıldı.")
        else:
            print(f"  ❌ Manuel: sudo systemctl start {svc}")
        return
    print("\n  ⚠️  Cron servisi bulunamadı.")
    print("     Arch/Manjaro : sudo pacman -S cronie && sudo systemctl enable --now cronie")


# ─── Linux: crontab ──────────────────────────────────────────
def _cron_entry(hour: int, minute: int, wrapper: Path) -> str:
    return f"{minute} {hour} * * * {wrapper} {_CRON_TAG}".rstrip() + "\n"


def _reboot_entry(wrapper: Path) -> str:
    return f"@reboot sleep 60 && {wrapper} {_REBOOT_TAG}\n"


def _get_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def cron_add(hour: int, minute: int, courses: list[str] | None = None) -> bool:
    wrapper = _write_wrapper(courses)

    current = _get_crontab()

    # Sadece ALMS etiketli satırları sil — kullanıcının @reboot'unu koru
    lines = [
        l for l in current.splitlines(keepends=True)
        if _CRON_TAG not in l and _REBOOT_TAG not in l
    ]

    # Saatli + @reboot ekle
    lines.append(_cron_entry(hour, minute, wrapper))
    lines.append(_reboot_entry(wrapper))

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
        if _CRON_TAG not in l and _REBOOT_TAG not in l
    ]
    new_cron = "".join(lines)
    with tempfile.NamedTemporaryFile("w", suffix=".cron", delete=False) as f:
        f.write(new_cron)
        tmp = f.name
    result = subprocess.run(["crontab", tmp])
    os.unlink(tmp)
    wp = _wrapper_script_path()
    if wp.exists():
        wp.unlink()
    return result.returncode == 0


def cron_status() -> str | None:
    for line in _get_crontab().splitlines():
        if _CRON_TAG in line:
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
        log=log_path, course_args=course_args,
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
def schtasks_add(hour: int, minute: int, courses: list[str] | None = None) -> bool:
    course_args = (f' --courses "{",".join(courses)}"' if courses else "")
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


# ─── Bildirim otomasyonu ─────────────────────────────────────────────────────

def _notify_wrapper_path() -> Path:
    from utils.paths import CONFIG_DIR
    return CONFIG_DIR / "alms_notify.sh"


def _write_notify_wrapper() -> Path:
    """Bildirim kontrol wrapper script'i yaz."""
    from utils.paths import CONFIG_DIR
    log_file = CONFIG_DIR / "notify.log"
    home     = Path.home()

    script = f"""#!/bin/bash
# ALMS bildirim kontrol — cron wrapper
# Oluşturuldu: scheduler.py tarafından

export HOME="{home}"
export PATH="/usr/local/bin:/usr/bin:/bin"

# Masaüstü bildirimi için DBUS/DISPLAY bul
find_display() {{
    for pid in $(pgrep -u "$USER" -x Xorg 2>/dev/null || pgrep -u "$USER" -x Xwayland 2>/dev/null); do
        local d=$(cat /proc/"$pid"/environ 2>/dev/null | tr '\\0' '\\n' | grep '^DISPLAY=' | cut -d= -f2)
        [ -n "$d" ] && echo "$d" && return
    done
    echo ":0"
}}

find_dbus() {{
    local uid=$(id -u)
    local bus="/run/user/$uid/bus"
    [ -S "$bus" ] && echo "unix:path=$bus" && return
    for pid in $(pgrep -u "$USER" dbus-daemon 2>/dev/null | head -1); do
        cat /proc/"$pid"/environ 2>/dev/null | tr '\\0' '\\n' | grep '^DBUS_SESSION_BUS_ADDRESS=' | cut -d= -f2- && return
    done
}}

PYTHON="{PYTHON}"
SCRIPT="{SCRIPT}"
LOG="{log_file}"
LOCK="{home}/.config/alms/.notify.lock"

# Atomik lock
exec 9>"$LOCK"
flock -n 9 || exit 0
echo $$ >&9
trap "rm -f '$LOCK'" EXIT

disp=$(find_display)
dbus=$(find_dbus)
export DISPLAY="$disp"
[ -n "$dbus" ] && export DBUS_SESSION_BUS_ADDRESS="$dbus"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [CHECK]" >> "$LOG"
"$PYTHON" "$SCRIPT" notify-check --quiet 2>&1 >> "$LOG"

# Log 512KB üzerindeyse eski logu arşivle
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 524288 ]; then
    mv "$LOG" "$LOG.old"
fi
"""
    path = _notify_wrapper_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script)
    path.chmod(0o755)
    return path


def _notify_cron_entry(interval_hours: int, wrapper: Path) -> list[str]:
    """Her N saatte bir çalışacak cron satırları."""
    if interval_hours <= 1:
        return [f"0 * * * * {wrapper} {_NOTIFY_TAG}\n"]
    return [f"0 */{interval_hours} * * * {wrapper} {_NOTIFY_TAG}\n"]


def notify_cron_add(interval_hours: int = 1) -> bool:
    wrapper  = _write_notify_wrapper()
    current  = _get_crontab()
    lines    = [l for l in current.splitlines(keepends=True) if _NOTIFY_TAG not in l]
    lines   += _notify_cron_entry(interval_hours, wrapper)
    new_cron = "".join(lines)
    with tempfile.NamedTemporaryFile("w", suffix=".cron", delete=False) as f:
        f.write(new_cron)
        tmp = f.name
    result = subprocess.run(["crontab", tmp])
    os.unlink(tmp)
    return result.returncode == 0


def notify_cron_remove() -> bool:
    current  = _get_crontab()
    lines    = [l for l in current.splitlines(keepends=True) if _NOTIFY_TAG not in l]
    new_cron = "".join(lines)
    with tempfile.NamedTemporaryFile("w", suffix=".cron", delete=False) as f:
        f.write(new_cron)
        tmp = f.name
    result = subprocess.run(["crontab", tmp])
    os.unlink(tmp)
    wp = _notify_wrapper_path()
    if wp.exists():
        wp.unlink()
    return result.returncode == 0


def notify_cron_status() -> str | None:
    for line in _get_crontab().splitlines():
        if _NOTIFY_TAG in line:
            return line.strip()
    return None


_NOTIFY_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.alms.notifier</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>{script}</string>
    <string>notify-check</string>
    <string>--quiet</string>
  </array>
  <key>StartInterval</key>
  <integer>{interval_secs}</integer>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


def notify_launchd_add(interval_hours: int, log_path: str) -> bool:
    plist = _NOTIFY_PLIST_TEMPLATE.format(
        python=PYTHON, script=SCRIPT,
        interval_secs=interval_hours * 3600,
        log=log_path,
    )
    _NOTIFY_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _NOTIFY_PLIST_PATH.write_text(plist)
    subprocess.run(["launchctl", "unload", str(_NOTIFY_PLIST_PATH)], capture_output=True)
    result = subprocess.run(["launchctl", "load", str(_NOTIFY_PLIST_PATH)])
    return result.returncode == 0


def notify_launchd_remove() -> bool:
    if _NOTIFY_PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(_NOTIFY_PLIST_PATH)], capture_output=True)
        _NOTIFY_PLIST_PATH.unlink()
    return True


def notify_launchd_status() -> str | None:
    return str(_NOTIFY_PLIST_PATH) if _NOTIFY_PLIST_PATH.exists() else None


def notify_schtasks_add(interval_hours: int) -> bool:
    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", _NOTIFY_JOB_NAME,
        "/TR", f'"{PYTHON}" "{SCRIPT}" notify-check --quiet',
        "/SC", "HOURLY",
        "/MO", str(interval_hours),
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def notify_schtasks_remove() -> bool:
    result = subprocess.run(
        ["schtasks", "/Delete", "/F", "/TN", _NOTIFY_JOB_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def notify_schtasks_status() -> str | None:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", _NOTIFY_JOB_NAME, "/FO", "LIST"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "Next Run" in line or "Sonraki" in line:
                return line.strip()
    return None


def add_notify_schedule(interval_hours: int = 1, log_path: str = "") -> bool:
    system = platform.system()
    if system == "Linux":
        _ensure_cron_running()
        return notify_cron_add(interval_hours)
    elif system == "Darwin":
        from utils.paths import CONFIG_DIR
        lp = log_path or str(CONFIG_DIR / "notify.log")
        return notify_launchd_add(interval_hours, lp)
    elif system == "Windows":
        return notify_schtasks_add(interval_hours)
    return False


def remove_notify_schedule() -> bool:
    system = platform.system()
    if system == "Linux":
        return notify_cron_remove()
    elif system == "Darwin":
        return notify_launchd_remove()
    elif system == "Windows":
        return notify_schtasks_remove()
    return False


def get_notify_schedule_status() -> str | None:
    system = platform.system()
    if system == "Linux":
        return notify_cron_status()
    elif system == "Darwin":
        return notify_launchd_status()
    elif system == "Windows":
        return notify_schtasks_status()
    return None
