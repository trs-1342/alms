"""
utils/paths.py — OS-aware path management
"""
import os
import platform
import stat
from pathlib import Path


def get_config_dir() -> Path:
    """Secure config directory (chmod 700 on Unix)."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "alms"


def get_download_dir() -> Path:
    """User-visible download directory."""
    system = platform.system()
    if system in ("Windows", "Darwin"):
        return Path.home() / "Documents" / "ALMS"
    return Path.home() / "ALMS"


def ensure_secure_dir(path: Path) -> Path:
    """Create directory with owner-only permissions (700)."""
    path.mkdir(parents=True, exist_ok=True)
    if platform.system() != "Windows":
        path.chmod(stat.S_IRWXU)  # 700
    return path


def secure_file(path: Path) -> None:
    """Set file to owner-only read/write (600)."""
    if platform.system() != "Windows":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600


CONFIG_DIR   = get_config_dir()
DOWNLOAD_DIR = get_download_dir()
CREDS_FILE   = CONFIG_DIR / "credentials.enc"
SESSIONS_FILE = CONFIG_DIR / "sessions.enc"
CONFIG_FILE  = CONFIG_DIR / "config.json"
LOG_FILE     = CONFIG_DIR / "alms.log"
LOCK_FILE    = CONFIG_DIR / ".alms.lock"
MANIFEST_FILE = CONFIG_DIR / "manifest.json"
