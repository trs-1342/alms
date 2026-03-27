#!/usr/bin/env bash
# setup.sh — ALMS İndirici Kurulum Scripti (Linux / macOS)
# Kullanım: chmod +x setup.sh && ./setup.sh
set -e

PYTHON_MIN="3.10"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ALMS İndirici — Kurulum                        ║"
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

echo ""
echo "  Kurulum tamamlandı!"
echo ""
echo "  İlk çalıştırma:"
echo "    $BIN_DIR/alms setup"
echo ""
echo "  veya yeni terminal açıp:"
echo "    alms setup"
echo ""
