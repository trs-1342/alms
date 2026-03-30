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
    "opt_sinav":     "Sınav Takvimi",
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
    "opt_sinav":     "Exam Schedule",
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


import random

_QUOTES = [
    "Kod yazmak zor değil; zor olan ne yazacağını bilmektir.",
    "Hata yapmak seni kötü yapmaz, aynı hatayı anlamadan tekrar etmek yapar.",
    "Stack Overflow seni kurtarabilir ama seni geliştirmez.",
    "Kopyaladığın kod çalışıyorsa şanslısın; anlıyorsan tehlikelisin.",
    "Bir dili öğrenmek başarı değildir, problemi çözebilmek başarıdır.",
    '"Biliyorum" dediğin anda gelişimin durur.',
    "En iyi yazılımcılar hızlı olanlar değil, hata ayıklamayı bilenlerdir.",
    "Proje bitirmek, tutorial izlemekten daha değerlidir.",
    "Temeli atlamanın bedelini her projede tekrar ödersin.",
    "Kodun çalışması yeterli değil; okunabilir olması seni profesyonel yapar.",
    "Disiplin, motivasyondan daha uzun yaşar.",
    "Her yeni teknolojiye atlamak seni ileri götürmez, derinleşmek götürür.",
    "Yazılım öğrenmek maraton; sprint gibi koşarsan yarı yolda kalırsın.",
    "her kod kusurludur, çünkü insanın kendisi böyledir.\n-trs"
]

_last_quote = [None]


def _random_quote() -> str:
    available = [q for q in _QUOTES if q != _last_quote[0]]
    q = random.choice(available)
    _last_quote[0] = q
    return q


def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")


def header(title="", show_quote=False):
    clear()
    w = 54
    print(cyan("╔" + "═" * w + "╗"))
    print(cyan("║") + bold(f"  {_t('main_title'):<{w-2}}") + cyan("║"))
    if title:
        print(cyan("║") + yellow(f"  {title:<{w-2}}") + cyan("║"))
    print(cyan("╚" + "═" * w + "╝"))

    if show_quote:
        q = _random_quote()
        words  = q.split()
        lines  = []
        line   = ""
        for w_word in words:
            if len(line) + len(w_word) + 1 <= 50:
                line = (line + " " + w_word).strip()
            else:
                lines.append(line)
                line = w_word
        if line:
            lines.append(line)

        print()
        for l in lines:
            print(f"  {dim(l)}")

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


# ─── Ok tuşu + Space seçici ───────────────────────────────────
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
    groups = {}
    for f in files:
        key = f["course_code"] or f["course_name"][:12]
        groups.setdefault(key, []).append(f)
    return groups


def file_selector(files):
    if not files:
        return []

    from core.downloader import is_downloaded

    groups      = _group_by_course(files)
    selected    = {id(f): False for f in files}
    downloaded  = {id(f): is_downloaded(f) for f in files}
    all_ordered = [f for gfiles in groups.values() for f in gfiles]
    filt        = ""
    cursor      = 0
    PAGE        = 15
    filter_mode = False

    def _filtered():
        if not filt:
            return all_ordered
        kw = filt.lower()
        return [
            f for f in all_ordered
            if kw in f["file_name"].lower()
            or kw in f["course_code"].lower()
        ]

    def _render(ordered):
        clear()
        print(cyan("╔" + "═" * 54 + "╗"))
        title = f"Dosya Seç  {yellow('/ ' + filt) if filt else ''}"
        print(cyan("║") + bold(f"  {title:<52}") + cyan("║"))
        print(cyan("╚" + "═" * 54 + "╝"))

        hint_items = [
            ("↑↓", "hareket"), ("SPACE", "seç"), ("G", "grup"),
            ("A", "hepsi"), ("N", "temizle"),
            ("F", "filtrele  ESC=temizle  ENTER=kapat"),
            ("ENTER", "onayla"), ("Q", "iptal"),
        ]
        hint = "  ".join(f"{bold(k)} {dim(v)}" for k, v in hint_items)
        print(f"  {hint}")

        if filter_mode:
            print(f"\n  {yellow('Filtre:')} {filt}{cyan('█')}")
        print()

        if not ordered:
            print(f"  {dim('Eşleşen dosya yok.')}")
        else:
            start = max(0, cursor - PAGE // 2)
            end   = min(len(ordered), start + PAGE)
            if end - start < PAGE:
                start = max(0, end - PAGE)

            prev_code = None
            for i in range(start, end):
                f    = ordered[i]
                code = f["course_code"] or f["course_name"][:12]

                if code != prev_code:
                    g_all = groups.get(code, [])
                    g_sel = sum(1 for gf in g_all if selected[id(gf)])
                    arrow_h = cyan("▶") if i == cursor else " "
                    print(f"\n  {arrow_h} {bold(cyan(code))}  {dim(f'{g_sel}/{len(g_all)}')}")
                    prev_code = code

                mb      = f"{f['size_bytes']/1_048_576:.1f} MB"
                is_dl   = downloaded.get(id(f), False)
                is_sel  = selected[id(f)]
                is_cur  = i == cursor

                if is_sel:
                    chk = green("●")
                elif is_dl:
                    chk = yellow("◉")
                else:
                    chk = dim("○")

                dl_tag = dim(" ✓") if is_dl else "  "
                name = f["file_name"][:38]
                row  = f"  {chk} W{f['week']:02d}  {name:<38}{dl_tag} {mb:>7}"
                arrow = bold(cyan("  ▶ ")) if is_cur else "    "

                if is_cur:
                    line = bold(row)
                elif is_sel:
                    line = green(row)
                elif is_dl:
                    line = yellow(row)
                else:
                    line = row

                print(f"{arrow}{line}")

        total_sel  = sum(1 for v in selected.values() if v)
        total_dl   = sum(1 for v in downloaded.values() if v)
        sel_mb     = sum(f["size_bytes"] for f in all_ordered if selected[id(f)]) / 1_048_576
        sel_label  = _t("selected")
        count_str  = f"{len(_filtered())}/{len(all_ordered)}" if filt else str(len(all_ordered))
        dl_str     = f"  {yellow(f'◉ {total_dl} indirilmiş')}" if total_dl else ""
        print(f"\n  {yellow(f'{total_sel} {sel_label}  (~{sel_mb:.1f} MB)')}  {dim(count_str + ' dosya')}{dl_str}")

    def _toggle_group(f, ordered):
        code   = f["course_code"] or f["course_name"][:12]
        gfiles = groups.get(code, [])
        visible = [gf for gf in gfiles if gf in ordered]
        all_on  = all(selected[id(gf)] for gf in visible)
        for gf in visible:
            selected[id(gf)] = not all_on

    while True:
        ordered = _filtered()
        safe_cursor = min(cursor, max(0, len(ordered) - 1))
        if safe_cursor != cursor:
            cursor = safe_cursor

        _render(ordered)
        key = _getch()

        if filter_mode:
            if key in ("\r", "\n"):
                filter_mode = False
            elif key in ("\x1b",):
                filter_mode = False
                filt = ""
                cursor = 0
            elif key in ("f", "F"):
                filter_mode = False
            elif key == "UP":
                filter_mode = False
                cursor = (cursor - 1) % max(1, len(ordered))
            elif key == "DOWN":
                filter_mode = False
                cursor = (cursor + 1) % max(1, len(ordered))
            elif key in ("\x7f", "\x08"):
                filt = filt[:-1]
                cursor = 0
            elif key == "\x03":
                return []
            elif key and len(key) == 1 and key.isprintable():
                filt += key
                cursor = 0
            continue

        if not ordered:
            if key in ("q", "Q", "\x03", "\x1b"):
                return []
            elif key in ("f", "F"):
                filter_mode = True
                filt = ""
            continue

        if key == "UP":
            cursor = (cursor - 1) % len(ordered)
        elif key == "DOWN":
            cursor = (cursor + 1) % len(ordered)
        elif key == " ":
            f = ordered[cursor]
            selected[id(f)] = not selected[id(f)]
        elif key in ("g", "G"):
            _toggle_group(ordered[cursor], ordered)
        elif key in ("a", "A"):
            for f in ordered:
                selected[id(f)] = True
        elif key in ("n", "N"):
            for f in ordered:
                selected[id(f)] = False
        elif key in ("f", "F"):
            filter_mode = True
            cursor = 0
        elif key in ("\r", "\n"):
            return [f for f in all_ordered if selected[id(f)]]
        elif key in ("q", "Q", "\x03", "\x1b"):
            return []


# ─── Ders listesi ─────────────────────────────────────────────
def screen_list_courses(token):
    from core.api import get_active_courses
    from utils.spinner import Spinner
    header(_t("opt_list"))
    with Spinner("Dersler alınıyor..."):
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


# ─── Sınav Takvimi ────────────────────────────────────────────
def screen_sinav():
    """OBİS sınav takvimini menüden göster."""
    header(_t("opt_sinav"))

    try:
        from core.obis import get_session, get_sinav_tarihleri, print_sinav_tarihleri
    except ImportError:
        print(f"  {red('OBİS modülü bulunamadı.')}")
        pause()
        return

    from utils.spinner import Spinner
    with Spinner("OBİS bağlanıyor..."):
        session = get_session()

    if not session:
        pause()
        return

    with Spinner("Sınav tarihleri alınıyor..."):
        sinavlar = get_sinav_tarihleri(session)

    print_sinav_tarihleri(sinavlar)
    pause()


# ─── İndirme ──────────────────────────────────────────────────
def screen_download(token):
    from core.api import get_active_courses
    from core.downloader import collect_files, download_all, deduplicate, sync_manifest_with_disk
    from utils.logger import log_action
    from utils.spinner import Spinner

    header(_t("opt_download"))
    sync_manifest_with_disk()

    with Spinner("Dersler alınıyor..."):
        courses = get_active_courses(token)

    if not courses:
        print(f"  {red('Ders bulunamadı.')}")
        pause()
        return

    print(f"  {bold('Hangi dersleri tarayalım?')}")
    print(f"  {dim('(Boş bırak = hepsi)')}\n")
    for i, c in enumerate(courses, 1):
        code = c.get("courseCode", "?")
        name = c.get("name", "").strip()[:38]
        print(f"  {cyan(f'[{i}]')} {yellow(code):<10} {name}")
    print(f"  {cyan('[0]')} Tümü\n")

    raw = ask("Ders numaraları (örn: 1,3 — boş = hepsi)", "")
    selected_courses = []
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit() and part != "0":
                idx = int(part) - 1
                if 0 <= idx < len(courses):
                    selected_courses.append(courses[idx])
    if not selected_courses:
        selected_courses = courses

    if len(selected_courses) == 1:
        c = selected_courses[0]
        code = c.get("courseCode", c.get("name", "")[:10])
        print(f"\n  {bold(code)} için dosya tipi:")
        ft_idx = menu([_t("all_types"), _t("pdf_only"), _t("video_only")])
        course_filters = {id(c): {0: None, 1: "pdf", 2: "video"}.get(ft_idx)}
        global_ft = course_filters[id(c)]
    else:
        print(f"\n  {bold('Dosya tipi')} ({len(selected_courses)} ders için):")
        ft_idx = menu([
            _t("all_types"),
            _t("pdf_only"),
            _t("video_only"),
            "Her ders için ayrı ayrı sor",
        ])
        ft_map = {0: None, 1: "pdf", 2: "video"}
        if ft_idx == 3:
            course_filters = {}
            for c in selected_courses:
                code = c.get("courseCode", c.get("name", "")[:10])
                print(f"\n  {yellow(code)} için dosya tipi:")
                ci = menu([_t("all_types"), _t("pdf_only"), _t("video_only")])
                course_filters[id(c)] = ft_map.get(ci)
            global_ft = None
        else:
            global_ft = ft_map.get(ft_idx)
            course_filters = {id(c): global_ft for c in selected_courses}

    week_raw = ask(_t("filter_week"))
    week_f   = int(week_raw) if week_raw.isdigit() else None

    with Spinner("Dosyalar taranıyor..."):
        all_files = []
        for c in selected_courses:
            ft = course_filters.get(id(c), global_ft)
            chunk = collect_files(
                token, [c],
                file_type=ft,
                course_filter=None,
                week_filter=week_f,
                dedup=True,
            )
            all_files.extend(chunk)

    if not all_files:
        print(f"\n  {red(_t('no_files'))}")
        pause()
        return

    total_mb = sum(f["size_bytes"] for f in all_files) / 1_048_576
    print(f"\n  {green(str(len(all_files)))} dosya  (~{total_mb:.0f} MB)")
    pause()

    chosen = file_selector(all_files)

    if not chosen:
        clear()
        print(f"\n  {yellow(_t('no_selection'))}")
        pause()
        return

    from core.downloader import is_downloaded
    already = [f for f in chosen if is_downloaded(f)]
    force   = False
    if already:
        clear()
        print(f"\n  {yellow(f'⚠️  {len(already)} dosya zaten indirilmiş:')}")
        for f in already[:5]:
            print(f"  {dim('•')} {f['course_code']} W{f['week']:02d}  {f['file_name'][:45]}")
        if len(already) > 5:
            print(f"  {dim(f'... ve {len(already)-5} dosya daha')}")
        print()
        force = yn("Zaten indirilen dosyaları tekrar indir?", default=False)
        print()

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

    log_action("download_start", {"selected": len(chosen)})
    result = download_all(token, chosen, only_new=not force, on_progress=on_progress)
    log_action("download_end", {
        "ok": result["ok"], "skipped": result["skipped"], "failed": result["failed"],
    })
    print()

    if result["ok"] > 0:
        from utils.notify import send as notify
        from core.config import get as cfg_get
        if cfg_get("notify_desktop"):
            notify(
                "ALMS İndirici",
                f"{result['ok']} dosya indirildi"
                + (f", {result['failed']} başarısız" if result["failed"] else ""),
            )
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

    if result["ok"] > 0:
        from core.config import get as cfg_get
        if cfg_get("open_after_download"):
            cmd_open()
        elif yn("\n  İndirme klasörünü aç?", default=False):
            cmd_open()

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
    from utils.network import check_alms_reachable
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
        token_str = (
            green(f"Geçerli ({mins} dk kaldı)") if mins > 30
            else yellow(f"⚠️  Süresi dolmak üzere ({mins} dk kaldı)")
            if mins > 0 else red("Süresi dolmuş")
        )
        print(f"  👤  {bold('Kullanıcı')}  : {green(username)}")
        print(f"  🔑  {bold('Token')}     : {token_str}")
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

    reachable, msg = check_alms_reachable()
    net_str = green("Erişilebilir") if reachable else red(f"Erişilemiyor — {msg}")
    print(f"  🌐  {bold('ALMS Ağ')}    : {net_str}")

    # OBİS oturum durumu
    try:
        from core.obis import load_session, _test_session
        obis_cookie = load_session()
        if obis_cookie:
            obis_ok = _test_session(obis_cookie)
            obis_str = green("Geçerli") if obis_ok else yellow("Sona ermiş")
        else:
            obis_str = dim("Kurulmamış  →  alms obis --setup")
        print(f"  🎓  {bold('OBİS')}       : {obis_str}")
    except Exception:
        pass

    print(f"  💻  {bold('Platform')}   : {platform.system()} {platform.release()}")
    print(f"  📂  {bold('Config')}     : {dim(str(CONFIG_DIR))}")
    print()
    pause()


# ─── Ayarlar ──────────────────────────────────────────────────
def screen_settings():
    from core import config as cfg

    while True:
        header(_t("settings_title"))
        c        = cfg.load()
        open_aft = c.get("open_after_download", False)
        notify   = c.get("notify_desktop", True)
        print(f"  {cyan('[1]')} {_t('set_dir'):<34} {dim(c.get('download_dir',''))}")
        print(f"  {cyan('[2]')} {_t('set_parallel'):<34} {yellow(str(c.get('parallel',3)))}")
        print(f"  {cyan('[3]')} {_t('set_lang'):<34} {yellow(c.get('language','tr'))}")
        print(f"  {cyan('[4]')} {'İndirince klasörü otomatik aç':<34} {green('Açık') if open_aft else dim('Kapalı')}")
        print(f"  {cyan('[5]')} {'Masaüstü bildirimi':<34} {green('Açık') if notify else dim('Kapalı')}")
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
        elif raw == "4":
            cfg.set_value("open_after_download", not open_aft)
        elif raw == "5":
            cfg.set_value("notify_desktop", not notify)
        else:
            break


# ─── Otomasyon ────────────────────────────────────────────────
def screen_auto(token=None):
    from utils.scheduler import add_schedule, remove_schedule, get_schedule_status
    from utils.paths import LOG_FILE
    from core import config as cfg

    header(_t("auto_title"))
    st = get_schedule_status()
    saved_courses = cfg.get("auto_sync_courses") or []

    print(f"  {bold(_t('auto_status'))}: {yellow(st) if st else dim(_t('no_schedule'))}")
    if saved_courses:
        print(f"  {bold('Seçili dersler')}: {cyan(', '.join(saved_courses))}")
    else:
        print(f"  {bold('Seçili dersler')}: {dim('Tümü')}")
    print()

    idx = menu([_t("auto_on"), "Ders Seçimini Güncelle", _t("auto_off"), _t("back")])

    if idx == 0:
        h = ask(_t("auto_hour"), "8")
        m = ask(_t("auto_min"),  "0")
        h = int(h) if h.isdigit() and 0 <= int(h) <= 23 else 8
        m = int(m) if m.isdigit() and 0 <= int(m) <= 59 else 0

        courses = _pick_auto_courses(token, saved_courses)
        cfg.set_value("auto_sync_courses", courses)
        cfg.set_value("auto_sync", True)
        cfg.set_value("auto_sync_hour", h)
        cfg.set_value("auto_sync_min", m)

        from utils.scheduler import _ensure_cron_running
        _ensure_cron_running()
        ok = add_schedule(h, m, str(LOG_FILE), courses or None)
        label = f"{h:02d}:{m:02d}"
        if courses:
            label += f" — {', '.join(courses)}"
        else:
            label += " — tüm dersler"
        print(f"\n  {green('✅ Etkinleştirildi: ' + label) if ok else red('❌ Hata.')}")

    elif idx == 1:
        courses = _pick_auto_courses(token, saved_courses)
        cfg.set_value("auto_sync_courses", courses)
        h = cfg.get("auto_sync_hour") or 8
        m = cfg.get("auto_sync_min")  or 0
        add_schedule(h, m, str(LOG_FILE), courses or None)
        label = ', '.join(courses) if courses else 'tüm dersler'
        print(f"\n  {green('✅ Ders seçimi güncellendi: ' + label)}")

    elif idx == 2:
        ok = remove_schedule()
        cfg.set_value("auto_sync", False)
        print(f"\n  {green('✅ Devre dışı.') if ok else red('❌ Hata.')}")

    pause()


def _pick_auto_courses(token, current: list[str]) -> list[str]:
    print()
    print(f"  {bold('Hangi dersler otomatik indirilsin?')}")
    print(f"  {dim('(Hiçbirini seçmezsen tüm dersler indirilir)')}\n")

    if token is None:
        raw = ask("Ders kodları (virgülle ayır, boş = hepsi)", ",".join(current))
        return [c.strip() for c in raw.split(",") if c.strip()] if raw else []

    try:
        from core.api import get_active_courses
        courses = get_active_courses(token)
    except Exception:
        raw = ask("Ders kodları (virgülle ayır, boş = hepsi)", ",".join(current))
        return [c.strip() for c in raw.split(",") if c.strip()] if raw else []

    if not courses:
        return []

    print(f"  {dim('Seçmek için numaraları virgülle gir. Boş bırak = hepsi.')}\n")
    for i, c in enumerate(courses, 1):
        code = c.get("courseCode", "?")
        name = c.get("name", "").strip()[:40]
        sel  = green("●") if code in current else dim("○")
        print(f"  {cyan(f'[{i}]')} {sel} {yellow(code):<10} {name}")

    print()
    raw = ask("Numara(lar) (örn: 1,3,5 — boş = hepsi)", "")
    if not raw:
        return []

    selected = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(courses):
                code = courses[idx].get("courseCode", "")
                if code:
                    selected.append(code)
    return selected


# ─── İstatistikler ────────────────────────────────────────────
def screen_stats():
    from utils.paths import MANIFEST_FILE, CONFIG_DIR
    from core.config import get_download_dir
    import json

    header("İstatistikler")

    if not MANIFEST_FILE.exists():
        print(f"  {dim('Henüz hiç dosya indirilmedi.')}")
        pause()
        return

    try:
        mf = json.loads(MANIFEST_FILE.read_text())
    except Exception:
        print(f"  {red('Manifest okunamadı.')}")
        pause()
        return

    course_stats: dict[str, dict] = {}
    total_bytes = 0
    missing     = 0

    for path_str in mf.values():
        p = __import__("pathlib").Path(path_str)
        try:
            dl_root  = get_download_dir()
            rel      = p.relative_to(dl_root)
            course   = rel.parts[0] if len(rel.parts) > 0 else "?"
        except ValueError:
            course = "?"

        size = p.stat().st_size if p.exists() else 0
        if not p.exists():
            missing += 1

        if course not in course_stats:
            course_stats[course] = {"count": 0, "bytes": 0}
        course_stats[course]["count"] += 1
        course_stats[course]["bytes"] += size
        total_bytes += size

    total_mb = total_bytes / 1_048_576
    print(f"  {bold('Toplam dosya')}  : {cyan(str(len(mf)))}")
    print(f"  {bold('Toplam boyut')} : {cyan(f'{total_mb:.1f} MB')}")
    if missing:
        print(f"  {bold('Eksik (silindi)')}: {yellow(str(missing))}")
    print()

    print(f"  {bold('Ders'):<14} {bold('Dosya'):>6}  {bold('Boyut')}")
    print("  " + cyan("─" * 36))
    for course, s in sorted(course_stats.items(), key=lambda x: -x[1]["bytes"]):
        mb = f"{s['bytes']/1_048_576:.1f} MB"
        print(f"  {yellow(course):<22} {s['count']:>5}  {mb:>8}")

    activity_log = CONFIG_DIR / "activity.log"
    if activity_log.exists():
        try:
            lines = activity_log.read_text().strip().splitlines()
            for line in reversed(lines):
                entry = json.loads(line)
                if entry.get("action") == "sync_end":
                    t = entry["time"][:16].replace("T", " ")
                    d = entry["detail"]
                    print(f"\n  {bold('Son sync')}  : {dim(t)}  "
                          f"{green(str(d.get('ok',0)) + ' indirildi')}")
                    break
        except Exception:
            pass
    print()
    pause()


# ─── Log görüntüleyici ────────────────────────────────────────
def screen_log():
    from utils.paths import CONFIG_DIR
    import json

    header("Aktivite Logu")

    activity_log = CONFIG_DIR / "activity.log"
    if not activity_log.exists():
        print(f"  {dim('Log dosyası henüz oluşmadı.')}")
        pause()
        return

    try:
        lines = activity_log.read_text().strip().splitlines()
    except Exception as e:
        print(f"  {red(f'Log okunamadı: {e}')}")
        pause()
        return

    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except Exception:
            continue

    recent = entries[-30:]

    print(f"  {bold('Zaman'):<22} {bold('Aksiyon'):<18} {bold('Detay')}")
    print("  " + cyan("─" * 70))

    ACTION_COLORS = {
        "sync_start":     dim,
        "sync_end":       green,
        "download_start": dim,
        "download_end":   green,
    }

    for e in reversed(recent):
        t      = e.get("time", "")[:16].replace("T", " ")
        action = e.get("action", "")
        detail = e.get("detail", {})

        if action == "sync_end":
            d_str = f"✅{detail.get('ok',0)} ⬛{detail.get('skipped',0)} ❌{detail.get('failed',0)}"
        elif action == "download_end":
            d_str = f"✅{detail.get('ok',0)} ⬛{detail.get('skipped',0)} ❌{detail.get('failed',0)}"
        elif action == "sync_start":
            d_str = f"force={detail.get('force', False)}"
        elif action == "download_start":
            d_str = f"seçilen={detail.get('selected', 0)}"
        else:
            d_str = str(detail)[:40]

        color  = ACTION_COLORS.get(action, str)
        print(f"  {dim(t):<22} {color(action):<27} {dim(d_str)}")

    print(f"\n  {dim(f'Son {len(recent)} kayıt gösteriliyor.')}")
    print()
    pause()


# ─── Dışa Aktar ───────────────────────────────────────────────
def cmd_export(token):
    import json
    from pathlib import Path
    from core.api import get_active_courses
    from utils.paths import MANIFEST_FILE
    from core.config import get_download_dir
    from utils.spinner import Spinner
    import datetime

    header("Dışa Aktar")
    print(f"  {bold('Format seç')}:")
    fmt_idx = menu(["Markdown (.md)", "JSON (.json)", "İkisi de"])
    if fmt_idx == -1:
        return

    with Spinner("Dersler alınıyor..."):
        courses = get_active_courses(token)

    dl_dir = get_download_dir()
    now    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    ts     = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    course_data = []
    for c in courses:
        code  = c.get("courseCode", "?")
        name  = c.get("name", "").strip()
        prog  = c.get("progress", 0)
        course_path = dl_dir / code
        downloaded  = []
        if course_path.exists():
            for f in sorted(course_path.rglob("*")):
                if f.is_file():
                    downloaded.append({
                        "path": str(f.relative_to(dl_dir)),
                        "size": f.stat().st_size,
                        "week": f.parent.name,
                    })
        course_data.append({
            "code": code, "name": name,
            "progress": prog, "downloaded": downloaded,
        })

    def to_markdown() -> str:
        lines = [
            "# ALMS Ders Materyali Indexi", "",
            f"Oluşturuldu: {now}",
            f"İndirme klasörü: `{dl_dir}`", "", "---", "",
        ]
        for c in course_data:
            lines += [f"## {c['code']} — {c['name']}", ""]
            lines.append(f"İlerleme: %{c['progress']}")
            lines.append("")
            if c["downloaded"]:
                lines += ["| Hafta | Dosya | Boyut |", "|-------|-------|-------|"]
                for f in c["downloaded"]:
                    mb = f"{f['size']/1_048_576:.1f} MB"
                    lines.append(f"| {f['week']} | `{Path(f['path']).name}` | {mb} |")
            else:
                lines.append("*Henüz indirilmedi*")
            lines.append("")
        return "\n".join(lines)

    def to_json() -> str:
        return json.dumps({
            "exported_at": now, "download_dir": str(dl_dir),
            "courses": course_data,
        }, ensure_ascii=False, indent=2)

    saved = []
    dl_dir.mkdir(parents=True, exist_ok=True)

    if fmt_idx in (0, 2):
        p = dl_dir / f"alms_index_{ts}.md"
        p.write_text(to_markdown(), encoding="utf-8")
        saved.append(str(p))
    if fmt_idx in (1, 2):
        p = dl_dir / f"alms_index_{ts}.json"
        p.write_text(to_json(), encoding="utf-8")
        saved.append(str(p))

    print(f"\n  {green('✅')} Dışa aktarıldı:")
    for p in saved:
        print(f"  {dim('📄')} {p}")
    pause()


def _token_warning(token, username):
    from core.auth import get_active_session
    active = get_active_session()
    if not active:
        return
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    exp = datetime.fromisoformat(active["expires"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    mins = int((exp - now).total_seconds() / 60)
    if mins <= 30:
        print(f"  {yellow(f'⚠️  Token {mins} dk sonra sona erecek.')}\n")


# ─── Güncelleme kontrolü ──────────────────────────────────────
# Güncelleme kontrolü — thread sonucu burada tutulur
_update_result: tuple | None = None   # (has_update, count, remote_ver)
_update_thread = None

def _start_update_check_bg():
    """
    git fetch --dry-run'ı daemon thread'de başlatır.
    Menü görünmeden ÖNCE çağrılır, menü açılırken arka planda çalışır.
    """
    import threading

    global _update_thread, _update_result

    def _run():
        global _update_result
        try:
            from utils.version import check_update_available
            _update_result = check_update_available()
        except Exception:
            _update_result = (False, 0, "")

    _update_thread = threading.Thread(target=_run, daemon=True)
    _update_thread.start()


_update_check_done = False  # menü oturumu boyunca bir kez göster

def _check_and_prompt_update():
    """
    Arka plan thread'in sonucunu okur ve kullanıcıya gösterir.
    Thread henüz bitmemişse max 2 saniye bekler — sonra geçer.
    """
    global _update_check_done, _update_thread, _update_result

    if _update_check_done:
        return
    _update_check_done = True

    try:
        # Thread sonucunu bekle (max 2s — timeout'ta sessiz geç)
        if _update_thread and _update_thread.is_alive():
            _update_thread.join(timeout=2.0)

        if not _update_result:
            return

        has_update, count, remote_ver = _update_result
        if not has_update:
            return

        from utils.version import get_current_version
        rv  = f" → v{remote_ver}" if remote_ver else ""
        cur = get_current_version()
        print(f"  {yellow('⬆️')}  {bold(f'{count} güncelleme mevcut')}  "
              f"{dim(f'v{cur}{rv}')}")
        print()

        try:
            r = input(f"  Şimdi güncellensin mi? [{green('E')}/{dim('H')}]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        if r in ("e", "y", "evet", "yes", "1"):
            from core.updater import perform_update
            perform_update()
            print(f"  {dim('Uygulamayı yeniden başlatın: alms')}")
            import sys
            sys.exit(0)
        else:
            print(f"  {dim('Güncelleme ertelendi. Manuel: alms update')}\n")
    except Exception:
        pass


# ─── Ana menü ─────────────────────────────────────────────────
def run_main_menu(token, username):
    # Güncelleme kontrolünü arka planda başlat — menü açılırken çalışır
    _start_update_check_bg()

    while True:
        header(show_quote=True)
        print(f"  {bold('👤')} {green(username)}\n")
        _token_warning(token, username)
        _check_and_prompt_update()

        opts = [
            _t("opt_list"),           # 1
            _t("opt_download"),       # 2
            _t("opt_sync"),           # 3
            _t("opt_today"),          # 4
            _t("opt_open"),           # 5
            _t("opt_status"),         # 6
            "İstatistikler",          # 7
            "Aktivite Logu",          # 8
            "Dışa Aktar",             # 9
            _t("opt_sinav"),          # 10  ← YENİ
            _t("opt_settings"),       # 11
            _t("opt_auto"),           # 12
            red(_t("opt_exit")),      # 13
        ]
        idx = menu(opts)

        if idx == 0:
            screen_list_courses(token)
        elif idx == 1:
            screen_download(token)
        elif idx == 2:
            from core.api import get_active_courses
            from core.downloader import collect_files, download_all, sync_manifest_with_disk
            from utils.logger import log_action
            from utils.notify import send as notify
            from utils.spinner import Spinner
            from core.config import get as cfg_get
            header(_t("opt_sync"))
            sync_manifest_with_disk()
            log_action("sync_start", {"force": False})
            if cfg_get("notify_desktop"):
                notify("ALMS Sync", "Yeni dosyalar taranıyor...")
            with Spinner("Dersler taranıyor..."):
                courses = get_active_courses(token)
                files   = collect_files(token, courses, dedup=True)
            if not files:
                print(f"  {dim('Yeni dosya yok.')}")
                log_action("sync_end", {"found": 0})
            else:
                print(f"  {green(str(len(files)))} yeni dosya bulundu\n")
                result = download_all(token, files, only_new=True)
                log_action("sync_end", {
                    "found": len(files), "ok": result["ok"],
                    "skipped": result["skipped"], "failed": result["failed"],
                })
                print(f"\n  {green('✅')} {result['ok']} indirildi  "
                      f"{dim('⬛')} {result['skipped']} atlandı  "
                      f"{red('❌')} {result['failed']} başarısız")
                if cfg_get("notify_desktop"):
                    msg = f"{result['ok']} dosya indirildi"
                    if result["failed"]:
                        msg += f", {result['failed']} başarısız"
                    notify("ALMS Sync Tamamlandı", msg)
            pause()
        elif idx == 3:
            screen_today(token)
        elif idx == 4:
            cmd_open()
            pause()
        elif idx == 5:
            screen_status(token, username)
        elif idx == 6:
            screen_stats()
        elif idx == 7:
            screen_log()
        elif idx == 8:
            cmd_export(token)
        elif idx == 9:                # ← Sınav Takvimi
            screen_sinav()
        elif idx == 10:
            screen_settings()
        elif idx == 11:
            screen_auto(token)
        else:
            break
