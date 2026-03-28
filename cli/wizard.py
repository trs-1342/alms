"""
cli/wizard.py — İlk kurulum sihirbazı
"""
import getpass
import platform
import sys
from pathlib import Path


def _clear():
    import os
    os.system("cls" if platform.system() == "Windows" else "clear")


def _ask(prompt: str, default: str = "") -> str:
    """KeyboardInterrupt'ta None döndürür."""
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"  {prompt}{hint}: ").strip()
        return val if val else default
    except KeyboardInterrupt:
        return None


def _ask_password(prompt: str) -> str:
    try:
        return getpass.getpass(f"  {prompt}: ")
    except KeyboardInterrupt:
        return None


def run_wizard(reconfigure: str | None = None) -> bool:
    """
    İlk kurulum sihirbazı.
    reconfigure: "credentials" | "schedule" | "path" | None (tam kurulum)
    Döner: True = kurulum tamamlandı, False = iptal/hata
    """
    _clear()

    # Kısmi yeniden yapılandırma
    if reconfigure == "credentials":
        return _reconfigure_credentials()
    elif reconfigure == "schedule":
        return _reconfigure_schedule()

    print("╔" + "═" * 52 + "╗")
    print("║  ALMS İndirici — Kurulum Sihirbazı              ║")
    print("╚" + "═" * 52 + "╝")
    print()
    print("  IGU ALMS sistemine bağlanmak için bilgilerini gir.")
    print("  Veriler şifreli olarak yalnızca bu bilgisayarda saklanır.")
    print("  Çıkmak için Ctrl+C.")
    print()

    try:
        # ── Dil seçimi ────────────────────────────────────────────
        print("  Dil / Language:")
        print("  [1] Türkçe")
        print("  [2] English")
        print()
        lang_raw = _ask("Seçim / Choice", "1")
        if lang_raw is None:
            print("\n  Kurulum iptal edildi.")
            return False
        lang = "en" if lang_raw == "2" else "tr"

        # ── Giriş bilgileri ────────────────────────────────────────
        print()
        print("  Öğrenci numarası veya e-posta:")
        username = _ask("Kullanıcı adı")
        if username is None:
            print("\n  Kurulum iptal edildi.")
            return False
        if not username:
            print("  Kullanıcı adı boş olamaz.")
            return False

        password = _ask_password("Şifre")
        if password is None:
            print("\n  Kurulum iptal edildi.")
            return False
        if not password:
            print("  Şifre boş olamaz.")
            return False

        # ── Test login ────────────────────────────────────────────
        print()
        print("  Giriş test ediliyor...")
        try:
            from core.auth import do_login, save_credentials, add_session
            token = do_login(username, password)
            save_credentials(username, password)
            add_session(username, token, source="wizard")
            print("  ✅ Giriş başarılı!")
        except Exception as e:
            print(f"  ❌ Giriş başarısız: {e}")
            return False

        # ── İndirme dizini ────────────────────────────────────────
        from utils.paths import DOWNLOAD_DIR
        from core.config import save as save_cfg, load as load_cfg

        default_dir = str(DOWNLOAD_DIR)
        print()
        print(f"  Varsayılan indirme klasörü: {default_dir}")
        custom = _ask("Farklı bir klasör belirt (boş = varsayılan)", "")
        if custom is None:
            print("\n  Kurulum iptal edildi.")
            return False
        dl_dir = custom if custom else default_dir
        Path(dl_dir).mkdir(parents=True, exist_ok=True)

        # ── Otomasyon ─────────────────────────────────────────────
        print()
        auto_raw = _ask("Otomatik günlük çalıştırma etkinleştirilsin mi? [e/H]", "H")
        if auto_raw is None:
            print("\n  Kurulum iptal edildi.")
            return False
        auto = auto_raw.lower() in ("e", "y", "evet", "yes")

        auto_hour = 8
        auto_min  = 0
        if auto:
            h_raw = _ask("Saat (0-23)", "8")
            if h_raw is None:
                print("\n  Kurulum iptal edildi.")
                return False
            m_raw = _ask("Dakika (0-59)", "0")
            if m_raw is None:
                print("\n  Kurulum iptal edildi.")
                return False
            auto_hour = int(h_raw) if h_raw.isdigit() and 0 <= int(h_raw) <= 23 else 8
            auto_min  = int(m_raw) if m_raw.isdigit() and 0 <= int(m_raw) <= 59 else 0

        # ── Config kaydet ─────────────────────────────────────────
        cfg = load_cfg()
        cfg["language"]       = lang
        cfg["download_dir"]   = dl_dir
        cfg["auto_sync"]      = auto
        cfg["auto_sync_hour"] = auto_hour
        cfg["auto_sync_min"]  = auto_min
        save_cfg(cfg)

        # ── Otomasyon kur ─────────────────────────────────────────
        if auto:
            from utils.scheduler import add_schedule, _ensure_cron_running
            from utils.paths import LOG_FILE
            _ensure_cron_running()   # cronie/cron servisini kontrol et
            ok = add_schedule(auto_hour, auto_min, str(LOG_FILE))
            if ok:
                print(f"  ✅ Otomasyon {auto_hour:02d}:{auto_min:02d}'e ayarlandı.")
            else:
                print("  ⚠️  Otomasyon ayarlanamadı (sonradan ayarlardan yapılabilir).")

        # ── PATH entegrasyonu ─────────────────────────────────────
        _setup_path()

        print()
        print("  ✅ Kurulum tamamlandı!")
        print()
        print("  Kullanım:")
        print("    alms            → menü aç")
        print("    alms sync       → yeni dosyaları indir")
        print("    alms --help     → yardım")
        print()
        _ask("Devam etmek için Enter'a basın", "")
        return True

    except KeyboardInterrupt:
        print("\n\n  Kurulum iptal edildi.")
        return False


def _reconfigure_credentials() -> bool:
    """Sadece kullanıcı adı/şifre güncelle."""
    print("╔" + "═" * 52 + "╗")
    print("║  Kimlik Bilgilerini Güncelle                     ║")
    print("╚" + "═" * 52 + "╝\n")
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
        print("  ✅ Güncellendi!")
        _ask("Enter'a basın", "")
        return True
    except KeyboardInterrupt:
        print("\n  İptal edildi.")
        return False
    except Exception as e:
        print(f"  ❌ Hata: {e}")
        return False


def _reconfigure_schedule() -> bool:
    """Sadece otomasyon ayarını güncelle."""
    print("╔" + "═" * 52 + "╗")
    print("║  Otomasyon Ayarı                                 ║")
    print("╚" + "═" * 52 + "╝\n")
    try:
        from utils.scheduler import add_schedule, remove_schedule, get_schedule_status
        from utils.paths import LOG_FILE
        current = get_schedule_status()
        print(f"  Mevcut: {current or 'Kapalı'}\n")
        auto_raw = _ask("Otomasyon etkinleştirilsin mi? [e/H]", "H")
        if auto_raw is None:
            return False
        auto = auto_raw.lower() in ("e", "y", "evet", "yes")
        if auto:
            h_raw = _ask("Saat (0-23)", "8")
            m_raw = _ask("Dakika (0-59)", "0")
            if h_raw is None or m_raw is None:
                return False
            h = int(h_raw) if h_raw.isdigit() and 0 <= int(h_raw) <= 23 else 8
            m = int(m_raw) if m_raw.isdigit() and 0 <= int(m_raw) <= 59 else 0
            ok = add_schedule(h, m, str(LOG_FILE))
            print(f"  {'✅ Ayarlandı: ' + f'{h:02d}:{m:02d}' if ok else '❌ Hata'}")
        else:
            remove_schedule()
            print("  ✅ Otomasyon devre dışı.")
        from core.config import set_value
        set_value("auto_sync", auto)
        _ask("Enter'a basın", "")
        return True
    except KeyboardInterrupt:
        print("\n  İptal edildi.")
        return False


def _setup_path():
    """Shell profili veya Windows PATH'e alms.py ekler."""
    system = platform.system()
    script = Path(__file__).parent.parent / "alms.py"

    if system == "Windows":
        _setup_path_windows(script)
    else:
        _setup_path_unix(script)


def _setup_path_unix(script: Path):
    """~/.local/bin/alms symlink oluşturur."""
    import os
    # macOS'ta Homebrew Python kullan
    if platform.system() == "Darwin":
        for brew_py in [
            Path("/opt/homebrew/bin/python3"),   # Apple Silicon
            Path("/usr/local/bin/python3"),       # Intel
        ]:
            if brew_py.exists():
                script = script  # script değişmiyor, sadece venv path için
                break
    bin_dir = Path.home() / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    link = bin_dir / "alms"

    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(script)
        script.chmod(0o755)
        print(f"  ✅ PATH'e eklendi: {link}")

        for profile in [".bashrc", ".zshrc", ".profile"]:
            pfile = Path.home() / profile
            if pfile.exists():
                content = pfile.read_text()
                if ".local/bin" not in content:
                    with pfile.open("a") as f:
                        f.write('\nexport PATH="$HOME/.local/bin:$PATH"\n')
                    print(f"  ✅ {profile} güncellendi.")
                break
    except Exception as e:
        print(f"  ⚠️  PATH eklenemedi: {e}")


def _setup_path_windows(script: Path):
    """Windows: kullanıcı PATH'ine script dizini ekler ve alms.bat oluşturur."""
    try:
        import winreg
        script_dir = str(script.parent)
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_ALL_ACCESS,
        )
        try:
            current_path, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current_path = ""

        if script_dir not in current_path:
            new_path = f"{current_path};{script_dir}" if current_path else script_dir
            winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
            print(f"  ✅ PATH'e eklendi: {script_dir}")

        # alms.bat wrapper — "alms" komutu olarak çalışsın
        bat = script.parent / "alms.bat"
        bat.write_text("@echo off\n" + f'"{sys.executable}" "{script}" %*\n')
        print(f"  ✅ alms.bat oluşturuldu: {bat}")

    except Exception as e:
        print(f"  ⚠️  PATH eklenemedi: {e}")
