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


def _version_file() -> Path:
    try:
        from utils.paths import CONFIG_DIR
        return CONFIG_DIR / "version.json"
    except Exception:
        return Path.home() / ".config" / "alms" / "version.json"


# ── Git yardımcıları ──────────────────────────────────────────

def _git(args: list, timeout: int = 5) -> str:
    """Git komutu çalıştır, stdout döner. Hata → boş string."""
    try:
        r = subprocess.run(
            ["git"] + args, cwd=_ROOT,
            capture_output=True, timeout=timeout
        )
        out = r.stdout.decode("utf-8", errors="replace").strip()
        return out if r.returncode == 0 else ""
    except Exception:
        return ""


def _current_build() -> str:
    """Mevcut commit hash (kısa)."""
    return _git(["rev-parse", "--short", "HEAD"]) or "unknown"


def _current_tag() -> str:
    """En son git tag (v prefix'siz). Tag yoksa boş."""
    tag = _git(["describe", "--tags", "--abbrev=0"])
    return tag.lstrip("v") if tag else ""


def _remote_tag() -> str:
    """origin/main üzerindeki en son tag. Tag yoksa boş."""
    tag = _git(["describe", "--tags", "--abbrev=0", "origin/main"])
    return tag.lstrip("v") if tag else ""


def _commits_behind() -> int:
    """origin/main'e göre kaç commit gerideyiz."""
    out = _git(["rev-list", "--count", "HEAD..origin/main"])
    try:
        return int(out)
    except ValueError:
        return 0


# ── version.json okuma/yazma ──────────────────────────────────

def _read() -> dict:
    vf = _version_file()
    if vf.exists():
        try:
            return json.loads(vf.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write(data: dict):
    vf = _version_file()
    vf.parent.mkdir(parents=True, exist_ok=True)
    vf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        vf.chmod(0o600)
    except Exception:
        pass  # Windows'ta chmod yok
    get_current_version.cache_clear()


# ── Public API ────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_current_version() -> str:
    """
    Mevcut sürümü döner.
    Öncelik: version.json → git tag + commit sayısı → git hash → "unknown"

    Versiyon formatı: MAJOR.MINOR.PATCH
      MAJOR.MINOR → en son git tag'den
      PATCH       → o tag'den bu yana commit sayısı
    """
    # 1. version.json varsa onu kullan (alms update sonrası set edilir)
    data = _read()
    if data.get("version"):
        return data["version"]

    # 2. Git tag + commit sayısından hesapla
    tag = _current_tag()
    if tag:
        patch = _git(["rev-list", "--count", f"v{tag}..HEAD"])
        if patch.isdigit():
            parts = tag.split(".")
            major_minor = ".".join(parts[:2]) if len(parts) >= 2 else tag
            return f"{major_minor}.{patch}"
        return tag

    # 3. Commit hash fallback
    build = _current_build()
    return f"dev-{build}" if build != "unknown" else "unknown"


def get_version_info() -> dict:
    """Tam sürüm bilgisi: version, build, updated_at, changelog."""
    data = _read()
    # build her zaman güncel olsun
    if not data.get("build"):
        data["build"] = _current_build()
    return data


def init_version_if_missing():
    """İlk kurulumda version.json yoksa oluşturur."""
    vf = _version_file()
    if vf.exists():
        return
    tag = _current_tag()
    ver = tag if tag else "1.4.0"
    save_version(ver, _current_build(), "İlk kurulum")


def save_version(version: str, build: str = "", changelog: str = ""):
    """version.json'u günceller. Güncelleme sonrası çağrılır."""
    data = {
        "version":    version,
        "build":      build or _current_build(),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "changelog":  changelog,
    }
    _write(data)
    log.debug("Sürüm kaydedildi: v%s (%s)", version, data["build"])


# ── Güncelleme kontrolü ───────────────────────────────────────

def check_update_available() -> tuple[bool, int, str]:
    """
    Uzak repo'da güncelleme var mı kontrol eder.
    Döner: (var_mi, commit_sayisi, uzak_versiyon)
    Ağ hatasında (False, 0, "") döner — sessiz başarısız.
    """
    try:
        # fetch — ağ isteği
        r = subprocess.run(
            ["git", "fetch", "origin", "main", "--dry-run"],
            cwd=_ROOT, capture_output=True, timeout=8
        )
        if r.returncode != 0:
            return False, 0, ""

        count = _commits_behind()
        if count == 0:
            return False, 0, ""

        remote_ver = _remote_tag()
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
