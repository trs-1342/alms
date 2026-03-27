#!/usr/bin/env python3
"""
IGU ALMS Scraper
────────────────
Kullanım:
  python alms_scraper.py -l              # giriş yap, kaydet
  python alms_scraper.py -loa            # tek seferlik giriş
  python alms_scraper.py                 # kayıtlı hesapla çalış
  python alms_scraper.py -c              # sadece dersler
  python alms_scraper.py -cal 14         # 14 günlük takvim
  python alms_scraper.py -o json         # sadece JSON çıktı
  python alms_scraper.py --no-save       # diske yazma
  python alms_scraper.py --status        # session ve hesap durumu
  python alms_scraper.py --logout        # kayıtlı bilgileri sil
  python alms_scraper.py -r              # token süresi dolmamış olsa bile yenile
  python alms_scraper.py -v              # verbose HTTP logları

Kurulum:
  pip install requests cryptography
"""

import argparse
import csv
import getpass
import hashlib
import json
import logging
import os
import platform
import socket
import sys
import uuid
from base64 import urlsafe_b64encode
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# ──────────────────────────────────────────────────────────
# SABITLER
# ──────────────────────────────────────────────────────────
AUTH_URL  = "https://almsp-auth.gelisim.edu.tr/connect/token"
API_BASE  = "https://almsp-api.gelisim.edu.tr"
APP_NAME  = "alms_scraper"
VERSION   = "1.0.0"


# ──────────────────────────────────────────────────────────
# OS-AWARE DIZINLER
# ──────────────────────────────────────────────────────────
def get_app_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    app_dir = base / APP_NAME
    (app_dir / "data").mkdir(parents=True, exist_ok=True)
    return app_dir


APP_DIR        = get_app_dir()
CREDS_FILE     = APP_DIR / "credentials.enc"
SESSIONS_FILE  = APP_DIR / "sessions.json"
LOG_FILE       = APP_DIR / "alms.log"
DATA_DIR       = APP_DIR / "data"


# ──────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt   = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    # requests kütüphanesinin debug loglarını kapat (verbose olmadıkça)
    if not verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# ŞİFRELEME — makineye özel Fernet anahtarı
# ──────────────────────────────────────────────────────────
def _machine_secret() -> bytes:
    """hostname + os username kombinasyonundan deterministik secret türetir."""
    raw = f"{socket.gethostname()}::{os.getlogin()}".encode()
    # 32-byte salt olarak raw'ın SHA256'sını kullan (sabit, makineden türetilmiş)
    salt = hashlib.sha256(raw).digest()
    kdf  = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    return urlsafe_b64encode(kdf.derive(raw))


def _fernet() -> Fernet:
    return Fernet(_machine_secret())


def encrypt_credentials(username: str, password: str) -> None:
    payload = json.dumps({"username": username, "password": password}).encode()
    CREDS_FILE.write_bytes(_fernet().encrypt(payload))
    log.debug("Kimlik bilgileri şifrelendi → %s", CREDS_FILE)


def decrypt_credentials() -> tuple[str, str] | None:
    if not CREDS_FILE.exists():
        return None
    try:
        payload = json.loads(_fernet().decrypt(CREDS_FILE.read_bytes()))
        return payload["username"], payload["password"]
    except (InvalidToken, KeyError, json.JSONDecodeError) as e:
        log.error("Kimlik dosyası okunamadı: %s", e)
        return None


def delete_credentials() -> None:
    if CREDS_FILE.exists():
        CREDS_FILE.unlink()
        log.info("Kayıtlı kimlik bilgileri silindi.")


# ──────────────────────────────────────────────────────────
# SESSION YÖNETİMİ
# ──────────────────────────────────────────────────────────
def load_sessions() -> list[dict]:
    if not SESSIONS_FILE.exists():
        return []
    try:
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_sessions(sessions: list[dict]) -> None:
    SESSIONS_FILE.write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_active_session() -> dict | None:
    """Süresi dolmamış son başarılı session'ı döndürür."""
    now = datetime.now(timezone.utc)
    for s in reversed(load_sessions()):
        if s.get("status") != "success":
            continue
        expires = datetime.fromisoformat(s["token_expires"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires > now:
            return s
    return None


def add_session(
    username: str,
    token: str,
    source: str,
    fetched: list[str],
    status: str = "success",
    error: str | None = None,
) -> dict:
    sessions = load_sessions()
    now      = datetime.now(timezone.utc)
    entry = {
        "id":            str(uuid.uuid4()),
        "username":      username,
        "login_time":    now.isoformat(),
        "token_expires": (now + timedelta(hours=6)).isoformat(),
        "token":         token,
        "source":        source,
        "fetched":       fetched,
        "status":        status,
        "error":         error,
        "platform":      platform.system(),
    }
    sessions.append(entry)
    # son 50 session'ı tut
    save_sessions(sessions[-50:])
    return entry


# ──────────────────────────────────────────────────────────
# API
# ──────────────────────────────────────────────────────────
def login(username: str, password: str) -> str:
    log.debug("Login isteği → %s", AUTH_URL)
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
        timeout=15,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError(f"Token alınamadı: {r.text}")
    log.info("✅ Giriş başarılı — %s", username)
    return token


def api_post(token: str, path: str, body: dict) -> dict | list:
    url = f"{API_BASE}{path}"
    log.debug("POST %s — body: %s", url, json.dumps(body, ensure_ascii=False))
    r = requests.post(
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Origin":        "https://lms.gelisim.edu.tr",
            "Referer":       "https://lms.gelisim.edu.tr/",
        },
        timeout=15,
    )
    log.debug("← %s %s (%d bytes)", r.status_code, path, len(r.content))
    r.raise_for_status()
    return r.json()


def get_courses(token: str) -> list[dict]:
    data = api_post(token, "/api/course/enrolledcourses", {
        "Take": 1000, "Skip": 0,
        "SearchCourseName": "", "ActiveStatus": 1,
        "CourseDateFilter": 4, "isNotifications": True,
        "SearchTermId": None, "SearchProgId": None,
        "SourceCourseId": "", "MasterCourseId": "", "CourseId": "",
    })
    items = data if isinstance(data, list) else data.get("items", [])
    log.info("📚 %d ders alındı.", len(items))
    return items


def get_calendar(token: str, days: int = 30) -> list[dict]:
    now = datetime.now(timezone.utc)
    data = api_post(token, "/api/calendar/my", {
        "Filter": {
            "activityType": None, "completed": 1,
            "dueDate": 1, "grade": 0,
            "isDatePassed": 0, "isFiltered": True,
        },
        "StartDate":   now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "EndDate":     (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "ContextType": 16, "ContextId": "",
        "Take": 100, "Skip": 0,
    })
    items = data if isinstance(data, list) else data.get("items", [])
    log.info("📅 %d aktivite alındı (%d günlük).", len(items), days)
    return items


# ──────────────────────────────────────────────────────────
# ÇIKTI
# ──────────────────────────────────────────────────────────
def save_json(data, filename: str) -> None:
    path = DATA_DIR / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("💾 %s", path)


def save_csv(data: list[dict], filename: str, fields: list[str]) -> None:
    if not data:
        return
    path = DATA_DIR / filename
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(data)
    log.info("💾 %s", path)


def print_courses_md(courses: list[dict]) -> None:
    active = [c for c in courses
              if "BAHAR" in c.get("termName", "") or "GÜZ" in c.get("termName", "")]
    if not active:
        active = courses

    col1, col2, col3 = 42, 30, 8
    sep = f"{'─'*col1}─{'─'*col2}─{'─'*col3}"
    hdr = f"{'Ders':<{col1}} {'Öğretmen':<{col2}} {'İlerleme':>{col3}}"

    print(f"\n## 📚 Aktif Dersler ({len(active)})\n")
    print(hdr)
    print(sep)
    for c in active:
        name    = c.get("name", "").strip()[:col1]
        teacher = (c.get("teachers") or "—").split(",")[0].strip()[:col2]
        prog    = f"%{c.get('progress', 0)}"
        print(f"{name:<{col1}} {teacher:<{col2}} {prog:>{col3}}")
    print()


def print_calendar_md(activities: list[dict]) -> None:
    if not activities:
        print("\nYaklaşan aktivite yok.\n")
        return

    col1, col2, col3, col4 = 10, 28, 22, 12
    sep = f"{'─'*col1}─{'─'*col2}─{'─'*col3}─{'─'*col4}"
    hdr = f"{'Tarih':<{col1}} {'Aktivite':<{col2}} {'Ders':<{col3}} {'Tür':<{col4}}"

    print(f"\n## 📅 Yaklaşan Aktiviteler ({len(activities)})\n")
    print(hdr)
    print(sep)
    for a in activities:
        due      = (a.get("dueDate") or "")[:10]
        act_name = a.get("activityName", "")[:col2]
        course   = a.get("courseName", "").strip()[:col3]
        atype    = a.get("activityType", "")[:col4]
        print(f"{due:<{col1}} {act_name:<{col2}} {course:<{col3}} {atype:<{col4}}")
    print()


# ──────────────────────────────────────────────────────────
# STATUS KOMUTU
# ──────────────────────────────────────────────────────────
def cmd_status() -> None:
    print(f"\n## ALMS Scraper v{VERSION} — Durum\n")
    print(f"  Veri dizini  : {APP_DIR}")
    print(f"  Platform     : {platform.system()} {platform.release()}")

    creds = decrypt_credentials()
    if creds:
        print(f"  Kayıtlı hesap: {creds[0]}")
    else:
        print("  Kayıtlı hesap: yok")

    sessions = load_sessions()
    print(f"  Toplam session: {len(sessions)}")

    active = get_active_session()
    if active:
        exp = datetime.fromisoformat(active["token_expires"])
        remaining = exp.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        mins = int(remaining.total_seconds() / 60)
        print(f"  Aktif token  : ✅ {mins} dakika kaldı ({active['username']})")
    else:
        print("  Aktif token  : ❌ yok (yeniden giriş gerekli)")

    if sessions:
        last = sessions[-1]
        print(f"\n  Son session  : {last['login_time'][:19]} — {last['status']}")
        if last.get("error"):
            print(f"  Hata         : {last['error']}")
    print()


# ──────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="alms_scraper",
        description="IGU ALMS — ders ve takvim verisi çekici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python alms_scraper.py -l              giriş yap, kaydet
  python alms_scraper.py -loa            tek seferlik giriş
  python alms_scraper.py -c              sadece dersler
  python alms_scraper.py -cal 7          7 günlük takvim
  python alms_scraper.py -c -cal 14 -o json   JSON + dersler + 14 gün takvim
  python alms_scraper.py --status        durum
  python alms_scraper.py --logout        kayıtlı bilgileri sil
        """,
    )

    auth = p.add_argument_group("kimlik doğrulama")
    auth_ex = auth.add_mutually_exclusive_group()
    auth_ex.add_argument("-l",   "--login",         action="store_true",
                         help="kullanıcı adı/şifre sor, şifreli kaydet")
    auth_ex.add_argument("-loa", "--login-other",   action="store_true",
                         help="tek seferlik giriş, kaydetme")
    auth_ex.add_argument("--logout",                action="store_true",
                         help="kayıtlı kimlik bilgilerini sil")
    auth.add_argument("-r",  "--refresh-token",     action="store_true",
                      help="token geçerli olsa bile yeniden giriş yap")

    data = p.add_argument_group("veri")
    data.add_argument("-c",   "--courses",          action="store_true",
                      help="kayıtlı dersleri çek")
    data.add_argument("-cal", "--calendar",         nargs="?", const=30,
                      type=int, metavar="DAYS",
                      help="takvimi çek (varsayılan: 30 gün)")
    data.add_argument("-o",   "--output",           choices=["json", "csv", "both"],
                      default="both", help="çıktı formatı (varsayılan: both)")
    data.add_argument("--no-save",                  action="store_true",
                      help="diske kaydetme, sadece terminalde göster")

    misc = p.add_argument_group("diğer")
    misc.add_argument("--status",                   action="store_true",
                      help="session ve hesap durumunu göster")
    misc.add_argument("-v", "--verbose",             action="store_true",
                      help="ayrıntılı HTTP logları")
    misc.add_argument("--version",                  action="version",
                      version=f"%(prog)s {VERSION}")
    return p


# ──────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────
def main():
    parser = build_parser()
    args   = parser.parse_args()

    setup_logging(args.verbose)
    log.debug("Platform: %s | App dir: %s", platform.system(), APP_DIR)

    # ── özel komutlar ──────────────────────────────────────

    if args.status:
        cmd_status()
        return

    if args.logout:
        delete_credentials()
        print("✅ Kayıtlı kimlik bilgileri silindi.")
        return

    # ── kimlik al ─────────────────────────────────────────

    token    = None
    username = None
    source   = "saved"

    # 1) Token yenileme gerekmiyorsa aktif session'ı kullan
    if not args.refresh_token and not args.login and not args.login_other:
        active = get_active_session()
        if active:
            token    = active["token"]
            username = active["username"]
            exp      = datetime.fromisoformat(active["token_expires"])
            remaining = exp.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
            log.info("♻️  Mevcut token kullanılıyor (%d dk kaldı) — %s",
                     int(remaining.total_seconds() / 60), username)
            source = "cached"

    # 2) Giriş gerekiyorsa
    if token is None:
        if args.login_other:
            username = input("Kullanıcı adı: ").strip()
            password = getpass.getpass("Şifre: ")
            source   = "manual"
        elif args.login:
            username = input("Kullanıcı adı: ").strip()
            password = getpass.getpass("Şifre: ")
            source   = "saved"
        else:
            # kayıtlı bilgileri dene
            creds = decrypt_credentials()
            if creds:
                username, password = creds
                log.info("🔑 Kayıtlı kimlik bilgileri kullanılıyor.")
                source = "saved"
            else:
                log.warning("Kayıtlı kimlik bilgisi yok. -l veya -loa ile giriş yapın.")
                parser.print_help()
                sys.exit(1)

        try:
            token = login(username, password)
        except requests.HTTPError as e:
            log.error("Giriş başarısız: %s", e)
            add_session(username or "?", "", source, [], "error", str(e))
            sys.exit(1)

        if args.login:
            encrypt_credentials(username, password)
            log.info("🔐 Kimlik bilgileri şifrelendi.")

    # ── hangi veriler çekilecek ────────────────────────────

    # parametre yoksa her ikisini de çek
    fetch_courses  = args.courses  or (not args.courses and args.calendar is None)
    fetch_calendar = args.calendar is not None or (not args.courses and args.calendar is None)
    calendar_days  = args.calendar if args.calendar is not None else 30

    fetched   = []
    courses   = []
    calendar  = []

    try:
        if fetch_courses:
            courses = get_courses(token)
            fetched.append("courses")

        if fetch_calendar:
            calendar = get_calendar(token, calendar_days)
            fetched.append("calendar")

    except requests.HTTPError as e:
        log.error("Veri çekme hatası: %s", e)
        add_session(username, token, source, fetched, "error", str(e))
        sys.exit(1)

    # ── session kaydet ─────────────────────────────────────
    if source != "cached":
        add_session(username, token, source, fetched)

    # ── çıktı ─────────────────────────────────────────────
    if courses:
        print_courses_md(courses)
        if not args.no_save:
            if args.output in ("json", "both"):
                save_json(courses, "courses.json")
            if args.output in ("csv", "both"):
                save_csv(courses, "courses.csv",
                         ["name", "teachers", "termName", "programName",
                          "progress", "startDate", "endDate", "newActivityCount"])

    if calendar:
        print_calendar_md(calendar)
        if not args.no_save:
            if args.output in ("json", "both"):
                save_json(calendar, "calendar.json")
            if args.output in ("csv", "both"):
                save_csv(calendar, "calendar.csv",
                         ["courseName", "activityName", "activityType",
                          "startDate", "endDate", "dueDate", "className"])

    if not args.no_save and (courses or calendar):
        log.info("📁 Veriler kaydedildi → %s", DATA_DIR)

    log.info("Tamamlandı ✓")


if __name__ == "__main__":
    main()
