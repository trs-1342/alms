"""
core/migration.py — Format geçiş yöneticisi

Uygulama başlangıcında eski format dosyaları yeni formata otomatik yükseltir.
Her migration idempotent — tekrar çalıştırmak güvenlidir.

Kapsanan geçişler:
  config_schema  — config.json'a yeni alan eklendiyse varsayılan değer doldur
  obis_session   — plain-text session → Fernet şifreli
  firebase_token — anonymous token → email/password tabanlı (temizle, yeniden auth)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def run_migrations() -> None:
    """
    Tüm migration'ları sırasıyla çalıştır.
    alms.py main() başında, kilit alınmadan önce çağrılır.
    Herhangi birinin başarısız olması diğerlerini durdurmaz.
    """
    for fn in (_migrate_config_schema, _migrate_obis_session, _migrate_firebase_token):
        try:
            fn()
        except Exception as e:
            log.warning("migration hatası [%s]: %s", fn.__name__, e)


# ── config.json schema migrasyonu ─────────────────────────────

def _migrate_config_schema() -> None:
    """
    DEFAULTS'ta tanımlı ama config.json'da olmayan alanları ekle.
    Eski kurulumlar KeyError atmaz; yeni özellikler sorunsuz çalışır.
    """
    from utils.paths import CONFIG_FILE
    if not Path(CONFIG_FILE).exists():
        return

    from core.config import DEFAULTS, load, save
    cfg = load()
    missing = {k: v for k, v in DEFAULTS.items() if k not in cfg}
    if missing:
        cfg.update(missing)
        save(cfg)
        log.info("config migration: %d eksik alan eklendi → %s",
                 len(missing), list(missing.keys()))


# ── obis_session migrasyonu ────────────────────────────────────

def _migrate_obis_session() -> None:
    """
    obis_session plain-text formatından Fernet şifreli formata geç.
    Zaten şifreli ise sessizce atlar.
    """
    from utils.paths import CONFIG_DIR
    session_file = CONFIG_DIR / "obis_session"
    if not session_file.exists():
        return

    raw = session_file.read_bytes()
    if not raw:
        return

    # Zaten geçerli Fernet token mu?
    try:
        from core.auth import _fernet
        from cryptography.fernet import InvalidToken
        _fernet().decrypt(raw)
        return  # Geçerli şifreli format — migration gerekmez
    except Exception:
        pass

    # Plain-text gibi görünüyor — re-encrypt et
    try:
        val = raw.decode(errors="ignore").strip()
        if len(val) < 10:
            return  # Çok kısa, geçersiz

        from core.auth import _fernet
        session_file.write_bytes(_fernet().encrypt(val.encode()))
        session_file.chmod(0o600)
        log.info("obis_session migration: plain-text → Fernet şifreli")
    except Exception as e:
        log.warning("obis_session migration hatası: %s", e)


# ── firebase_token migrasyonu ──────────────────────────────────

def _migrate_firebase_token() -> None:
    """
    Eski anonymous Firebase token'larını temizle.

    Yeni token formatı '_auth_method': 'email' alanı içerir.
    Bu alan yoksa anonymous (eski) token — temizle.
    Bir sonraki firebase_login(student_no) çağrısı email/password
    hesabı oluşturur veya mevcut hesaba giriş yapar.
    """
    from utils.paths import CONFIG_DIR
    token_file = CONFIG_DIR / "firebase_token.json"
    if not token_file.exists():
        return

    try:
        data = json.loads(token_file.read_text(encoding="utf-8"))
    except Exception:
        token_file.unlink(missing_ok=True)
        return

    if data.get("_auth_method") == "email":
        return  # Yeni format — migration gerekmez

    token_file.unlink(missing_ok=True)
    log.info("firebase_token migration: anonymous token temizlendi, "
             "bir sonraki başlangıçta yeni hesap oluşturulacak")
