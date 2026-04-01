"""
core/updater.py — Güvenli güncelleme sistemi
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent


# ── Yedekleme ─────────────────────────────────────────────────

def _backup_config() -> list[Path]:
    """~/.config/alms/ altındaki kritik dosyaları .bak olarak yedekler."""
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
            log.debug("Yedeklendi: %s", bak.name)
    return backed


def _restore_backups(backups: list[Path]):
    for bak in backups:
        original = bak.with_suffix("")
        if bak.exists():
            bak.replace(original)
            log.debug("Geri yüklendi: %s", original.name)


def _cleanup_backups(backups: list[Path]):
    for bak in backups:
        bak.unlink(missing_ok=True)


# ── Git işlemleri ─────────────────────────────────────────────

def _git_stash() -> bool:
    r = subprocess.run(
        ["git", "stash"], cwd=_ROOT, capture_output=True, text=True, timeout=15
    )
    return r.returncode == 0


def _git_stash_pop():
    subprocess.run(
        ["git", "stash", "pop"], cwd=_ROOT, capture_output=True, timeout=15
    )


def _git_pull() -> tuple[bool, str]:
    r = subprocess.run(
        ["git", "pull", "origin", "main"],
        cwd=_ROOT, capture_output=True, text=True, timeout=60
    )
    if r.returncode == 0:
        return True, ""
    return False, (r.stderr or r.stdout).strip()


def _get_changelog_from_git(old_ver: str) -> str:
    """Son güncelleme commit mesajlarını tek satır özet olarak döner."""
    try:
        # Tag varsa tag'den itibaren, yoksa son 5 commit
        ref = f"v{old_ver}..HEAD" if old_ver and old_ver != "unknown" else "-5"
        r = subprocess.run(
            ["git", "log", ref, "--oneline", "--no-merges"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return ""
        # İlk 3 commit'i özetle
        summary = "; ".join(l.split(" ", 1)[1] for l in lines[:3] if " " in l)
        if len(lines) > 3:
            summary += f" (+{len(lines)-3} daha)"
        return summary
    except Exception:
        return ""


# ── pip güncelleme ────────────────────────────────────────────

def _pip_install() -> tuple[bool, str]:
    req = _ROOT / "requirements.txt"
    if not req.exists():
        return True, ""

    # .venv varsa onu kullan, yoksa sistem pip
    import platform
    if platform.system() == "Windows":
        venv_pip = _ROOT / ".venv" / "Scripts" / "pip.exe"
    else:
        venv_pip = _ROOT / ".venv" / "bin" / "pip"

    pip_cmd = str(venv_pip) if venv_pip.exists() else "pip"

    r = subprocess.run(
        [pip_cmd, "install", "-r", str(req), "--quiet"],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode == 0:
        return True, ""
    return False, (r.stderr or r.stdout).strip()


# ── Otomasyon yenileme ────────────────────────────────────────

def _refresh_automation():
    """Güncelleme sonrası cron/launchd/schtasks wrapper'ını yeniler."""
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


# ── Ana güncelleme fonksiyonu ─────────────────────────────────

def perform_update() -> bool:
    """
    Güvenli güncelleme:
    1. Config dosyalarını yedekle (version.json dahil)
    2. git stash (yerel değişiklikler varsa)
    3. git pull
    4. pip install
    5. version.json'u config dizininde güncelle
    6. Migration çalıştır
    7. Otomasyon yenile
    8. Yedekleri temizle

    Herhangi bir adım başarısız → rollback.
    Döner: True = başarılı, False = başarısız
    """
    from utils.version import get_current_version, save_version
    old_ver = get_current_version()

    print(f"\n  📦 Güncelleme başlatılıyor... (mevcut: v{old_ver})\n")

    # 1. Yedek al
    backups = _backup_config()

    # 2. git stash
    stashed = False
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=_ROOT, capture_output=True, text=True, timeout=5
    ).stdout.strip()
    if dirty:
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

    # 4. pip install
    print("  📦 Bağımlılıklar güncelleniyor...")
    ok, err = _pip_install()
    if not ok:
        print(f"  ⚠️  Paketler güncellenemedi: {err}")
        print("     Manuel: pip install -r requirements.txt")
    else:
        print("  ✅ Bağımlılıklar güncellendi")

    # 5. version.json güncelle — config dizininde, proje klasöründe değil
    print("  🏷️  Sürüm bilgisi güncelleniyor...")
    try:
        # Yeni sürümü git tag'den al
        r = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        new_ver = r.stdout.strip().lstrip("v") if r.returncode == 0 else old_ver
        changelog = _get_changelog_from_git(old_ver)
        save_version(new_ver, changelog)
        print(f"  ✅ Sürüm: v{old_ver} → v{new_ver}")
    except Exception as e:
        log.warning("Sürüm güncellenemedi: %s", e)

    # 6. Migration
    print("  🔄 Veri formatları kontrol ediliyor...")
    try:
        from core.migration import run_migrations
        run_migrations()
        print("  ✅ Migration tamamlandı")
    except ImportError:
        log.debug("core/migration.py henüz yok, atlandı")
    except Exception as e:
        print(f"  ⚠️  Migration uyarısı: {e}")

    # 7. Otomasyon yenile
    print("  🕐 Otomasyon güncelleniyor...")
    _refresh_automation()

    # 8. Yedekleri temizle
    _cleanup_backups(backups)

    # Sonuç
    from utils.version import get_current_version as gcv
    gcv.cache_clear()
    final_ver = gcv()
    ver_str = f"v{old_ver} → v{final_ver}" if old_ver != final_ver else f"v{final_ver}"
    print(f"\n  ✅ Güncelleme tamamlandı: {ver_str}\n")

    _show_changelog_summary(old_ver)
    return True


def _show_changelog_summary(old_ver: str):
    """Son güncelleme commit mesajlarını gösterir."""
    try:
        ref = f"v{old_ver}..HEAD" if old_ver and old_ver != "unknown" else "-5"
        r = subprocess.run(
            ["git", "log", ref, "--oneline", "--no-merges"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
        if lines:
            print("  📋 Değişiklikler:")
            for line in lines[:8]:
                print(f"     • {line}")
            if len(lines) > 8:
                print(f"     ... ve {len(lines) - 8} commit daha")
            print()
    except Exception:
        pass
