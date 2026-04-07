"""
utils/term.py — Terminal yetenek tespiti
Windows 10/11, Linux, macOS farklarını tek yerden yönetir.

Kullanım:
    from utils.term import ic, USE_EMOJI, USE_COLOR, IS_WIN10, IS_WIN11
"""
from __future__ import annotations

import os
import platform
import sys

_SYS = platform.system()   # "Windows" | "Darwin" | "Linux"
_WIN = _SYS == "Windows"

# ── Windows build numarası ─────────────────────────────────────
def _win_build() -> int:
    """Windows build numarası (örn: 19045 = Win10, 22621 = Win11). Non-Windows: 0."""
    if not _WIN:
        return 0
    try:
        return int(platform.version().split(".")[-1])
    except Exception:
        return 0

WIN_BUILD = _win_build()
IS_WIN10  = _WIN and WIN_BUILD < 22000   # Windows 10 (build 10000-21999)
IS_WIN11  = _WIN and WIN_BUILD >= 22000  # Windows 11 (build 22000+)

# ── Terminal emülatör tespiti ──────────────────────────────────
IN_WINDOWS_TERMINAL = bool(os.environ.get("WT_SESSION"))   # Windows Terminal (her OS'ta)
IN_VSCODE           = os.environ.get("TERM_PROGRAM") == "vscode"
IN_CONEMU           = bool(os.environ.get("ConEmuPID"))    # ConEmu / Cmder
IN_JETBRAINS        = bool(os.environ.get("TERMINAL_EMULATOR"))  # JetBrains IDE

_IS_TTY = sys.stdout.isatty()

# ── VT100 / ANSI renk desteği ─────────────────────────────────
def _enable_vt100_win() -> bool:
    """
    Win10+: VirtualTerminalProcessing'i programatik açar.
    Döner: True = etkinleştirildi/zaten açık.
    """
    if not _WIN:
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        ENABLE_VT = 0x0004
        if mode.value & ENABLE_VT:
            return True  # Zaten açık
        return bool(kernel32.SetConsoleMode(h, mode.value | ENABLE_VT))
    except Exception:
        return False


def _check_vt100() -> bool:
    if not _IS_TTY:
        return False
    if not _WIN:
        return True   # macOS / Linux her zaman
    if IN_WINDOWS_TERMINAL or IN_VSCODE or IN_CONEMU or IN_JETBRAINS:
        return True   # Modern terminal emülatörleri
    if WIN_BUILD >= 16299:  # Win10 Fall Creators Update (1709)
        return _enable_vt100_win()
    return False


USE_VT100  = _check_vt100()
USE_COLOR  = USE_VT100   # Renk = VT100 var mı?

# ── Emoji / Unicode sembol desteği ────────────────────────────
def _check_emoji() -> bool:
    """
    Emoji destekleniyor mu?
    - macOS / Linux: evet
    - Windows Terminal (her versiyonda): evet
    - Windows 11 yeni terminal: evet
    - Windows 10 eski cmd.exe / powershell.exe: HAYIR
    """
    if not _IS_TTY:
        return False
    if not _WIN:
        return True
    if IN_WINDOWS_TERMINAL or IN_VSCODE or IN_CONEMU or IN_JETBRAINS:
        return True
    if IS_WIN11:
        return True   # Win11 varsayılan terminali emoji destekler
    return False      # Win10 cmd.exe / legacy powershell → desteklemez


USE_EMOJI = _check_emoji()

# ── Yardımcı: emoji / ASCII seçici ────────────────────────────
def ic(emoji: str, fallback: str = "") -> str:
    """
    Emoji destekleniyorsa `emoji`, aksi halde `fallback` döner.

    Örnekler:
        ic("✅", "[OK]")  → "✅" veya "[OK]"
        ic("❌", "[x]")   → "❌" veya "[x]"
        ic("⚠️",  "[!]")  → "⚠️"  veya "[!]"
    """
    return emoji if USE_EMOJI else fallback
