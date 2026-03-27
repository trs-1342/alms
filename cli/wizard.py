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


def run_wizard() -> bool:
    """
    İlk kurulum sihirbazı.
    Döner: True = kurulum tamamlandı
    """
    _clear()
    print("╔" + "═" * 52 + "╗")
    print("║  ALMS İndirici — Kurulum Sihirbazı              ║")
    print("╚" + "═" * 52 + "╝")
    print()
    print("  IGU ALMS sistemine bağlanmak için bilgilerini gir.")
    print("  Veriler şifreli olarak yalnızca bu bilgisayarda saklanır.")
    print()

    # ── Dil seçimi ────────────────────────────────────────────
    print("  Dil / Language:")
    print("  [1] Türkçe")
    print("  [2] English")
    print()
    lang_raw = input("  Seçim / Choice [1]: ").strip()
    lang = "en" if lang_raw == "2" else "tr"

    # ── Giriş bilgileri ────────────────────────────────────────
    print()
    print("  Öğrenci numarası veya e-posta:")
    username = input("  Kullanıcı adı: ").strip()
    if not username:
        print("  Kullanıcı adı boş olamaz.")
        return False

    password = getpass.getpass("  Şifre: ")
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
    custom = input("  Farklı bir klasör belirt (boş = varsayılan): ").strip()
    dl_dir = custom if custom else default_dir

    Path(dl_dir).mkdir(parents=True, exist_ok=True)

    # ── Otomasyon ─────────────────────────────────────────────
    print()
    auto_raw = input("  Otomatik günlük çalıştırma etkinleştirilsin mi? [e/H]: ").strip().lower()
    auto = auto_raw in ("e", "y", "evet", "yes")

    auto_hour = 8
    auto_min  = 0
    if auto:
        h_raw = input("  Saat (0-23) [8]: ").strip()
        m_raw = input("  Dakika (0-59) [0]: ").strip()
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
        from utils.scheduler import add_schedule
        from utils.paths import LOG_FILE
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
    input("  Devam etmek için Enter'a basın...")
    return True


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
    bin_dir = Path.home() / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    link = bin_dir / "alms"

    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(script)
        script.chmod(0o755)
        print(f"  ✅ PATH'e eklendi: {link}")

        # Shell profil kontrolü
        for profile in [".bashrc", ".zshrc", ".profile"]:
            pfile = Path.home() / profile
            if pfile.exists():
                content = pfile.read_text()
                if ".local/bin" not in content:
                    pfile.open("a").write('\nexport PATH="$HOME/.local/bin:$PATH"\n')
                    print(f"  ✅ {profile} güncellendi.")
                break
    except Exception as e:
        print(f"  ⚠️  PATH eklenemedi: {e}")
        print(f"     Manuel: export PATH=\"$HOME/.local/bin:$PATH\"")


def _setup_path_windows(script: Path):
    """Windows: kullanıcı PATH'ine script dizini ekler."""
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

        # .bat wrapper oluştur
        bat = script.parent / "alms.bat"
        bat.write_text(
            f'@echo off\n"{sys.executable}" "{script}" %*\n'
        )
    except Exception as e:
        print(f"  ⚠️  PATH eklenemedi: {e}")
