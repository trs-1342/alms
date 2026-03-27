"""
cli/menu.py — İnteraktif menü sistemi
Numara seçimi, dil desteği (tr/en)
"""
import logging
import os
import platform
import sys
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ─── Dil ─────────────────────────────────────────────────────
TR = {
    "main_title":       "ALMS İndirici",
    "main_menu":        "Ana Menü",
    "opt_list":         "Dersleri Listele",
    "opt_download":     "Dosya İndir",
    "opt_sync":         "Yeni Dosyaları Senkronize Et",
    "opt_calendar":     "Takvim / Yaklaşan Aktiviteler",
    "opt_settings":     "Ayarlar",
    "opt_status":       "Durum",
    "opt_auto":         "Otomatik Çalıştırma",
    "opt_exit":         "Çıkış",
    "choose":           "Seçiminiz",
    "back":             "Geri",
    "cancel":           "İptal",
    "invalid":          "Geçersiz seçim, tekrar deneyin.",
    "press_enter":      "Devam etmek için Enter'a basın...",
    "done":             "Tamamlandı ✓",
    "download_filter":  "Dosya Tipi",
    "all_types":        "Tümü",
    "pdf_only":         "Yalnızca PDF / Dökümanlar",
    "video_only":       "Yalnızca Videolar",
    "filter_course":    "Ders Filtresi (boş = hepsi)",
    "filter_week":      "Hafta Numarası (boş = hepsi)",
    "filter_new":       "Sadece yeni dosyalar mı?",
    "yes": "Evet", "no": "Hayır",
    "settings_title":   "Ayarlar",
    "set_download_dir": "İndirme Klasörü",
    "set_parallel":     "Paralel İndirme Sayısı",
    "set_language":     "Dil / Language",
    "set_notify":       "Masaüstü Bildirimi",
    "current_value":    "Mevcut",
    "new_value":        "Yeni değer (boş = değiştirme)",
    "auto_title":       "Otomatik Çalıştırma",
    "auto_enable":      "Etkinleştir",
    "auto_disable":     "Devre Dışı Bırak",
    "auto_status":      "Mevcut Durum",
    "auto_hour":        "Saat (0-23)",
    "auto_minute":      "Dakika (0-59)",
    "no_schedule":      "Otomatik çalıştırma kapalı.",
    "status_title":     "Sistem Durumu",
}

EN = {
    "main_title":       "ALMS Downloader",
    "main_menu":        "Main Menu",
    "opt_list":         "List Courses",
    "opt_download":     "Download Files",
    "opt_sync":         "Sync New Files",
    "opt_calendar":     "Calendar / Upcoming Activities",
    "opt_settings":     "Settings",
    "opt_status":       "Status",
    "opt_auto":         "Auto Run",
    "opt_exit":         "Exit",
    "choose":           "Your choice",
    "back":             "Back",
    "cancel":           "Cancel",
    "invalid":          "Invalid choice, try again.",
    "press_enter":      "Press Enter to continue...",
    "done":             "Done ✓",
    "download_filter":  "File Type",
    "all_types":        "All",
    "pdf_only":         "PDF / Documents only",
    "video_only":       "Videos only",
    "filter_course":    "Course filter (empty = all)",
    "filter_week":      "Week number (empty = all)",
    "filter_new":       "New files only?",
    "yes": "Yes", "no": "No",
    "settings_title":   "Settings",
    "set_download_dir": "Download Directory",
    "set_parallel":     "Parallel Downloads",
    "set_language":     "Language / Dil",
    "set_notify":       "Desktop Notification",
    "current_value":    "Current",
    "new_value":        "New value (empty = no change)",
    "auto_title":       "Auto Run",
    "auto_enable":      "Enable",
    "auto_disable":     "Disable",
    "auto_status":      "Current Status",
    "auto_hour":        "Hour (0-23)",
    "auto_minute":      "Minute (0-59)",
    "no_schedule":      "Auto run is disabled.",
    "status_title":     "System Status",
}


def _t(key: str) -> str:
    from core.config import get
    lang = get("language") or "tr"
    return (TR if lang == "tr" else EN).get(key, key)


def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")


def header(title: str = ""):
    clear()
    print("╔" + "═" * 50 + "╗")
    print(f"║  {_t('main_title'):48}║")
    if title:
        print(f"║  {title:48}║")
    print("╚" + "═" * 50 + "╝")
    print()


def menu(options: list[str], prompt: str = "") -> int:
    """0-indexed seçimi döndürür. Quit/back için -1."""
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    print()
    while True:
        try:
            raw = input(f"  {prompt or _t('choose')}: ").strip()
            if not raw:
                return -1
            n = int(raw)
            if 1 <= n <= len(options):
                return n - 1
            print(f"  {_t('invalid')}")
        except (ValueError, KeyboardInterrupt):
            return -1


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"  {prompt}{hint}: ").strip()
        return val if val else default
    except KeyboardInterrupt:
        return default


def yn(prompt: str, default: bool = True) -> bool:
    hint = f"[{_t('yes')}/{_t('no')}]"
    try:
        raw = input(f"  {prompt} {hint}: ").strip().lower()
        if not raw:
            return default
        return raw in ("e", "y", "evet", "yes", "1")
    except KeyboardInterrupt:
        return default


def pause():
    try:
        input(f"\n  {_t('press_enter')}")
    except KeyboardInterrupt:
        pass


# ─── Kurs listesi ekranı ─────────────────────────────────────
def screen_list_courses(token: str):
    from core.api import get_active_courses
    header(_t("opt_list"))
    print("  Dersler alınıyor...")
    courses = get_active_courses(token)

    print(f"\n  {'#':<4} {'Kod':<10} {'Ders':<42} {'İlerleme'}")
    print("  " + "─" * 70)
    for i, c in enumerate(courses, 1):
        code  = c.get("courseCode", "?")
        name  = c.get("name", "").strip()[:40]
        prog  = f"%{c.get('progress', 0)}"
        print(f"  {i:<4} {code:<10} {name:<42} {prog}")
    print()
    pause()


# ─── İndirme ekranı ──────────────────────────────────────────
def screen_download(token: str):
    from core.api import get_active_courses
    from core.downloader import collect_files, download_all

    header(_t("opt_download"))

    # Filtreler
    print(f"  {_t('download_filter')}:")
    ft_idx = menu([_t("all_types"), _t("pdf_only"), _t("video_only")])
    ft_map = {0: None, 1: "pdf", 2: "video"}
    file_type = ft_map.get(ft_idx)

    course_f = ask(_t("filter_course"))
    week_raw = ask(_t("filter_week"))
    week_f   = int(week_raw) if week_raw.isdigit() else None
    only_new = yn(_t("filter_new"), default=True)

    print("\n  Dersler ve dosyalar alınıyor...")
    courses = get_active_courses(token)
    files   = collect_files(
        token, courses,
        file_type=file_type,
        course_filter=course_f or None,
        week_filter=week_f,
    )

    if not files:
        print("\n  Dosya bulunamadı.")
        pause()
        return

    total_mb = sum(f["size_bytes"] for f in files) / 1_048_576
    print(f"\n  {len(files)} dosya bulundu (~{total_mb:.0f} MB)")
    print(f"  {'#':<4} {'Kod':<10} {'Hafta':<7} {'Dosya':<40} {'Boyut'}")
    print("  " + "─" * 75)
    for i, f in enumerate(files[:30], 1):
        mb = f"{f['size_bytes'] / 1_048_576:.1f} MB"
        print(f"  {i:<4} {f['course_code']:<10} {f['week']:<7} "
              f"{f['file_name'][:38]:<40} {mb}")
    if len(files) > 30:
        print(f"  ... ve {len(files) - 30} dosya daha")

    print()
    if not yn("İndirmeye başlansın mı?"):
        return

    from core.config import get_download_dir
    print(f"\n  📁 {get_download_dir()}")
    print()

    done_count = [0]

    def on_progress(done, total, f, result):
        done_count[0] = done
        status = "✅" if result["ok"] and not result.get("skipped") else (
            "⬛" if result.get("skipped") else "❌"
        )
        bar_len = 20
        filled  = int(bar_len * done / max(total, 1))
        bar     = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {done}/{total} {status} {f['file_name'][:30]:<30}", end="", flush=True)

    result = download_all(token, files, only_new=only_new, on_progress=on_progress)
    print()
    print(f"\n  ✅ {result['ok']} indirildi  "
          f"⬛ {result['skipped']} atlandı  "
          f"❌ {result['failed']} başarısız")

    if result["failed_files"]:
        print("\n  Başarısız dosyalar:")
        for ff in result["failed_files"]:
            print(f"    - {ff['file']} ({ff['error']})")

    pause()


# ─── Takvim ekranı ───────────────────────────────────────────
def screen_calendar(token: str):
    from core.api import get_calendar
    header(_t("opt_calendar"))
    days = ask("Kaç günlük takvim? [30]", "30")
    acts = get_calendar(token, int(days) if days.isdigit() else 30)

    if not acts:
        print("  Yaklaşan aktivite yok.")
    else:
        print(f"\n  {'Tarih':<12} {'Ders':<30} {'Aktivite':<35} {'Tür'}")
        print("  " + "─" * 90)
        for a in acts:
            due    = (a.get("dueDate") or "")[:10]
            course = a.get("courseName", "")[:28]
            name   = a.get("activityName", "")[:33]
            atype  = a.get("activityType", "")
            print(f"  {due:<12} {course:<30} {name:<35} {atype}")
    pause()


# ─── Durum ekranı ────────────────────────────────────────────
def screen_status(token: str, username: str):
    from core.auth import get_active_session
    from core.config import get_download_dir
    from utils.scheduler import get_schedule_status
    from utils.paths import CONFIG_DIR, MANIFEST_FILE
    import json

    header(_t("status_title"))
    now = datetime.now(timezone.utc)

    active = get_active_session()
    if active:
        exp = datetime.fromisoformat(active["expires"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        mins = int((exp - now).total_seconds() / 60)
        print(f"  👤 Kullanıcı   : {username}")
        print(f"  🔑 Token       : Geçerli ({mins} dakika kaldı)")
    else:
        print(f"  🔑 Token       : Süresi dolmuş")

    dl_dir = get_download_dir()
    print(f"  📁 İndirme     : {dl_dir}")

    if MANIFEST_FILE.exists():
        try:
            mf = json.loads(MANIFEST_FILE.read_text())
            print(f"  📦 İndirilen   : {len(mf)} dosya")
        except Exception:
            pass

    sched = get_schedule_status()
    print(f"  🕐 Otomasyon   : {sched or _t('no_schedule')}")
    print(f"  💻 Platform    : {platform.system()} {platform.release()}")
    print(f"  📂 Config      : {CONFIG_DIR}")
    print()
    pause()


# ─── Ayarlar ekranı ──────────────────────────────────────────
def screen_settings():
    from core import config as cfg

    while True:
        header(_t("settings_title"))
        current = cfg.load()
        dl_dir   = current.get("download_dir", "")
        parallel = current.get("parallel", 3)
        lang     = current.get("language", "tr")
        notify   = current.get("notify_desktop", True)

        print(f"  [1] {_t('set_download_dir'):<30} {dl_dir}")
        print(f"  [2] {_t('set_parallel'):<30} {parallel}")
        print(f"  [3] {_t('set_language'):<30} {lang}")
        print(f"  [4] {_t('set_notify'):<30} {'Açık' if notify else 'Kapalı'}")
        print(f"  [0] {_t('back')}")
        print()

        choice = menu(
            [_t("set_download_dir"), _t("set_parallel"),
             _t("set_language"), _t("set_notify"), _t("back")]
        )

        if choice == 0:
            new = ask(f"{_t('set_download_dir')} ({_t('current_value')}: {dl_dir})",
                      dl_dir)
            if new:
                cfg.set_value("download_dir", new)
        elif choice == 1:
            new = ask(f"{_t('set_parallel')} (1-10)", str(parallel))
            if new.isdigit() and 1 <= int(new) <= 10:
                cfg.set_value("parallel", int(new))
        elif choice == 2:
            idx = menu(["Türkçe (tr)", "English (en)"])
            if idx == 0:
                cfg.set_value("language", "tr")
            elif idx == 1:
                cfg.set_value("language", "en")
        elif choice == 3:
            cfg.set_value("notify_desktop", not notify)
        else:
            break


# ─── Otomasyon ekranı ────────────────────────────────────────
def screen_auto():
    from utils.scheduler import add_schedule, remove_schedule, get_schedule_status
    from utils.paths import LOG_FILE

    header(_t("auto_title"))
    status = get_schedule_status()
    print(f"  {_t('auto_status')}: {status or _t('no_schedule')}")
    print()

    idx = menu([_t("auto_enable"), _t("auto_disable"), _t("back")])

    if idx == 0:
        hour = ask(_t("auto_hour"), "8")
        minute = ask(_t("auto_minute"), "0")
        h = int(hour) if hour.isdigit() and 0 <= int(hour) <= 23 else 8
        m = int(minute) if minute.isdigit() and 0 <= int(minute) <= 59 else 0
        ok = add_schedule(h, m, str(LOG_FILE))
        print(f"\n  {'✅ Otomasyon etkinleştirildi.' if ok else '❌ Hata oluştu.'}")
    elif idx == 1:
        ok = remove_schedule()
        print(f"\n  {'✅ Otomasyon devre dışı.' if ok else '❌ Hata oluştu.'}")

    pause()


# ─── Ana menü ────────────────────────────────────────────────
def run_main_menu(token: str, username: str):
    while True:
        header()
        print(f"  👤 {username}\n")

        options = [
            _t("opt_list"),
            _t("opt_download"),
            _t("opt_sync"),
            _t("opt_calendar"),
            _t("opt_status"),
            _t("opt_settings"),
            _t("opt_auto"),
            _t("opt_exit"),
        ]
        idx = menu(options)

        if idx == 0:
            screen_list_courses(token)
        elif idx == 1:
            screen_download(token)
        elif idx == 2:
            # Hızlı sync — sadece yeniler, filtre yok
            from core.api import get_active_courses
            from core.downloader import collect_files, download_all
            header(_t("opt_sync"))
            print("  Dersler taranıyor...")
            courses = get_active_courses(token)
            files   = collect_files(token, courses)
            if not files:
                print("  Yeni dosya yok.")
            else:
                result = download_all(token, files, only_new=True)
                print(f"\n  ✅ {result['ok']} indirildi, {result['skipped']} atlandı, {result['failed']} başarısız")
            pause()
        elif idx == 3:
            screen_calendar(token)
        elif idx == 4:
            screen_status(token, username)
        elif idx == 5:
            screen_settings()
        elif idx == 6:
            screen_auto()
        else:
            break
