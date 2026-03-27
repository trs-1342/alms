"""
cli/menu.py — İnteraktif menü sistemi
"""
import logging
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ─── ANSI Renkler ─────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty() and (
    platform.system() != "Windows" or os.environ.get("WT_SESSION")
)

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def cyan(t):    return _c("96", t)
def green(t):   return _c("92", t)
def yellow(t):  return _c("93", t)
def red(t):     return _c("91", t)
def bold(t):    return _c("1",  t)
def dim(t):     return _c("2",  t)
def blue(t):    return _c("94", t)

# ─── Dil ──────────────────────────────────────────────────────
TR = {
    "main_title":    "ALMS İndirici",
    "opt_list":      "Dersleri Listele",
    "opt_download":  "Dosya İndir",
    "opt_sync":      "Yeni Dosyaları Senkronize Et",
    "opt_today":     "Bugünkü Program / Takvim",
    "opt_open":      "İndirme Klasörünü Aç",
    "opt_settings":  "Ayarlar",
    "opt_status":    "Durum",
    "opt_auto":      "Otomatik Çalıştırma",
    "opt_exit":      "Çıkış",
    "choose":        "Seçiminiz",
    "back":          "Geri",
    "invalid":       "Geçersiz seçim.",
    "press_enter":   "Devam için Enter...",
    "all_types":     "Tümü",
    "pdf_only":      "PDF / Dökümanlar",
    "video_only":    "Videolar",
    "filter_course": "Ders filtresi (boş = hepsi)",
    "filter_week":   "Hafta no (boş = hepsi)",
    "no_files":      "Dosya bulunamadı.",
    "no_selection":  "Hiçbir dosya seçilmedi.",
    "select_hint":   "↑↓ hareket   SPACE seç   A hepsi   N hiçbiri   ENTER onayla   Q iptal",
    "selected":      "seçili",
    "settings_title":"Ayarlar",
    "set_dir":       "İndirme Klasörü",
    "set_parallel":  "Paralel İndirme",
    "set_lang":      "Dil",
    "current":       "Mevcut",
    "auto_title":    "Otomatik Çalıştırma",
    "auto_on":       "Etkinleştir",
    "auto_off":      "Devre Dışı Bırak",
    "auto_status":   "Durum",
    "auto_hour":     "Saat (0-23)",
    "auto_min":      "Dakika (0-59)",
    "no_schedule":   "Kapalı",
    "status_title":  "Sistem Durumu",
    "dup_removed":   "duplicate kaldırıldı",
}

EN = {
    "main_title":    "ALMS Downloader",
    "opt_list":      "List Courses",
    "opt_download":  "Download Files",
    "opt_sync":      "Sync New Files",
    "opt_today":     "Today's Schedule / Calendar",
    "opt_open":      "Open Download Folder",
    "opt_settings":  "Settings",
    "opt_status":    "Status",
    "opt_auto":      "Auto Run",
    "opt_exit":      "Exit",
    "choose":        "Your choice",
    "back":          "Back",
    "invalid":       "Invalid choice.",
    "press_enter":   "Press Enter to continue...",
    "all_types":     "All",
    "pdf_only":      "PDF / Documents",
    "video_only":    "Videos",
    "filter_course": "Course filter (empty = all)",
    "filter_week":   "Week number (empty = all)",
    "no_files":      "No files found.",
    "no_selection":  "No files selected.",
    "select_hint":   "↑↓ move   SPACE toggle   A all   N none   ENTER confirm   Q cancel",
    "selected":      "selected",
    "settings_title":"Settings",
    "set_dir":       "Download Directory",
    "set_parallel":  "Parallel Downloads",
    "set_lang":      "Language",
    "current":       "Current",
    "auto_title":    "Auto Run",
    "auto_on":       "Enable",
    "auto_off":      "Disable",
    "auto_status":   "Status",
    "auto_hour":     "Hour (0-23)",
    "auto_min":      "Minute (0-59)",
    "no_schedule":   "Disabled",
    "status_title":  "System Status",
    "dup_removed":   "duplicates removed",
}


def _t(key):
    from core.config import get
    lang = get("language") or "tr"
    return (TR if lang == "tr" else EN).get(key, key)


def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")


def header(title=""):
    clear()
    w = 54
    print(cyan("╔" + "═" * w + "╗"))
    print(cyan("║") + bold(f"  {_t('main_title'):<{w-2}}") + cyan("║"))
    if title:
        print(cyan("║") + yellow(f"  {title:<{w-2}}") + cyan("║"))
    print(cyan("╚" + "═" * w + "╝"))
    print()


def menu(options, prompt=""):
    for i, opt in enumerate(options, 1):
        print(f"  {cyan(f'[{i}]')} {opt}")
    print()
    while True:
        try:
            raw = input(f"  {bold(prompt or _t('choose'))}: ").strip()
            if not raw:
                return -1
            n = int(raw)
            if 1 <= n <= len(options):
                return n - 1
            print(f"  {red(_t('invalid'))}")
        except (ValueError, KeyboardInterrupt):
            return -1


def ask(prompt, default=""):
    hint = f" {dim('['+default+']')}" if default else ""
    try:
        v = input(f"  {prompt}{hint}: ").strip()
        return v if v else default
    except KeyboardInterrupt:
        return default


def yn(prompt, default=True):
    hint = (green("E") + "/" + dim("H")) if default else (dim("E") + "/" + green("H"))
    try:
        r = input(f"  {prompt} [{hint}]: ").strip().lower()
        return default if not r else r in ("e", "y", "evet", "yes", "1")
    except KeyboardInterrupt:
        return default


def pause():
    try:
        input(f"\n  {dim(_t('press_enter'))}")
    except KeyboardInterrupt:
        pass


# ─── Ok tuşu + Space seçici (ders gruplu) ────────────────────
def _getch():
    if platform.system() == "Windows":
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b"\xe0", b"\x00"):
            ch2 = msvcrt.getch()
            return "UP" if ch2 == b"H" else "DOWN" if ch2 == b"P" else None
        return ch.decode(errors="replace")
    else:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                c2 = sys.stdin.read(1)
                if c2 == "[":
                    c3 = sys.stdin.read(1)
                    return "UP" if c3 == "A" else "DOWN" if c3 == "B" else None
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _group_by_course(files):
    """Dosyaları ders bazlı grupla: {course_code: [files]}"""
    groups = {}
    for f in files:
        key = f["course_code"] or f["course_name"][:12]
        groups.setdefault(key, []).append(f)
    return groups


def file_selector(files):
    """
    Ders bazlı gruplu dosya seçici.
    Döner: seçilen dosyaların listesi.
    """
    if not files:
        return []

    groups   = _group_by_course(files)
    selected = {id(f): False for f in files}
    # Flat sıralı dosya listesi (grup sırasına göre)
    ordered  = [f for gfiles in groups.values() for f in gfiles]
    cursor   = 0   # ordered içinde dosya indeksi
    PAGE     = 15  # görünür dosya satırı sayısı

    def _render():
        clear()
        print(cyan("╔" + "═" * 54 + "╗"))
        print(cyan("║") + bold(f"  {'Dosya Seç':<52}") + cyan("║"))
        print(cyan("╚" + "═" * 54 + "╝"))
        print(f"  {dim(_t('select_hint'))}\n")

        # Sayfalama: cursor etrafında PAGE kadar dosya göster
        start = max(0, cursor - PAGE // 2)
        end   = min(len(ordered), start + PAGE)
        if end - start < PAGE:
            start = max(0, end - PAGE)

        prev_code = None
        for i in range(start, end):
            f    = ordered[i]
            code = f["course_code"] or f["course_name"][:12]

            # Grup başlığı — sadece grup değişince göster
            if code != prev_code:
                g_files = groups[code]
                g_sel   = sum(1 for gf in g_files if selected[id(gf)])
                arrow_h = cyan("▶") if i == cursor else " "
                print(f"\n  {arrow_h} {bold(cyan(code))}  {dim(f'{g_sel}/{len(g_files)}')}")
                prev_code = code

            mb    = f"{f['size_bytes']/1_048_576:.1f} MB"
            chk   = green("●") if selected[id(f)] else dim("○")
            name  = f["file_name"][:40]
            row   = f"  {chk} W{f['week']:02d}  {name:<40} {mb:>7}"
            arrow = bold(cyan("  ▶ ")) if i == cursor else "    "
            line  = bold(row) if i == cursor else (green(row) if selected[id(f)] else row)
            print(f"{arrow}{line}")

        total_sel = sum(1 for v in selected.values() if v)
        sel_mb    = sum(f["size_bytes"] for f in ordered if selected[id(f)]) / 1_048_576
        sel_label = _t("selected")
        print(f"\n  {yellow(f'{total_sel} {sel_label}  (~{sel_mb:.1f} MB)')}")

    def _toggle_group(f):
        """f'nin ait olduğu grubun tamamını seç/kaldır."""
        code   = f["course_code"] or f["course_name"][:12]
        gfiles = groups[code]
        all_on = all(selected[id(gf)] for gf in gfiles)
        for gf in gfiles:
            selected[id(gf)] = not all_on

    while True:
        _render()
        key = _getch()

        if key == "UP":
            cursor = max(0, cursor - 1)
        elif key == "DOWN":
            cursor = min(len(ordered) - 1, cursor + 1)
        elif key == " ":
            f = ordered[cursor]
            selected[id(f)] = not selected[id(f)]
        elif key in ("g", "G"):
            # G tuşu: tüm grubu seç/kaldır
            _toggle_group(ordered[cursor])
        elif key in ("a", "A"):
            for f in ordered:
                selected[id(f)] = True
        elif key in ("n", "N"):
            for f in ordered:
                selected[id(f)] = False
        elif key in ("\r", "\n"):
            return [f for f in ordered if selected[id(f)]]
        elif key in ("q", "Q", "\x03", "\x1b"):
            return []


# ─── Ders listesi ─────────────────────────────────────────────
def screen_list_courses(token):
    from core.api import get_active_courses
    header(_t("opt_list"))
    print(f"  {dim('Dersler alınıyor...')}")
    courses = get_active_courses(token)

    print(f"\n  {bold('Kod'):<12} {bold('Ders'):<44} {bold('İlerleme')}")
    print("  " + cyan("─" * 68))
    for c in courses:
        code = yellow(c.get("courseCode", "?"))
        name = c.get("name", "").strip()[:42]
        prog = c.get("progress", 0)
        filled = int(prog / 10)
        bar = green("█" * filled) + dim("░" * (10 - filled))
        print(f"  {code:<20} {name:<44} {bar} {prog}%")

    print()
    print(f"  {dim('Ders kodunu indirme filtresinde kullanabilirsin.')}")
    print()
    pause()


# ─── İndirme ──────────────────────────────────────────────────
def screen_download(token):
    from core.api import get_active_courses
    from core.downloader import collect_files, download_all, deduplicate

    header(_t("opt_download"))

    print(f"  {bold('Dosya tipi')}:")
    ft_idx   = menu([_t("all_types"), _t("pdf_only"), _t("video_only")])
    ft_map   = {0: None, 1: "pdf", 2: "video"}
    file_type = ft_map.get(ft_idx)

    course_f = ask(_t("filter_course"))
    week_raw = ask(_t("filter_week"))
    week_f   = int(week_raw) if week_raw.isdigit() else None

    print(f"\n  {dim('Dersler taranıyor...')}")
    courses = get_active_courses(token)
    files   = collect_files(
        token, courses,
        file_type=file_type,
        course_filter=course_f or None,
        week_filter=week_f,
        dedup=True,
    )

    if not files:
        print(f"\n  {red(_t('no_files'))}")
        pause()
        return

    total_mb = sum(f["size_bytes"] for f in files) / 1_048_576
    print(f"\n  {green(str(len(files)))} dosya  (~{total_mb:.0f} MB)")
    pause()

    chosen = file_selector(files)

    if not chosen:
        clear()
        print(f"\n  {yellow(_t('no_selection'))}")
        pause()
        return

    from core.config import get_download_dir
    dl_dir = get_download_dir()
    print(f"\n  {bold('📁')} {dl_dir}\n")

    completed = []

    def on_progress(done, total, f, result):
        status = (green("✅") if result["ok"] and not result.get("skipped")
                  else dim("⬛") if result.get("skipped") else red("❌"))
        b = 22
        filled = int(b * done / max(total, 1))
        bar = green("█" * filled) + dim("░" * (b - filled))
        print(f"\r  [{bar}] {done}/{total} {status} {f['file_name'][:32]:<32}",
              end="", flush=True)
        if result["ok"] and not result.get("skipped"):
            completed.append((f, result.get("path", "")))

    result = download_all(token, chosen, only_new=True, on_progress=on_progress)
    print()
    print(f"\n  {green('✅')} {result['ok']} indirildi  "
          f"{dim('⬛')} {result['skipped']} atlandı  "
          f"{red('❌')} {result['failed']} başarısız")

    if completed:
        print(f"\n  {bold('İndirilenler:')}")
        for f, path in completed:
            week_label = f"Hafta {f['week']:02d}"
            print(f"  {dim('📄')} {cyan(f['course_code']):<10} {dim(week_label)}  "
                  f"{f['file_name']}")
            print(f"      {dim(path)}")

    if result["failed_files"]:
        print(f"\n  {red('Başarısız:')}")
        for ff in result["failed_files"]:
            print(f"    {dim('•')} {ff['file']} — {red(ff['error'][:60])}")

    pause()


# ─── Bugün ────────────────────────────────────────────────────
def screen_today(token):
    from core.api import get_calendar
    header(_t("opt_today"))

    acts = get_calendar(token, days=14)
    now  = datetime.now(timezone.utc).date()

    today     = [a for a in acts if (a.get("dueDate") or "")[:10] == str(now)]
    upcoming  = [a for a in acts if (a.get("dueDate") or "")[:10] > str(now)]

    if today:
        print(f"  {bold(yellow('Bugün'))} {dim('— ' + str(now))}\n")
        for a in today:
            atype = a.get("activityType", "")
            color = red if atype == "Exam" else yellow if atype == "Assignment" else str
            print(f"  {color('●')} {a.get('courseName','')[:28]:<28} {color(a.get('activityName','')[:36])}")
        print()

    if upcoming:
        print(f"  {bold('Yaklaşan')}\n")
        print(f"  {dim('Tarih'):<14} {dim('Ders'):<28} {dim('Aktivite'):<36} {dim('Tür')}")
        print("  " + dim("─" * 85))
        for a in upcoming[:10]:
            due    = cyan((a.get("dueDate") or "")[:10])
            course = a.get("courseName", "")[:26]
            name   = a.get("activityName", "")[:34]
            atype  = a.get("activityType", "")
            color  = red if atype == "Exam" else yellow if atype == "Assignment" else str
            print(f"  {due:<22} {course:<28} {color(name):<43} {dim(atype)}")
    elif not today:
        print(f"  {dim('Yaklaşan aktivite yok.')}")

    pause()


# ─── Klasörü aç ───────────────────────────────────────────────
def cmd_open():
    from core.config import get_download_dir
    dl = get_download_dir()
    dl.mkdir(parents=True, exist_ok=True)
    system = platform.system()
    if system == "Windows":
        os.startfile(str(dl))
    elif system == "Darwin":
        subprocess.run(["open", str(dl)])
    else:
        # Linux: xdg-open, nautilus, thunar, dolphin — ne varsa dene
        for cmd in ["xdg-open", "nautilus", "thunar", "dolphin", "nemo"]:
            try:
                subprocess.Popen([cmd, str(dl)],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
                break
            except FileNotFoundError:
                continue
    print(f"\n  📁 {dl}")


# ─── Durum ────────────────────────────────────────────────────
def screen_status(token, username):
    from core.auth import get_active_session
    from core.config import get_download_dir
    from utils.scheduler import get_schedule_status
    from utils.paths import CONFIG_DIR, MANIFEST_FILE
    import json

    header(_t("status_title"))
    now = datetime.now(timezone.utc)

    active = get_active_session()
    if active:
        exp  = datetime.fromisoformat(active["expires"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        mins = int((exp - now).total_seconds() / 60)
        print(f"  👤  {bold('Kullanıcı')}  : {green(username)}")
        print(f"  🔑  {bold('Token')}     : {green(f'Geçerli ({mins} dk kaldı)')}")
    else:
        print(f"  🔑  {bold('Token')}     : {red('Süresi dolmuş')}")

    dl = get_download_dir()
    print(f"  📁  {bold('İndirme')}    : {dl}")

    if MANIFEST_FILE.exists():
        try:
            mf = json.loads(MANIFEST_FILE.read_text())
            print(f"  📦  {bold('İndirilen')}  : {cyan(str(len(mf)) + ' dosya')}")
        except Exception:
            pass

    sched = get_schedule_status()
    print(f"  🕐  {bold('Otomasyon')}  : {yellow(sched) if sched else dim(_t('no_schedule'))}")
    print(f"  💻  {bold('Platform')}   : {platform.system()} {platform.release()}")
    print(f"  📂  {bold('Config')}     : {dim(str(CONFIG_DIR))}")
    print()
    pause()


# ─── Ayarlar ──────────────────────────────────────────────────
def screen_settings():
    from core import config as cfg

    while True:
        header(_t("settings_title"))
        c = cfg.load()
        print(f"  {cyan('[1]')} {_t('set_dir'):<32} {dim(c.get('download_dir',''))}")
        print(f"  {cyan('[2]')} {_t('set_parallel'):<32} {yellow(str(c.get('parallel',3)))}")
        print(f"  {cyan('[3]')} {_t('set_lang'):<32} {yellow(c.get('language','tr'))}")
        print(f"  {cyan('[0]')} {_t('back')}")
        print()
        raw = input(f"  {bold(_t('choose'))}: ").strip()
        if raw == "1":
            new = ask(_t("set_dir"), c.get("download_dir", ""))
            if new:
                cfg.set_value("download_dir", new)
        elif raw == "2":
            new = ask(f"{_t('set_parallel')} (1-10)", str(c.get("parallel", 3)))
            if new.isdigit() and 1 <= int(new) <= 10:
                cfg.set_value("parallel", int(new))
        elif raw == "3":
            idx = menu(["Türkçe (tr)", "English (en)"])
            if idx == 0:
                cfg.set_value("language", "tr")
            elif idx == 1:
                cfg.set_value("language", "en")
        else:
            break


# ─── Otomasyon ────────────────────────────────────────────────
def screen_auto():
    from utils.scheduler import add_schedule, remove_schedule, get_schedule_status
    from utils.paths import LOG_FILE

    header(_t("auto_title"))
    st = get_schedule_status()
    print(f"  {bold(_t('auto_status'))}: {yellow(st) if st else dim(_t('no_schedule'))}\n")

    idx = menu([_t("auto_on"), _t("auto_off"), _t("back")])
    if idx == 0:
        h = ask(_t("auto_hour"), "8")
        m = ask(_t("auto_min"),  "0")
        h = int(h) if h.isdigit() and 0 <= int(h) <= 23 else 8
        m = int(m) if m.isdigit() and 0 <= int(m) <= 59 else 0
        ok = add_schedule(h, m, str(LOG_FILE))
        print(f"\n  {green('✅ Etkinleştirildi.') if ok else red('❌ Hata.')}")
    elif idx == 1:
        ok = remove_schedule()
        print(f"\n  {green('✅ Devre dışı.') if ok else red('❌ Hata.')}")
    pause()


# ─── Ana menü ─────────────────────────────────────────────────
def run_main_menu(token, username):
    while True:
        header()
        print(f"  {bold('👤')} {green(username)}\n")

        opts = [
            _t("opt_list"),
            _t("opt_download"),
            _t("opt_sync"),
            _t("opt_today"),
            _t("opt_open"),
            _t("opt_status"),
            _t("opt_settings"),
            _t("opt_auto"),
            red(_t("opt_exit")),
        ]
        idx = menu(opts)

        if idx == 0:
            screen_list_courses(token)
        elif idx == 1:
            screen_download(token)
        elif idx == 2:
            from core.api import get_active_courses
            from core.downloader import collect_files, download_all
            header(_t("opt_sync"))
            print(f"  {dim('Taranıyor...')}")
            courses = get_active_courses(token)
            files   = collect_files(token, courses, dedup=True)
            if not files:
                print(f"  {dim('Yeni dosya yok.')}")
            else:
                result = download_all(token, files, only_new=True)
                print(f"\n  {green('✅')} {result['ok']} indirildi  "
                      f"{dim('⬛')} {result['skipped']} atlandı  "
                      f"{red('❌')} {result['failed']} başarısız")
            pause()
        elif idx == 3:
            screen_today(token)
        elif idx == 4:
            cmd_open()
            pause()
        elif idx == 5:
            screen_status(token, username)
        elif idx == 6:
            screen_settings()
        elif idx == 7:
            screen_auto()
        else:
            break
