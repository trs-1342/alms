"""
core/cache.py — Çevrimdışı OBİS veri önbelleği
Ağ bağlantısı olmadan akademik verilere erişim sağlar.

Önbelleklenen veriler:
  sinav       → sınav tarihleri (list[dict])
  notlar      → ders notları    (list[dict])
  transkript  → transkript      (list[dict])
  program     → ders programı   (list[dict])
  devamsizlik → devamsızlık     (list[dict])
  duyurular   → duyurular       (list[dict])
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from utils.paths import CONFIG_DIR, ensure_secure_dir

CACHE_DIR = CONFIG_DIR / "cache"

_LABELS = {
    "tr": {
        "sinav":       "Sınav Tarihleri",
        "notlar":      "Ders Notları",
        "transkript":  "Transkript",
        "program":     "Ders Programı",
        "devamsizlik": "Devamsızlık",
        "duyurular":   "Duyurular",
    },
    "en": {
        "sinav":       "Exam Schedule",
        "notlar":      "Grades",
        "transkript":  "Transcript",
        "program":     "Course Schedule",
        "devamsizlik": "Attendance",
        "duyurular":   "Announcements",
    },
}

ALL_KEYS = list(_LABELS["tr"].keys())


def _lang() -> str:
    try:
        from core.config import get
        return get("language") or "tr"
    except Exception:
        return "tr"


def get_label(key: str) -> str:
    lang = _lang()
    return _LABELS.get(lang, _LABELS["tr"]).get(key, key)


def _cache_file(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def save(key: str, data) -> None:
    """Veriyi önbelleğe kaydet (JSON)."""
    ensure_secure_dir(CACHE_DIR)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    path = _cache_file(key)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")
    if hasattr(path, "chmod"):
        try:
            path.chmod(0o600)
        except Exception:
            pass


def load(key: str) -> tuple:
    """
    Önbellekten veri yükle.
    Döner: (data, updated_at_str) veya (None, None) bulunamadıysa.
    """
    path = _cache_file(key)
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("data"), payload.get("updated_at")
    except Exception:
        return None, None


def has(key: str) -> bool:
    """Önbellekte veri var mı?"""
    return _cache_file(key).exists()


def age_hours(key: str) -> float | None:
    """Önbellek kaç saat önce güncellendi? Yoksa None."""
    _, updated_at = load(key)
    if not updated_at:
        return None
    try:
        t = datetime.fromisoformat(updated_at)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - t
        return delta.total_seconds() / 3600
    except Exception:
        return None


def is_stale(key: str, max_hours: float = 24.0) -> bool:
    """Önbellek `max_hours` saatten eski mi?"""
    h = age_hours(key)
    return h is None or h > max_hours


def clear(key: str | None = None) -> int:
    """Önbelleği temizle. key=None → hepsini temizle. Silinen dosya sayısını döner."""
    count = 0
    keys = [key] if key else ALL_KEYS
    for k in keys:
        path = _cache_file(k)
        if path.exists():
            path.unlink()
            count += 1
    return count


def status() -> list[dict]:
    """
    Tüm önbellek girişlerinin durumunu döner.
    [{"key", "label", "exists", "updated_at", "age_hours", "stale"}]
    """
    result = []
    now = datetime.now(timezone.utc)
    for k in ALL_KEYS:
        _, updated_at = load(k)
        h: float | None = None
        if updated_at:
            try:
                t = datetime.fromisoformat(updated_at)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                h = (now - t).total_seconds() / 3600
            except Exception:
                pass
        result.append({
            "key":        k,
            "label":      get_label(k),
            "exists":     updated_at is not None,
            "updated_at": updated_at,
            "age_hours":  h,
            "stale":      h is None or h > 24.0,
        })
    return result


def fetch_all(session, token: str | None = None) -> dict[str, bool]:
    """
    Tüm OBİS verilerini çek ve önbelleğe kaydet.
    Döner: {key: başarılı mı}
    """
    from core.obis import (
        get_sinav_tarihleri, get_notlar, get_transkript,
        get_ders_programi, get_devamsizlik,
        get_obis_duyurular, get_lms_duyurular,
    )
    results = {}

    def _try(key, fn, *args):
        try:
            data = fn(*args)
            if data:
                save(key, data)
                results[key] = True
            else:
                results[key] = False
        except Exception:
            results[key] = False

    if session:
        _try("sinav",       get_sinav_tarihleri, session)
        _try("notlar",      get_notlar,          session)
        _try("transkript",  get_transkript,       session)
        _try("program",     get_ders_programi,    session)
        _try("devamsizlik", get_devamsizlik,      session)

        obis_d = []
        try:
            obis_d = get_obis_duyurular(session)
        except Exception:
            pass
        lms_d = []
        if token:
            try:
                lms_d = get_lms_duyurular(token)
            except Exception:
                pass
        combined = {"obis": obis_d, "lms": lms_d}
        if obis_d or lms_d:
            save("duyurular", combined)
            results["duyurular"] = True
        else:
            results["duyurular"] = False
    else:
        for k in ALL_KEYS:
            results[k] = False

    return results
