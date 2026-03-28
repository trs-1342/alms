"""
utils/spinner.py — Terminal yükleme animasyonu
"""
import logging
import sys
import threading
import time


# ── Animasyon: büyüyen/küçülen blok halkası ──────────────────
#
#  Soldan sağa büyür, sonra sağdan sola erir
#  ▏msg...
#  ▎msg...
#  ▍msg...
#  ▌msg...
#  ▋msg...
#  ▊msg...
#  ▉msg...
#  █msg...    ← tam dolu
#  ▉msg...
#  ▊msg...
#  ...        ← geri eriyor
#
_GROW   = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
_SHRINK = ["▉", "▊", "▋", "▌", "▍", "▎", "▏", " "]
FRAMES  = _GROW + _SHRINK


class _BufferingHandler(logging.Handler):
    """Spinner çalışırken log mesajlarını tamponlar."""
    def __init__(self):
        super().__init__()
        self._buf  = []
        self._lock = threading.Lock()

    def emit(self, record):
        with self._lock:
            self._buf.append(self.format(record))

    def flush_to(self, stream):
        with self._lock:
            msgs, self._buf = self._buf, []
        for m in msgs:
            stream.write(m + "\n")
        stream.flush()


class Spinner:
    """
    Context manager.
    Spinner aktifken INFO+ loglar tamponlanır,
    spinner bitince temiz şekilde gösterilir.
    """
    def __init__(self, message: str = ""):
        self.message      = message
        self._stop        = threading.Event()
        self._thread      = None
        self._buf_handler = None
        self._tty         = sys.stdout.isatty()

    def _spin(self):
        i = 0
        pad = len(self.message) + 8
        while not self._stop.is_set():
            frame = FRAMES[i % len(FRAMES)]
            sys.stdout.write(
                f"\r  \033[96m{frame}\033[0m  \033[2m{self.message}\033[0m"
                + " " * 2
            )
            sys.stdout.flush()
            i += 1
            time.sleep(0.07)

    def start(self):
        if not self._tty:
            return self

        # Logları tamponla
        self._buf_handler = _BufferingHandler()
        self._buf_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logging.getLogger().addHandler(self._buf_handler)

        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if self._tty:
            sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
            sys.stdout.flush()
        if self._buf_handler:
            logging.getLogger().removeHandler(self._buf_handler)
            self._buf_handler.flush_to(sys.stdout)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()


def spin(message: str) -> Spinner:
    return Spinner(message)
