"""
utils/network.py — Ağ bağlantısı kontrolü
"""
import logging
import socket

import requests

log = logging.getLogger(__name__)

_CHECK_URL     = "https://almsp-auth.gelisim.edu.tr/connect/token"
_CHECK_TIMEOUT = 5


def is_online() -> bool:
    """DNS + TCP ile hızlı bağlantı kontrolü."""
    try:
        socket.setdefaulttimeout(3)
        socket.getaddrinfo("almsp-auth.gelisim.edu.tr", 443)
        return True
    except OSError:
        return False


def check_alms_reachable() -> tuple[bool, str]:
    """
    ALMS API'sine erişilebiliyor mu?
    Döner: (erişilebilir, mesaj)
    """
    if not is_online():
        return False, "İnternet bağlantısı yok"

    try:
        r = requests.head(_CHECK_URL, timeout=_CHECK_TIMEOUT, verify=True)
        # 405 Method Not Allowed = sunucu cevap veriyor, erişilebilir
        if r.status_code in (200, 400, 401, 405):
            return True, "OK"
        return False, f"Sunucu yanıt kodu: {r.status_code}"
    except requests.exceptions.SSLError:
        return False, "SSL hatası"
    except requests.exceptions.ConnectionError:
        return False, "Bağlantı kurulamadı"
    except requests.exceptions.Timeout:
        return False, "Zaman aşımı"
    except Exception as e:
        return False, str(e)
