"""
core/topics.py — Sınav konuları modülü
Firebase Firestore ile çalışır.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ── IGU fakülte/bölüm listesi ────────────────────────────────
IGU_FACULTIES = {
    "Mühendislik ve Mimarlık Fakültesi": [
        "Yazılım Mühendisliği",
        "Bilgisayar Mühendisliği",
        "Elektrik-Elektronik Mühendisliği",
        "Makine Mühendisliği",
        "İnşaat Mühendisliği",
        "Mimarlık",
        "İç Mimarlık ve Çevre Tasarımı",
    ],
    "İktisadi, İdari ve Sosyal Bilimler Fakültesi": [
        "İşletme",
        "İktisat",
        "Uluslararası İlişkiler",
        "Kamu Yönetimi",
        "Sosyoloji",
        "Psikoloji",
    ],
    "Sağlık Bilimleri Fakültesi": [
        "Hemşirelik",
        "Beslenme ve Diyetetik",
        "Fizyoterapi ve Rehabilitasyon",
        "Ebelik",
    ],
    "Hukuk Fakültesi": ["Hukuk"],
    "Güzel Sanatlar ve Tasarım Fakültesi": [
        "Grafik Tasarım",
        "Moda Tasarımı",
        "Tekstil Tasarımı",
    ],
    "Diğer / Manuel Gir": [],
}

SOURCE_TYPES = {
    "1": ("email",    "E-posta (hocanın gönderdiği)"),
    "2": ("birebir",  "Bire bir konuşma / yüz yüze"),
    "3": ("ders",     "Ders sırasında söylendi"),
    "4": ("yazisma",  "Özel yazışma (WhatsApp/DM)"),
    "5": ("duyuru",   "ALMS/OBİS duyurusu"),
    "6": ("diger",    "Diğer"),
}

EXAM_TYPES = {
    "1": "vize",
    "2": "final",
    "3": "quiz",
    "4": "butunleme",
}

# ── Renk yardımcıları ─────────────────────────────────────────

def _c(code, txt):
    import sys, platform, os
    use = sys.stdout.isatty() and (
        platform.system() != "Windows" or os.environ.get("WT_SESSION")
    )
    return f"\033[{code}m{txt}\033[0m" if use else txt

def _cyan(t):   return _c("96", t)
def _green(t):  return _c("92", t)
def _yellow(t): return _c("93", t)
def _red(t):    return _c("91", t)
def _dim(t):    return _c("2",  t)
def _bold(t):   return _c("1",  t)
def _magenta(t):return _c("95", t)


# ── Arrow-key menü seçimi ─────────────────────────────────────

def _arrow_menu(title: str, options: list[str]) -> int:
    """
    Oklu klavye navigasyonu ile seçim menüsü.
    Döner: seçilen indeks (0-based). -1 = iptal.
    Render: ekranı satır satır temizleyerek yeniden çizer.
    """
    import sys, platform, os
    if not sys.stdin.isatty():
        return -1

    n_opts = len(options)

    # Platform'a göre getch
    if platform.system() == "Windows":
        import msvcrt
        def getch() -> str:
            ch = msvcrt.getwch()
            if ch in ('\xe0', '\x00'):
                ch2 = msvcrt.getwch()
                return 'UP' if ch2 == 'H' else ('DOWN' if ch2 == 'P' else '')
            if ch == '\r':    return 'ENTER'
            if ch == '\x1b':  return 'ESC'
            return ch
    else:
        import tty, termios
        def getch() -> str:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    nxt = sys.stdin.read(2)
                    if nxt == '[A': return 'UP'
                    if nxt == '[B': return 'DOWN'
                    return 'ESC'
                if ch in ('\r', '\n'): return 'ENTER'
                if ch == '\x03': raise KeyboardInterrupt
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    idx          = 0
    # Kaç satır çizildiğini takip et
    lines_drawn  = 0

    def render(first: bool = False):
        nonlocal lines_drawn
        if not first and lines_drawn > 0:
            # Önceki render'ı sil
            # "\n".join() trailing newline bırakmaz — imleç son satırda kalır.
            # Önce \n ile yeni satıra geç, sonra lines_drawn satır yukarı çık.
            sys.stdout.write(f"\n\033[{lines_drawn}A")  # yukarı çık
            for _ in range(lines_drawn):
                sys.stdout.write("\033[2K\n")            # satırı temizle
            sys.stdout.write(f"\033[{lines_drawn}A")     # tekrar yukarı

        # Yeni render
        out_lines = []
        out_lines.append(f"  {_bold(title)}")
        for i, opt in enumerate(options):
            if i == idx:
                out_lines.append(f"  {_cyan('▶')} {_bold(opt)}")
            else:
                out_lines.append(f"    {_dim(opt)}")
        out_lines.append(f"  {_dim('↑↓ hareket   ENTER seç   ESC iptal')}")

        sys.stdout.write("\n".join(out_lines))
        sys.stdout.flush()
        lines_drawn = len(out_lines)

    print()  # boşluk
    render(first=True)

    try:
        while True:
            key = getch()
            if key == 'UP':
                idx = (idx - 1) % n_opts
                render()
            elif key == 'DOWN':
                idx = (idx + 1) % n_opts
                render()
            elif key == 'ENTER':
                # Temizle ve seçimi göster
                if lines_drawn > 0:
                    sys.stdout.write(f"\n\033[{lines_drawn}A")
                    for _ in range(lines_drawn):
                        sys.stdout.write("\033[2K\n")
                    sys.stdout.write(f"\033[{lines_drawn}A")
                print(f"  {_cyan('✔')} {_bold(options[idx])}")
                sys.stdout.flush()
                return idx
            elif key == 'ESC':
                if lines_drawn > 0:
                    sys.stdout.write(f"\n\033[{lines_drawn}A")
                    for _ in range(lines_drawn):
                        sys.stdout.write("\033[2K\n")
                    sys.stdout.write(f"\033[{lines_drawn}A")
                print(f"  {_dim('İptal')}")
                sys.stdout.flush()
                return -1
    except KeyboardInterrupt:
        print()
        return -1


# ── Input yardımcıları ────────────────────────────────────────

def _ask(prompt: str, required: bool = True, default: str = "") -> str:
    import sys
    if not sys.stdin.isatty():
        return default
    prompt_str = f"  {prompt}" + (f" [{_dim(default)}]" if default else "") + ": "
    while True:
        try:
            val = input(prompt_str).strip()
            if not val and default:
                return default
            if not val and required:
                print(f"  {_red('❌')} Bu alan zorunlu.")
                continue
            return val
        except (KeyboardInterrupt, EOFError):
            print()
            return ""


# ── Firebase sorgusu ──────────────────────────────────────────

def _fetch_all_topics() -> list[dict]:
    """
    Tüm konuları Firebase'den çeker (filtre yok — client-side filtre).
    Composite index gerektirmez.
    """
    from core.firebase import query_collection
    try:
        docs = query_collection(
            "topics",
            filters=None,
            order_by=None,
            limit=100,
            descending=False,
        )
        if docs is None:
            log.warning("_fetch_all_topics: sorgu None döndü")
            return []
        return docs
    except Exception as e:
        log.warning("_fetch_all_topics başarısız: %s", e)
        return []


def list_topics(
    exam_type: str | None = None,
    course_code: str | None = None,
    department: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Konuları çeker ve filtreler."""
    docs = _fetch_all_topics()

    # Client-side filtrele
    result = []
    for doc in docs:
        if doc.get("status") == "rejected":
            continue
        if exam_type and doc.get("exam_type") != exam_type:
            continue
        if course_code and doc.get("course_code", "").upper() != course_code.upper():
            continue
        if department and doc.get("department") != department:
            continue
        result.append(doc)

    # Sırala: onaylı önce, sonra tarihe göre
    result.sort(key=lambda x: (
        x.get("status") != "approved",
        x.get("submitted_at", ""),
    ), reverse=False)
    result.reverse()

    return result[:limit]


# ── Güven skoru ───────────────────────────────────────────────

def _trust_score(up: int, down: int) -> float:
    total = up + down
    return round((up / total) * 10, 1) if total > 0 else 5.0


def _trust_label(score: float, status: str) -> str:
    if status == "approved":
        return _green("✅ Onaylı")
    if status == "rejected":
        return _red("❌ Reddedildi")
    if score >= 8:   return _green(f"⭐ {score}/10")
    if score >= 6:   return _yellow(f"👍 {score}/10")
    if score >= 4:   return _dim(f"⚪ {score}/10")
    return _red(f"⚠️  {score}/10")


# ── Konuları yazdır ───────────────────────────────────────────

def print_topics(topics: list[dict]):
    if not topics:
        print(f"\n  {_dim('Henüz konu girilmemiş.')}")
        return
    print()
    for i, t in enumerate(topics, 1):
        score  = _trust_score(t.get("votes_up", 0), t.get("votes_down", 0))
        label  = _trust_label(score, t.get("status", "active"))
        tur    = t.get("exam_type", "?").upper()
        ders   = t.get("course_code", "?")
        ad     = t.get("course_name", "")[:25]
        bolum  = t.get("department", "")[:22]
        sinif  = t.get("class_year", "?")
        sube   = t.get("section", "")
        tarih  = (t.get("submitted_at") or "")[:10]
        tid    = (t.get("_id") or "")[:8]
        kaynak = t.get("source_type", "")

        # Başlık
        sube_str = f" · Şube {sube}" if sube else ""
        print(f"  {_bold(_yellow(f'[{i}]'))} {_cyan(f'{ders}')}"
              f"  {_bold(_magenta(tur))}"
              f"  {_bold(ad) if ad else ''}"
              f"  {_dim(f'{bolum} · {sinif}.sınıf{sube_str}')}")
        print(f"       {label}  {_dim(f'#{tid}  {tarih}  kaynak:{kaynak}')}")

        # Konular
        raw = t.get("raw_text", "")
        tlist = t.get("topics_list", [])

        if raw:
            # Ham metin göster (serbest format)
            for satir in raw.splitlines():
                satir = satir.strip()
                if satir:
                    print(f"       {satir}")
        elif tlist:
            for konu in tlist:
                if str(konu).strip():
                    print(f"       • {konu}")

        note = t.get("note", "")
        if note:
            print(f"       {_dim('Not: ' + note)}")

        up   = t.get("votes_up",   0)
        down = t.get("votes_down", 0)
        print(f"       {_green(f'▲{up}')}  {_red(f'▼{down}')}  "
              f"{_dim('  oy vermek için: alms konular --oyla ' + tid)}")
        print(f"  {_dim('─' * 68)}")
    print()


# ── Konu ekleme ───────────────────────────────────────────────

_MAX_TOPIC_CHARS = 500


def submit_topic(student_no: str) -> bool:
    from core.firebase import add_document, student_hash, is_configured

    if not is_configured():
        print("\n  ⚠️  Firebase bağlantısı kurulmamış.")
        print("  Kurmak için: alms konular --setup\n")
        return False

    print(f"\n  {_bold('── Sınav Konusu Ekle ────────────────────────────────')}")
    print(f"  {_dim('Ctrl+C ile iptal')}\n")

    # 1. Sınav türü — arrow key ile
    tur_labels = ["Vize", "Final", "Quiz", "Bütünleme"]
    tur_vals   = ["vize", "final", "quiz", "butunleme"]
    tur_idx = _arrow_menu("Sınav türü seçin:", tur_labels)
    if tur_idx < 0:
        return False
    exam_type = tur_vals[tur_idx]
    print(f"  Tür: {_yellow(exam_type.upper())}\n")

    # 2. Fakülte — arrow key ile
    fac_labels = list(IGU_FACULTIES.keys())
    fac_idx = _arrow_menu("Fakülte seçin:", fac_labels)
    if fac_idx < 0:
        return False
    fac_key = fac_labels[fac_idx]

    if fac_key == "Diğer / Manuel Gir":
        faculty = _ask("Fakülte adı")
        if not faculty:
            return False
    else:
        faculty = fac_key
    print(f"  Fakülte: {faculty}\n")

    # 3. Bölüm — arrow key ile (fakülteye göre)
    dept_list = IGU_FACULTIES.get(fac_key, [])
    if dept_list:
        dept_list = dept_list + ["Diğer / Manuel Gir"]
        dept_idx = _arrow_menu("Bölüm seçin:", dept_list)
        if dept_idx < 0:
            return False
        if dept_list[dept_idx] == "Diğer / Manuel Gir":
            department = _ask("Bölüm adı")
            if not department:
                return False
        else:
            department = dept_list[dept_idx]
    else:
        department = _ask("Bölüm adı")
        if not department:
            return False
    print(f"  Bölüm: {department}\n")

    # 4. Sınıf ve şube
    sinif_idx = _arrow_menu("Sınıf seçin:", ["1. Sınıf", "2. Sınıf", "3. Sınıf", "4. Sınıf"])
    if sinif_idx < 0:
        return False
    class_year = str(sinif_idx + 1)
    section = _ask("Şube (A/B/C... boş bırakılabilir)", required=False)
    print()

    # 5. Ders kodu
    course_code = _ask("Ders kodu (örn: FIZ108)").upper()
    if not course_code:
        return False
    course_name = _ask("Ders adı  (örn: Fizik II)", required=False)
    print()

    # 6. Konu giriş modu — arrow key ile
    mod_idx = _arrow_menu(
        "Konuları nasıl gireceksiniz?",
        [
            "Tek mesaj  — Her şeyi bir arada yazın",
            "Liste      — Konu konu ekleyin",
        ]
    )
    if mod_idx < 0:
        return False

    raw_text   = ""
    topics_list = []

    if mod_idx == 0:
        # Tek mesaj modu
        print(f"\n  {_bold('Konuları yazın')}:")
        print(f"  {_dim('Örn: Kirchhoff yasaları, RC devre analizi, manyetik alan')}")
        print(f"  {_dim(f'Birden fazla satır yazabilirsiniz. Bitirmek için boş satır bırakın. (maks. {_MAX_TOPIC_CHARS} karakter)')}\n")
        lines = []
        while True:
            try:
                import sys
                line = input("  > ").strip() if sys.stdin.isatty() else ""
            except (KeyboardInterrupt, EOFError):
                break
            if not line:
                if lines:
                    break
                print(f"  {_dim('En az bir şey yazın...')}")
                continue
            current_len = len("\n".join(lines + [line]))
            if current_len > _MAX_TOPIC_CHARS:
                print(f"  ⚠️  Karakter sınırına ulaşıldı ({_MAX_TOPIC_CHARS}). Bu satır eklenmedi.")
                break
            lines.append(line)
        if not lines:
            print("  ❌ Konu girilmedi.")
            return False
        raw_text = "\n".join(lines)
        # Virgülle ayrılmışsa listeye çevir de
        if "," in raw_text or ";" in raw_text:
            topics_list = [t.strip() for t in re.split(r"[,;]", raw_text) if t.strip()]
        else:
            topics_list = [l.strip() for l in lines if l.strip()]

    else:
        # Liste modu
        print(f"\n  {_bold('Konuları sırayla girin')} — bitirmek için boş bırakın:\n")
        while True:
            try:
                import sys
                konu = input(f"  • ").strip() if sys.stdin.isatty() else ""
            except (KeyboardInterrupt, EOFError):
                break
            if not konu:
                break
            topics_list.append(konu)
        if not topics_list:
            print("  ❌ Konu girilmedi.")
            return False
        raw_text = "; ".join(topics_list)

    # Karakter sınırı kontrolü
    if len(raw_text) > _MAX_TOPIC_CHARS:
        print(f"\n  ⚠️  Konu metni çok uzun: {len(raw_text)} karakter "
              f"(maks. {_MAX_TOPIC_CHARS}).")
        print(f"  Lütfen daha kısa yazın veya gereksiz ayrıntıları çıkarın.\n")
        return False

    # 7. Not
    print()
    note = _ask("Ek not (opsiyonel, örn: '1-6. haftalar arası')", required=False)

    # 8. Kaynak — arrow key ile
    src_labels = [v[1] for v in SOURCE_TYPES.values()]
    src_vals   = [v[0] for v in SOURCE_TYPES.values()]
    print()
    src_idx = _arrow_menu("Bilginin kaynağı:", src_labels)
    if src_idx < 0:
        return False
    source_type  = src_vals[src_idx]
    source_label = src_labels[src_idx]
    source_detail = _ask("Kaynak detayı (opsiyonel)", required=False)

    # 9. Özet + onay
    print(f"\n  {_bold('── Özet ──────────────────────────────────────────')}")
    print(f"  {_cyan(course_code)} {course_name}  "
          f"{_yellow(exam_type.upper())}  {department}  {class_year}.sınıf"
          + (f" Şube:{section}" if section else ""))
    if raw_text:
        print(f"  Konular:")
        for konu in topics_list:
            print(f"    • {konu}")
    print(f"  Kaynak: {source_label}")
    if note:
        print(f"  Not: {note}")
    print()

    import sys
    if not sys.stdin.isatty():
        return False
    try:
        onay = input("  Kaydet? [E/h]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return False
    if onay not in ("", "e", "evet", "y", "yes"):
        print("  İptal edildi.")
        return False

    # 10. Firebase'e kaydet
    now_dt = datetime.now(timezone.utc)
    now    = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    doc_id = add_document("topics", {
        "exam_type":     exam_type,
        "faculty":       faculty,
        "department":    department,
        "class_year":    class_year,
        "section":       section,
        "course_code":   course_code,
        "course_name":   course_name,
        "topics_list":   topics_list,
        "raw_text":      raw_text,
        "note":          note,
        "source_type":   source_type,
        "source_detail": source_detail,
        "submitted_by":  student_hash(student_no),
        "submitted_at":  now,
        "votes_up":      0,
        "votes_down":    0,
        "status":        "active",
        "admin_note":    None,
    })

    if doc_id:
        # Rate limit güncelle (bir sonraki ekleme için cooldown başlat)
        try:
            from core.firebase import get_uid, set_document
            uid = get_uid()
            if uid:
                set_document("user_limits", uid, {"last_topic_at": now_dt})
        except Exception:
            pass
        print(f"\n  {_green('✅ Kaydedildi!')}  ID: {_dim(doc_id[:8])}")
        print(f"  {_dim('Diğer öğrenciler görebilir ve oy verebilir.')}\n")
        return True

    print(f"  {_red('❌')} Kayıt başarısız.")
    print(f"  {_dim('Olası nedenler:')}")
    print(f"  {_dim('• Son 30 dakikada zaten bir konu eklediniz (spam koruması)')}")
    print(f"  {_dim('• İnternet bağlantısı yok')}")
    print(f"  {_dim('• Firebase oturumu süresi dolmuş — alms çıkış && alms komutunu çalıştırın')}")
    return False


# ── Oylama ───────────────────────────────────────────────────

def vote_topic(topic_id_prefix: str, student_no: str) -> bool:
    from core.firebase import (
        query_collection, update_document, set_document,
        get_document, student_hash,
    )
    docs  = _fetch_all_topics()
    topic = next((t for t in docs if (t.get("_id") or "").startswith(topic_id_prefix)), None)
    if not topic:
        print(f"  ❌ Konu bulunamadı: {topic_id_prefix}")
        return False

    tid   = topic["_id"]
    shash = student_hash(student_no)
    existing = get_document("votes", f"{shash}_{tid}")
    if existing:
        print(f"  ⚠️  Bu konuya zaten oy verdiniz: {existing.get('vote','?')}")
        return False

    print(f"\n  {_cyan(topic.get('course_code','?'))} "
          f"{_yellow(topic.get('exam_type','').upper())}\n")
    tlist = topic.get("topics_list", [])
    for k in tlist:
        print(f"  • {k}")
    print()

    oy_idx = _arrow_menu("Oyunuz:", ["👍 Doğru — bilgi güvenilir", "👎 Yanlış — bilgi hatalı"])
    if oy_idx < 0:
        return False
    vote = "up" if oy_idx == 0 else "down"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    vote_ok = set_document("votes", f"{shash}_{tid}", {
        "student_hash": shash, "topic_id": tid,
        "vote": vote, "voted_at": now,
    })
    if not vote_ok:
        print(f"\n  {_red('❌')} Oy kaydedilemedi — bağlantı hatası veya izin sorunu.\n")
        return False

    up   = topic.get("votes_up",   0) + (1 if vote == "up"   else 0)
    down = topic.get("votes_down", 0) + (1 if vote == "down" else 0)
    score = _trust_score(up, down)
    update_document("topics", tid, {
        "votes_up": up, "votes_down": down,
        "trust_score": score,
    })

    emoji = _green("👍 Doğru") if vote == "up" else _red("👎 Yanlış")
    print(f"\n  {emoji} oyunuz kaydedildi.  Skor: {_trust_label(score, 'active')}\n")
    return True


# ── Admin ─────────────────────────────────────────────────────

def admin_review(topic_id_prefix: str, student_no: str, action: str, note: str = "") -> bool:
    from core.firebase import is_admin, update_document, student_hash

    admin, role, dept = is_admin(student_no)
    if not admin:
        print("  ❌ Admin yetkiniz yok.")
        return False

    docs  = _fetch_all_topics()
    topic = next((t for t in docs if (t.get("_id") or "").startswith(topic_id_prefix)), None)
    if not topic:
        print(f"  ❌ Konu bulunamadı: {topic_id_prefix}")
        return False

    if role == "dept" and dept and topic.get("department") != dept:
        print(f"  ❌ Bu konu sizin bölümünüze ait değil.")
        return False

    status = "approved" if action == "approve" else "rejected"
    now    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ok = update_document("topics", topic["_id"], {
        "status":      status,
        "admin_note":  note,
        "reviewed_at": now,
        "reviewed_by": student_hash(student_no),
    })
    if not ok:
        print(f"  {_red('❌')} Güncelleme başarısız — bağlantı veya izin hatası.\n")
        return False
    emoji = _green("✅ Onaylandı") if status == "approved" else _red("❌ Reddedildi")
    print(f"\n  {emoji}: {topic.get('course_code')} — {topic.get('exam_type','').upper()}\n")
    return True


# ── Ana giriş noktası ─────────────────────────────────────────

def topics_main(args=None, username: str = ""):
    from core.firebase import is_configured, setup_firebase

    if args and getattr(args, "setup", False):
        setup_firebase(as_admin=True)
        return

    if not is_configured():
        print(f"\n  {_yellow('⚠️  Firebase bağlantısı kurulmamış.')}")
        print(f"  {_dim('Kurmak için: alms konular --setup')}\n")
        return

    # Öğrenci no — önce parametre, sonra token
    student_no = str(username) if username and str(username) not in ("", "?", "None") else ""
    if not student_no:
        try:
            from core.auth import get_or_refresh_token as _gt
            _, uname = _gt()
            student_no = str(uname) if uname else ""
        except Exception:
            pass

    vote_id     = getattr(args, "oyla",  None) if args else None
    add_mode    = getattr(args, "ekle",  False) if args else False
    exam_type   = None
    course_code = getattr(args, "ders",  None) if args else None

    if args:
        if getattr(args, "vize",  False): exam_type = "vize"
        if getattr(args, "final", False): exam_type = "final"

    if vote_id:
        if not student_no:
            print("  ❌ Öğrenci bilgisi alınamadı — alms logout && alms setup deneyin.")
            return
        vote_topic(vote_id, student_no)
        return

    if add_mode:
        if not student_no:
            print("  ❌ Öğrenci bilgisi alınamadı — alms logout && alms setup deneyin.")
            return
        submit_topic(student_no)
        return

    # Listele
    print(f"\n  {_bold(_cyan('── Sınav Konuları ──'))}")
    if exam_type:
        print(f"  {_dim('Filtre: ' + exam_type.upper())}")
    if course_code:
        print(f"  {_dim('Ders: ' + course_code.upper())}")

    from utils.spinner import Spinner
    with Spinner("Konular yükleniyor..."):
        topics = list_topics(exam_type=exam_type, course_code=course_code)

    print_topics(topics)

    if not topics:
        print(f"  {_dim('İlk konuyu siz girin:')}  {_cyan('alms konular --ekle')}\n")
