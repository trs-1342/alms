"""
utils/integrity.py — Dosya bütünlük doğrulama
"""
import hashlib
import re
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_download(path: Path, expected_size: int) -> tuple[bool, str]:
    """
    İndirilen dosyayı doğrula.
    Döner: (ok, hata_mesajı)
    """
    if not path.exists():
        return False, "Dosya bulunamadı"

    actual_size = path.stat().st_size
    if expected_size > 0 and actual_size != expected_size:
        return False, f"Boyut uyuşmazlığı: beklenen={expected_size}, gerçek={actual_size}"

    if actual_size == 0:
        return False, "Dosya boş"

    return True, ""


def sanitize_log(text: str) -> str:
    """Log satırlarından token/şifre sızdırmaz."""
    # Bearer token maskele
    text = re.sub(
        r"(Bearer\s+)[A-Za-z0-9\-_\.]+",
        r"\1***",
        text,
    )
    # password= maskele
    text = re.sub(
        r"(password=)[^\s&\"']+",
        r"\1***",
        text,
        flags=re.IGNORECASE,
    )
    # JSON "password":"..." maskele
    text = re.sub(
        r'("password"\s*:\s*")[^"]+(")',
        r'\1***\2',
        text,
        flags=re.IGNORECASE,
    )
    # access_token maskele
    text = re.sub(
        r'("access_token"\s*:\s*")[^"]{20,}(")',
        r'\1***\2',
        text,
    )
    return text
