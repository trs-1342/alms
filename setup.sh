#!/usr/bin/env bash
# setup.sh — ALMS İndirici Kurulum Scripti (Linux / macOS)
# Kullanım: chmod +x setup.sh && ./setup.sh
set -e

PYTHON_MIN="3.10"
UNAME=$(uname)

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
    if [ "$UNAME" = "Darwin" ]; then
        echo ""
        echo "  Homebrew ile kur:"
        echo "    /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo "    brew install python3"
        echo ""
        echo "  Veya doğrudan indir: https://www.python.org/downloads/macos/"
    else
        echo "     Arch/Manjaro : sudo pacman -S python"
        echo "     Ubuntu/Debian: sudo apt install python3"
        echo "     Fedora       : sudo dnf install python3"
    fi
    exit 1
fi

# ── macOS: Homebrew Python PATH kontrolü ─────────────────────
if [ "$UNAME" = "Darwin" ]; then
    BREW_PYTHON="/opt/homebrew/bin/python3"
    BREW_PYTHON_INTEL="/usr/local/bin/python3"
    if [ -f "$BREW_PYTHON" ]; then
        PYTHON="$BREW_PYTHON"
        echo "  ✅ Homebrew Python kullanılıyor: $BREW_PYTHON"
    elif [ -f "$BREW_PYTHON_INTEL" ]; then
        PYTHON="$BREW_PYTHON_INTEL"
        echo "  ✅ Homebrew Python kullanılıyor: $BREW_PYTHON_INTEL"
    fi
fi

# ── Sanal ortam ───────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "  Sanal ortam oluşturuluyor..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
PY="$VENV_DIR/bin/python"

echo "  Paketler yükleniyor..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "  ✅ Paketler yüklendi."

# ── Çalıştırma izni ──────────────────────────────────────────
chmod +x "$SCRIPT_DIR/alms.py"

# ── alms wrapper scripti ─────────────────────────────────────
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/alms" << WRAPPER
#!/usr/bin/env bash
exec "$PY" "$SCRIPT_DIR/alms.py" "\$@"
WRAPPER
chmod +x "$BIN_DIR/alms"
echo "  ✅ alms komutu oluşturuldu: $BIN_DIR/alms"

# ── PATH kontrolü ────────────────────────────────────────────
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
    zsh)  PROFILE="$HOME/.zshrc" ;;
    bash) PROFILE="$HOME/.bashrc" ;;
    fish) PROFILE="$HOME/.config/fish/config.fish" ;;
    *)    PROFILE="$HOME/.profile" ;;
esac

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    if [ "$SHELL_NAME" = "fish" ]; then
        echo "fish_add_path $BIN_DIR" >> "$PROFILE"
    else
        echo "" >> "$PROFILE"
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$PROFILE"
    fi
    echo "  ✅ PATH güncellendi: $PROFILE"
    echo "  ⚠️  Değişiklik için yeni terminal aç veya: source $PROFILE"
else
    echo "  ✅ PATH zaten doğru."
fi

# ── Config dizini izinleri ────────────────────────────────────
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
    CRON_SERVICE=""
    for svc in cronie cron crond; do
        if systemctl list-unit-files --quiet "$svc.service" 2>/dev/null | grep -q "$svc"; then
            CRON_SERVICE="$svc"
            break
        fi
    done

    if [ -z "$CRON_SERVICE" ]; then
        echo "  ⚠️  Cron servisi bulunamadı. Otomatik indirme çalışmaz."
        echo "     Arch/Manjaro : sudo pacman -S cronie"
        echo "     Ubuntu/Debian: sudo apt install cron"
        echo "     Fedora       : sudo dnf install cronie"
        echo "     Kurulumdan sonra: sudo systemctl enable --now $CRON_SERVICE"
    else
        if systemctl is-active --quiet "$CRON_SERVICE"; then
            echo "  ✅ $CRON_SERVICE çalışıyor."
        else
            echo "  ⚠️  $CRON_SERVICE çalışmıyor. Başlatılıyor..."
            sudo systemctl start "$CRON_SERVICE" 2>/dev/null && \
                echo "  ✅ $CRON_SERVICE başlatıldı." || \
                echo "  ❌ Başlatılamadı. Manuel: sudo systemctl start $CRON_SERVICE"
        fi
        if ! systemctl is-enabled --quiet "$CRON_SERVICE" 2>/dev/null; then
            echo "  ⚠️  Otomatik başlangıç kapalı. Etkinleştiriliyor..."
            sudo systemctl enable "$CRON_SERVICE" 2>/dev/null && \
                echo "  ✅ $CRON_SERVICE otomatik başlangıca eklendi." || \
                echo "  ❌ Etkinleştirilemedi. Manuel: sudo systemctl enable $CRON_SERVICE"
        else
            echo "  ✅ $CRON_SERVICE otomatik başlangıçta etkin."
        fi
    fi
fi

# ── macOS: launchd bilgilendirme ─────────────────────────────
if [ "$UNAME" = "Darwin" ]; then
    echo ""
    echo "  ℹ️  macOS otomatik çalıştırma: launchd kullanır."
    echo "     alms kurulumundan sonra 'alms setup' ile ayarlayabilirsin."
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Kurulum tamamlandı!                             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Sonraki adım — yeni terminal aç ve çalıştır:"
echo ""
echo "    alms setup"
echo ""
echo "  Veya şu anki terminalde:"
echo "    source $PROFILE && alms setup"
echo ""
