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
               "obis_session", "manifest.json"]
    for name in targets:
        src = CONFIG_DIR / name
        if src.exists():
            bak = src.with_suffix(src.suffix + ".bak")
            shutil.copy2(src, bak)
            backed.append(bak)
            log.debug("Yedeklendi: %s", bak.name)
    return backed


def _restore_backups(backups: list[Path]):
    """Yedekleri orijinal konumlarına geri yükler."""
    for bak in backups:
        original = bak.with_suffix("")  # .bak kaldır
        if bak.exists():
            bak.replace(original)
            log.debug("Geri yüklendi: %s", original.name)


def _cleanup_backups(backups: list[Path]):
    """Başarılı güncelleme sonrası yedekleri sil."""
    for bak in backups:
        bak.unlink(missing_ok=True)


# ── Git işlemleri ─────────────────────────────────────────────

def _fetch_remote() -> bool:
    """origin/main'i gerçekten günceller (önizleme + hızlı pull için)."""
    r = subprocess.run(
        ["git", "fetch", "origin", "main"],
        cwd=_ROOT, capture_output=True, timeout=30
    )
    return r.returncode == 0


def _get_remote_version() -> str:
    """Fetch sonrası uzaktaki version.txt içeriğini okur."""
    try:
        r = subprocess.run(
            ["git", "show", "origin/main:version.txt"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _incoming_commits() -> list[str]:
    """HEAD..origin/main arası commit mesajlarını döner (fetch sonrası)."""
    try:
        r = subprocess.run(
            ["git", "log", "HEAD..origin/main", "--oneline", "--no-merges"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        return [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
    except Exception:
        return []


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
    """
    git pull origin main çalıştırır.
    Döner: (başarılı, hata_mesajı)
    """
    r = subprocess.run(
        ["git", "pull", "origin", "main"],
        cwd=_ROOT, capture_output=True, text=True, timeout=60
    )
    if r.returncode == 0:
        return True, ""
    return False, (r.stderr or r.stdout).strip()


# ── pip güncelleme ────────────────────────────────────────────

def _pip_install() -> tuple[bool, str]:
    req = _ROOT / "requirements.txt"
    if not req.exists():
        return True, ""  # requirements yok, geç

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
            return  # otomasyon kapalı, gerek yok

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
    Güvenli güncelleme işlemi:
    1. Yedek al
    2. git stash (yerel değişiklikler varsa)
    3. git pull
    4. pip install
    5. Migration çalıştır
    6. Otomasyon yenile
    7. Yedekleri temizle

    Herhangi bir adım başarısız olursa rollback yapar.
    Döner: True = başarılı, False = başarısız
    """
    from utils.version import get_current_version
    old_ver = get_current_version()

    print(f"\n  📦 Güncelleme başlatılıyor... (mevcut: v{old_ver})\n")

    # 0. Remote fetch + önizleme
    print("  🔍 Uzak repo kontrol ediliyor...")
    fetched = _fetch_remote()
    if fetched:
        remote_ver = _get_remote_version()
        if remote_ver and remote_ver != old_ver:
            print(f"  🆕 Yeni sürüm: v{old_ver} → v{remote_ver}\n")

        commits = _incoming_commits()
        if commits:
            print(f"  📋 Gelmekte olan değişiklikler ({len(commits)} commit):")
            for line in commits[:8]:
                print(f"     • {line}")
            if len(commits) > 8:
                print(f"     ... ve {len(commits) - 8} commit daha")
            print()
    else:
        print("  ⚠️  Uzak repo erişilemedi, doğrudan pull deneniyor...\n")

    # 1. Yedek al
    backups = _backup_config()
    if backups:
        log.debug("%d dosya yedeklendi", len(backups))

    # 2. git stash (yerel değişiklik varsa)
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
        # Kritik değil — devam et
    else:
        print("  ✅ Bağımlılıklar güncellendi")

    # 5. Migration
    print("  🔄 Veri formatları kontrol ediliyor...")
    try:
        from core.migration import run_migrations
        run_migrations()
        print("  ✅ Migration tamamlandı")
    except ImportError:
        log.debug("core/migration.py henüz yok, atlandı")
    except Exception as e:
        log.warning("Migration uyarısı: %s", e)
        print(f"  ⚠️  Migration uyarısı: {e}")

    # 6. Otomasyon yenile
    print("  🕐 Otomasyon güncelleniyor...")
    _refresh_automation()

    # 7. Yedekleri temizle
    _cleanup_backups(backups)

    # Yeni versiyon
    # lru_cache temizle — yeni version.txt okunsun
    from utils.version import get_current_version as gcv
    gcv.cache_clear()
    new_ver = gcv()

    ver_str = f"v{old_ver} → v{new_ver}" if old_ver != new_ver else f"v{new_ver}"
    print(f"\n  ✅ Güncelleme tamamlandı: {ver_str}\n")

    # Changelog özeti göster
    _show_changelog_summary(old_ver)

    return True


def _show_changelog_summary(old_ver: str):
    """Son güncelleme commit mesajlarını kısaca gösterir."""
    try:
        # Önce git tag ile dene (ör. v1.4.0..HEAD)
        r = subprocess.run(
            ["git", "log", f"v{old_ver}..HEAD", "--oneline", "--no-merges"],
            cwd=_ROOT, capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]

        # Tag yoksa veya boşsa ORIG_HEAD kullan (git pull sonrası her zaman set edilir)
        if not lines:
            r = subprocess.run(
                ["git", "log", "ORIG_HEAD..HEAD", "--oneline", "--no-merges"],
                cwd=_ROOT, capture_output=True, text=True, timeout=5
            )
            lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]

        if lines:
            print("  📋 Yüklenen değişiklikler:")
            for line in lines[:8]:
                print(f"     • {line}")
            if len(lines) > 8:
                print(f"     ... ve {len(lines) - 8} commit daha")
            print()
    except Exception:
        pass
