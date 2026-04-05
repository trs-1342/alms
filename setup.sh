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

# ── Yönetici izni yardımcıları ───────────────────────────────

# Şifresiz sudo var mı?
_has_sudo() {
    sudo -n true 2>/dev/null
}

# Gerekirse kullanıcıdan sudo iste; başarısızsa 1 döndür
_try_sudo() {
    if _has_sudo; then
        return 0
    fi
    echo ""
    echo "  ⚠️  Bu adım yönetici (sudo) izni gerektiriyor."
    echo "  Şifrenizi girin. Atlamak istiyorsanız Ctrl+C'ye, ardından Enter'a basın."
    if sudo -v 2>/dev/null; then
        return 0
    fi
    echo "  ❌ Yönetici izni alınamadı — bu adım atlandı."
    return 1
}

# ── macOS: Homebrew kontrolü ve kurulumu ─────────────────────
if [ "$UNAME" = "Darwin" ]; then
    if command -v brew &>/dev/null; then
        echo "  ✅ Homebrew mevcut: $(brew --prefix)"
    else
        echo "  ⚠️  Homebrew bulunamadı. Otomatik kuruluyor..."
        echo "  (Bu işlem birkaç dakika sürebilir — internet bağlantısı gerekli)"
        echo ""
        # Homebrew kurulumu — sudo gerektirmez, kullanıcı düzeyinde çalışır
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
            echo ""
            echo "  ❌ Homebrew kurulamadı. İnternet bağlantınızı kontrol edin."
            echo "  Manuel: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        }
        echo ""

        # Apple Silicon (M1/M2/M3) için Homebrew PATH
        if [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
            # Shell profiline ekle (zsh veya bash)
            BREW_PROFILE="$HOME/.zprofile"
            [ "$(basename "$SHELL")" = "bash" ] && BREW_PROFILE="$HOME/.bash_profile"
            if ! grep -q "homebrew" "$BREW_PROFILE" 2>/dev/null; then
                echo "" >> "$BREW_PROFILE"
                echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$BREW_PROFILE"
            fi
        elif [ -f "/usr/local/bin/brew" ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
        echo "  ✅ Homebrew kuruldu."
    fi
fi

# ── Linux: Paket yöneticisi tespiti ──────────────────────────
PKG_MGR=""
if [ "$UNAME" = "Linux" ]; then
    if   command -v pacman  &>/dev/null; then PKG_MGR="pacman"
    elif command -v apt-get &>/dev/null; then PKG_MGR="apt"
    elif command -v dnf     &>/dev/null; then PKG_MGR="dnf"
    elif command -v yum     &>/dev/null; then PKG_MGR="yum"
    elif command -v zypper  &>/dev/null; then PKG_MGR="zypper"
    fi
fi

# Dağıtıma göre paket kurulum komutu
_pkg_install() {
    local pkg="$1"
    case "$PKG_MGR" in
        pacman)  sudo pacman -S --noconfirm "$pkg" ;;
        apt)     sudo apt-get install -y "$pkg" ;;
        dnf|yum) sudo "$PKG_MGR" install -y "$pkg" ;;
        zypper)  sudo zypper install -y "$pkg" ;;
        *)       return 1 ;;
    esac
}

# ── git kontrolü ve kurulumu ─────────────────────────────────
if ! command -v git &>/dev/null; then
    echo "  ⚠️  git bulunamadı."
    if [ "$UNAME" = "Darwin" ]; then
        echo "  brew ile kuruluyor..."
        brew install git && echo "  ✅ git kuruldu." || {
            echo "  ❌ git kurulamadı."
            echo "  Manuel: brew install git"
            echo "  Veya Xcode araçları: xcode-select --install"
            exit 1
        }
    elif [ "$UNAME" = "Linux" ] && [ -n "$PKG_MGR" ]; then
        echo "  Paket yöneticisi ile kuruluyor ($PKG_MGR)..."
        if _try_sudo; then
            _pkg_install git && echo "  ✅ git kuruldu." || {
                echo "  ❌ git kurulamadı."
                exit 1
            }
        else
            echo "  ❌ git kurmak için yönetici izni gerekli."
            echo "  Manuel olarak kurun, ardından setup.sh'ı yeniden çalıştırın."
            exit 1
        fi
    else
        echo "  ❌ git bulunamadı ve otomatik kurulum desteklenmiyor."
        echo "  git'i manuel olarak kurup tekrar çalıştırın."
        exit 1
    fi
else
    echo "  ✅ git mevcut: $(git --version)"
fi

# ── Python kontrolü ──────────────────────────────────────────
PYTHON=""

# macOS: Homebrew Python'ını önce kontrol et
if [ "$UNAME" = "Darwin" ]; then
    for brew_py in \
        "/opt/homebrew/bin/python3" \
        "/usr/local/bin/python3"; do
        if [ -f "$brew_py" ]; then
            VER=$("$brew_py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            MAJOR=$(echo "$VER" | cut -d. -f1)
            MINOR=$(echo "$VER" | cut -d. -f2)
            if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
                PYTHON="$brew_py"
                echo "  ✅ Python $VER (Homebrew): $brew_py"
                break
            fi
        fi
    done
fi

# Genel arama (henüz bulunamadıysa)
if [ -z "$PYTHON" ]; then
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
            MAJOR=$(echo "$VER" | cut -d. -f1)
            MINOR=$(echo "$VER" | cut -d. -f2)
            if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
                PYTHON="$cmd"
                echo "  ✅ Python $VER bulundu ($cmd)"
                break
            fi
        fi
    done
fi

# Python bulunamazsa otomatik kur
if [ -z "$PYTHON" ]; then
    echo "  ⚠️  Python $PYTHON_MIN+ bulunamadı."
    if [ "$UNAME" = "Darwin" ]; then
        echo "  brew ile kuruluyor..."
        brew install python3 && echo "  ✅ Python kuruldu." || {
            echo "  ❌ Python kurulamadı."
            echo "  Manuel: brew install python3"
            echo "  Veya: https://www.python.org/downloads/macos/"
            exit 1
        }
        # Homebrew Python yolunu yeniden bul
        for brew_py in "/opt/homebrew/bin/python3" "/usr/local/bin/python3"; do
            [ -f "$brew_py" ] && PYTHON="$brew_py" && break
        done
        [ -z "$PYTHON" ] && PYTHON="$(command -v python3)"
    elif [ "$UNAME" = "Linux" ] && [ -n "$PKG_MGR" ]; then
        echo "  Paket yöneticisi ile kuruluyor ($PKG_MGR)..."
        PY_PKG="python3"
        [ "$PKG_MGR" = "pacman" ] && PY_PKG="python"
        if _try_sudo; then
            _pkg_install "$PY_PKG" && echo "  ✅ Python kuruldu." || {
                echo "  ❌ Python kurulamadı."
                exit 1
            }
            PYTHON="$(command -v python3 || command -v python)"
        else
            echo "  ❌ Python kurmak için yönetici izni gerekli."
            echo "  Kurulumdan sonra setup.sh'ı yeniden çalıştırın."
            exit 1
        fi
    else
        echo "  ❌ Python $PYTHON_MIN+ gerekli, otomatik kurulum desteklenmiyor."
        [ "$UNAME" = "Darwin" ] && echo "  Manuel: brew install python3 || https://www.python.org/downloads/macos/"
        exit 1
    fi

    # Son kontrol
    if [ -z "$PYTHON" ] || ! "$PYTHON" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
        echo "  ❌ Python $PYTHON_MIN+ hâlâ bulunamadı. Lütfen manuel kurun."
        exit 1
    fi
    VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "  ✅ Python $VER kullanılacak: $PYTHON"
fi

# ── Sanal ortam ───────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "  Sanal ortam oluşturuluyor..."
    "$PYTHON" -m venv "$VENV_DIR" || {
        echo "  ❌ Sanal ortam oluşturulamadı."
        if [ "$UNAME" = "Darwin" ]; then
            echo "  macOS: xcode-select --install çalıştırıp tekrar deneyin."
        elif [ "$UNAME" = "Linux" ]; then
            echo "  Linux: python3-venv paketi gerekebilir."
            if [ -n "$PKG_MGR" ]; then
                echo "  Kurulum:"
                case "$PKG_MGR" in
                    apt)     echo "    sudo apt install python3-venv" ;;
                    pacman)  echo "    (Arch'ta python paketi zaten venv içerir)" ;;
                    dnf|yum) echo "    sudo $PKG_MGR install python3-virtualenv" ;;
                esac
            fi
        fi
        exit 1
    }
fi

PY="$VENV_DIR/bin/python"

echo "  Paketler yükleniyor..."
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "  ✅ Paketler yüklendi."

# ── Çalıştırma izni ──────────────────────────────────────────
chmod +x "$SCRIPT_DIR/alms.py"

# ── alms wrapper scripti (venv Python kullanır) ──────────────
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

if [ "$UNAME" = "Darwin" ] && [ "$SHELL_NAME" = "zsh" ]; then
    # macOS Terminal.app login shell açar → .zprofile okunur
    if [ -f "$HOME/.zprofile" ]; then
        PROFILE="$HOME/.zprofile"
    else
        PROFILE="$HOME/.zshrc"
    fi
elif [ "$UNAME" = "Darwin" ] && [ "$SHELL_NAME" = "bash" ]; then
    # macOS bash login shell → .bash_profile
    if [ -f "$HOME/.bash_profile" ]; then
        PROFILE="$HOME/.bash_profile"
    else
        PROFILE="$HOME/.bashrc"
    fi
else
    case "$SHELL_NAME" in
        zsh)  PROFILE="$HOME/.zshrc" ;;
        bash) PROFILE="$HOME/.bashrc" ;;
        fish) PROFILE="$HOME/.config/fish/config.fish" ;;
        *)    PROFILE="$HOME/.profile" ;;
    esac
fi

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

# ── Linux: cron servisi kontrolü ve kurulumu ─────────────────
if [ "$UNAME" = "Linux" ]; then
    echo ""
    echo "  Cron servisi kontrol ediliyor..."
    CRON_SERVICE=""

    for svc in cronie cron crond; do
        if systemctl list-unit-files --quiet 2>/dev/null | grep -q "^${svc}\.service"; then
            CRON_SERVICE="$svc"
            break
        fi
    done

    if [ -z "$CRON_SERVICE" ]; then
        echo "  ⚠️  Cron servisi bulunamadı — otomatik indirme çalışmaz."
        if [ -n "$PKG_MGR" ]; then
            echo "  Kuruluyor..."
            CRON_PKG="cronie"
            [ "$PKG_MGR" = "apt" ] && CRON_PKG="cron"
            if _try_sudo; then
                _pkg_install "$CRON_PKG" && {
                    sudo systemctl enable --now "$CRON_PKG" 2>/dev/null && \
                        echo "  ✅ Cron kuruldu ve başlatıldı." || \
                        echo "  ⚠️  Cron kuruldu, başlatmak için: sudo systemctl enable --now $CRON_PKG"
                } || echo "  ❌ Cron kurulamadı."
            else
                echo "  ⚠️  Cron kurmak için yönetici izni gerekli."
                case "$PKG_MGR" in
                    pacman) echo "     sudo pacman -S cronie && sudo systemctl enable --now cronie" ;;
                    apt)    echo "     sudo apt install cron" ;;
                    dnf|yum) echo "     sudo $PKG_MGR install cronie && sudo systemctl enable --now cronie" ;;
                esac
            fi
        fi
    else
        if systemctl is-active --quiet "$CRON_SERVICE"; then
            echo "  ✅ $CRON_SERVICE çalışıyor."
        else
            echo "  ⚠️  $CRON_SERVICE çalışmıyor. Başlatılıyor..."
            if _try_sudo; then
                sudo systemctl start "$CRON_SERVICE" 2>/dev/null && \
                    echo "  ✅ $CRON_SERVICE başlatıldı." || \
                    echo "  ❌ Başlatılamadı. Manuel: sudo systemctl start $CRON_SERVICE"
            else
                echo "  ❌ Başlatmak için yönetici izni gerekli."
                echo "  Manuel: sudo systemctl start $CRON_SERVICE"
            fi
        fi

        if ! systemctl is-enabled --quiet "$CRON_SERVICE" 2>/dev/null; then
            echo "  ⚠️  Otomatik başlangıç kapalı. Etkinleştiriliyor..."
            if _try_sudo; then
                sudo systemctl enable "$CRON_SERVICE" 2>/dev/null && \
                    echo "  ✅ $CRON_SERVICE otomatik başlangıca eklendi." || \
                    echo "  ❌ Etkinleştirilemedi. Manuel: sudo systemctl enable $CRON_SERVICE"
            else
                echo "  ⚠️  Etkinleştirmek için yönetici izni gerekli."
                echo "  Manuel: sudo systemctl enable $CRON_SERVICE"
            fi
        else
            echo "  ✅ $CRON_SERVICE otomatik başlangıçta etkin."
        fi
    fi
fi

# ── macOS: launchd bilgilendirme ─────────────────────────────
if [ "$UNAME" = "Darwin" ]; then
    echo ""
    echo "  ℹ️  macOS otomatik çalıştırma: launchd kullanır."
    echo "     Kurulumdan sonra 'alms setup' ile ayarlayabilirsin."
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
