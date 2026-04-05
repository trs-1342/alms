"""
cli/wizard.py — Kurulum sihirbazı
Hem ilk kurulum hem de kurulu sistemde akıllı yönetim menüsü.
"""
import getpass
import platform
import sys
from pathlib import Path


def _clear():
    import os
    os.system("cls" if platform.system() == "Windows" else "clear")


def _ask(prompt: str, default: str = "") -> str | None:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"  {prompt}{hint}: ").strip()
        return val if val else default
    except KeyboardInterrupt:
        return None


def _ask_password(prompt: str) -> str | None:
    try:
        return getpass.getpass(f"  {prompt}: ")
    except KeyboardInterrupt:
        return None


def _banner(title: str):
    _clear()
    w = 52
    print("╔" + "═" * w + "╗")
    print(f"║  ALMS İndirici — {title:<{w-18}}║")
    print("╚" + "═" * w + "╝")
    print()


def _is_installed() -> bool:
    """Kurulum daha önce yapılmış mı?"""
    from utils.paths import CREDS_FILE
    return CREDS_FILE.exists()


# ─── Akıllı başlatma ─────────────────────────────────────────
def run_wizard(reconfigure: str | None = None) -> bool:
    """
    Kurulum sihirbazı giriş noktası.
    - Kurulu değilse: tam kurulum
    - Kuruluysa: yönetim menüsü
    - reconfigure: doğrudan bir alt menüyü aç
    """
    if reconfigure:
        _clear()
        if reconfigure == "credentials":
            return _reconfigure_credentials()
        elif reconfigure == "schedule":
            return _reconfigure_schedule()
        elif reconfigure == "path":
            return _reconfigure_path()

    if _is_installed():
        return _management_menu()
    else:
        return _fresh_install()


# ─── Yönetim menüsü (kurulu sistem) ─────────────────────────
def _management_menu() -> bool:
    """Kurulu sistemde ne yapmak istediğini sor."""
    from core.config import load as load_cfg
    from core.auth import get_active_session
    from utils.scheduler import get_schedule_status

    _banner("Sistem Yönetimi")

    cfg     = load_cfg()
    active  = get_active_session()
    sched   = get_schedule_status()

    # Mevcut durum özeti
    print("  Mevcut durum:")
    print(f"    İndirme klasörü : {cfg.get('download_dir', '?')}")
    print(f"    Token           : {'Geçerli' if active else 'Süresi dolmuş'}")
    print(f"    Otomasyon       : {sched or 'Kapalı'}")
    print()

    print("  Ne yapmak istiyorsun?")
    print()
    print("  [1] Kimlik bilgilerini güncelle")
    print("  [2] Otomasyon saatini değiştir")
    print("  [3] İndirme klasörünü değiştir")
    print("  [4] Güncelleme kontrol et  (git pull)")
    print("  [5] Sistemi tamamen sıfırla")
    print("  [6] ALMS'i kaldır")
    print("  [0] İptal")
    print()

    try:
        choice = input("  Seçiminiz: ").strip()
    except KeyboardInterrupt:
        return False

    if choice == "1":
        return _reconfigure_credentials()
    elif choice == "2":
        return _reconfigure_schedule()
    elif choice == "3":
        return _reconfigure_path()
    elif choice == "4":
        return _update()
    elif choice == "5":
        return _reset()
    elif choice == "6":
        return _uninstall()
    return False


# ─── Kimlik güncelle ─────────────────────────────────────────
def _reconfigure_credentials() -> bool:
    _banner("Kimlik Bilgilerini Güncelle")
    print("  Mevcut kimlik bilgileri silinip yenileri kaydedilecek.")
    print()
    try:
        username = _ask("Kullanıcı adı")
        if username is None:
            return False
        password = _ask_password("Şifre")
        if password is None:
            return False

        print("\n  Giriş test ediliyor...")
        from core.auth import do_login, save_credentials, add_session, clear_sessions
        token = do_login(username, password)
        clear_sessions()
        save_credentials(username, password)
        add_session(username, token, source="reconfigure")
        print("  ✅ Kimlik bilgileri güncellendi!")
        _ask("Enter'a basın", "")
        return True
    except KeyboardInterrupt:
        print("\n  İptal edildi.")
        return False
    except Exception as e:
        print(f"  ❌ Hata: {e}")
        _ask("Enter'a basın", "")
        return False


# ─── Otomasyon saati güncelle ─────────────────────────────────
def _reconfigure_schedule() -> bool:
    _banner("Otomasyon Ayarı")
    from utils.scheduler import add_schedule, remove_schedule, get_schedule_status
    from utils.paths import LOG_FILE
    from core.config import set_value

    current = get_schedule_status()
    print(f"  Mevcut: {current or 'Kapalı'}\n")

    try:
        auto_raw = _ask("Otomasyon etkin olsun mu? [e/H]", "H")
        if auto_raw is None:
            return False
        auto = auto_raw.lower() in ("e", "y", "evet", "yes")

        if auto:
            h_raw = _ask("Saat (0-23)", "1")
            m_raw = _ask("Dakika (0-59)", "25")
            if h_raw is None or m_raw is None:
                return False
            h = int(h_raw) if h_raw.isdigit() and 0 <= int(h_raw) <= 23 else 1
            m = int(m_raw) if m_raw.isdigit() and 0 <= int(m_raw) <= 59 else 25
            ok = add_schedule(h, m, str(LOG_FILE))
            set_value("auto_sync", True)
            print(f"\n  {'✅ Ayarlandı: ' + f'{h:02d}:{m:02d}' if ok else '❌ Hata oluştu'}")
        else:
            remove_schedule()
            set_value("auto_sync", False)
            print("\n  ✅ Otomasyon devre dışı.")

        _ask("Enter'a basın", "")
        return True
    except KeyboardInterrupt:
        print("\n  İptal edildi.")
        return False


# ─── İndirme klasörü güncelle ────────────────────────────────
def _reconfigure_path() -> bool:
    _banner("İndirme Klasörü")
    from core.config import get_download_dir, set_value

    current = get_download_dir()
    print(f"  Mevcut: {current}\n")

    try:
        new = _ask("Yeni klasör yolu (boş = değiştirme)", str(current))
        if new is None or new == str(current):
            print("  Değişiklik yapılmadı.")
            _ask("Enter'a basın", "")
            return False
        Path(new).mkdir(parents=True, exist_ok=True)
        set_value("download_dir", new)
        print(f"\n  ✅ İndirme klasörü güncellendi: {new}")
        _ask("Enter'a basın", "")
        return True
    except KeyboardInterrupt:
        print("\n  İptal edildi.")
        return False
    except Exception as e:
        print(f"\n  ❌ Hata: {e}")
        _ask("Enter'a basın", "")
        return False


# ─── Güncelleme ───────────────────────────────────────────────
def _update() -> bool:
    _banner("Güncelleme")
    import subprocess

    script_dir = Path(__file__).parent.parent
    print(f"  Proje dizini: {script_dir}")
    print()

    # git kontrolü
    git_dir = script_dir / ".git"
    if not git_dir.exists():
        print("  ❌ Bu dizin bir git reposu değil.")
        print("     Manuel güncelleme için:")
        print("     https://github.com/trs-1342/alms")
        _ask("Enter'a basın", "")
        return False

    try:
        # Mevcut commit
        cur = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=script_dir, capture_output=True, text=True
        )
        print(f"  Mevcut sürüm: {cur.stdout.strip()}")

        # Fetch
        print("  Güncellemeler kontrol ediliyor...")
        fetch = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=script_dir, capture_output=True, text=True
        )

        # Kaç commit geride?
        behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=script_dir, capture_output=True, text=True
        )
        count = behind.stdout.strip()

        if count == "0":
            print("  ✅ Zaten güncel.")
            _ask("Enter'a basın", "")
            return True

        print(f"  {count} yeni güncelleme var.\n")
        confirm = _ask("Güncelleme yapılsın mı? [e/H]", "e")
        if confirm and confirm.lower() in ("e", "y", "evet", "yes"):
            pull = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=script_dir, capture_output=True, text=True
            )
            if pull.returncode == 0:
                print("  ✅ Güncelleme tamamlandı!")
                print()
                # Pip güncelle
                venv_pip = script_dir / ".venv" / "bin" / "pip"
                if venv_pip.exists():
                    print("  Paketler güncelleniyor...")
                    subprocess.run(
                        [str(venv_pip), "install", "-q", "-r",
                         str(script_dir / "requirements.txt")],
                        capture_output=True
                    )
                    print("  ✅ Paketler güncellendi.")
            else:
                print(f"  ❌ Hata:\n{pull.stderr}")

        _ask("Enter'a basın", "")
        return True
    except KeyboardInterrupt:
        print("\n  İptal edildi.")
        return False
    except Exception as e:
        print(f"  ❌ Hata: {e}")
        _ask("Enter'a basın", "")
        return False


# ─── Sıfırlama ────────────────────────────────────────────────
def _reset() -> bool:
    _banner("Sistemi Sıfırla")
    print("  ⚠️  Bu işlem şunları siler:")
    print("     • Kayıtlı kimlik bilgileri")
    print("     • Oturumlar")
    print("     • Manifest (indirme geçmişi)")
    print("     • Config ayarları")
    print("     • Otomasyon zamanlaması")
    print()
    print("  İndirilen DOSYALAR SİLİNMEZ.\n")

    try:
        confirm = _ask("Sıfırlamayı onayla (evet yazın)", "")
        if confirm != "evet":
            print("  İptal edildi.")
            _ask("Enter'a basın", "")
            return False

        from core.auth import delete_credentials, clear_sessions
        from utils.scheduler import remove_schedule
        from utils.paths import CONFIG_DIR, MANIFEST_FILE, CONFIG_FILE
        import os

        delete_credentials()
        clear_sessions()
        remove_schedule()

        if MANIFEST_FILE.exists():
            MANIFEST_FILE.unlink()
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()

        print("\n  ✅ Sistem sıfırlandı.")
        print("  Yeniden kurulum için: alms setup")
        _ask("Enter'a basın", "")
        return True
    except KeyboardInterrupt:
        print("\n  İptal edildi.")
        return False
    except Exception as e:
        print(f"  ❌ Hata: {e}")
        _ask("Enter'a basın", "")
        return False


# ─── Kaldırma ────────────────────────────────────────────────
def _uninstall() -> bool:
    _banner("ALMS'i Kaldır")
    print("  ⚠️  Bu işlem şunları siler:")
    print("     • Tüm config ve kimlik bilgileri")
    print("     • Oturumlar ve manifest")
    print("     • Crontab zamanlaması")
    print("     • ~/.local/bin/alms komutu")
    print()
    print("  İndirilen DOSYALAR ve proje klasörü SİLİNMEZ.\n")

    try:
        confirm = _ask("Kaldırmayı onayla (kaldır yazın)", "")
        if confirm != "kaldır":
            print("  İptal edildi.")
            _ask("Enter'a basın", "")
            return False

        from core.auth import delete_credentials, clear_sessions
        from utils.scheduler import remove_schedule
        from utils.paths import CONFIG_DIR
        import shutil

        delete_credentials()
        clear_sessions()
        remove_schedule()

        # Config dizinini sil
        if CONFIG_DIR.exists():
            shutil.rmtree(CONFIG_DIR)
            print(f"  ✅ Config silindi: {CONFIG_DIR}")

        # ~/.local/bin/alms symlink
        link = Path.home() / ".local" / "bin" / "alms"
        if link.exists() or link.is_symlink():
            link.unlink()
            print(f"  ✅ Komut silindi: {link}")

        # Windows alms.bat
        script_dir = Path(__file__).parent.parent
        bat = script_dir / "alms.bat"
        if bat.exists():
            bat.unlink()

        print("\n  ✅ ALMS kaldırıldı.")
        print("  Proje klasörünü de silmek istersen:")
        print(f"  rm -rf {script_dir}")
        _ask("Enter'a basın", "")
        return True
    except KeyboardInterrupt:
        print("\n  İptal edildi.")
        return False
    except Exception as e:
        print(f"  ❌ Hata: {e}")
        _ask("Enter'a basın", "")
        return False


# ─── İlk kurulum ─────────────────────────────────────────────
def _fresh_install() -> bool:
    _banner("Kurulum Sihirbazı")
    print("  IGU ALMS sistemine bağlanmak için bilgilerini gir.")
    print("  Veriler şifreli olarak yalnızca bu bilgisayarda saklanır.")
    print("  Çıkmak için Ctrl+C.\n")

    try:
        # Dil
        print("  Dil / Language:")
        print("  [1] Türkçe")
        print("  [2] English\n")
        lang_raw = _ask("Seçim / Choice", "1")
        if lang_raw is None:
            print("\n  Kurulum iptal edildi.")
            return False
        lang = "en" if lang_raw == "2" else "tr"

        # Kimlik
        print()
        username = _ask("Kullanıcı adı (öğrenci no)")
        if not username:
            print("  Kullanıcı adı boş olamaz.")
            return False

        password = _ask_password("Şifre")
        if not password:
            print("  Şifre boş olamaz.")
            return False

        # Login test
        print("\n  Giriş test ediliyor...")
        try:
            from core.auth import do_login, save_credentials, add_session
            token = do_login(username, password)
            save_credentials(username, password)
            add_session(username, token, source="wizard")
            print("  ✅ Giriş başarılı!")
        except Exception as e:
            print(f"  ❌ Giriş başarısız: {e}")
            return False

        # İndirme dizini
        from utils.paths import DOWNLOAD_DIR
        from core.config import save as save_cfg, load as load_cfg

        default_dir = str(DOWNLOAD_DIR)
        print()
        print(f"  Varsayılan indirme klasörü: {default_dir}")
        custom = _ask("Farklı klasör (boş = varsayılan)", "")
        if custom is None:
            print("\n  Kurulum iptal edildi.")
            return False
        dl_dir = custom if custom else default_dir
        Path(dl_dir).mkdir(parents=True, exist_ok=True)

        # İndirme sonrası klasör açma
        print()
        open_raw = _ask("İndirince klasör otomatik açılsın mı? [e/H]", "H")
        if open_raw is None:
            return False
        open_after = open_raw.lower() in ("e", "y", "evet", "yes")

        # Otomasyon
        print()
        auto_raw = _ask("Otomatik günlük indirme etkinleştirilsin mi? [e/H]", "H")
        if auto_raw is None:
            return False
        auto = auto_raw.lower() in ("e", "y", "evet", "yes")

        auto_hour = 1
        auto_min  = 25
        if auto:
            h_raw = _ask("Saat (0-23)", "1")
            m_raw = _ask("Dakika (0-59)", "25")
            if h_raw is None or m_raw is None:
                return False
            auto_hour = int(h_raw) if h_raw.isdigit() and 0 <= int(h_raw) <= 23 else 1
            auto_min  = int(m_raw) if m_raw.isdigit() and 0 <= int(m_raw) <= 59 else 25

        # Config kaydet
        cfg = load_cfg()
        cfg.update({
            "language":            lang,
            "download_dir":        dl_dir,
            "auto_sync":           auto,
            "auto_sync_hour":      auto_hour,
            "auto_sync_min":       auto_min,
            "open_after_download": open_after,
        })
        save_cfg(cfg)

        # Otomasyon kur
        if auto:
            from utils.scheduler import add_schedule, _ensure_cron_running
            from utils.paths import LOG_FILE
            _ensure_cron_running()
            ok = add_schedule(auto_hour, auto_min, str(LOG_FILE))

            if ok:
                print(f"\n  ✅ Otomasyon {auto_hour:02d}:{auto_min:02d}'e ayarlandı.")
            else:
                print("\n  ⚠️  Otomasyon ayarlanamadı.")

        # PATH
        _setup_path()

        print()
        print("  ✅ Kurulum tamamlandı!")
        print()
        print("  Kullanım:")
        print("    alms            → menü aç")
        print("    alms sync       → yeni dosyaları indir")
        print("    alms --help     → tüm komutlar")
        print()
        _ask("Devam etmek için Enter'a basın", "")
        return True

    except KeyboardInterrupt:
        print("\n\n  Kurulum iptal edildi.")
        return False


def _setup_path():
    system = platform.system()
    script = Path(__file__).parent.parent / "alms.py"
    if system == "Windows":
        _setup_path_windows(script)
    else:
        _setup_path_unix(script)


def _setup_path_unix(script: Path):
    bin_dir = Path.home() / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "alms"

    # Venv Python'ını bul (symlink değil wrapper — sistem Python değil venv kullanılsın)
    for candidate in [
        script.parent / ".venv" / "bin" / "python",
        script.parent / ".venv" / "bin" / "python3",
    ]:
        if candidate.exists():
            venv_py = candidate
            break
    else:
        venv_py = Path(sys.executable)

    try:
        wrapper.write_text(
            f'#!/usr/bin/env bash\nexec "{venv_py}" "{script}" "$@"\n'
        )
        wrapper.chmod(0o755)
        print(f"  ✅ alms komutu oluşturuldu: {wrapper}")

        # macOS: login shell .zprofile okur (Terminal.app); Linux: .zshrc / .bashrc
        is_macos = platform.system() == "Darwin"
        if is_macos:
            profiles = [".zprofile", ".zshrc", ".bash_profile", ".bashrc", ".profile"]
        else:
            profiles = [".zshrc", ".bashrc", ".profile"]

        for profile in profiles:
            pfile = Path.home() / profile
            if pfile.exists():
                if ".local/bin" not in pfile.read_text():
                    with pfile.open("a") as f:
                        f.write('\nexport PATH="$HOME/.local/bin:$PATH"\n')
                    print(f"  ✅ {profile} güncellendi.")
                break
    except Exception as e:
        print(f"  ⚠️  PATH eklenemedi: {e}")


def _setup_path_windows(script: Path):
    try:
        import winreg
        script_dir = str(script.parent)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS)
        try:
            current_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current_path = ""
        if script_dir not in current_path:
            new_path = f"{current_path};{script_dir}" if current_path else script_dir
            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
            print(f"  ✅ PATH'e eklendi: {script_dir}")
        bat = script.parent / "alms.bat"
        venv_py = script.parent / ".venv" / "Scripts" / "python.exe"
        py_exe = str(venv_py) if venv_py.exists() else sys.executable
        bat.write_text(f'@echo off\n"{py_exe}" "{script}" %*\n')
        print(f"  ✅ alms.bat oluşturuldu.")
    except Exception as e:
        print(f"  ⚠️  PATH eklenemedi: {e}")
