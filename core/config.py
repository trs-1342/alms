"""
core/config.py — Uygulama ayarları
"""
import json
import logging
from pathlib import Path

from utils.paths import CONFIG_DIR, CONFIG_FILE, DOWNLOAD_DIR, ensure_secure_dir

log = logging.getLogger(__name__)

DEFAULTS = {
    "language":       "tr",          # tr | en
    "download_dir":   str(DOWNLOAD_DIR),
    "parallel":       3,             # eş zamanlı indirme sayısı
    "retry_count":    3,
    "retry_delay":    2,             # saniye (exponential backoff)
    "chunk_size":     65536,         # bytes
    "log_level":      "INFO",
    "notify_desktop": True,          # indirme bitince bildirim
    "auto_sync":      False,
    "auto_sync_hour": 8,
    "auto_sync_min":  0,
    "auto_sync_courses": [],  # boş = tüm dersler
    "open_after_download": False,  # indirme sonrası klasörü otomatik aç, ["FIZ108","YZM102"] = sadece bunlar
}


def load() -> dict:
    ensure_secure_dir(CONFIG_DIR)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # Eksik anahtarları default ile doldur
            for k, v in DEFAULTS.items():
                data.setdefault(k, v)
            return data
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Config okunamadı, default kullanılıyor: %s", e)
    return dict(DEFAULTS)


def save(cfg: dict) -> None:
    ensure_secure_dir(CONFIG_DIR)
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.debug("Config kaydedildi.")


def get(key: str):
    return load().get(key, DEFAULTS.get(key))


def set_value(key: str, value) -> None:
    cfg = load()
    cfg[key] = value
    save(cfg)


def get_download_dir() -> Path:
    return Path(get("download_dir"))
