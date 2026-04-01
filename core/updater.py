"""
core/updater.py — Güvenli güncelleme sistemi
"""
from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent


# ── Yedekleme ─────────────────────────────────────────────────

def _backup_config() -> list[Path]:
    from utils.paths import CONFIG_DIR
    backed = []
    targets = ["credentials.enc", "sessions.enc", "config.json",
               "obis_session", "manifest.json", "version.json"]
    for name in targets:
        src = CONFIG_DIR / name
        if src.exists():
            bak = src.with_suffix(src.suffix + ".bak")
            shutil.copy2(src, bak)
            backed.append(bak)
    return backed


def _restore_backups(backups: list[Path]):
    for bak in backups:
        if bak.exists():
            bak.replace(bak.with_suffix(""))


def _cleanup_backups(backups: list[Path]):
    for bak in backups:
        bak.unlink(missing_ok=True)


# ── Git ───────────────────────────────────────────────────────

def _git(args: list, timeout: int = 60) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["git"] + args, cwd=_ROOT,
            capture_output=True, timeout=timeout
        )
        out = (
            r.stdout.decode("utf-8", errors="replace") +
            r.stderr.decode("utf-8", errors="replace")
        ).strip()
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)


def _git_out(args: list, timeout: int = 5) -> str:
    try:
        r = subprocess.run(
            ["git"] + args, cwd=_ROOT,
            capture_output=True, timeout=timeout
        )
        # encoding='utf-8' + errors='replace' — Windows cp1252 bozulmasını önler
        out = r.stdout.decode("utf-8", errors="replace").strip()
        return out if r.returncode == 0 else ""
    except Exception:
        return ""


def _git_stash() -> bool:
    ok, _ = _git(["stash"], timeout=15)
    return ok


def _git_stash_pop():
    _git(["stash", "pop"], timeout=15)


def _git_pull() -> tuple[bool, str]:
    return _git(["pull", "origin", "main"], timeout=60)


# ── pip ───────────────────────────────────────────────────────

def _pip_install() -> tuple[bool, str]:
    req = _ROOT / "requirements.txt"
    if not req.exists():
        return True, ""

    if platform.system() == "Windows":
        venv_pip = _ROOT / ".venv" / "Scripts" / "pip.exe"
    else:
        venv_pip = _ROOT / ".venv" / "bin" / "pip"

    pip_cmd = str(venv_pip) if venv_pip.exists() else "pip"

    try:
        r = subprocess.run(
            [pip_cmd, "install", "-r", str(req), "--quiet"],
            capture_output=True, text=True, timeout=120
        )
        return r.returncode == 0, (r.stderr or r.stdout).strip()
    except Exception as e:
        return False, str(e)


# ── Versiyon güncelleme ───────────────────────────────────────

def _resolve_new_version(old_ver: str) -> tuple[str, str]:
    """
    git pull sonrası yeni versiyon ve build'i belirle.

    Mantık:
      - En son tag'in MAJOR.MINOR'ını al (örn: v1.4 → 1.4)
      - PATCH = o tag'den bu yana kaç commit var
      - Sonuç: 1.4.0, 1.4.1, 1.4.2 ... otomatik artar
      - Yeni tag atılırsa (v1.5) MAJOR.MINOR değişir

    Döner: (new_version, build_hash)
    """
    build = _git_out(["rev-parse", "--short", "HEAD"]) or "unknown"

    # En son tag'i bul
    tag = _git_out(["describe", "--tags", "--abbrev=0"]).lstrip("v")

    if not tag:
        # Tag hiç yok — eski versiyonu koru, sadece build güncelle
        return old_ver, build

    # Tag'den bu yana kaç commit var?
    patch = _git_out(["rev-list", "--count", f"v{tag}..HEAD"])

    if not patch.isdigit():
        # Sayım başarısız — tag'i olduğu gibi kullan
        return tag, build

    # MAJOR.MINOR tag'den, PATCH commit sayısından
    parts = tag.split(".")
    if len(parts) >= 2:
        major_minor = ".".join(parts[:2])  # örn: "1.4"
        new_ver = f"{major_minor}.{patch}"  # örn: "1.4.5"
    else:
        new_ver = f"{tag}.{patch}"

    return new_ver, build


def _get_changelog(old_ver: str) -> str:
    """Son commit mesajlarından changelog özeti üret."""
    try:
        # Tag varsa tag'den itibaren, yoksa son 5 commit
        tag = _git_out(["describe", "--tags", "--abbrev=0"]).lstrip("v")
        ref = f"v{old_ver}..HEAD" if tag and tag != old_ver else "-5"
        out = _git_out(["log", ref, "--oneline", "--no-merges"])
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        if not lines:
            return ""
        summary = "; ".join(l.split(" ", 1)[1] for l in lines[:3] if " " in l)
        if len(lines) > 3:
            summary += f" (+{len(lines)-3} daha)"
        return summary
    except Exception:
        return ""


# ── Otomasyon yenileme ────────────────────────────────────────

def _refresh_automation():
    try:
        from core.config import get as cfg_get
        from utils.scheduler import add_schedule, get_schedule_status
        from utils.paths import LOG_FILE
        if not get_schedule_status():
            return
        h = cfg_get("auto_sync_hour") or 8
        m = cfg_get("auto_sync_min") or 0
        courses = cfg_get("auto_sync_courses") or None
        add_schedule(h, m, str(LOG_FILE), courses)
        log.info("Otomasyon yenilendi: %02d:%02d", h, m)
    except Exception as e:
        log.warning("Otomasyon yenilenemedi: %s", e)


# ── Ana fonksiyon ─────────────────────────────────────────────

def perform_update() -> bool:
    """
    Güvenli güncelleme akışı:
    1. Config yedekle
    2. git stash (yerel değişiklik varsa)
    3. git pull
    4. pip install
    5. version.json güncelle (tag veya commit sayısından)
    6. Migration
    7. Otomasyon yenile
    8. Yedek temizle

    Hata → rollback. Döner: True/False
    """
    from utils.version import get_current_version, save_version
    old_ver = get_current_version()

    print(f"\n  📦 Güncelleme başlatılıyor... (mevcut: v{old_ver})\n")

    # 1. Yedek
    backups = _backup_config()

    # 2. Stash
    stashed = False
    ok, dirty = _git(["status", "--porcelain"], timeout=5)
    if ok and dirty:
        print("  📌 Yerel değişiklikler saklanıyor...")
        stashed = _git_stash()

    # 3. git pull
    print("  ⬇️  Kaynak kod güncelleniyor...")
    ok, err = _git_pull()
    if not ok:
        print(f"  ❌ git pull başarısız: {err}")
        if stashed:
            _git_stash_pop()
        _restore_backups(backups)
        return False
    print("  ✅ Kaynak kod güncellendi")

    if stashed:
        _git_stash_pop()

    # 4. pip
    print("  📦 Bağımlılıklar güncelleniyor...")
    ok, err = _pip_install()
    if not ok:
        print(f"  ⚠️  Paketler güncellenemedi: {err}")
        print("     Manuel: pip install -r requirements.txt")
    else:
        print("  ✅ Bağımlılıklar güncellendi")

    # 5. version.json güncelle
    print("  🏷️  Sürüm belirleniyor...")
    new_ver, build = _resolve_new_version(old_ver)
    changelog = _get_changelog(old_ver)
    save_version(new_ver, build, changelog)

    if new_ver != old_ver:
        print(f"  ✅ Sürüm: v{old_ver} → v{new_ver} ({build})")
    else:
        print(f"  ✅ Build güncellendi: {build}")

    # 6. Migration
    print("  🔄 Veri formatları kontrol ediliyor...")
    try:
        from core.migration import run_migrations
        run_migrations()
        print("  ✅ Migration tamamlandı")
    except ImportError:
        pass
    except Exception as e:
        print(f"  ⚠️  Migration uyarısı: {e}")

    # 7. Otomasyon
    print("  🕐 Otomasyon güncelleniyor...")
    _refresh_automation()

    # 8. Temizlik
    _cleanup_backups(backups)

    # Sonuç
    from utils.version import get_current_version as gcv
    gcv.cache_clear()
    final_ver = gcv()
    print(f"\n  ✅ Güncelleme tamamlandı: v{old_ver} → v{final_ver}\n")

    # Changelog göster
    _show_changelog(old_ver)
    return True


def _show_changelog(old_ver: str):
    try:
        tag = _git_out(["describe", "--tags", "--abbrev=0"]).lstrip("v")
        ref = f"v{old_ver}..HEAD" if tag and tag != old_ver else "-5"
        out = _git_out(["log", ref, "--oneline", "--no-merges"])
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        if lines:
            print("  📋 Değişiklikler:")
            for line in lines[:8]:
                print(f"     • {line}")
            if len(lines) > 8:
                print(f"     ... ve {len(lines)-8} commit daha")
            print()
    except Exception:
        pass
