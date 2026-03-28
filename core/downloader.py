"""
core/downloader.py — Paralel indirme motoru
"""
import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from core.api import api_get_stream, get_term_weeks, get_activities
from core.config import get_download_dir, get as cfg_get
from utils.integrity import verify_download
from utils.paths import MANIFEST_FILE, ensure_secure_dir, CONFIG_DIR

log = logging.getLogger(__name__)

VALID_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx",
    ".xls", ".xlsx", ".mp4", ".mkv", ".avi", ".mov", ".webm",
    ".zip", ".rar", ".7z", ".txt",
}

_ERROR_CONTENT_TYPES = {"application/json", "text/html", "text/plain"}


# ─── Manifest ─────────────────────────────────────────────────
def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_manifest(manifest: dict) -> None:
    ensure_secure_dir(CONFIG_DIR)
    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _content_hash(name: str, size: int) -> str:
    """Aynı içerikli dosyalar için deduplication anahtarı."""
    return hashlib.md5(f"{name.lower()}:{size}".encode()).hexdigest()[:12]


# ─── Duplicate tespiti ────────────────────────────────────────
def sync_manifest_with_disk() -> int:
    """
    Manifest'teki silinen dosyaları temizler.
    Döner: kaç kayıt kaldırıldı.
    """
    manifest = load_manifest()
    to_remove = [h for h, path in manifest.items() if not Path(path).exists()]
    for h in to_remove:
        del manifest[h]
    if to_remove:
        save_manifest(manifest)
        log.info("Manifest temizlendi — %d kayıt kaldırıldı.", len(to_remove))
    return len(to_remove)


def deduplicate(files: list[dict]) -> tuple[list[dict], int]:
    """
    Aynı dosya adı + boyuta sahip tekrarları temizler.
    Her benzersiz dosyanın en son URL'ini tutar.
    Döner: (temiz_liste, kaç_duplicate_kaldırıldı)
    """
    seen: dict[str, dict] = {}   # content_hash → file_info
    for f in files:
        key = _content_hash(f["file_name"], f["size_bytes"])
        # Aynı içerikli dosya varsa, daha yüksek hafta numaralı olanı tut
        if key not in seen or f["week"] > seen[key]["week"]:
            seen[key] = f

    clean = list(seen.values())
    removed = len(files) - len(clean)
    if removed:
        log.info("🔁 %d duplicate dosya filtrelendi.", removed)
    return clean, removed


# ─── Dosya toplama ────────────────────────────────────────────
def collect_files(
    token: str,
    courses: list[dict],
    file_type: str | None = None,
    course_filter: str | None = None,
    week_filter: int | None = None,
    dedup: bool = True,
) -> list[dict]:
    files = []
    seen_urls = set()

    for course in courses:
        cname    = course.get("name", "").strip()
        ccode    = course.get("courseCode", "")
        cid      = course.get("classId", "")
        courseid = course.get("courseId", "")

        if course_filter:
            filt = course_filter.upper()
            if filt not in cname.upper() and filt not in ccode.upper():
                continue

        log.info("  📖 %s", cname)

        try:
            weeks = get_term_weeks(token, cid, courseid)
        except Exception as e:
            log.warning("    Hafta listesi alınamadı: %s", e)
            continue

        for week in weeks:
            wnum = week.get("week", 0)
            wid  = week.get("termWeekId", "")

            if week_filter is not None and wnum != week_filter:
                continue

            try:
                acts = get_activities(token, cid, courseid, wid)
            except Exception as e:
                log.warning("    Hafta %d aktiviteleri alınamadı: %s", wnum, e)
                continue

            for act in acts:
                for f in (act.get("file") or []):
                    url  = f.get("filePath", "")
                    name = f.get("fileName", "")
                    ext  = (f.get("extension") or Path(name).suffix).lower()
                    size = int(f.get("size") or 0)

                    if not url or url in seen_urls:
                        continue
                    if ext and ext not in VALID_EXTENSIONS:
                        continue

                    seen_urls.add(url)
                    is_video = ext in (".mp4", ".mkv", ".avi", ".mov", ".webm")

                    if file_type == "pdf" and is_video:
                        continue
                    if file_type == "video" and not is_video:
                        continue

                    files.append({
                        "course_name":   cname,
                        "course_code":   ccode,
                        "class_id":      cid,
                        "week":          wnum,
                        "activity_name": act.get("name") or "",
                        "activity_type": act.get("activityType", ""),
                        "file_name":     name,
                        "file_path":     url,
                        "ext":           ext,
                        "size_bytes":    size,
                        "is_video":      is_video,
                    })

    if dedup:
        files, _ = deduplicate(files)

    return files


# ─── Yardımcılar ──────────────────────────────────────────────
def _safe_name(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "_", s)
    return s.strip()[:80]


def _build_dest(f: dict) -> Path:
    base = get_download_dir()
    # Kurs kodu varsa onu kullan (daha kısa), yoksa ismin ilk 20 karakteri
    folder = f["course_code"] if f.get("course_code") else _safe_name(f["course_name"])[:20]
    course_dir = base / folder
    week_dir   = course_dir / f"Hafta_{f['week']:02d}"
    return week_dir / _safe_name(f["file_name"])


def _is_error_response(r: requests.Response) -> tuple[bool, str]:
    if r.status_code >= 400:
        body = r.content[:300].decode(errors="replace").strip()
        return True, f"HTTP {r.status_code}: {body}"

    ct = r.headers.get("content-type", "").split(";")[0].strip().lower()
    cl = int(r.headers.get("content-length", -1))

    if ct in _ERROR_CONTENT_TYPES:
        body = r.content[:300].decode(errors="replace").strip()
        return True, f"Hata yanıtı (CT={ct}): {body}"

    if 0 < cl < 512:
        body = r.content[:300].decode(errors="replace").strip()
        return True, f"Yanıt çok küçük ({cl} byte): {body}"

    return False, ""


# ─── Tek dosya indir ──────────────────────────────────────────
def download_one(token: str, f: dict, overwrite: bool = False) -> dict:
    dest     = _build_dest(f)
    url      = f["file_path"]
    size_exp = f["size_bytes"]

    if not overwrite and dest.exists():
        ok, _ = verify_download(dest, size_exp)
        if ok:
            return {"ok": True, "path": str(dest), "skipped": True}

    dest.parent.mkdir(parents=True, exist_ok=True)

    retry_count = int(cfg_get("retry_count") or 3)
    retry_delay = float(cfg_get("retry_delay") or 2)
    chunk_size  = int(cfg_get("chunk_size") or 65536)

    last_error = ""
    for attempt in range(1, retry_count + 1):
        try:
            r = api_get_stream(token, url)
            r.raise_for_status()

            is_err, err_msg = _is_error_response(r)
            if is_err:
                last_error = err_msg
                log.warning("Deneme %d/%d başarısız: %s → %s",
                             attempt, retry_count, f["file_name"], last_error)
                time.sleep(retry_delay * attempt)
                continue

            tmp = dest.with_suffix(dest.suffix + ".tmp")
            written = 0
            with open(tmp, "wb") as out:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        out.write(chunk)
                        written += len(chunk)

            if size_exp > 0:
                ok, err = verify_download(tmp, size_exp)
                if not ok:
                    tmp.unlink(missing_ok=True)
                    last_error = f"Doğrulama hatası: {err}"
                    log.warning("Deneme %d/%d başarısız: %s → %s",
                                 attempt, retry_count, f["file_name"], last_error)
                    time.sleep(retry_delay * attempt)
                    continue
            elif written == 0:
                tmp.unlink(missing_ok=True)
                last_error = "Boş dosya"
                time.sleep(retry_delay * attempt)
                continue

            tmp.rename(dest)
            return {"ok": True, "path": str(dest), "skipped": False}

        except requests.HTTPError as e:
            last_error = f"HTTP {e.response.status_code if e.response else '?'}"
        except requests.RequestException as e:
            last_error = str(e)

        log.warning("Deneme %d/%d başarısız: %s → %s",
                     attempt, retry_count, f["file_name"], last_error)
        time.sleep(retry_delay * attempt)

    return {"ok": False, "path": "", "error": last_error}


# ─── Paralel indirme ──────────────────────────────────────────
def download_all(
    token: str,
    files: list[dict],
    only_new: bool = True,
    on_progress=None,
) -> dict:
    manifest = load_manifest()
    workers  = int(cfg_get("parallel") or 3)

    to_download = []
    pre_skipped = 0
    for f in files:
        h = _url_hash(f["file_path"])
        if only_new and h in manifest:
            pre_skipped += 1
            continue
        to_download.append(f)

    total   = len(to_download)
    ok      = 0
    skipped = pre_skipped
    failed  = 0
    failed_files = []
    done    = 0

    def _task(f):
        return f, download_one(token, f, overwrite=not only_new)

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_task, f): f for f in to_download}
            for future in as_completed(futures):
                try:
                    f, result = future.result()
                except Exception as e:
                    f = futures[future]
                    result = {"ok": False, "path": "", "error": str(e)}

                done += 1
                h = _url_hash(f["file_path"])

                if result["ok"]:
                    if result.get("skipped"):
                        skipped += 1
                    else:
                        ok += 1
                    manifest[h] = result["path"]
                else:
                    failed += 1
                    failed_files.append({
                        "file":   f["file_name"],
                        "course": f["course_name"],
                        "error":  result.get("error", ""),
                    })

                save_manifest(manifest)
                if on_progress:
                    on_progress(done, total, f, result)

    except KeyboardInterrupt:
        log.warning("İndirme kullanıcı tarafından durduruldu (%d/%d tamamlandı).",
                    done, total)
        save_manifest(manifest)
    finally:
        # Python 3.14'te ThreadPoolExecutor kapanırken çıkan uyarıyı sessizleştir
        import warnings
        warnings.filterwarnings("ignore", category=RuntimeWarning)

    return {
        "ok": ok, "skipped": skipped,
        "failed": failed, "failed_files": failed_files,
        "cancelled": done < total,
    }
