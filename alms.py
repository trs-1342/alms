#!/usr/bin/env python3
"""
alms.py — ALMS İndirici Ana Giriş Noktası
──────────────────────────────────────────
Kullanım:
  alms                   → interaktif menü
  alms setup             → ilk kurulum sihirbazı
  alms sync              → yeni dosyaları indir (sessiz)
  alms sync --quiet      → cron/scheduler için
  alms list              → dersleri listele
  alms download          → interaktif indirme
  alms status            → sistem durumu
  alms logout            → kimlik bilgilerini sil
  alms config            → ayarları göster
  alms obis              → sınav tarihleri
  alms obis --setup      → OBİS oturum kurulumu
  alms obis notlar       → ders notları
  alms obis devamsizlik  → devamsızlık
  alms --help / -h       → yardım
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
                try:
                    os.kill(old_pid, 0)  # 0 sinyali: process var mı? (POSIX — Linux + macOS)
                except ProcessLookupError:
                    LOCK_FILE.unlink(missing_ok=True)  # process yok, eski lock temizle
                except PermissionError:
                    pass  # process var ama izin yok — lock geçerli
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


atexit.register(_release_lock)


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
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="alms",
        description="IGU ALMS — Ders Materyali İndirici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("command", nargs="?", default="menu",
                   choices=["menu", "setup", "sync", "list",
                            "download", "today", "open",
                            "status", "stats", "log", "export",
                            "logout", "config", "obis", "update"],
                   help="Çalıştırılacak komut (varsayılan: menu)")
    p.add_argument("--version", action="store_true",
                   help="Sürüm bilgisini göster ve güncelleme var mı kontrol et")
    p.add_argument("subcommand", nargs="?", default=None,
                   help="obis alt komutu: sinav | notlar | devamsizlik")
    p.add_argument("--setup", action="store_true",
                   help="obis: OBİS oturum kurulumu")
    p.add_argument("--sinav", action="store_true",
                   help="obis: sınav tarihlerini göster")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Ayrıntılı loglar")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="Sadece hata logları (cron için)")
    p.add_argument("-f", "--format", choices=["pdf", "video"],
                   help="sync/download için dosya tipi filtresi")
    p.add_argument("--course", metavar="KOD",
                   help="Ders kodu veya isim filtresi (örn. FIZ108)")
    p.add_argument("--courses", metavar="KOD1,KOD2",
                   help="Virgülle ayrılmış ders kodları (otomasyon için)")
    p.add_argument("--week", type=int, metavar="N",
                   help="Sadece N. haftayı indir")
    p.add_argument("--all", action="store_true",
                   help="sync: daha önce indirilenler dahil tümünü indir")
    p.add_argument("--force", action="store_true",
                   help="Dosya diskde olsa bile yeniden indir (--all ile benzer)")
    return p


# ─── Komutlar ────────────────────────────────────────────────
def cmd_setup():
    from cli.wizard import run_wizard
    from utils.version import init_version_if_missing
    run_wizard()
    # version.json yoksa oluştur (ilk kurulum)
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
        cmd_setup()
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
    except KeyboardInterrupt:
        print("\nÇıkılıyor...")
    except Exception as e:
        log.exception("Beklenmeyen hata: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
