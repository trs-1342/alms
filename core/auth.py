"""
core/auth.py — Kimlik doğrulama ve şifreleme
"""
import hashlib
import json
import logging
import os
import platform
import socket
import uuid
from base64 import urlsafe_b64encode
from datetime import datetime, timezone, timedelta

import requests
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from utils.paths import (
    CREDS_FILE, SESSIONS_FILE, CONFIG_DIR,
    ensure_secure_dir, secure_file,
)
from utils.integrity import sanitize_log

log = logging.getLogger(__name__)

AUTH_URL = "https://almsp-auth.gelisim.edu.tr/connect/token"
SESSION_TTL_HOURS = 6


# ─── Şifreleme anahtarı ───────────────────────────────────────
def _machine_key() -> bytes:
    """
    hostname + os_username + machine-id → PBKDF2 → Fernet key
    Makineye özel, taşınamaz.
    """
    parts = [
        socket.gethostname(),
        os.environ.get("USER") or os.environ.get("USERNAME") or os.environ.get("LOGNAME") or "user",
    ]

    # Ekstra entropi: Windows = MachineGuid, Linux = /etc/machine-id
    try:
        if platform.system() == "Windows":
            import winreg
            reg = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            parts.append(winreg.QueryValueEx(reg, "MachineGuid")[0])
        elif platform.system() == "Linux":
            mid = "/etc/machine-id"
            if os.path.exists(mid):
                parts.append(open(mid).read().strip())
        elif platform.system() == "Darwin":
            result = __import__("subprocess").run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    parts.append(line.split('"')[-2])
                    break
    except Exception:
        pass  # entropi olmadan devam

    raw  = ":".join(parts).encode()
    salt = hashlib.sha256(b"alms-kdf-v1:" + raw).digest()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return urlsafe_b64encode(kdf.derive(raw))


def _fernet() -> Fernet:
    return Fernet(_machine_key())


# ─── Kimlik bilgileri ─────────────────────────────────────────
def save_credentials(username: str, password: str) -> None:
    ensure_secure_dir(CONFIG_DIR)
    payload = json.dumps({"u": username, "p": password}).encode()
    CREDS_FILE.write_bytes(_fernet().encrypt(payload))
    secure_file(CREDS_FILE)
    log.debug("Kimlik bilgileri şifrelendi → %s", CREDS_FILE)


def load_credentials() -> tuple[str, str] | None:
    if not CREDS_FILE.exists():
        return None
    try:
        data = json.loads(_fernet().decrypt(CREDS_FILE.read_bytes()))
        return data["u"], data["p"]
    except InvalidToken:
        import sys
        print("\n⚠️  Kimlik bilgileri güvenlik güncellemesi nedeniyle sıfırlandı.")
        print("   Tekrar giriş yapın: alms setup")
        delete_credentials()
        clear_sessions()
        sys.exit(0)
    except (KeyError, json.JSONDecodeError) as e:
        log.error("Kimlik dosyası okunamadı: %s", e)
        return None


def delete_credentials() -> None:
    if CREDS_FILE.exists():
        # Güvenli silme: üzerine yaz, sonra sil
        size = CREDS_FILE.stat().st_size
        CREDS_FILE.write_bytes(os.urandom(size))
        CREDS_FILE.unlink()
        log.info("Kimlik bilgileri güvenli silindi.")


# ─── Sessions ─────────────────────────────────────────────────
def _load_sessions_raw() -> list[dict]:
    if not SESSIONS_FILE.exists():
        return []
    try:
        data = json.loads(_fernet().decrypt(SESSIONS_FILE.read_bytes()))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_sessions_raw(sessions: list[dict]) -> None:
    ensure_secure_dir(CONFIG_DIR)
    payload = json.dumps(sessions, ensure_ascii=False).encode()
    SESSIONS_FILE.write_bytes(_fernet().encrypt(payload))
    secure_file(SESSIONS_FILE)


def get_active_session() -> dict | None:
    now = datetime.now(timezone.utc)
    for s in reversed(_load_sessions_raw()):
        if s.get("status") != "success":
            continue
        exp_str = s.get("expires")
        if not exp_str:
            continue
        exp = datetime.fromisoformat(exp_str)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp > now:
            return s
    return None


def add_session(username: str, token: str, source: str,
                status: str = "success", error: str | None = None) -> None:
    sessions = _load_sessions_raw()
    now = datetime.now(timezone.utc)
    sessions.append({
        "id":       str(uuid.uuid4()),
        "username": username,
        "token":    token,
        "login_at": now.isoformat(),
        "expires":  (now + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
        "source":   source,
        "platform": platform.system(),
        "status":   status,
        "error":    error,
    })
    _save_sessions_raw(sessions[-50:])  # son 50 session


def clear_sessions() -> None:
    if SESSIONS_FILE.exists():
        size = SESSIONS_FILE.stat().st_size
        SESSIONS_FILE.write_bytes(os.urandom(size))
        SESSIONS_FILE.unlink()


# ─── Login ────────────────────────────────────────────────────
def do_login(username: str, password: str) -> str:
    """JWT token döndürür. Hata → exception."""
    log.debug("Login → %s", AUTH_URL)
    r = requests.post(
        AUTH_URL,
        data={
            "client_id":          "api",
            "grant_type":         "password",
            "username":           username,
            "password":           password,
            "googleCaptchaToken": "",
            "address":            "lms.gelisim.edu.tr",
            "port":               "3000",
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin":       "https://lms.gelisim.edu.tr",
            "Referer":      "https://lms.gelisim.edu.tr/",
        },
        timeout=20,
        verify=True,  # SSL her zaman açık
    )
    # Yanıtı loglamadan önce sanitize et
    log.debug("Login yanıt: %s", sanitize_log(r.text[:200]))
    r.raise_for_status()

    token = r.json().get("access_token")
    if not token:
        raise RuntimeError("Token alınamadı — kullanıcı adı/şifre yanlış olabilir")

    log.info("✅ Giriş başarılı — %s", username)
    return token


def get_or_refresh_token() -> tuple[str, str]:
    """
    Mevcut geçerli token varsa kullan, yoksa kayıtlı bilgilerle login yap.
    Döner: (token, username)
    """
    active = get_active_session()
    if active:
        log.debug("Mevcut token kullanılıyor.")
        return active["token"], active["username"]

    creds = load_credentials()
    if not creds:
        raise RuntimeError("Kayıtlı giriş bilgisi yok. `alms setup` çalıştırın.")

    username, password = creds
    token = do_login(username, password)
    add_session(username, token, source="auto")
    return token, username
