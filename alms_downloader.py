"""
alms_downloader.py — IGU ALMS Dosya İndirici
─────────────────────────────────────────────
alms_scraper.py ile birlikte çalışır.

Kullanım:
  python alms_downloader.py                   # tüm dersler, PDF+video
  python alms_downloader.py -f pdf            # sadece PDF
  python alms_downloader.py -f video          # sadece video
  python alms_downloader.py --course FIZ      # ders adı filtresi
  python alms_downloader.py --week 7          # sadece belirli hafta
  python alms_downloader.py --list            # indirmeden listele
  python alms_downloader.py --new             # sadece yeni dosyaları indir

Kurulum:
  pip install requests cryptography tqdm
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

# alms_scraper modülünden ortak fonksiyonları al
try:
    from alms_scraper import (
        API_BASE, APP_DIR, DATA_DIR,
        decrypt_credentials, get_active_session, add_session,
        login, api_post, log, setup_logging,
    )
except ImportError:
    print("❌ alms_scraper.py bu dosyayla aynı klasörde olmalı.")
    sys.exit(1)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# ─── İndirme dizini ───────────────────────────────────────────
DOWNLOAD_DIR = APP_DIR / "downloads"
MANIFEST_FILE = APP_DIR / "download_manifest.json"


# ─── Manifest (daha önce ne indirildi) ───────────────────────
def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_manifest(manifest: dict):
    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── Ders programı çek ────────────────────────────────────────
def get_courses(token: str) -> list[dict]:
    data = api_post(token, "/api/course/enrolledcourses", {
        "Take": 1000, "Skip": 0,
        "SearchCourseName": "", "ActiveStatus": 1,
        "CourseDateFilter": 4, "isNotifications": True,
        "SearchTermId": None, "SearchProgId": None,
        "SourceCourseId": "", "MasterCourseId": "", "CourseId": "",
    })
    return data if isinstance(data, list) else data.get("items", [])


def get_term_weeks(token: str, class_id: str, course_id: str) -> list[dict]:
    """Dersin hafta listesini döndürür."""
    data = api_post(token, "/api/activity/contentpagemenu", {
        "ClassId": class_id,
        "CourseId": course_id,
    })
    return data.get("termWeeks", [])


def get_activities(token: str, class_id: str, course_id: str,
                   term_week_id: str) -> list[dict]:
    """Bir haftanın aktivitelerini (dosyalar dahil) döndürür."""
    data = api_post(token, "/api/activity/activitylist", {
        "ActivityId": "",
        "ClassId": class_id,
        "CourseId": course_id,
        "GetActivityType": 3,
        "Skip": 0,
        "Take": 500,
        "TermWeekId": term_week_id,
        "weekZero": False,
        "activityFilters": {
            "selectedActivityTypes": [],
            "searchedText": "",
            "sort": "-",
            "hasFilter": False,
        },
    })
    return data if isinstance(data, list) else []


# ─── Dosya listesi oluştur ────────────────────────────────────
def collect_files(
    token: str,
    courses: list[dict],
    file_type_filter: str | None = None,   # "pdf", "video", None=hepsi
    course_filter: str | None = None,
    week_filter: int | None = None,
) -> list[dict]:
    """
    İndirilecek dosyaların listesini döndürür.
    Her öğe: {course_name, week, activity_name, file_name,
               file_path, ext, size_bytes, class_id}
    """
    files = []
    seen_paths = set()   # tekrar çekilmiş aynı dosyaları atla

    for course in courses:
        course_name = course.get("name", "").strip()
        class_id    = course.get("classId", "")
        course_id   = course.get("courseId", "")

        # ders filtresi
        if course_filter and course_filter.upper() not in course_name.upper():
            continue

        log.info("  📖 %s", course_name)

        try:
            weeks = get_term_weeks(token, class_id, course_id)
        except Exception as e:
            log.warning("    Hafta listesi alınamadı: %s", e)
            continue

        for week in weeks:
            week_num    = week.get("week", 0)
            week_id     = week.get("termWeekId", "")
            week_label  = week.get("weekLabel", str(week_num))

            if week_filter is not None and week_num != week_filter:
                continue
            if not week_id or week_id == "0":
                continue

            try:
                activities = get_activities(token, class_id, course_id, week_id)
            except Exception as e:
                log.warning("    Hafta %s aktiviteleri alınamadı: %s", week_num, e)
                continue

            for act in activities:
                act_name  = act.get("name") or act.get("activityType", "")
                act_type  = act.get("activityType", "")
                file_list = act.get("file") or []

                for f in file_list:
                    file_path = f.get("filePath", "")
                    file_name = f.get("fileName", "")
                    ext       = f.get("extension", "").lower()
                    size      = int(f.get("size") or 0)

                    if not file_path or file_path in seen_paths:
                        continue
                    seen_paths.add(file_path)

                    # tip filtresi
                    is_video = ext in (".mp4", ".mkv", ".avi", ".mov", ".webm")
                    is_pdf   = ext in (".pdf",)
                    is_doc   = ext in (".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx")

                    if file_type_filter == "pdf" and not (is_pdf or is_doc):
                        continue
                    if file_type_filter == "video" and not is_video:
                        continue

                    files.append({
                        "course_name":  course_name,
                        "class_id":     class_id,
                        "week":         week_num,
                        "week_label":   week_label,
                        "activity_name": act_name,
                        "activity_type": act_type,
                        "file_name":    file_name,
                        "file_path":    file_path,
                        "ext":          ext,
                        "size_bytes":   size,
                    })

            # API'ye yük bindirmemek için küçük bekleme
            time.sleep(0.15)

    return files


# ─── Tek dosya indir ─────────────────────────────────────────
def download_file(token: str, file_info: dict, dest_path: Path) -> bool:
    url = file_info["file_path"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "https://lms.gelisim.edu.tr",
        "Referer": "https://lms.gelisim.edu.tr/",
    }

    try:
        r = requests.get(url, headers=headers, stream=True, timeout=60)
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_TQDM and total:
            bar = tqdm(total=total, unit="B", unit_scale=True,
                       desc=dest_path.name[:40], leave=False)
        else:
            bar = None

        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                if bar:
                    bar.update(len(chunk))

        if bar:
            bar.close()

        return True

    except requests.HTTPError as e:
        log.error("HTTP hata %s → %s", e, url)
        return False
    except Exception as e:
        log.error("İndirme hatası: %s", e)
        return False


# ─── Güvenli dosya adı ────────────────────────────────────────
def safe_name(name: str) -> str:
    """Windows ve Linux'ta sorun çıkarmayacak dosya/klasör adı."""
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip()[:80]


# ─── Ana indirme döngüsü ──────────────────────────────────────
def download_all(
    token: str,
    files: list[dict],
    only_new: bool = False,
) -> tuple[int, int]:
    """(başarılı, atlanan) sayısını döndürür."""
    manifest  = load_manifest()
    ok = skipped = 0

    for i, f in enumerate(files, 1):
        # manifest hash
        path_hash = hashlib.md5(f["file_path"].encode()).hexdigest()[:12]

        if only_new and path_hash in manifest:
            skipped += 1
            continue

        # klasör yapısı: downloads/DERS ADI/Hafta N/dosya.pdf
        course_dir = DOWNLOAD_DIR / safe_name(f["course_name"])
        week_dir   = course_dir / safe_name(f"Hafta_{f['week']:02d}")
        dest       = week_dir / safe_name(f["file_name"])

        # zaten var mı?
        if dest.exists() and dest.stat().st_size > 0 and only_new:
            manifest[path_hash] = str(dest)
            skipped += 1
            continue

        size_mb = f["size_bytes"] / 1_048_576
        log.info("[%d/%d] %s — %s (%.1f MB)",
                 i, len(files), f["course_name"][:30],
                 f["file_name"][:40], size_mb)

        success = download_file(token, f, dest)
        if success:
            manifest[path_hash] = str(dest)
            ok += 1
        else:
            skipped += 1

        save_manifest(manifest)
        time.sleep(0.3)   # sunucuya nazik ol

    return ok, skipped


# ─── Listeleme ────────────────────────────────────────────────
def print_file_list(files: list[dict]):
    manifest = load_manifest()
    print(f"\n{'Ders':35} {'Hafta':6} {'Dosya':45} {'Boyut':8} {'Durum'}")
    print("─" * 105)
    for f in files:
        path_hash = hashlib.md5(f["file_path"].encode()).hexdigest()[:12]
        status    = "✅ var" if path_hash in manifest else "⬇ yeni"
        size_mb   = f"{f['size_bytes'] / 1_048_576:.1f} MB"
        print(f"{f['course_name'][:34]:35} {f['week']:<6} "
              f"{f['file_name'][:44]:45} {size_mb:>8} {status}")
    print(f"\nToplam: {len(files)} dosya")


# ─── CLI ─────────────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(
        prog="alms_downloader",
        description="IGU ALMS — Dosya İndirici",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python alms_downloader.py                    tüm dosyaları indir
  python alms_downloader.py -f pdf             sadece PDF'ler
  python alms_downloader.py -f video           sadece videolar
  python alms_downloader.py --course FIZ       Fizik dersi
  python alms_downloader.py --week 7           sadece 7. hafta
  python alms_downloader.py --list             indirmeden listele
  python alms_downloader.py --new              sadece yenileri indir
        """,
    )
    p.add_argument("-f", "--format", choices=["pdf", "video"],
                   help="dosya tipi filtresi")
    p.add_argument("--course", metavar="ANAHTAR",
                   help="ders adında aranacak kelime (örn. FIZ, MAT, YZM)")
    p.add_argument("--week", type=int, metavar="N",
                   help="sadece N. haftayı indir")
    p.add_argument("--list", action="store_true",
                   help="indirmeden listele")
    p.add_argument("--new", action="store_true",
                   help="sadece daha önce indirilmemiş dosyaları al")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="ayrıntılı loglar")
    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()
    setup_logging(args.verbose)

    # ── token al ──────────────────────────────────────────────
    token    = None
    username = None

    active = get_active_session()
    if active:
        token    = active["token"]
        username = active["username"]
        log.info("♻️  Mevcut token kullanılıyor — %s", username)
    else:
        creds = decrypt_credentials()
        if not creds:
            log.error("Kayıtlı giriş bilgisi yok. Önce: python alms_scraper.py -l")
            sys.exit(1)
        username, password = creds
        try:
            token = login(username, password)
            add_session(username, token, "saved", [])
        except Exception as e:
            log.error("Giriş başarısız: %s", e)
            sys.exit(1)

    # ── kurs listesi ──────────────────────────────────────────
    log.info("Dersler alınıyor...")
    try:
        courses = get_courses(token)
    except Exception as e:
        log.error("Dersler alınamadı: %s", e)
        sys.exit(1)

    active_courses = [
        c for c in courses
        if "BAHAR" in c.get("termName", "") or "GÜZ" in c.get("termName", "")
    ] or courses

    log.info("Aktiviteler taranıyor (%d ders)...", len(active_courses))

    # ── dosya listesi ─────────────────────────────────────────
    files = collect_files(
        token,
        active_courses,
        file_type_filter=args.format,
        course_filter=args.course,
        week_filter=args.week,
    )

    if not files:
        log.info("Seçilen kriterlere uygun dosya bulunamadı.")
        return

    total_mb = sum(f["size_bytes"] for f in files) / 1_048_576
    log.info("📦 %d dosya bulundu (toplam ~%.0f MB)", len(files), total_mb)

    # ── listele veya indir ────────────────────────────────────
    if args.list:
        print_file_list(files)
        return

    print(f"\n📁 İndirme klasörü: {DOWNLOAD_DIR}")
    print(f"   {len(files)} dosya, ~{total_mb:.0f} MB\n")

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ok, skipped = download_all(token, files, only_new=args.new)

    print(f"\n✅ Tamamlandı — {ok} indirildi, {skipped} atlandı")
    print(f"📁 {DOWNLOAD_DIR}")


if __name__ == "__main__":
    main()
