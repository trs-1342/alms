#!/usr/bin/env bash
# setup.sh — ALMS İndirici Kurulum Scripti (Linux / macOS)
# Kullanım: chmod +x setup.sh && ./setup.sh
set -e

PYTHON_MIN="3.10"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ALMS İndirici — Kurulum                         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Python kontrolü ──────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON="$cmd"
            echo "  ✅ Python $VER bulundu ($cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  ❌ Python $PYTHON_MIN+ bulunamadı."
    echo "     Linux : sudo apt install python3  (veya pacman -S python)"
    echo "     macOS : brew install python3"
    exit 1
fi

# ── Sanal ortam ───────────────────────────────────────────────
VENV_DIR="$(dirname "$0")/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "  Sanal ortam oluşturuluyor..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
PY="$VENV_DIR/bin/python"

echo "  Paketler yükleniyor..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$(dirname "$0")/requirements.txt"
echo "  ✅ Paketler yüklendi."

# ── Çalıştırma izni ──────────────────────────────────────────
chmod +x "$(dirname "$0")/alms.py"

# ── alms wrapper scripti ─────────────────────────────────────
SCRIPT_ABS="$(cd "$(dirname "$0")" && pwd)/alms.py"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/alms" << WRAPPER
#!/usr/bin/env bash
exec "$PY" "$SCRIPT_ABS" "\$@"
WRAPPER
chmod +x "$BIN_DIR/alms"
echo "  ✅ alms komutu oluşturuldu: $BIN_DIR/alms"

# ── PATH kontrolü ────────────────────────────────────────────
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    SHELL_NAME=$(basename "$SHELL")
    case "$SHELL_NAME" in
        zsh)  PROFILE="$HOME/.zshrc" ;;
        bash) PROFILE="$HOME/.bashrc" ;;
        *)    PROFILE="$HOME/.profile" ;;
    esac
    echo "" >> "$PROFILE"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$PROFILE"
    echo "  ✅ PATH güncellendi: $PROFILE"
    echo "  ⚠️  Değişiklik için yeni terminal aç veya: source $PROFILE"
fi

# ── Config dizini izinleri ────────────────────────────────────
UNAME=$(uname)
if [ "$UNAME" = "Linux" ]; then
    CONFIG_BASE="$HOME/.config/alms"
elif [ "$UNAME" = "Darwin" ]; then
    CONFIG_BASE="$HOME/Library/Application Support/alms"
fi
if [ -n "$CONFIG_BASE" ]; then
    mkdir -p "$CONFIG_BASE"
    chmod 700 "$CONFIG_BASE"
    echo "  ✅ Config dizini güvenli: $CONFIG_BASE"
fi

# ── Linux: cron servisi kontrolü ─────────────────────────────
if [ "$UNAME" = "Linux" ]; then
    echo ""
    echo "  Cron servisi kontrol ediliyor..."

    # Hangi cron servisi var?
    CRON_SERVICE=""
    for svc in cronie cron crond; do
        if systemctl list-unit-files --quiet "$svc.service" 2>/dev/null | grep -q "$svc"; then
            CRON_SERVICE="$svc"
            break
        fi
    done

    if [ -z "$CRON_SERVICE" ]; then
        echo "  ⚠️  Cron servisi bulunamadı."
        echo "     Arch/Manjaro : sudo pacman -S cronie"
        echo "     Ubuntu/Debian: sudo apt install cron"
        echo "     Fedora/RHEL  : sudo dnf install cronie"
        echo "     (Otomatik indirme için cron gereklidir)"
    else
        # Çalışıyor mu?
        if systemctl is-active --quiet "$CRON_SERVICE"; then
            echo "  ✅ $CRON_SERVICE çalışıyor."
        else
            echo "  ⚠️  $CRON_SERVICE kurulu ama çalışmıyor. Başlatılıyor..."
            if sudo systemctl start "$CRON_SERVICE" 2>/dev/null; then
                echo "  ✅ $CRON_SERVICE başlatıldı."
            else
                echo "  ❌ Başlatılamadı. Manuel çalıştır:"
                echo "     sudo systemctl start $CRON_SERVICE"
            fi
        fi

        # Otomatik başlangıç açık mı?
        if systemctl is-enabled --quiet "$CRON_SERVICE" 2>/dev/null; then
            echo "  ✅ $CRON_SERVICE otomatik başlangıçta etkin."
        else
            echo "  ⚠️  $CRON_SERVICE otomatik başlangıçta değil. Etkinleştiriliyor..."
            if sudo systemctl enable "$CRON_SERVICE" 2>/dev/null; then
                echo "  ✅ $CRON_SERVICE otomatik başlangıca eklendi."
            else
                echo "  ❌ Etkinleştirilemedi. Manuel çalıştır:"
                echo "     sudo systemctl enable $CRON_SERVICE"
            fi
        fi
    fi
fi

echo ""
echo "  Kurulum tamamlandı!"
echo ""
echo "  İlk çalıştırma:"
echo "    $BIN_DIR/alms setup"
echo ""
echo "  veya yeni terminal açıp:"
echo "    alms setup"
echo ""
