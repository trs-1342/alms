"""
utils/notify.py — Masaüstü bildirimi (Linux/macOS/Windows)
"""
import logging
import platform
import subprocess

log = logging.getLogger(__name__)


def send(title: str, message: str) -> bool:
    """
    OS'a göre masaüstü bildirimi gönderir.
    Döner: True = başarılı
    """
    system = platform.system()
    try:
        if system == "Linux":
            return _linux(title, message)
        elif system == "Darwin":
            return _macos(title, message)
        elif system == "Windows":
            return _windows(title, message)
    except Exception as e:
        log.debug("Bildirim gönderilemedi: %s", e)
    return False


def _linux(title: str, message: str) -> bool:
    # notify-send (libnotify) — çoğu masaüstünde mevcut
    result = subprocess.run(
        ["notify-send", "--app-name=ALMS", title, message],
        capture_output=True,
    )
    return result.returncode == 0


def _macos(title: str, message: str) -> bool:
    script = (
        f'display notification "{message}" '
        f'with title "{title}" '
        f'subtitle "ALMS İndirici"'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
    )
    return result.returncode == 0


def _windows(title: str, message: str) -> bool:
    # Windows 10+ Toast bildirimi — winrt gerektirir, yoksa fallback
    try:
        from winrt.windows.ui.notifications import (
            ToastNotificationManager, ToastNotification, ToastTemplateType,
        )
        from winrt.windows.data.xml.dom import XmlDocument
        mgr  = ToastNotificationManager.create_toast_notifier("ALMS")
        xml  = ToastNotificationManager.get_template_content(
            ToastTemplateType.TOAST_TEXT02
        )
        texts = xml.get_elements_by_tag_name("text")
        texts[0].inner_text = title
        texts[1].inner_text = message
        mgr.show(ToastNotification(xml))
        return True
    except ImportError:
        pass

    # Fallback: msg komutu (her Windows'ta var)
    subprocess.run(
        ["msg", "*", f"{title}: {message}"],
        capture_output=True,
    )
    return True
