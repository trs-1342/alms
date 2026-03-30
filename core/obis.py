#!/usr/bin/env python3
"""
ALMS İndirici — OBİS modülü
Sınav tarihleri, notlar, devamsızlık çekme
"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import date
from collections import defaultdict
from utils.paths import CONFIG_DIR, ensure_secure_dir

SESSION_FILE = CONFIG_DIR / "obis_session"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
    "Referer":    "https://obis.gelisim.edu.tr/",
}

from utils.colors import PALETTE as _COLORS, RESET as _RESET, BOLD as _BOLD, DIM as _DIM

_TR_AYLAR = {
    "Ocak":1,"Şubat":2,"Mart":3,"Nisan":4,
    "Mayıs":5,"Haziran":6,"Temmuz":7,"Ağustos":8,
    "Eylül":9,"Ekim":10,"Kasım":11,"Aralık":12,
}

def _parse_tarih(tarih_str: str) -> date | None:
    tarih_str = tarih_str.strip()
    m = re.match(r'(\d+)\s+(\w+)\s+(\d{4})', tarih_str)
    if not m:
        return None
    gun, ay_ad, yil = int(m.group(1)), m.group(2), int(m.group(3))
    ay = _TR_AYLAR.get(ay_ad)
    if not ay:
        return None
    try:
        return date(yil, ay, gun)
    except ValueError:
        return None

# ── Cookie yönetimi ───────────────────────────────────────────────────────────

def save_session(cookie: str):
    ensure_secure_dir(CONFIG_DIR)
    from core.auth import _fernet
    encrypted = _fernet().encrypt(cookie.strip().encode())
    SESSION_FILE.write_bytes(encrypted)
    SESSION_FILE.chmod(0o600)
    print("✅ OBİS oturumu şifreli olarak kaydedildi.")

def load_session() -> str | None:
    if not SESSION_FILE.exists():
        return None
    try:
        from core.auth import _fernet
        from cryptography.fernet import InvalidToken
        raw = SESSION_FILE.read_bytes()
        try:
            val = _fernet().decrypt(raw).decode().strip()
        except (InvalidToken, ValueError):
            # Eski format: düz metin — sessiz geçiş
            val = raw.decode(errors="ignore").strip()
        return val if val else None
    except Exception:
        return None

def _extract_token(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r'ASP\.NET_SessionId[=:"\s]+([a-z0-9]+)', raw, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'["\']([a-z0-9]{20,})["\']', raw)
    if m:
        return m.group(1)
    m = re.search(r'([a-z0-9]{20,})', raw)
    if m:
        return m.group(1)
    return raw

def _test_session(cookie: str) -> bool:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.cookies.set("ASP.NET_SessionId", cookie, domain="obis.gelisim.edu.tr")
    try:
        r = s.get("https://obis.gelisim.edu.tr/Default.aspx",
                  allow_redirects=True, timeout=10)
        return "login" not in r.url.lower()
    except requests.RequestException:
        return False

def setup_obis(force: bool = False):
    if not force:
        existing = load_session()
        if existing and _test_session(existing):
            print("✅ OBİS oturumu zaten geçerli.")
            print("   Zorla yenilemek için: alms obis --setup --force")
            return
    print("\n── OBİS Oturum Kurulumu ─────────────────────────────")
    print("1. Tarayıcıda https://obis.gelisim.edu.tr adresine giriş yap")
    print("2. F12 → Storage → Cookies → obis.gelisim.edu.tr")
    print("3. ASP.NET_SessionId değerini kopyala")
    print("   (düz token, tırnaklı veya tam satır — fark etmez)\n")
    try:
        raw = input("ASP.NET_SessionId: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n❌ İptal edildi.")
        return
    if not raw:
        print("❌ Boş giriş.")
        return
    cookie = _extract_token(raw)
    print(f"  → Ayıklanan token: {cookie[:8]}...{cookie[-4:]}")
    if _test_session(cookie):
        save_session(cookie)
    else:
        print("❌ Cookie geçersiz veya süresi dolmuş.")

def get_session() -> requests.Session | None:
    cookie = load_session()
    if cookie:
        s = requests.Session()
        s.headers.update(HEADERS)
        s.cookies.set("ASP.NET_SessionId", cookie, domain="obis.gelisim.edu.tr")
        try:
            r = s.get("https://obis.gelisim.edu.tr/Default.aspx",
                      allow_redirects=True, timeout=10)
            if "login" not in r.url.lower():
                return s
        except requests.RequestException:
            print("⚠️  OBİS'e bağlanılamadı.")
            return None
        print("⚠️  OBİS oturumu sona ermiş.")
    else:
        print("⚠️  OBİS oturumu bulunamadı.")

    print("Yeni token gir (Enter ile iptal):")
    try:
        raw = input("ASP.NET_SessionId: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n❌ İptal edildi.")
        return None
    if not raw:
        print("❌ İptal edildi.")
        return None

    new_cookie = _extract_token(raw)
    print(f"  → Ayıklanan token: {new_cookie[:8]}...{new_cookie[-4:]}")
    if _test_session(new_cookie):
        save_session(new_cookie)
        s = requests.Session()
        s.headers.update(HEADERS)
        s.cookies.set("ASP.NET_SessionId", new_cookie, domain="obis.gelisim.edu.tr")
        return s
    print("❌ Token geçersiz.")
    return None

# ── Sınav tarihleri ───────────────────────────────────────────────────────────

def get_sinav_tarihleri(session: requests.Session) -> list[dict]:
    try:
        r = session.get("https://obis.gelisim.edu.tr/Sinav_Tarihlerim.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠️  Sınav tarihleri alınamadı: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": "grdTanim"})
    if not table:
        return []
    results = []
    for row in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not cells or not any(cells) or len(cells) < 5:
            continue
        results.append({
            "kod":   cells[0],
            "ders":  cells[1],
            "sube":  cells[2],
            "tur":   cells[3],
            "tarih": cells[4],
            "saat":  cells[5] if len(cells) > 5 else "",
            "durum": cells[6] if len(cells) > 6 else "",
            "yer":   cells[7] if len(cells) > 7 else "",
            "date":  _parse_tarih(cells[4]),
        })
    return results

def print_sinav_tarihleri(sinavlar: list[dict]):
    if not sinavlar:
        print("  Sınav tarihi bulunamadı.")
        return

    parse_ok  = [s for s in sinavlar if s["date"]]
    parse_bad = [s for s in sinavlar if not s["date"]]
    parse_ok.sort(key=lambda s: s["date"])

    groups: dict = defaultdict(list)
    for s in parse_ok:
        groups[s["date"]].append(s)

    sorted_dates = sorted(groups.keys())
    color_map = {d: _COLORS[i % len(_COLORS)] for i, d in enumerate(sorted_dates)}
    today = date.today()

    print()
    prev_date = None

    for d in sorted_dates:
        # Boşluk gösterimi
        if prev_date is not None:
            delta = (d - prev_date).days
            if delta > 2:
                print(f"  {_DIM}{'─'*52}{_RESET}")
                print(f"  {_DIM}           ⏳  {delta} gün boş{_RESET}")
                print(f"  {_DIM}{'─'*52}{_RESET}")
                print()

        color = color_map[d]

        # Türkçe tarih etiketi
        ay_ad = next(tr for tr, num in _TR_AYLAR.items() if num == d.month)
        gun_label = f"{d.day} {ay_ad} {d.year}"

        # Kalan gün
        kalan = (d - today).days
        if kalan == 0:
            kalan_str = "  ← BUGÜN 🔴"
        elif kalan == 1:
            kalan_str = "  ← YARIN ⚡"
        elif kalan > 0:
            kalan_str = f"  ← {kalan} gün kaldı"
        else:
            kalan_str = "  (geçti)"

        print(f"  {color}{_BOLD}📅  {gun_label}{kalan_str}{_RESET}")
        print(f"  {color}{'─'*68}{_RESET}")

        for s in groups[d]:
            yer = s['yer'][:28] if s['yer'] else "—"
            print(f"  {color}  {s['kod']:<10} {s['ders'][:26]:<28} "
                  f"{s['tur']:<8} {s['saat']:<6} {yer}{_RESET}")
        print()
        prev_date = d

    if parse_bad:
        print(f"  {_DIM}── Tarihi belirlenemeyen ──{_RESET}")
        for s in parse_bad:
            print(f"  {s['kod']:<10} {s['ders'][:26]:<28} {s['tarih']}")
        print()

    print(f"  Toplam: {len(sinavlar)} sınav\n")

# ── Notlar ────────────────────────────────────────────────────────────────────

def get_notlar(session: requests.Session) -> list[list]:
    try:
        r = session.get("https://obis.gelisim.edu.tr/Ders_Notlari.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠️  Notlar alınamadı: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": lambda x: x and "grd" in x.lower()})
    if not table:
        return []
    results = []
    for row in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if any(cells):
            results.append(cells)
    return results

# ── Devamsızlık ───────────────────────────────────────────────────────────────

def get_devamsizlik(session: requests.Session) -> list[list]:
    try:
        r = session.get("https://obis.gelisim.edu.tr/Devamsizlik.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠️  Devamsızlık bilgisi alınamadı: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": lambda x: x and "grd" in x.lower()})
    if not table:
        return []
    results = []
    for row in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if any(cells):
            results.append(cells)
    return results

# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def obis_main(args=None):
    if args and getattr(args, "setup", False):
        force = getattr(args, "force", False)
        setup_obis(force=force)
        return

    cmd = getattr(args, "subcommand", None) or "sinav"

    session = get_session()
    if not session:
        return

    if cmd == "sinav":
        sinavlar = get_sinav_tarihleri(session)
        print_sinav_tarihleri(sinavlar)
    elif cmd == "notlar":
        notlar = get_notlar(session)
        for row in notlar:
            print(" | ".join(row))
    elif cmd == "devamsizlik":
        devamsizlik = get_devamsizlik(session)
        for row in devamsizlik:
            print(" | ".join(row))
    else:
        sinavlar = get_sinav_tarihleri(session)
        print_sinav_tarihleri(sinavlar)

if __name__ == "__main__":
    import sys
    class _Args:
        setup      = "--setup" in sys.argv
        force      = "--force" in sys.argv
        subcommand = next((a for a in sys.argv[1:]
                           if a in ("sinav","notlar","devamsizlik")), "sinav")
    obis_main(_Args())
