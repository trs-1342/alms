"""
core/notifier.py — Bildirim Otomasyonu
──────────────────────────────────────
Bağımsız otomasyon için: yeni duyuru, yeni sınav, yeni konu eklenince bildir.
Görülen öğeleri hash ile takip eder — aynı bildirimi tekrar göndermez.

Kullanım:
  alms notify-check          → durumu göster
  alms notify-check --quiet  → sessiz kontrol, sadece yeni öğe varsa bildirim
"""

import hashlib
import json
from pathlib import Path
from utils.paths import NOTIFIER_STATE_FILE, ensure_secure_dir, CONFIG_DIR

# ── Dil yardımcısı ────────────────────────────────────────────────────────────

def _lang() -> str:
    try:
        from core.config import get as _cfg
        return _cfg("language") or "tr"
    except Exception:
        return "tr"


_S: dict[str, dict[str, str]] = {
    "tr": {
        "title_duyuru":  "📢 {} yeni duyuru",
        "title_sinav":   "📅 {} yeni sınav eklendi",
        "title_konu":    "📚 {} yeni sınav konusu",
        "more":          "+{} daha...",
        "print_duyuru":  "Yeni duyuru ({})",
        "print_sinav":   "Yeni sınav ({})",
        "print_konu":    "Yeni konu ({})",
    },
    "en": {
        "title_duyuru":  "📢 {} new announcements",
        "title_sinav":   "📅 {} new exams added",
        "title_konu":    "📚 {} new exam topics",
        "more":          "+{} more...",
        "print_duyuru":  "New announcements ({})",
        "print_sinav":   "New exams ({})",
        "print_konu":    "New topics ({})",
    },
}


def _s(key: str, *args) -> str:
    lang = _lang()
    tmpl = _S.get(lang, _S["tr"]).get(key, key)
    return tmpl.format(*args) if args else tmpl


# ── State yönetimi ────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if not NOTIFIER_STATE_FILE.exists():
        return {"duyurular": [], "sinav": [], "konular": []}
    try:
        return json.loads(NOTIFIER_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"duyurular": [], "sinav": [], "konular": []}


def _save_state(state: dict) -> None:
    ensure_secure_dir(CONFIG_DIR)
    NOTIFIER_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        NOTIFIER_STATE_FILE.chmod(0o600)
    except Exception:
        pass


def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


# ── Yeni duyuru kontrolü ─────────────────────────────────────────────────────

def check_duyurular(session) -> list[str]:
    """
    Yeni OBİS duyurularını kontrol et.
    Döner: yeni duyuru başlıklarının listesi.
    """
    try:
        from core.obis import get_obis_duyurular
        duyurular = get_obis_duyurular(session)
    except Exception:
        return []

    state = _load_state()
    seen  = set(state.get("duyurular", []))
    new_items = []
    new_hashes = []

    for d in duyurular:
        key  = _hash(f"{d.get('baslik','')}|{d.get('tarih','')}")
        if key not in seen:
            new_items.append(d.get("baslik", "—"))
            new_hashes.append(key)

    if new_hashes:
        state["duyurular"] = list(seen | set(new_hashes))
        # Maksimum 200 hash tut
        state["duyurular"] = state["duyurular"][-200:]
        _save_state(state)

    return new_items


# ── Yeni sınav kontrolü ───────────────────────────────────────────────────────

def check_sinav(session) -> list[str]:
    """
    Yeni eklenen sınavları kontrol et.
    Döner: yeni sınav açıklamalarının listesi.
    """
    try:
        from core.obis import get_sinav_tarihleri
        sinavlar = get_sinav_tarihleri(session)
    except Exception:
        return []

    state = _load_state()
    seen  = set(state.get("sinav", []))
    new_items = []
    new_hashes = []

    for s in sinavlar:
        key = _hash(f"{s.get('kod','')}|{s.get('tarih','')}|{s.get('tur','')}")
        if key not in seen:
            new_items.append(
                f"{s.get('kod','')} — {s.get('ders','')} [{s.get('tur','')}] {s.get('tarih','')}"
            )
            new_hashes.append(key)

    if new_hashes:
        state["sinav"] = list(seen | set(new_hashes))
        state["sinav"] = state["sinav"][-200:]
        _save_state(state)

    return new_items


# ── Yeni konu kontrolü ────────────────────────────────────────────────────────

def check_konular() -> list[str]:
    """
    Firebase'deki yeni sınav konularını kontrol et.
    OBİS oturumu gerektirmez.
    Döner: yeni konu açıklamalarının listesi.
    """
    try:
        from core.firebase import is_configured
        if not is_configured():
            return []
        from core.topics import list_topics
        topics = list_topics(limit=50)
    except Exception:
        return []

    state = _load_state()
    seen  = set(state.get("konular", []))
    new_items = []
    new_hashes = []

    for t in topics:
        key = _hash(
            f"{t.get('course_code','')}|{t.get('topic','')[:60]}|{t.get('submitted_at','')}"
        )
        if key not in seen:
            label = f"{t.get('course_code','')} — {str(t.get('topic',''))[:50]}"
            new_items.append(label)
            new_hashes.append(key)

    if new_hashes:
        state["konular"] = list(seen | set(new_hashes))
        state["konular"] = state["konular"][-200:]
        _save_state(state)

    return new_items


# ── Ana kontrol fonksiyonu ────────────────────────────────────────────────────

def run_check(token: str | None = None, quiet: bool = True) -> dict:
    """
    Tüm kontrolleri çalıştır ve yeni öğeleri bildir.
    Döner: {"duyurular": [...], "sinav": [...], "konular": [...]}

    quiet=True → sadece bildirim gönder, terminale yazma
    quiet=False → terminale de yaz
    """
    from utils.notify import send as _notify
    from utils.network import check_alms_reachable

    result = {"duyurular": [], "sinav": [], "konular": []}

    # Ağ kontrolü — OBİS için gerekli; Firebase (konular) bağımsız çalışır
    reachable, _ = check_alms_reachable()

    # OBİS oturumu (sessiz) — yalnızca ALMS erişilebilirse
    session = None
    if reachable:
        try:
            from core.obis import get_session_silent
            session = get_session_silent()
        except Exception:
            pass

    # Duyurular
    if session:
        new_d = check_duyurular(session)
        if new_d:
            result["duyurular"] = new_d
            title = _s("title_duyuru", len(new_d))
            body  = "\n".join(new_d[:3])
            if len(new_d) > 3:
                body += f"\n{_s('more', len(new_d) - 3)}"
            _notify(title, body)
            if not quiet:
                print(f"  {_s('print_duyuru', len(new_d))}:")
                for d in new_d:
                    print(f"  · {d}")

    # Sınavlar
    if session:
        new_s = check_sinav(session)
        if new_s:
            result["sinav"] = new_s
            title = _s("title_sinav", len(new_s))
            body  = "\n".join(new_s[:3])
            if len(new_s) > 3:
                body += f"\n{_s('more', len(new_s) - 3)}"
            _notify(title, body)
            if not quiet:
                print(f"  {_s('print_sinav', len(new_s))}:")
                for s in new_s:
                    print(f"  · {s}")

    # Sınav konuları (Firebase — ALMS erişilebilirliğinden bağımsız)
    new_k = check_konular()
    if new_k:
        result["konular"] = new_k
        title = _s("title_konu", len(new_k))
        body  = "\n".join(new_k[:3])
        if len(new_k) > 3:
            body += f"\n{_s('more', len(new_k) - 3)}"
        _notify(title, body)
        if not quiet:
            print(f"  {_s('print_konu', len(new_k))}:")
            for k in new_k:
                print(f"  · {k}")

    return result


def reset_state(key: str | None = None) -> None:
    """State dosyasını sıfırla (test / manuel temizlik için)."""
    state = _load_state()
    if key and key in state:
        state[key] = []
    else:
        state = {"duyurular": [], "sinav": [], "konular": []}
    _save_state(state)
