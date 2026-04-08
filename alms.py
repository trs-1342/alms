#!/usr/bin/env python3
"""
alms.py — ALMS İndirici Ana Giriş Noktası
──────────────────────────────────────────

── Temel Komutlar ──────────────────────────────────────
  alms                            → interaktif menü
  alms setup                      → ilk kurulum sihirbazı
  alms sync                       → yeni dosyaları indir
  alms sync --quiet               → sessiz mod (cron/otomasyon)
  alms sync --course FIZ108       → tek ders indir
  alms sync --courses FIZ108,MAT106  → birden fazla ders
  alms sync -f pdf                → sadece PDF
  alms sync -f video              → sadece video
  alms sync --week 7              → sadece 7. hafta
  alms sync --all / --force       → tümünü yeniden indir
  alms list                       → ders listesi
  alms download                   → interaktif dosya seçici
  alms today                      → yaklaşan aktiviteler
  alms open                       → indirme klasörünü aç
  alms status                     → sistem durumu + sürüm
  alms stats                      → indirme istatistikleri
  alms log                        → aktivite logu
  alms export                     → ders indexini dışa aktar

── OBİS / LMS Komutları ────────────────────────────────
  alms obis --setup               → OBİS oturum kurulumu
  alms obis --setup --force       → oturumu zorla yenile
  alms obis sinav                 → sınav tarihleri (varsayılan)
  alms obis notlar                → ders notları (ödev/vize/final/harf)
  alms obis transkript            → transkript + ANO/GANO
  alms obis program               → haftalık ders programı
  alms obis devamsizlik           → devamsızlık durumu
  alms obis duyurular             → OBİS + LMS duyurular
  alms takvim                     → LMS zaman çizelgesi (ödev/sınav)
  alms duyurular                  → kısayol: duyurular ekranı
  alms transkript                 → kısayol: transkript ekranı
  alms program                    → kısayol: ders programı ekranı
  alms devamsizlik                → kısayol: devamsızlık durumu
  alms notlar                     → kısayol: ders notları
  alms sinav                      → kısayol: sınav tarihleri

── Sınav Konuları (Firebase) ───────────────────────────────
  alms konular                    → sınav konularını listele
  alms konular --ekle             → yeni konu gir
  alms konular --vize             → sadece vize konuları
  alms konular --final            → sadece final konuları
  alms konular --ders FIZ108      → belirli ders konuları
  alms konular --setup            → Firebase bağlantısını kur

── Çevrimdışı Önbellek ──────────────────────────────────
  alms cache                      → önbellek durumunu göster
  alms cache --guncelle           → tüm OBİS verilerini çek ve önbelleğe kaydet
  alms cache --temizle            → önbelleği temizle

── Bildirim Otomasyonu ─────────────────────────────────
  alms notify-check               → yeni duyuru/sınav/konu durumunu göster
  alms notify-check --quiet       → sessiz kontrol (cron için)

── Güncelleme & Sistem ─────────────────────────────────
  alms update                     → güncelleme yükle
  alms --version                  → sürüm + güncelleme kontrolü
  alms logout                     → kimlik bilgilerini sil
  alms config                     → mevcut ayarları göster
  alms --help / -h                → bu yardım

── Filtreler ────────────────────────────────────────────
  -v / --verbose                  → ayrıntılı log
  -q / --quiet                    → sadece hata (cron için)
  -f {pdf,video}                  → dosya tipi filtresi
  --course KOD                    → ders kodu filtresi
  --courses KOD1,KOD2             → çoklu ders filtresi
  --week N                        → hafta filtresi
  --all / --force                 → tümünü yeniden indir

── OBİS Kurulum Notu ────────────────────────────────────
  1. obis.gelisim.edu.tr adresine tarayıcıda giriş yap
  2. F12 → Storage → Cookies → ASP.NET_SessionId kopyala
  3. alms obis --setup komutu ile yapıştır
"""

import argparse
import atexit
import logging
import os
import platform
import sys
from pathlib import Path

# Proje kökünü sys.path'e ekle
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.paths import CONFIG_DIR, LOG_FILE, LOCK_FILE, ensure_secure_dir
from utils.integrity import sanitize_log


# ─── Lock dosyası (tek instance) ─────────────────────────────
_lock_fd = None


def _acquire_lock() -> bool:
    global _lock_fd
    ensure_secure_dir(CONFIG_DIR)

    if platform.system() == "Windows":
        if LOCK_FILE.exists():
            try:
                pid = int(LOCK_FILE.read_text().strip())
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                if h:
                    ctypes.windll.kernel32.CloseHandle(h)
                    return False
            except Exception:
                pass
        LOCK_FILE.write_text(str(os.getpid()))
        return True
    else:
        import fcntl
        if LOCK_FILE.exists():
            try:
                old_pid = int(LOCK_FILE.read_text().strip())
                if not Path(f"/proc/{old_pid}").exists():
                    LOCK_FILE.unlink(missing_ok=True)
            except Exception:
                LOCK_FILE.unlink(missing_ok=True)
        try:
            _lock_fd = open(LOCK_FILE, "w")
            fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_fd.write(str(os.getpid()))
            _lock_fd.flush()
            return True
        except OSError:
            return False


def _release_lock():
    global _lock_fd
    if platform.system() != "Windows":
        if _lock_fd:
            try:
                import fcntl
                fcntl.flock(_lock_fd, fcntl.LOCK_UN)
                _lock_fd.close()
            except Exception:
                pass
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass


def _signal_handler(signum, frame):
    """SIGTERM/SIGHUP alındığında lock'ı temizle ve çık."""
    _release_lock()
    sys.exit(0)


atexit.register(_release_lock)

# Signal handler — lock'u temizle (crash, kill, Ctrl+C)
import signal as _signal

def _signal_handler(signum, frame):
    _release_lock()
    sys.exit(0)

_signal.signal(_signal.SIGTERM, _signal_handler)
# SIGINT (Ctrl+C) zaten KeyboardInterrupt ile yakalanıyor
try:
    _signal.signal(_signal.SIGHUP, _signal_handler)   # terminal kapandığında
except AttributeError:
    pass  # Windows'ta SIGHUP yok

# Signal handler'ları kaydet — crash ve kill sonrası lock temizlenir
try:
    import signal
    signal.signal(signal.SIGTERM, _signal_handler)
    if hasattr(signal, "SIGHUP"):        # Windows'ta yok
        signal.signal(signal.SIGHUP, _signal_handler)
except Exception:
    pass


# ─── Logging ─────────────────────────────────────────────────
class _SanitizingFilter(logging.Filter):
    def filter(self, record):
        record.msg = sanitize_log(str(record.msg))
        return True


def setup_logging(verbose: bool = False, quiet: bool = False):
    from logging.handlers import TimedRotatingFileHandler
    ensure_secure_dir(CONFIG_DIR)
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    fmt   = "%(asctime)s [%(levelname)s] %(message)s"

    file_handler = TimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1,
        backupCount=7, encoding="utf-8", utc=True,
    )
    file_handler.setFormatter(logging.Formatter(fmt))

    handlers: list[logging.Handler] = [file_handler]
    if not quiet:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(logging.Formatter(fmt))
        handlers.append(stream)

    logging.basicConfig(level=level, format=fmt, handlers=handlers)

    sanitizer = _SanitizingFilter()
    for h in logging.root.handlers:
        h.addFilter(sanitizer)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


# ─── CLI ─────────────────────────────────────────────────────

# Komut takma adları — hem TR hem EN çalışır
_CMD_ALIASES: dict[str, str] = {
    # TR → kanonik
    "senkronize":   "sync",
    "indir":        "download",
    "listele":      "list",
    "bugun":        "today",
    "bugün":        "today",
    "ac":           "open",
    "aç":           "open",
    "durum":        "status",
    "istatistik":   "stats",
    "istatistikler": "stats",
    "guncelle":     "update",
    "güncelle":     "update",
    "kur":          "setup",
    "cikis":        "logout",
    "çıkış":        "logout",
    "ayarlar-goster": "config",
    # EN → kanonik
    "synchronize":    "sync",
    "download-files": "download",
    "courses":        "list",
    "schedule":       "program",
    "absence":        "devamsizlik",
    "attendance":     "devamsizlik",
    "grades":         "notlar",
    "notes":          "notlar",
    "exam":           "sinav",
    "exams":          "sinav",
    "transcript":     "transkript",
    "announcements":  "duyurular",
    "calendar":       "takvim",
    "topics":         "konular",
    "update-check":   "update",
    "quit":           "logout",
    # cache aliases
    "onbellek":       "cache",
    "önbellek":       "cache",
    "cevrimdisi":     "cache",
    "çevrimdışı":     "cache",
    "offline":        "cache",
    # notify aliases
    "notify":         "notify-check",
    "bildir":         "notify-check",
    "bildirim":       "notify-check",
    "bildirim-kontrol": "notify-check",
}

_CANONICAL_COMMANDS = frozenset([
    "menu", "setup", "sync", "list", "download", "today", "open",
    "status", "stats", "log", "export", "logout", "config", "obis",
    "update", "transkript", "program", "duyurular", "takvim",
    "devamsizlik", "notlar", "sinav", "konular", "cache", "notify-check",
])


def _suggest_commands(cmd: str) -> list[str]:
    """Girilen komut adına benzer kanonik komutları öner."""
    cmd_l = cmd.lower()
    # Önce alias listesinde tam eşleşme
    if cmd_l in _CMD_ALIASES:
        return [_CMD_ALIASES[cmd_l]]
    # Prefix veya substring eşleşmesi
    hits = []
    for c in sorted(_CANONICAL_COMMANDS):
        if c.startswith(cmd_l[:3]) or cmd_l in c or c in cmd_l:
            hits.append(c)
    return hits[:4]


class _BilingualParser(argparse.ArgumentParser):
    """Bilinmeyen komut / flag hatalarını TR/EN olarak göster."""

    def error(self, message: str):  # type: ignore[override]
        lang = "tr"
        try:
            from core.config import get as _cfg
            lang = _cfg("language") or "tr"
        except Exception:
            pass

        # Bilinmeyen komut mu?
        cmd_given = None
        for arg in sys.argv[1:]:
            if not arg.startswith("-"):
                cmd_given = arg
                break

        if cmd_given and cmd_given not in _CANONICAL_COMMANDS and cmd_given not in _CMD_ALIASES:
            suggestions = _suggest_commands(cmd_given)
            if lang == "tr":
                print(f"\n  ❌ Bilinmeyen komut: '{cmd_given}'")
                if suggestions:
                    print(f"  💡 Bunu mu demek istediniz?\n")
                    for s in suggestions:
                        print(f"       alms {s}")
                print(f"\n  Kullanılabilir komutlar: alms --help\n")
            else:
                print(f"\n  ❌ Unknown command: '{cmd_given}'")
                if suggestions:
                    print(f"  💡 Did you mean?\n")
                    for s in suggestions:
                        print(f"       alms {s}")
                print(f"\n  Available commands: alms --help\n")
        else:
            # Diğer argparse hatası (hatalı flag vb.)
            if lang == "tr":
                print(f"\n  ❌ Hata: {message}")
                print(f"  Yardım için: alms --help\n")
            else:
                print(f"\n  ❌ Error: {message}")
                print(f"  For help: alms --help\n")
        sys.exit(2)


def build_parser() -> _BilingualParser:
    p = _BilingualParser(
        prog="alms",
        description="IGU ALMS — Ders Materyali İndirici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # choices kaldırıldı — alias çözümlemesi main() içinde yapılır
    p.add_argument("command", nargs="?", default="menu",
                   help="Komut (TR veya EN) — varsayılan: menu  |  alms --help")
    p.add_argument("--version", action="store_true",
                   help="Sürüm bilgisini göster ve güncelleme var mı kontrol et")
    p.add_argument("subcommand", nargs="?", default=None,
                   help="obis alt komutu: sinav | notlar | transkript | program | devamsizlik | duyurular | takvim")
    p.add_argument("--setup", "--kurulum", dest="setup", action="store_true",
                   help="obis: OBİS oturum kurulumu  |  --setup / --kurulum")
    p.add_argument("--sinav", "--exam-flag", dest="sinav", action="store_true",
                   help="obis: sınav tarihlerini göster")
    p.add_argument("-v", "--verbose", "--ayrintili", "--ayrıntılı",
                   dest="verbose", action="store_true",
                   help="Ayrıntılı loglar  |  -v / --verbose / --ayrintili")
    p.add_argument("-q", "--quiet", "--sessiz",
                   dest="quiet", action="store_true",
                   help="Sadece hata logları (cron için)  |  -q / --quiet / --sessiz")
    p.add_argument("-f", "--format", "--bicim", "--biçim",
                   dest="format", choices=["pdf", "video"],
                   help="sync/download için dosya tipi  |  -f pdf  |  --bicim video")
    p.add_argument("--course", "--ders-kodu", dest="course", metavar="KOD",
                   help="Ders kodu filtresi (örn. FIZ108)  |  --course / --ders-kodu")
    p.add_argument("--courses", "--dersler", dest="courses", metavar="KOD1,KOD2",
                   help="Virgülle ayrılmış ders kodları  |  --courses / --dersler")
    p.add_argument("--week", "--hafta", dest="week", type=int, metavar="N",
                   help="Sadece N. haftayı indir  |  --week / --hafta")
    p.add_argument("--all", "--hepsi", dest="all", action="store_true",
                   help="Daha önce indirilenler dahil tümünü indir  |  --all / --hepsi")
    p.add_argument("--force", "--zorla", dest="force", action="store_true",
                   help="Dosya diskde olsa bile yeniden indir  |  --force / --zorla")
    p.add_argument("--ekle", "--add", dest="ekle", action="store_true",
                   help="konular: yeni sınav konusu gir  |  --ekle / --add")
    p.add_argument("--vize", "--midterm", dest="vize", action="store_true",
                   help="konular: sadece vize konularını göster  |  --vize / --midterm")
    p.add_argument("--final", "--finals", dest="final", action="store_true",
                   help="konular: sadece final konularını göster  |  --final / --finals")
    p.add_argument("--ders", "--course-filter", dest="ders", metavar="KOD",
                   help="konular: ders kodu filtresi  |  --ders / --course-filter")
    p.add_argument("--oyla", "--vote", dest="oyla", metavar="ID",
                   help="konular: konuya oy ver (ID)  |  --oyla / --vote")
    p.add_argument("--reconfigure", "--yeniden-yapilandir", "--yeniden-yapılandır",
                   dest="reconfigure", metavar="ALAN",
                   nargs="?", const="credentials",
                   choices=["credentials", "schedule", "path"],
                   help="setup: yeniden yapılandır  |  --reconfigure / --yeniden-yapilandir")
    p.add_argument("--simule", "--simulate", "--simulasyon",
                   dest="simule", action="store_true",
                   help="notlar: final not simülasyonu  |  --simule / --simulate")
    p.add_argument("--guncelle", "--update-cache", "--güncelle",
                   dest="guncelle", action="store_true",
                   help="cache: tüm OBİS verilerini çek ve kaydet  |  --guncelle / --update-cache")
    p.add_argument("--temizle", "--clear-cache",
                   dest="temizle", action="store_true",
                   help="cache: önbelleği temizle  |  --temizle / --clear-cache")
    return p


# ─── Komutlar ────────────────────────────────────────────────
def cmd_setup(reconfigure: str | None = None):
    from cli.wizard import run_wizard
    from utils.version import init_version_if_missing
    run_wizard(reconfigure=reconfigure)
    init_version_if_missing()


def cmd_menu(token: str, username: str):
    from cli.menu import run_main_menu
    run_main_menu(token, username)


def cmd_sync(token: str, args):
    log = logging.getLogger(__name__)
    from core.api import get_active_courses
    from core.downloader import collect_files, download_all, sync_manifest_with_disk, deduplicate
    from utils.logger import log_action

    quiet = getattr(args, "quiet", False)
    force = getattr(args, "force", False) or getattr(args, "all", False)

    course_filter = None
    courses_arg   = getattr(args, "courses", None)
    course_arg    = getattr(args, "course",  None)

    if courses_arg:
        course_filter = [c.strip() for c in courses_arg.split(",") if c.strip()]
    elif course_arg:
        course_filter = [course_arg]
    else:
        from core.config import get as cfg_get
        saved = cfg_get("auto_sync_courses") or []
        if saved:
            course_filter = saved

    from utils.network import check_alms_reachable
    reachable, net_msg = check_alms_reachable()
    if not reachable:
        log.error("ALMS'e erişilemiyor: %s", net_msg)
        if not quiet:
            print(f"\n  ❌ Bağlantı hatası: {net_msg}")
        return

    removed = sync_manifest_with_disk()
    if removed:
        log.info("🗑  Manifest temizlendi — %d kayıt kaldırıldı.", removed)

    log.info("Sync başladı...%s",
             f" (dersler: {', '.join(course_filter)})" if course_filter else "")
    log_action("sync_start", {"force": force, "courses": course_filter or []})

    from utils.notify import send as notify
    from core.config import get as cfg_get
    if cfg_get("notify_desktop"):
        label = f"({', '.join(course_filter)})" if course_filter else "Tüm dersler"
        notify("ALMS Sync Başladı", label)

    all_courses = get_active_courses(token)

    if course_filter:
        raw = []
        for code in course_filter:
            raw += collect_files(
                token, all_courses,
                file_type=getattr(args, "format", None),
                course_filter=code,
                week_filter=getattr(args, "week", None),
                dedup=False,
            )
        files, _ = deduplicate(raw)
    else:
        files = collect_files(
            token, all_courses,
            file_type=getattr(args, "format", None),
            course_filter=None,
            week_filter=getattr(args, "week", None),
            dedup=True,
        )

    if not files:
        log.info("Yeni dosya bulunamadı.")
        log_action("sync_end", {"found": 0})
        return

    log.info("📦 %d dosya indirilecek...", len(files))

    _ok_count   = [0]
    _fail_count = [0]

    def on_progress(done, total, f, result):
        if result["ok"] and not result.get("skipped"):
            _ok_count[0] += 1
        elif not result["ok"]:
            _fail_count[0] += 1

        pct    = int(done / max(total, 1) * 100)
        bar_w  = 20
        filled = int(bar_w * pct / 100)
        bar    = "█" * filled + "░" * (bar_w - filled)
        status = "✅" if result["ok"] and not result.get("skipped") else (
                 "⬛" if result.get("skipped") else "❌")

        if quiet:
            if pct % 10 == 0 or done == total:
                log.info("  %d/%d (%d%%) — ✅%d ❌%d",
                         done, total, pct, _ok_count[0], _fail_count[0])
        else:
            print(f"\r  [{bar}] {pct:3d}%  {done}/{total} {status} {f['file_name'][:38]:<38}",
                  end="", flush=True)

    result = download_all(token, files, only_new=not force, on_progress=on_progress)

    if not quiet:
        print()

    log_action("sync_end", {
        "found":    len(files),
        "ok":       result["ok"],
        "skipped":  result["skipped"],
        "failed":   result["failed"],
        "cancelled": result.get("cancelled", False),
    })

    if result.get("cancelled"):
        log.warning("Sync iptal edildi — %d indirildi.", result["ok"])
    else:
        log.info("Sync tamamlandı — %d indirildi, %d atlandı, %d başarısız",
                 result["ok"], result["skipped"], result["failed"])
        if cfg_get("notify_desktop") and (result["ok"] > 0 or result["failed"] > 0):
            if result["ok"] > 0:
                msg = f"{result['ok']} dosya indirildi"
                if result["failed"]:
                    msg += f", {result['failed']} başarısız"
                notify("ALMS Sync Tamamlandı ✅", msg)
            else:
                notify("ALMS Sync", "Yeni dosya bulunamadı")

    if result.get("failed_files") and not quiet:
        for ff in result["failed_files"]:
            log.error("  ❌ %s — %s", ff["file"], ff["error"])

    # Yaklaşan sınav bildirimi (1 ve 3 gün kala) — get_session_silent: cron'da interaktif prompt yok
    if cfg_get("notify_desktop"):
        try:
            from core.obis import get_session_silent, check_upcoming_exams_notify
            sess = get_session_silent()
            if sess:
                check_upcoming_exams_notify(sess)
        except Exception:
            pass


def cmd_list(token: str):
    from core.api import get_active_courses
    courses = get_active_courses(token)
    print(f"\n{'#':<4} {'Kod':<10} {'Ders':<44} {'İlerleme'}")
    print("─" * 70)
    for i, c in enumerate(courses, 1):
        code = c.get("courseCode", "?")
        name = c.get("name", "").strip()[:42]
        prog = f"%{c.get('progress', 0)}"
        print(f"{i:<4} {code:<10} {name:<44} {prog}")
    print()


def cmd_open():
    import subprocess
    from core.config import get_download_dir
    dl = get_download_dir()
    dl.mkdir(parents=True, exist_ok=True)
    system = platform.system()
    if system == "Windows":
        os.startfile(str(dl))
    elif system == "Darwin":
        subprocess.run(["open", str(dl)])
    else:
        for cmd in ["xdg-open", "nautilus", "thunar", "dolphin", "nemo"]:
            try:
                subprocess.Popen([cmd, str(dl)],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
                break
            except FileNotFoundError:
                continue
    print(f"📁 {dl}")


def cmd_today(token: str):
    from cli.menu import screen_today
    screen_today(token)


def cmd_status(token: str, username: str):
    from cli.menu import screen_status
    screen_status(token, username)


def cmd_logout():
    from core.auth import delete_credentials, clear_sessions
    delete_credentials()
    clear_sessions()
    print("✅ Kimlik bilgileri ve oturumlar silindi.")


def cmd_config():
    from core.config import load
    import json
    cfg = load()
    safe = {k: v for k, v in cfg.items() if "token" not in k.lower()}
    print(json.dumps(safe, ensure_ascii=False, indent=2))


def _cmd_cache(args, token: str):
    """alms cache — offline cache management / çevrimdışı önbellek yönetimi."""
    from core import cache as _cache

    try:
        from core.config import get as _cfg
        lang = _cfg("language") or "tr"
    except Exception:
        lang = "tr"

    _S = {
        "tr": {
            "cleared":        "Önbellek temizlendi — {n} dosya silindi.",
            "session_get":    "OBİS oturumu alınıyor...",
            "session_fail":   "❌ OBİS oturumu kurulamadı.",
            "fetching":       "Veriler çekiliyor...\n",
            "saved":          "{ok}/{total} önbelleğe kaydedildi.",
            "title":          "Çevrimdışı Önbellek Durumu",
            "col_data":       "Veri",
            "col_status":     "Durum",
            "col_updated":    "Güncelleme",
            "fresh":          "taze",
            "stale":          "eski",
            "none":           "yok",
            "ago":            "önce",
            "hint_update":    "alms cache --guncelle   → tüm verileri güncelle",
            "hint_clear":     "alms cache --temizle    → önbelleği temizle",
        },
        "en": {
            "cleared":        "Cache cleared — {n} file(s) deleted.",
            "session_get":    "Getting OBIS session...",
            "session_fail":   "❌ Could not establish OBIS session.",
            "fetching":       "Fetching data...\n",
            "saved":          "{ok}/{total} saved to cache.",
            "title":          "Offline Cache Status",
            "col_data":       "Data",
            "col_status":     "Status",
            "col_updated":    "Updated",
            "fresh":          "fresh",
            "stale":          "stale",
            "none":           "none",
            "ago":            "ago",
            "hint_update":    "alms cache --guncelle   → fetch and cache all data",
            "hint_clear":     "alms cache --temizle    → clear the cache",
        },
    }
    s = _S.get(lang, _S["tr"])

    if getattr(args, "temizle", False):
        removed = _cache.clear()
        print(f"✅ " + s["cleared"].format(n=removed))
        return

    if getattr(args, "guncelle", False):
        from core.obis import get_session
        print(s["session_get"])
        session = get_session()
        if not session:
            print(s["session_fail"])
            return
        print(s["fetching"])
        results = _cache.fetch_all(session, token)
        ok = sum(1 for v in results.values() if v)
        for k, success in results.items():
            icon = "✅" if success else "❌"
            print(f"  {icon} {_cache.get_label(k)}")
        print(f"\n" + s["saved"].format(ok=ok, total=len(results)))
        return

    # Default: show status
    st = _cache.status()
    print(f"\n  {s['title']}\n")
    print(f"  {s['col_data']:<22} {s['col_status']:<10} {s['col_updated']}")
    print("  " + "─" * 52)
    for entry in st:
        if entry["exists"]:
            h = entry["age_hours"]
            freshness = s["fresh"] if not entry["stale"] else s["stale"]
            ts = (entry["updated_at"] or "")[:16].replace("T", " ")
            age_str = f"({h:.0f}h {s['ago']})" if h is not None else ""
            print(f"  {entry['label']:<22} {freshness:<10} {ts}  {age_str}")
        else:
            print(f"  {entry['label']:<22} {s['none']:<10}")
    print()
    print(f"  {s['hint_update']}")
    print(f"  {s['hint_clear']}\n")


def cmd_obis(args):
    from core.obis import obis_main
    # --sinav → subcommand="sinav" olarak çevir
    if getattr(args, "sinav", False):
        args.subcommand = "sinav"
    obis_main(args)


# ─── Main ─────────────────────────────────────────────────────
def main():
    parser = build_parser()
    args   = parser.parse_args()

    setup_logging(args.verbose, args.quiet)
    log = logging.getLogger(__name__)

    # Başlangıç migration'ları — kilit gerekmez, tüm komutlardan önce çalışır
    try:
        from core.migration import run_migrations
        run_migrations()
    except Exception:
        pass

    # Komut takma adını kanonik forma çevir (TR/EN alias desteği)
    if args.command and args.command not in _CANONICAL_COMMANDS:
        resolved = _CMD_ALIASES.get(args.command.lower())
        if resolved:
            args.command = resolved
        else:
            # Bilinmeyen komut — yardımcı mesaj ve çıkış
            lang = "tr"
            try:
                from core.config import get as _cfg
                lang = _cfg("language") or "tr"
            except Exception:
                pass
            suggestions = _suggest_commands(args.command)
            if lang == "tr":
                print(f"\n  ❌ Bilinmeyen komut: '{args.command}'")
                if suggestions:
                    print(f"  💡 Bunu mu demek istediniz?\n")
                    for s in suggestions:
                        print(f"       alms {s}")
                print(f"\n  Kullanılabilir komutlar: alms --help\n")
            else:
                print(f"\n  ❌ Unknown command: '{args.command}'")
                if suggestions:
                    print(f"  💡 Did you mean?\n")
                    for s in suggestions:
                        print(f"       alms {s}")
                print(f"\n  Available commands: alms --help\n")
            sys.exit(2)

    # --version
    if getattr(args, "version", False):
        from utils.version import get_current_version, get_version_info, check_update_available
        ver  = get_current_version()
        info = get_version_info()
        build = info.get("build", "")
        build_str = f" (build: {build})" if build else ""
        print(f"  ALMS İndirici v{ver}{build_str}")
        if info.get("updated_at"):
            print(f"  Güncellendi : {info['updated_at'][:10]}")
        if info.get("changelog"):
            print(f"  Değişiklik  : {info['changelog']}")
        print("  Güncelleme kontrol ediliyor...")
        has_update, count, remote_ver = check_update_available()
        if has_update:
            rv = f" → v{remote_ver}" if remote_ver else ""
            print(f"  ⬆️  {count} güncelleme mevcut{rv} — yüklemek için: alms update")
        else:
            print("  ✅ Güncel")
        return

    # OBİS komutu — token gerektirmez
    if args.command == "obis":
        cmd_obis(args)
        return

    # Update komutu — token gerektirmez
    if args.command == "update":
        from core.updater import perform_update
        perform_update()
        return

    # Setup komutu kilit gerektirmez
    if args.command == "setup":
        reconfigure = getattr(args, "reconfigure", None)
        cmd_setup(reconfigure=reconfigure)
        return

    if not _acquire_lock():
        print("⚠️  ALMS zaten çalışıyor.")
        sys.exit(1)

    # version.json yoksa oluştur
    try:
        from utils.version import init_version_if_missing
        init_version_if_missing()
    except Exception:
        pass

    from utils.paths import CREDS_FILE
    if not CREDS_FILE.exists() and args.command != "logout":
        print("Henüz kurulum yapılmamış. Kurulum sihirbazı başlatılıyor...\n")
        cmd_setup()
        return

    try:
        from core.auth import get_or_refresh_token
        token, username = get_or_refresh_token()
    except Exception as e:
        log.error("Giriş yapılamadı: %s", e)
        sys.exit(1)

    # Firebase: öğrenci no ile deterministik hesap.
    # Token geçerliyse anında döner; yoksa ~500ms auth işlemi yapar.
    if username:
        try:
            from core.firebase import firebase_login, is_configured
            if is_configured():
                firebase_login(str(username))
        except Exception:
            pass

    try:
        if args.command in ("menu", None):
            cmd_menu(token, username)
        elif args.command == "sync":
            cmd_sync(token, args)
        elif args.command == "list":
            cmd_list(token)
        elif args.command == "download":
            from cli.menu import screen_download
            screen_download(token)
        elif args.command == "today":
            cmd_today(token)
        elif args.command == "open":
            cmd_open()
        elif args.command == "status":
            cmd_status(token, username)
        elif args.command == "stats":
            from cli.menu import screen_stats
            screen_stats()
        elif args.command == "log":
            from cli.menu import screen_log
            screen_log()
        elif args.command == "export":
            from cli.menu import cmd_export
            cmd_export(token)
        elif args.command == "logout":
            cmd_logout()
        elif args.command == "config":
            cmd_config()
        elif args.command == "transkript":
            from core.obis import get_session, get_transkript, print_transkript
            s = get_session()
            if s:
                print_transkript(get_transkript(s))
        elif args.command == "program":
            from core.obis import get_session, get_ders_programi, print_ders_programi
            s = get_session()
            if s:
                print_ders_programi(get_ders_programi(s))
        elif args.command == "duyurular":
            from core.obis import get_session, get_obis_duyurular, get_lms_duyurular, print_duyurular
            s = get_session()
            obis_d = get_obis_duyurular(s) if s else []
            lms_d  = get_lms_duyurular(token) if token else []
            print_duyurular(obis_d, lms_d)
        elif args.command == "takvim":
            from core.obis import get_lms_zaman_cizelgesi, print_zaman_cizelgesi
            print_zaman_cizelgesi(get_lms_zaman_cizelgesi(token))
        elif args.command == "devamsizlik":
            from core.obis import get_session, get_devamsizlik, print_devamsizlik
            s = get_session()
            if s:
                print_devamsizlik(get_devamsizlik(s))
        elif args.command == "notlar":
            from core.obis import (get_session, get_notlar, print_notlar,
                                   simulate_final_grades, print_final_simulation)
            s = get_session()
            if s:
                notlar = get_notlar(s)
                if getattr(args, "simule", False):
                    print_final_simulation(simulate_final_grades(notlar))
                else:
                    print_notlar(notlar)
        elif args.command == "sinav":
            from core.obis import get_session, get_sinav_tarihleri, print_sinav_tarihleri
            s = get_session()
            if s:
                print_sinav_tarihleri(get_sinav_tarihleri(s))
        elif args.command == "konular":
            from core.topics import topics_main
            topics_main(args, username)
        elif args.command == "cache":
            _cmd_cache(args, token)
        elif args.command == "notify-check":
            from core.notifier import run_check
            from core.config import get as _cfg
            quiet = getattr(args, "quiet", False)
            result = run_check(token=token, quiet=quiet)
            if not quiet:
                total = sum(len(v) for v in result.values())
                if total == 0:
                    lang = _cfg("language") or "tr"
                    msg = "No new items." if lang == "en" else "Yeni öğe yok."
                    print(f"  ✅ {msg}")
    except KeyboardInterrupt:
        print("\nÇıkılıyor...")
    except Exception as e:
        log.exception("Beklenmeyen hata: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
