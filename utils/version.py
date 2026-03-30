"""
utils/version.py — Sürüm yönetimi
"""
from __future__ import annotations

import subprocess
import logging
from pathlib import Path
from functools import lru_cache

log = logging.getLogger(__name__)

# Proje kökü: bu dosya utils/ altında, bir üst dizin kök
_ROOT = Path(__file__).parent.parent
_VERSION_FILE = _ROOT / "version.txt"

# ── Mevcut sürüm ──────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_current_version() -> str:
    """
    Mevcut uygulama sürümünü döner.
    Öncelik: version.txt → git tag → git hash → "unknown"
    """
    # 1. version.txt
    if _VERSION_FILE.exists():
        v = _VERSION_FILE.read_text().strip()
        if v:
            return v

    # 2. git tag
    try:
        r = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            return r.stdout.strip().lstrip("v")
    except Exception:
        pass

    # 3. git hash (kısa)
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


# ── Güncelleme kontrolü ───────────────────────────────────────

def check_update_available() -> tuple[bool, int, str]:
    """
    Uzak repo'da güncelleme var mı kontrol eder.
    Döner: (var_mi, commit_sayisi, mevcut_versiyon)

    Ağ/git hatasında (False, 0, "") döner — sessiz başarısız.
    """
    try:
        # Uzaktan bilgi al (ağ erişimi — kısa timeout)
        fetch = subprocess.run(
            ["git", "fetch", "origin", "main", "--dry-run"],
            cwd=_ROOT, capture_output=True, timeout=8
        )
        if fetch.returncode != 0:
            return False, 0, ""

        # Kaç commit geride?
        behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        if behind.returncode != 0:
            return False, 0, ""

        count = int(behind.stdout.strip() or "0")
        if count == 0:
            return False, 0, ""

        # Uzaktaki son tag'i bul
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
    """
    v1 < v2 → -1
    v1 == v2 → 0
    v1 > v2 → 1
    """
    def _parse(v: str) -> tuple:
        try:
            return tuple(int(x) for x in v.strip().lstrip("v").split("."))
        except ValueError:
            return (0, 0, 0)

    a, b = _parse(v1), _parse(v2)
    if a < b:
        return -1
    if a > b:
        return 1
    return 0
