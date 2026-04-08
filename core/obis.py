#!/usr/bin/env python3
"""
ALMS İndirici — OBİS + LMS modülü
Sınav tarihleri, notlar, devamsızlık, transkript,
ders programı, duyurular, zaman çizelgesi
"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
from collections import defaultdict
from utils.paths import CONFIG_DIR, ensure_secure_dir

SESSION_FILE     = CONFIG_DIR / "obis_session"
LMS_SESSION_FILE = CONFIG_DIR / "lms_session"

OBIS_BASE = "https://obis.gelisim.edu.tr"
LMS_BASE  = "https://lms.gelisim.edu.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
    "Referer":    f"{OBIS_BASE}/",
}
LMS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
    "Referer":    f"{LMS_BASE}/",
}

from utils.colors import PALETTE as _COLORS, RESET as _RESET, BOLD as _BOLD, DIM as _DIM
import utils.colors as _C

_TR_AYLAR = {
    "Ocak":1,"Şubat":2,"Mart":3,"Nisan":4,
    "Mayıs":5,"Haziran":6,"Temmuz":7,"Ağustos":8,
    "Eylül":9,"Ekim":10,"Kasım":11,"Aralık":12,
}
_TR_GUNLER = {
    "Monday":"Pazartesi","Tuesday":"Salı","Wednesday":"Çarşamba",
    "Thursday":"Perşembe","Friday":"Cuma","Saturday":"Cumartesi","Sunday":"Pazar"
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

def _ay_adi(month: int) -> str:
    return next((tr for tr, num in _TR_AYLAR.items() if num == month), "?")

# ── OBİS Cookie yönetimi ──────────────────────────────────────────────────────

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
            val = raw.decode(errors="ignore").strip()
        return val if val else None
    except Exception:
        return None

def _extract_token(raw: str) -> str:
    raw = raw.strip()
    for pattern in [
        r'ASP\.NET_SessionId[=:"\s]+([a-z0-9]+)',
        r'["\']([a-z0-9]{20,})["\']',
        r'([a-z0-9]{20,})',
    ]:
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            return m.group(1)
    return raw

def _test_session(cookie: str) -> bool:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.cookies.set("ASP.NET_SessionId", cookie, domain="obis.gelisim.edu.tr")
    try:
        r = s.get(f"{OBIS_BASE}/Default.aspx", allow_redirects=True, timeout=10)
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
    print("3. ASP.NET_SessionId değerini kopyala\n")
    try:
        raw = input("ASP.NET_SessionId: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n❌ İptal edildi.")
        return
    if not raw:
        print("❌ Boş giriş.")
        return
    cookie = _extract_token(raw)
    print(f"  → Token: {cookie[:8]}...{cookie[-4:]}")
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
            r = s.get(f"{OBIS_BASE}/Default.aspx", allow_redirects=True, timeout=10)
            if "login" not in r.url.lower():
                return s
        except requests.RequestException:
            print("⚠  OBİS'e bağlanılamadı.")
            return None
        print("⚠  OBİS oturumu sona ermiş.")
    else:
        print("⚠  OBİS oturumu bulunamadı.")

    print("Yeni token gir (Enter ile iptal):")
    try:
        raw = input("ASP.NET_SessionId: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None
    if not raw:
        return None

    new_cookie = _extract_token(raw)
    if _test_session(new_cookie):
        save_session(new_cookie)
        s = requests.Session()
        s.headers.update(HEADERS)
        s.cookies.set("ASP.NET_SessionId", new_cookie, domain="obis.gelisim.edu.tr")
        return s
    print("❌ Token geçersiz.")
    return None


def get_session_silent() -> "requests.Session | None":
    """
    OBİS oturumu al — interaktif prompt YOK.
    Otomasyon (cron, notify-check) için kullanılır.
    Oturum geçersizse None döner, kullanıcıya sormaz.
    """
    cookie = load_session()
    if not cookie:
        return None
    s = requests.Session()
    s.headers.update(HEADERS)
    s.cookies.set("ASP.NET_SessionId", cookie, domain="obis.gelisim.edu.tr")
    try:
        r = s.get(f"{OBIS_BASE}/Default.aspx", allow_redirects=True, timeout=10)
        if "login" not in r.url.lower():
            return s
    except requests.RequestException:
        pass
    return None

# ── Sınav tarihleri ───────────────────────────────────────────────────────────

def get_sinav_tarihleri(session: requests.Session) -> list[dict]:
    try:
        r = session.get(f"{OBIS_BASE}/Sinav_Tarihlerim.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠  Sınav tarihleri alınamadı: {e}")
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
    parse_ok  = sorted([s for s in sinavlar if s["date"]], key=lambda s: s["date"])
    parse_bad = [s for s in sinavlar if not s["date"]]
    groups = defaultdict(list)
    for s in parse_ok:
        groups[s["date"]].append(s)
    sorted_dates = sorted(groups.keys())
    color_map = {d: _COLORS[i % len(_COLORS)] for i, d in enumerate(sorted_dates)}
    today = date.today()
    print()
    prev_date = None
    for d in sorted_dates:
        if prev_date is not None:
            delta = (d - prev_date).days
            if delta > 2:
                print(f"  {_DIM}{'─'*52}{_RESET}")
                print(f"  {_DIM}           ⏳  {delta} gün boş{_RESET}")
                print(f"  {_DIM}{'─'*52}{_RESET}")
                print()
        color = color_map[d]
        gun_label = f"{d.day} {_ay_adi(d.month)} {d.year}"
        kalan = (d - today).days
        kalan_str = (
            "  ← BUGÜN 🔴" if kalan == 0 else
            "  ← YARIN ⚡" if kalan == 1 else
            f"  ← {kalan} gün kaldı" if kalan > 0 else "  (geçti)"
        )
        print(f"  {color}{_BOLD}📅  {gun_label}{kalan_str}{_RESET}")
        print(f"  {color}{'─'*68}{_RESET}")
        for s in groups[d]:
            yer = s["yer"][:28] if s["yer"] else "—"
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

# ── Ders notları (Ders_Notlari.aspx) ─────────────────────────────────────────

def get_notlar(session: requests.Session) -> list[dict]:
    """
    Döner: [{
        "donem": "2025-2026-BAHAR (1.SINIF-2)",
        "dersler": [{
            "kod", "ad", "kredi", "akts", "hoca",
            "odev", "lab", "quiz", "vize", "vize_mazeret",
            "final", "final_uygulama", "butunleme", "harf"
        }]
    }]
    """
    try:
        r = session.get(f"{OBIS_BASE}/Ders_Notlari.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠  Notlar alınamadı: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    # Her dönem ayrı bir tablo içinde: dtList_Sinif_grdTanim_0, _1, ...
    donemler = []
    sinif_list = soup.find("table", {"id": "dtList_Sinif"})
    if not sinif_list:
        return []
    for idx, td in enumerate(sinif_list.find_all("td", recursive=False)):
        baslik_el = td.find(id=lambda x: x and "lblBASLIK" in x)
        if not baslik_el:
            continue
        donem_adi = baslik_el.get_text(strip=True)
        tablo = td.find("table", {"id": lambda x: x and f"grdTanim_{idx}" in str(x)})
        if not tablo:
            continue
        dersler = []
        for row in tablo.find_all("tr")[1:]:
            cells = [td2.get_text(strip=True) for td2 in row.find_all("td")]
            if len(cells) < 5 or not cells[0]:
                continue
            dersler.append({
                "kod":              cells[0],
                "ad":               cells[1],
                "kredi":            cells[2],
                "akts":             cells[3],
                "hoca":             cells[4],
                "odev":             cells[5]  if len(cells) > 5  else "",
                "lab":              cells[7]  if len(cells) > 7  else "",
                "quiz":             cells[9]  if len(cells) > 9  else "",
                "vize":             cells[11] if len(cells) > 11 else "",
                "vize_mazeret":     cells[13] if len(cells) > 13 else "",
                "final":            cells[14] if len(cells) > 14 else "",
                "final_uygulama":   cells[16] if len(cells) > 16 else "",
                "butunleme":        cells[18] if len(cells) > 18 else "",
                "harf":             cells[19] if len(cells) > 19 else "",
            })
        if dersler:
            donemler.append({"donem": donem_adi, "dersler": dersler})
    return donemler

def print_notlar(donemler: list[dict]):
    if not donemler:
        print("  Not bilgisi bulunamadı.")
        return
    for d in donemler:
        print(f"\n  {_BOLD}{_C.CYAN}{d['donem']}{_RESET}")
        print(f"  {'─'*80}")
        print(f"  {'Kod':<10} {'Ders':<28} {'Kr':>3} {'Ödev':>5} {'Quiz':>5} "
              f"{'Vize':>5} {'Final':>6} {'Büt':>5} {'Harf':>6}")
        print(f"  {'─'*80}")
        for dr in d["dersler"]:
            harf = dr["harf"]
            # Renk: FF/DZ kırmızı, geçti yeşil, boş dim
            if harf in ("FF", "DZ", "NA"):
                harf_str = f"{_C.RED}{_BOLD}{harf:<6}{_RESET}"
            elif harf and harf not in ("E", ""):
                harf_str = f"{_C.GREEN}{_BOLD}{harf:<6}{_RESET}"
            else:
                harf_str = f"{_DIM}{harf or '—':<6}{_RESET}"

            final = dr["final"] or dr["butunleme"] or "—"
            print(f"  {dr['kod']:<10} {dr['ad'][:27]:<28} {dr['kredi']:>3} "
                  f"{dr['odev'] or '—':>5} {dr['quiz'] or '—':>5} "
                  f"{dr['vize'] or '—':>5} {final:>6}   {dr['butunleme'] or '—':>5} "
                  f"  {harf_str}")
    print()

# ── Transkript (Transcript_Trk.aspx) ─────────────────────────────────────────

def get_transkript(session: requests.Session) -> dict:
    """
    Döner: {
        "donemler": [{
            "donem", "dersler": [{kod, ad, z_s, t, u, k, akts, harf, ak}],
            "som_al_kr", "som_tam_kr", "som_akts", "som_ag_kr", "ano",
            "kum_al_kr", "kum_tam_kr", "kum_akts", "kum_ag_kr", "gano"
        }]
    }
    """
    try:
        r = session.get(f"{OBIS_BASE}/Transcript_Trk.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠  Transkript alınamadı: {e}")
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    main_table = soup.find("table", {"id": "tblNotlar_1_Sene"})
    if not main_table:
        return {}

    donemler = []
    # Her dönem ayrı bir iç tabloda
    for inner in main_table.find_all("table"):
        rows = inner.find_all("tr")
        if not rows:
            continue
        # İlk satır dönem başlığı
        baslik = rows[0].get_text(strip=True)
        if not baslik or "SINIF" not in baslik and "GÜZ" not in baslik and "BAHAR" not in baslik:
            continue
        dersler = []
        som_str = ""
        kum_str = ""
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if not cells:
                continue
            # Özet satırları
            txt = " ".join(cells)
            if "Söm" in txt:
                som_str = txt
            elif "Küm" in txt:
                kum_str = txt
            elif len(cells) >= 9 and cells[0]:
                dersler.append({
                    "kod":  cells[0],
                    "ad":   cells[1],
                    "z_s":  cells[2],
                    "t":    cells[3],
                    "u":    cells[4],
                    "k":    cells[5],
                    "akts": cells[6],
                    "harf": cells[8],
                    "ak":   cells[9] if len(cells) > 9 else "",
                })

        def _parse_ozet(s: str) -> dict:
            d = {}
            for key, pat in [
                ("al_kr",  r'Al\.Kr:\s*([\d,\.]+)'),
                ("tam_kr", r'Tam\.Kr:\s*([\d,\.]+)'),
                ("akts",   r'Tam\.Akts:\s*([\d,\.]+)'),
                ("ag_kr",  r'Ağ\.Kr\s*:\s*([\d,\.]+)'),
                ("ort",    r'(?:ANO|GANO)\s*:\s*([\d,\.]+)'),
            ]:
                m = re.search(pat, s)
                d[key] = m.group(1) if m else ""
            return d

        som = _parse_ozet(som_str)
        kum = _parse_ozet(kum_str)
        ano  = som.pop("ort", "")
        gano = kum.pop("ort", "")

        if dersler:
            donemler.append({
                "donem":       baslik,
                "dersler":     dersler,
                **{f"som_{k}": v for k, v in som.items()},
                "ano":         ano,
                **{f"kum_{k}": v for k, v in kum.items()},
                "gano":        gano,
            })
    return {"donemler": donemler}

def print_transkript(data: dict):
    if not data or not data.get("donemler"):
        print("  Transkript bulunamadı.")
        return
    donemler = data["donemler"]
    print()
    for d in donemler:
        print(f"  {_BOLD}{_C.CYAN}{d['donem']}{_RESET}")
        print(f"  {'─'*72}")
        print(f"  {'Kod':<10} {'Ders':<32} {'Z/S':>3} {'K':>3} {'AKTS':>5} {'Harf':>6} {'AK':>6}")
        print(f"  {'─'*72}")
        for dr in d["dersler"]:
            harf = dr["harf"]
            if harf in ("FF", "DZ"):
                h = f"{_C.RED}{_BOLD}{harf}{_RESET}"
            elif harf and harf not in ("E", ""):
                h = f"{_C.GREEN}{harf}{_RESET}"
            else:
                h = f"{_DIM}{harf or '—'}{_RESET}"
            print(f"  {dr['kod']:<10} {dr['ad'][:31]:<32} {dr['z_s']:>3} "
                  f"{dr['k']:>3} {dr['akts']:>5} {h:>6}   {dr['ak']:>6}")
        # Özet
        if d.get("ano"):
            print(f"  {_DIM}  Dönem → Al.Kr: {d.get('som_al_kr','?')}  "
                  f"Tam.Kr: {d.get('som_tam_kr','?')}  "
                  f"AKTS: {d.get('som_akts','?')}  ANO: {_BOLD}{d['ano']}{_RESET}")
        if d.get("gano"):
            print(f"  {_DIM}  Kümülatif → Al.Kr: {d.get('kum_al_kr','?')}  "
                  f"Tam.Kr: {d.get('kum_tam_kr','?')}  "
                  f"AKTS: {d.get('kum_akts','?')}  {_BOLD}GANO: {d['gano']}{_RESET}")
        print()

# ── Ders programı (Ders_Program.aspx) ────────────────────────────────────────

def get_ders_programi(session: requests.Session) -> list[dict]:
    """
    Döner: [{gun, saat, ders_kodu, ders_adi, yer, hoca, sube}]
    """
    try:
        r = session.get(f"{OBIS_BASE}/Ders_Program.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠  Ders programı alınamadı: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    tablo = soup.find("table", {"id": "tbl"})
    if not tablo:
        return []

    rows = tablo.find_all("tr")
    if not rows:
        return []

    # Başlık satırından günleri al
    gunler = []
    for th in rows[0].find_all("td"):
        txt = th.get_text(strip=True)
        if txt and txt != "SAAT":
            gunler.append(txt)

    dersler = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        saat = cells[0].get_text(strip=True)
        for i, cell in enumerate(cells[1:]):
            if i >= len(gunler):
                break
            txt = cell.get_text(" ", strip=True)
            if not txt or txt == " ":
                continue
            # Format: "KOD-AD\nYER\nHOCA\nŞUBE"
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
            if not lines:
                continue
            # İlk satır genelde KOD-DERS ADI
            ilk = lines[0]
            m = re.match(r'([A-Z]{2,6}\d{3})-(.+)', ilk)
            kod  = m.group(1) if m else ""
            ad   = m.group(2) if m else ilk
            yer  = lines[1] if len(lines) > 1 else ""
            hoca = lines[2] if len(lines) > 2 else ""
            sube = lines[3] if len(lines) > 3 else ""
            dersler.append({
                "gun":       gunler[i],
                "saat":      saat,
                "ders_kodu": kod,
                "ders_adi":  ad.strip(),
                "yer":       yer,
                "hoca":      hoca,
                "sube":      sube,
            })
    return dersler

def _trunc(text: str, max_len: int) -> str:
    """Metni max_len'de kes, kelime sınırında, … ile bitir."""
    if not text or len(text) <= max_len:
        return text or ""
    cut = text[:max_len - 1]
    sp  = cut.rfind(" ")
    if sp > max_len // 2:
        cut = cut[:sp]
    return cut.rstrip() + "…"


def _parse_ders_cell(raw_adi: str, raw_yer: str) -> tuple[str, str]:
    """
    OBİS bazen yer bilgisini ders adının içine koyar:
    'MATEMATİK II (J BLOK) KAT: 3' → ('MATEMATİK II', 'J BLOK · KAT: 3')
    Eğer yer zaten ayrı geldiyse dokunma.
    """
    if raw_yer:
        return raw_adi, raw_yer
    m = re.match(r'^(.+?)\s*\((.+?)\)\s*(.*)$', raw_adi)
    if m:
        ad    = m.group(1).strip()
        yer   = m.group(2).strip()
        extra = m.group(3).strip()
        if extra:
            yer = f"{yer} · {extra}"
        return ad, yer
    return raw_adi, ""


def print_ders_programi(dersler: list[dict]):
    if not dersler:
        print("  Ders programı bulunamadı.")
        return

    gun_sirasi = ["PAZARTESİ","SALI","ÇARŞAMBA","PERŞEMBE","CUMA","CUMARTESİ","PAZAR"]
    _WEEKDAY_TO_GUN = ["PAZARTESİ","SALI","ÇARŞAMBA","PERŞEMBE","CUMA","CUMARTESİ","PAZAR"]
    today_gun = _WEEKDAY_TO_GUN[date.today().weekday()]

    # Aynı gündeki aynı dersi (ders_kodu) grupla → saat aralığı hesapla
    by_gun_kod: dict[tuple, list] = defaultdict(list)
    for d in dersler:
        by_gun_kod[(d["gun"].upper(), d["ders_kodu"])].append(d)

    print()
    for gun in gun_sirasi:
        # Bu güne ait kurs grupları — ilk saate göre sırala
        gun_gruplari = [
            (kod, slots)
            for (g, kod), slots in by_gun_kod.items()
            if g == gun
        ]
        if not gun_gruplari:
            continue

        gun_gruplari.sort(key=lambda x: min(s["saat"] for s in x[1]))

        is_today = (gun == today_gun)
        if is_today:
            print(f"  {_BOLD}{_C.GREEN}── {gun}  ← BUGÜN ──{_RESET}")
        else:
            print(f"  {_BOLD}{_C.CYAN}── {gun} ──{_RESET}")
        print()

        for kod, slots in gun_gruplari:
            slots = sorted(slots, key=lambda s: s["saat"])
            first = slots[0]
            last  = slots[-1]

            # Saat aralığı: "09:00-09:50" → başlangıç "09:00", bitiş "09:50"
            def _t(saat, part):
                return saat.split("-")[part] if "-" in saat else saat
            baslangic = _t(first["saat"], 0)
            bitis     = _t(last["saat"],  1)
            sure_str  = f"{baslangic}–{bitis}"  if baslangic != bitis else baslangic

            # Ders adı ve yer ayrıştır
            ders_adi, yer = _parse_ders_cell(first["ders_adi"], first["yer"])
            hoca = first["hoca"] or ""

            # Saat sayısı
            saat_sayi = len(slots)
            saat_label = f"{saat_sayi} saat" if saat_sayi > 1 else "1 saat"

            # Satır 1: KOD  Ders Adı (kırpılmış)     09:00–14:50  5 saat
            ad_goster = _trunc(ders_adi, 30)
            row_color = _C.GREEN if is_today else _C.YELLOW
            print(
                f"  {_BOLD}{row_color}{kod:<8}{_RESET}"
                f"  {_BOLD}{ad_goster:<32}{_RESET}"
                f"  {(_C.GREEN if is_today else _C.CYAN)}{sure_str}{_RESET}"
                f"  {_DIM}{saat_label}{_RESET}"
            )

            # Satır 2: (boşluk hizalı) Yer · Hoca
            yer_goster  = _trunc(yer,  35) if yer  else "—"
            hoca_goster = _trunc(hoca, 30) if hoca else ""
            alt_satir   = yer_goster
            if hoca_goster:
                alt_satir += f"  ·  {hoca_goster}"
            print(f"  {' ' * 8}  {_DIM}{alt_satir}{_RESET}")
            print()

        print()

# ── OBİS Duyuruları (Default.aspx) ───────────────────────────────────────────

def get_obis_duyurular(session: requests.Session) -> list[dict]:
    """
    OBİS anasayfasındaki duyurular — başlık, tarih, tür, birim ve içerik.
    DOM: grdTanim_lblDUYURU_BASLIK_N, lblYAYIN_DATE_N, lblDUYURU_TURU_N,
         lblDUYURUYU_YAPANIN_BIRIMI_N, lblDUYURU_N (içerik)
    """
    try:
        r = session.get(f"{OBIS_BASE}/Default.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠  OBİS duyuruları alınamadı: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    duyurular = []
    for i in range(20):
        baslik_el = soup.find(id=f"grdTanim_lblDUYURU_BASLIK_{i}")
        if not baslik_el:
            break
        tarih_el  = soup.find(id=f"grdTanim_lblYAYIN_DATE_{i}")
        tur_el    = soup.find(id=f"grdTanim_lblDUYURU_TURU_{i}")
        birim_el  = soup.find(id=f"grdTanim_lblDUYURUYU_YAPANIN_BIRIMI_{i}")
        icerik_el = soup.find(id=f"grdTanim_lblDUYURU_{i}")

        # İçeriği temiz metin olarak al, fazla boşlukları temizle
        icerik = ""
        if icerik_el:
            # Paragraflar arası boş satır bırak
            parcalar = []
            for el in icerik_el.find_all(["p", "div", "span", "li"]):
                txt = el.get_text(" ", strip=True)
                if txt and len(txt) > 3:
                    parcalar.append(txt)
            icerik = "\n".join(dict.fromkeys(parcalar))  # tekrarları kaldır
            if not icerik:
                icerik = icerik_el.get_text(" ", strip=True)
            # Max 600 karakter
            if len(icerik) > 600:
                icerik = icerik[:597] + "..."

        duyurular.append({
            "baslik": baslik_el.get_text(strip=True),
            "tarih":  tarih_el.get_text(strip=True)  if tarih_el  else "",
            "tur":    tur_el.get_text(strip=True)     if tur_el    else "",
            "birim":  birim_el.get_text(strip=True)   if birim_el  else "",
            "icerik": icerik,
        })
    return duyurular

# ── LMS Duyuruları + Zaman Çizelgesi ─────────────────────────────────────────

def get_lms_session(alms_token: str | None = None) -> requests.Session | None:
    """
    LMS oturumu oluşturur. ALMS token'ı varsa kullan,
    yoksa mevcut LMS session cookie'yi dene.
    """
    s = requests.Session()
    s.headers.update(LMS_HEADERS)
    if alms_token:
        # ALMS token'ı LMS'e bearer olarak geç
        s.headers["Authorization"] = f"Bearer {alms_token}"
    try:
        r = s.get(f"{LMS_BASE}/almsp/u/home", allow_redirects=True, timeout=10)
        if r.status_code == 200 and "home" in r.url:
            return s
    except requests.RequestException:
        pass
    return None

def get_lms_duyurular(alms_token: str) -> list[dict]:
    """
    LMS/ALMS duyuruları. ALMS web UI ile Bearer token birlikte çalışmıyor
    (web UI cookie-based, API JWT-based), bu yüzden sessiz boş döner.
    İleride ALMS API endpoint bulunursa buraya eklenir.
    """
    return []

def get_lms_zaman_cizelgesi(alms_token: str) -> list[dict]:
    """
    LMS zaman çizelgesi.
    DOM: #activity-card → h4 (tarih başlığı), ul → li → span (saat), label (tür+ad), p (ders)
    """
    s = requests.Session()
    s.headers.update(LMS_HEADERS)
    s.headers["Authorization"] = f"Bearer {alms_token}"
    try:
        r = s.get(f"{LMS_BASE}/almsp/u/home", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠  Zaman çizelgesi alınamadı: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    aktiviteler = []
    for card in soup.find_all(id="activity-card"):
        tarih_el = card.find("h4")
        tarih_str = tarih_el.get_text(strip=True) if tarih_el else ""
        ul = card.find("ul")
        if not ul:
            continue
        for li in ul.find_all("li"):
            saat  = li.find("span")
            label = li.find("label")
            ders  = li.find("p")
            if not label:
                continue
            # label içinde <b>Tür</b> ve ad var
            b = label.find("b")
            tur = b.get_text(strip=True) if b else ""
            ad  = label.get_text(strip=True).replace(tur, "").strip(" -–")
            aktiviteler.append({
                "tarih":     tarih_str,
                "saat":      saat.get_text(strip=True) if saat else "",
                "tur":       tur,
                "ad":        ad,
                "ders":      ders.get_text(strip=True) if ders else "",
                "gecmis":    "active" in li.get("class", []),
            })
    return aktiviteler

# ── Birleşik duyuru ekranı ────────────────────────────────────────────────────

def print_duyurular(obis: list[dict], lms: list[dict]):
    import textwrap
    print()
    if not obis and not lms:
        print("  Duyuru bulunamadı.")
        return

    if lms:
        print(f"  {_BOLD}{_C.CYAN}── LMS Duyuruları ──{_RESET}")
        for i, d in enumerate(lms[:5], 1):
            print(f"  {_C.YELLOW}{i}.{_RESET} {_BOLD}{d['baslik'][:70]}{_RESET}")
            if d.get("yazar"):
                print(f"     {_DIM}{d['yazar']}  ·  {d.get('tarih','')}{_RESET}")
        print()

    if obis:
        print(f"  {_BOLD}{_C.CYAN}── OBİS Duyuruları ──{_RESET}")
        for i, d in enumerate(obis, 1):
            # Başlık
            tur_str = f"{_DIM}[{d['tur']}]{_RESET} " if d["tur"] else ""
            print()
            print(f"  {_C.YELLOW}{_BOLD}{i}.{_RESET} {tur_str}{_BOLD}{d['baslik'][:75]}{_RESET}")

            # Birim + tarih
            meta = []
            if d.get("birim"):
                meta.append(d["birim"])
            if d.get("tarih"):
                meta.append(d["tarih"])
            if meta:
                print(f"     {_DIM}{' · '.join(meta)}{_RESET}")

            # İçerik — satıra böl, girintili göster
            if d.get("icerik"):
                # Her satırı 72 karakterde sar
                for satir in d["icerik"].splitlines():
                    satir = satir.strip()
                    if not satir:
                        continue
                    for wraped in textwrap.wrap(satir, width=72):
                        print(f"     {wraped}")

            print(f"  {_DIM}{'─'*70}{_RESET}")
        print()

def print_zaman_cizelgesi(aktiviteler: list[dict]):
    if not aktiviteler:
        print("  Zaman çizelgesi boş.")
        return
    tur_renk = {
        "Ödev":    _C.YELLOW,
        "Sınav":   _C.RED,
        "Doküman": _C.CYAN,
        "Quiz":    _C.MAGENTA,
    }
    print()
    bugun = []
    gelecek = []
    gecmis = []
    for a in aktiviteler:
        if a["gecmis"]:
            gecmis.append(a)
        elif "today" in a.get("tarih","").lower() or a["tarih"] == "":
            bugun.append(a)
        else:
            gelecek.append(a)

    if gelecek:
        print(f"  {_BOLD}{_C.GREEN}── Yaklaşan ──{_RESET}")
        prev = ""
        for a in gelecek:
            if a["tarih"] != prev:
                print(f"\n  {_BOLD}{a['tarih']}{_RESET}")
                prev = a["tarih"]
            renk = tur_renk.get(a["tur"], _C.CYAN)
            print(f"    {renk}{_BOLD}{a['tur']:<10}{_RESET}  "
                  f"{a['saat']:<18} {a['ad'][:40]}")
            if a["ders"]:
                print(f"    {_DIM}{'':>10}  {a['ders']}{_RESET}")
        print()

    if gecmis:
        print(f"  {_DIM}── Geçmiş ({len(gecmis)} etkinlik) ──{_RESET}")
        for a in gecmis[:3]:
            renk = tur_renk.get(a["tur"], _DIM)
            print(f"  {_DIM}  {a['tur']:<10}  {a['saat']:<18} {a['ad'][:40]}{_RESET}")
        if len(gecmis) > 3:
            print(f"  {_DIM}  ... ve {len(gecmis)-3} tane daha{_RESET}")
        print()

# ── Devamsızlık ───────────────────────────────────────────────────────────────

def get_devamsizlik(session: requests.Session) -> list[dict]:
    """
    Devamsızlık sayfasını parse eder.
    Kolon başlıklarını okuyarak sütun indekslerini dinamik olarak belirler.
    Döner: [{kod, ad, devamsizlik, limit, oran}]
    """
    try:
        r = session.get(f"{OBIS_BASE}/Devamsizlik.aspx", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠  Devamsızlık bilgisi alınamadı: {e}")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": lambda x: x and "grd" in x.lower()})
    if not table:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    # Kolon başlıklarını oku
    headers = [th.get_text(strip=True).upper() for th in rows[0].find_all(["th", "td"])]

    # Anahtar kolonları bul
    def col(keywords):
        for i, h in enumerate(headers):
            if any(k in h for k in keywords):
                return i
        return -1

    i_kod  = col(["KOD", "DERS KODU"])
    i_ad   = col(["ADI", "DERS ADI", "DERS", "DERSLER"])
    i_dev  = col(["DEVAMSIZLIK", "DEVAM"])
    i_lim  = col(["LİMİT", "LIMIT", "HAKKEDERST", "MAKSİMUM"])

    # Fallback: OBİS genelde kod, ad, devamsızlık, limit sırası
    if i_kod < 0: i_kod = 0
    if i_ad  < 0: i_ad  = 1
    if i_dev < 0: i_dev = 2
    if i_lim < 0: i_lim = 3

    results = []
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not any(cells) or len(cells) < 2:
            continue
        def safe(i):
            return cells[i] if 0 <= i < len(cells) else ""
        results.append({
            "kod":        safe(i_kod),
            "ad":         safe(i_ad),
            "devamsizlik": safe(i_dev),
            "limit":      safe(i_lim),
        })
    return results

def print_devamsizlik(rows: list[dict]):
    if not rows:
        print("  Devamsızlık bilgisi bulunamadı.")
        return
    print()
    print(f"  {'Kod':<10} {'Ders':<34} {'Devamsızlık':>12} {'Limit':>8}")
    print(f"  {'─'*70}")
    for r in rows:
        kod  = (r.get("kod","") or "")[:9]
        ders = (r.get("ad","")  or "")[:33]
        dev  = r.get("devamsizlik","") or "—"
        lim  = r.get("limit","")      or "—"
        # Kırmızı: devamsızlık limiti >= %80
        uyari = False
        try:
            d = float(dev.replace(",","."))
            l = float(lim.replace(",","."))
            if l > 0 and d >= l * 0.8:
                uyari = True
        except (ValueError, ZeroDivisionError):
            pass
        satir = f"  {kod:<10} {ders:<34} {dev:>12} {lim:>8}"
        if uyari:
            print(f"{_C.RED}{_BOLD}{satir}  ⚠{_RESET}")
        else:
            print(satir)
    print()

# ── Yaklaşan sınav bildirimi ──────────────────────────────────────────────────

def check_upcoming_exams_notify(session: requests.Session) -> None:
    """
    1 ve 3 gün içindeki sınavlar için masaüstü bildirimi gönder.
    cmd_sync'ten çağrılır — cron her gün otomatik kontrol eder.
    """
    from datetime import date as _date
    from utils.notify import send as _notify

    try:
        sinavlar = get_sinav_tarihleri(session)
    except Exception:
        return

    today = _date.today()
    for s in sinavlar:
        sinav_date = s.get("date")
        if not isinstance(sinav_date, _date):
            continue
        delta = (sinav_date - today).days
        if delta not in (1, 3):
            continue

        gun_str = "Yarın" if delta == 1 else "3 gün sonra"
        title   = f"📚 Sınav: {gun_str}"
        parts   = [f"{s['ders']}  {s.get('tur','')}",
                   f"{s['tarih']}  {s.get('saat','')}"]
        if s.get("yer"):
            parts.append(s["yer"])
        _notify(title, "  ·  ".join(p for p in parts if p.strip()))


# ── GPA / Not simülasyonu ─────────────────────────────────────────────────────

# Türkiye standart harf notu → minimum puan eşiği
_HARF_ESIK = [
    ("AA", 90), ("BA", 85), ("BB", 75), ("CB", 65),
    ("CC", 55), ("DC", 50), ("DD", 45), ("FD", 40), ("FF", 0),
]

# 4'lük sistemdeki katsayılar
_HARF_KATSAYI = {
    "AA": 4.0, "BA": 3.5, "BB": 3.0, "CB": 2.5,
    "CC": 2.0, "DC": 1.5, "DD": 1.0, "FD": 0.5, "FF": 0.0,
}


def simulate_final_grades(notlar: list[dict]) -> list[dict]:
    """
    Vize notu bilinen her ders için finalden kaç alınması gerektiğini hesapla.
    Ağırlık: %40 vize + %60 final (Türkiye üniversite standardı).

    Döner: [{
        "kod": "FIZ108", "ad": "Fizik II",
        "vize": 72.0, "final": None | float,
        "current_harf": "BB",
        "simulations": [{"harf": "AA", "gerekli": 96.7, "mumkun": True}, ...]
    }]
    """
    results = []
    for donem in notlar:
        for d in donem.get("dersler", []):
            vize_str = (d.get("vize") or "").strip()
            if not vize_str:
                continue
            try:
                vize = float(vize_str)
            except ValueError:
                continue

            final_str = (d.get("final") or "").strip()
            try:
                current_final: float | None = float(final_str) if final_str else None
            except ValueError:
                current_final = None

            sims = []
            for harf, min_puan in _HARF_ESIK:
                # min_puan = 0.4 * vize + 0.6 * final  →  final = (min - 0.4*vize) / 0.6
                gerekli = (min_puan - 0.4 * vize) / 0.6
                gerekli = round(max(0.0, min(100.0, gerekli)), 1)
                sims.append({
                    "harf":    harf,
                    "gerekli": gerekli,
                    "mumkun":  gerekli <= 100,
                })

            results.append({
                "kod":          d.get("kod", ""),
                "ad":           d.get("ad", ""),
                "vize":         vize,
                "final":        current_final,
                "current_harf": d.get("harf", ""),
                "simulations":  sims,
            })
    return results


def print_final_simulation(simdata: list[dict]):
    """
    GPA simülasyonu ekrana yazar.
    Her ders için finalden alınması gereken notları gösterir.
    """
    if not simdata:
        print("\n  Not verisi bulunamadı.")
        return

    print()
    print(f"  {_BOLD}Ağırlık: %40 Vize + %60 Final{_RESET}")
    print(f"  {_DIM}Sadece vize notu girilen dersler gösterilir.{_RESET}")
    print()

    for d in simdata:
        vize_str  = f"{d['vize']:.0f}"
        final_str = f"{d['final']:.0f}" if d["final"] is not None else "—"
        harf_str  = d["current_harf"] or "—"

        print(f"  {_BOLD}{_COLORS.get('cyan','')}{d['kod']:<8}{_RESET}"
              f"  {d['ad'][:32]:<34}"
              f"  {_DIM}Vize:{vize_str}  Final:{final_str}  {harf_str}{_RESET}")

        # Mümkün olan hedef notlar
        mumkun = [(s["harf"], s["gerekli"]) for s in d["simulations"] if s["mumkun"]]
        if mumkun:
            parts = []
            for harf, ger in mumkun:
                if ger <= 0:
                    tag = _COLORS.get("green","") + f"{harf}:geçti" + _RESET
                else:
                    tag = f"{harf}:{ger:.0f}"
                parts.append(tag)
            print(f"  {'':8}  {_DIM}Gerekli final → {_RESET}"
                  + "  ".join(parts))
        else:
            print(f"  {'':8}  {_DIM}Mevcut vize ile hiçbir not almak mümkün değil.{_RESET}")
        print()


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def obis_main(args=None):
    if args and getattr(args, "setup", False):
        setup_obis(force=getattr(args, "force", False))
        return

    cmd = getattr(args, "subcommand", None) or "sinav"

    # LMS token'ı al (duyuru ve zaman çizelgesi için)
    alms_token = None
    try:
        from core.auth import get_or_refresh_token
        tok, _ = get_or_refresh_token()
        alms_token = tok
    except Exception:
        pass

    # OBİS session
    session = get_session()

    if cmd == "sinav":
        if not session:
            return
        sinavlar = get_sinav_tarihleri(session)
        print_sinav_tarihleri(sinavlar)

    elif cmd == "notlar":
        if not session:
            return
        donemler = get_notlar(session)
        print_notlar(donemler)

    elif cmd == "transkript":
        if not session:
            return
        data = get_transkript(session)
        print_transkript(data)

    elif cmd == "program":
        if not session:
            return
        dersler = get_ders_programi(session)
        print_ders_programi(dersler)

    elif cmd == "devamsizlik":
        if not session:
            return
        rows = get_devamsizlik(session)
        print_devamsizlik(rows)

    elif cmd == "duyurular":
        obis_d = get_obis_duyurular(session) if session else []
        lms_d  = get_lms_duyurular(alms_token) if alms_token else []
        print_duyurular(obis_d, lms_d)

    elif cmd == "takvim":
        if not alms_token:
            print("⚠  LMS token gerekli.")
            return
        aktiviteler = get_lms_zaman_cizelgesi(alms_token)
        print_zaman_cizelgesi(aktiviteler)

    else:
        if not session:
            return
        sinavlar = get_sinav_tarihleri(session)
        print_sinav_tarihleri(sinavlar)
