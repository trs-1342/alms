"""
utils/version.py — Sürüm yönetimi
"""
from __future__ import annotations

import json
import subprocess
import logging
from pathlib import Path
from functools import lru_cache
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent

# Sürüm bilgisi config dizininde tutulur — proje klasöründe değil
def _version_file() -> Path:
    try:
        from utils.paths import CONFIG_DIR
        return CONFIG_DIR / "version.json"
    except Exception:
        return Path.home() / ".config" / "alms" / "version.json"

# Repo içindeki version.txt sadece kaynak referansı olarak kalır (opsiyonel)
_VERSION_TXT = _ROOT / "version.txt"


# ── Okuma ─────────────────────────────────────────────────────

def _read_version_json() -> dict:
    """~/.config/alms/version.json oku. Yoksa boş dict."""
    vf = _version_file()
    if vf.exists():
        try:
            return json.loads(vf.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


@lru_cache(maxsize=1)
def get_current_version() -> str:
    """
    Mevcut sürümü döner.
    Öncelik: version.json → version.txt → git tag → git hash → "unknown"
    """
    # 1. ~/.config/alms/version.json
    data = _read_version_json()
    if data.get("version"):
        return data["version"]

    # 2. Repo içindeki version.txt (fallback)
    if _VERSION_TXT.exists():
        v = _VERSION_TXT.read_text().strip()
        if v:
            return v

    # 3. git tag
    try:
        r = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            return r.stdout.strip().lstrip("v")
    except Exception:
        pass

    # 4. git hash
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            return f"dev-{r.stdout.strip()}"
    except Exception:
        pass

    return "unknown"


def get_version_info() -> dict:
    """Tam sürüm bilgisini döner (version, updated_at, changelog)."""
    return _read_version_json()


# ── Yazma ─────────────────────────────────────────────────────

def save_version(version: str, changelog: str = ""):
    """
    Yeni sürümü ~/.config/alms/version.json'a kaydeder.
    Güncelleme sonrası çağrılır.
    """
    vf = _version_file()
    vf.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version":    version,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "changelog":  changelog,
    }
    vf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    vf.chmod(0o600)

    # lru_cache'i temizle — yeni sürüm okunabilsin
    get_current_version.cache_clear()
    log.debug("Sürüm kaydedildi: %s", version)


def init_version_if_missing(version: str = "1.4.0"):
    """
    İlk kurulumda version.json yoksa oluşturur.
    alms setup veya uygulama ilk başlangıcında çağrılır.
    """
    vf = _version_file()
    if not vf.exists():
        save_version(version, "İlk kurulum")


# ── Güncelleme kontrolü ───────────────────────────────────────

def check_update_available() -> tuple[bool, int, str]:
    """
    Uzak repo'da güncelleme var mı kontrol eder.
    Döner: (var_mi, commit_sayisi, uzak_versiyon)

    Ağ/git hatasında (False, 0, "") döner — sessiz başarısız.
    """
    try:
        fetch = subprocess.run(
            ["git", "fetch", "origin", "main", "--dry-run"],
            cwd=_ROOT, capture_output=True, timeout=8
        )
        if fetch.returncode != 0:
            return False, 0, ""

        behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        if behind.returncode != 0:
            return False, 0, ""

        count = int(behind.stdout.strip() or "0")
        if count == 0:
            return False, 0, ""

        # Uzaktaki son tag
        remote_tag = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "origin/main"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        remote_ver = remote_tag.stdout.strip().lstrip("v") if remote_tag.returncode == 0 else ""

        return True, count, remote_ver

    except Exception as e:
        log.debug("Güncelleme kontrolü başarısız: %s", e)
        return False, 0, ""


def compare_versions(v1: str, v2: str) -> int:
    """v1 < v2 → -1 | v1 == v2 → 0 | v1 > v2 → 1"""
    def _parse(v: str) -> tuple:
        try:
            return tuple(int(x) for x in v.strip().lstrip("v").split("."))
        except ValueError:
            return (0, 0, 0)
    a, b = _parse(v1), _parse(v2)
    return -1 if a < b else (1 if a > b else 0)
