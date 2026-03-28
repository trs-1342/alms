"""
utils/logger.py — Kullanıcı aksiyon audit log'u
Her aksiyon JSON satırı olarak activity.log'a yazılır.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from utils.paths import CONFIG_DIR, ensure_secure_dir

ACTIVITY_LOG = CONFIG_DIR / "activity.log"

_audit = logging.getLogger("alms.audit")
_audit.propagate = False  # ana logger'a taşma


def _setup_audit_handler():
    if _audit.handlers:
        return
    ensure_secure_dir(CONFIG_DIR)
    handler = logging.FileHandler(ACTIVITY_LOG, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _audit.addHandler(handler)
    _audit.setLevel(logging.INFO)


def log_action(action: str, detail: dict | None = None) -> None:
    """
    Kullanıcı aksiyonunu JSON olarak yaz.
    Örnek: log_action("sync", {"files": 12, "ok": 10})
    """
    _setup_audit_handler()
    entry = {
        "time":   datetime.now(timezone.utc).isoformat(),
        "action": action,
        "detail": detail or {},
    }
    _audit.info(json.dumps(entry, ensure_ascii=False))
