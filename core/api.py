"""
core/api.py — ALMS REST API istemcisi
"""
import json
import logging
import re
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

API_BASE        = "https://almsp-api.gelisim.edu.tr"
STREAM_HOST     = "almsp-stream.gelisim.edu.tr"
REQUEST_TIMEOUT = 20

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _api_headers(token: str) -> dict:
    return {
        "Authorization":   f"Bearer {token}",
        "Content-Type":    "application/json",
        "Accept":          "application/json",
        "Accept-Language": "tr-TR",
        "User-Agent":      _USER_AGENT,
        "Origin":          "https://lms.gelisim.edu.tr",
        "Referer":         "https://lms.gelisim.edu.tr/",
    }


def _stream_headers() -> dict:
    """Stream sunucusu için minimal header — Authorization/Origin yok."""
    return {
        "User-Agent": _USER_AGENT,
        "Accept":     "*/*",
    }


def api_post(token: str, path: str, body: dict) -> Any:
    url = f"{API_BASE}{path}"
    log.debug("POST %s", url)
    r = requests.post(
        url, json=body,
        headers=_api_headers(token),
        timeout=REQUEST_TIMEOUT,
        verify=True,
    )
    log.debug("<- %d (%d bytes)", r.status_code, len(r.content))
    r.raise_for_status()
    return r.json()


def api_get_stream(token: str, url: str):
    """
    Dosya indirme isteği.

    /api/file/content/ endpoint'i iki farklı şekilde yanıt verebilir:
    A) Redirect (3xx) → stream URL'ine yönlendirme
    B) JSON string → stream URL'i doğrudan döner: "https://almsp-stream..."

    Her iki durumda da stream URL'ine Authorization/Origin göndermeden istek atılır.
    """
    # Adım 1: API isteği
    r = requests.get(
        url,
        headers=_api_headers(token),
        stream=False,           # önce yanıtı tam oku (JSON olabilir)
        allow_redirects=False,
        timeout=30,
        verify=True,
    )
    log.debug("API yanıt: %d, CT=%s, CL=%s",
              r.status_code,
              r.headers.get("content-type", "-"),
              r.headers.get("content-length", "-"))

    # Durum B: JSON string ile stream URL dönüyor
    ct = r.headers.get("content-type", "").split(";")[0].strip().lower()
    if r.status_code == 200 and ct == "application/json":
        try:
            stream_url = r.json()
            if isinstance(stream_url, str) and stream_url.startswith("http"):
                log.debug("JSON stream URL alındı → %s", stream_url[:80])
                return requests.get(
                    stream_url,
                    headers=_stream_headers(),
                    stream=True,
                    timeout=60,
                    verify=True,
                )
        except (json.JSONDecodeError, ValueError):
            pass

    # Durum A: Redirect zinciri
    for hop in range(5):
        if r.status_code not in (301, 302, 303, 307, 308):
            break
        redirect_url = r.headers.get("Location", "")
        if not redirect_url:
            break
        is_stream = STREAM_HOST in redirect_url
        hdrs = _stream_headers() if is_stream else _api_headers(token)
        log.debug("Redirect hop %d → %s", hop + 1, redirect_url[:80])
        r = requests.get(
            redirect_url,
            headers=hdrs,
            stream=True,
            allow_redirects=False,
            timeout=60,
            verify=True,
        )
        log.debug("  yanıt: %d, CT=%s, CL=%s",
                  r.status_code,
                  r.headers.get("content-type", "-"),
                  r.headers.get("content-length", "-"))

    # Son adım: stream=True garantisi
    if not r.is_permanent_redirect and r.status_code == 200:
        return r

    # Hiçbiri uymadıysa son r'yi döndür (hata tespiti downloader'da yapılır)
    return r


# ─── Ders kodu ayrıştır ───────────────────────────────────────
def parse_course_code(name: str) -> str:
    m = re.search(r"\(([A-Z]{2,5}\d{3}[A-Z]?)\)", name)
    return m.group(1) if m else ""


# ─── Kurs listesi ─────────────────────────────────────────────
def get_courses(token: str) -> list[dict]:
    data = api_post(token, "/api/course/enrolledcourses", {
        "Take": 1000, "Skip": 0,
        "SearchCourseName": "", "ActiveStatus": 1,
        "CourseDateFilter": 4, "isNotifications": True,
        "SearchTermId": None, "SearchProgId": None,
        "SourceCourseId": "", "MasterCourseId": "", "CourseId": "",
    })
    courses = data if isinstance(data, list) else data.get("items", [])
    for c in courses:
        c["courseCode"] = parse_course_code(c.get("name", ""))
    log.info("📚 %d ders alındı.", len(courses))
    return courses


def get_active_courses(token: str) -> list[dict]:
    courses = get_courses(token)
    return [
        c for c in courses
        if "BAHAR" in c.get("termName", "") or "GÜZ" in c.get("termName", "")
    ] or courses


# ─── Hafta & aktivite ─────────────────────────────────────────
def get_term_weeks(token: str, class_id: str, course_id: str) -> list[dict]:
    data = api_post(token, "/api/activity/contentpagemenu", {
        "ClassId": class_id,
        "CourseId": course_id,
    })
    return [
        w for w in data.get("termWeeks", [])
        if w.get("termWeekId") and w.get("termWeekId") != "0"
    ]


def get_activities(
    token: str, class_id: str, course_id: str, term_week_id: str,
    delay: float = 0.15,
) -> list[dict]:
    time.sleep(delay)
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


# ─── Takvim ───────────────────────────────────────────────────
def get_calendar(token: str, days: int = 30) -> list[dict]:
    from datetime import datetime, timezone, timedelta
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
