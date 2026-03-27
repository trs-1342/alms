"""
core/api.py — ALMS REST API istemcisi
"""
import logging
import re
import time
from typing import Any

import requests

from utils.integrity import sanitize_log

log = logging.getLogger(__name__)

API_BASE   = "https://almsp-api.gelisim.edu.tr"
REQUEST_TIMEOUT = 20


def _headers(token: str) -> dict:
    return {
        "Authorization":           f"Bearer {token}",
        "Content-Type":            "application/json",
        "Accept":                  "application/json",
        "Accept-Language":         "tr-TR",
        "Origin":                  "https://lms.gelisim.edu.tr",
        "Referer":                 "https://lms.gelisim.edu.tr/",
    }


def api_post(token: str, path: str, body: dict) -> Any:
    url = f"{API_BASE}{path}"
    log.debug("POST %s", url)
    r = requests.post(
        url, json=body,
        headers=_headers(token),
        timeout=REQUEST_TIMEOUT,
        verify=True,
    )
    log.debug("← %d (%d bytes)", r.status_code, len(r.content))
    r.raise_for_status()
    return r.json()


def api_get_stream(token: str, url: str):
    """İndirme için stream=True isteği döndürür."""
    return requests.get(
        url,
        headers=_headers(token),
        stream=True,
        timeout=60,
        verify=True,
    )


# ─── Kurs kodu ayrıştır ───────────────────────────────────────
def parse_course_code(name: str) -> str:
    """'FİZİK II (FIZ108) ' → 'FIZ108'"""
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

    # Ders kodu ekle
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


# ─── Hafta & aktivite listesi ─────────────────────────────────
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
    time.sleep(delay)  # API'ye nazik ol
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


# ─── Takvim (ödevler) ─────────────────────────────────────────
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
