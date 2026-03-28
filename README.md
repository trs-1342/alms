# ALMS İndirici

IGU (İstanbul Gelişim Üniversitesi) ALMS sistemindeki ders materyallerini otomatik indiren komut satırı aracı.

## Amaç

ALMS web arayüzüne her girmeden, tek komutla tüm ders materyallerini senkronize etmek. Dosyalar ders koduna ve haftaya göre düzenlenir, belirtilen saatte otomatik indirilir.

```
~/ALMS/
├── FIZ108/
│   ├── Hafta_01/  →  fizik_2_1_hafta.pdf
│   └── Hafta_07/  →  Fizik_2_Bolum_6.pdf
├── YZM102/
│   └── Hafta_04/  →  Pointers2.pdf
└── MAT106/
    └── Hafta_03/  →  mat_3_hafta.pdf
```

---

## Kurulum

### Linux (Arch, Ubuntu, Fedora, vb.)

**Gereksinimler:** Python 3.10+, Git

```bash
# 1. Repoyu klonla
git clone https://github.com/trs-1342/alms
cd alms

# 2. Kurulum scriptini çalıştır
chmod +x setup.sh && ./setup.sh
```

`setup.sh` otomatik olarak şunları yapar:
- Python sürümünü kontrol eder
- `.venv` sanal ortamını oluşturur ve paketleri yükler
- `alms` komutunu `~/.local/bin`'e ekler
- Shell profilini (`~/.bashrc` / `~/.zshrc`) günceller
- `cronie` / `cron` servisini kontrol eder, çalışmıyorsa başlatır

```bash
# 3. Yeni terminal aç (PATH için) ve kurulumu tamamla
alms setup
```

> **Not:** `cronie` kurulu değilse:
> ```bash
> # Arch/Manjaro
> sudo pacman -S cronie
> sudo systemctl enable --now cronie
>
> # Ubuntu/Debian
> sudo apt install cron
>
> # Fedora
> sudo dnf install cronie
> sudo systemctl enable --now cronie
> ```

---

### macOS

**Gereksinimler:** Python 3.10+ (Homebrew önerilir), Git

```bash
# Homebrew ile Python kur (zaten yoksa)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python3 git

# Repoyu klonla
git clone https://github.com/trs-1342/alms
cd alms

# Kurulum
chmod +x setup.sh && ./setup.sh
```

```bash
# Yeni terminal aç ve kurulumu tamamla
alms setup
```

Otomatik çalıştırma macOS'ta **launchd** ile yapılır. `alms setup` veya menüden ayarlanır.

> **Not:** `alms` komutu tanınmıyorsa:
> ```bash
> source ~/.zshrc   # veya ~/.bashrc
> ```

---

### Windows

**Gereksinimler:** Python 3.10+, Git

1. [Python 3.10+](https://www.python.org/downloads/) indir ve kur
   - ⚠️ Kurulumda **"Add Python to PATH"** seçeneğini işaretle
2. [Git for Windows](https://git-scm.com/download/win) indir ve kur

```bat
:: CMD veya PowerShell'de:
git clone https://github.com/trs-1342/alms
cd alms
setup.bat
```

`setup.bat` otomatik olarak şunları yapar:
- Python sürümünü kontrol eder
- `.venv` sanal ortamını oluşturur
- `alms.bat` wrapper oluşturur ve PATH'e ekler
- Task Scheduler erişimini test eder

```bat
:: Yeni terminal aç ve kurulumu tamamla:
alms setup
```

> **Not:** `alms` tanınmıyorsa (PATH henüz yüklenmedi):
> ```bat
> alms.bat setup
> ```

> **Otomatik çalıştırma için** `setup.bat`'ı sağ tık → "Yönetici olarak çalıştır" ile çalıştırın.

---

## Kullanım

### Komutlar

| Komut | Açıklama |
|-------|----------|
| `alms` | İnteraktif menü |
| `alms setup` | İlk kurulum / yeniden yapılandırma |
| `alms setup --reconfigure credentials` | Sadece şifre güncelle |
| `alms setup --reconfigure schedule` | Sadece otomasyon saatini güncelle |
| `alms sync` | Yeni dosyaları indir |
| `alms sync --courses FIZ108,YZM102` | Belirli dersleri indir |
| `alms sync --force` | Tüm dosyaları yeniden indir |
| `alms list` | Dersleri listele |
| `alms download` | Dosya seçerek indir |
| `alms today` | Yaklaşan aktiviteler |
| `alms open` | İndirme klasörünü aç |
| `alms status` | Sistem durumu |
| `alms stats` | İndirme istatistikleri |
| `alms log` | Aktivite logu |
| `alms logout` | Kayıtlı kimlik bilgilerini sil |

### Filtreler

```bash
alms sync --course FIZ108          # Tek ders
alms sync --courses FIZ108,MAT106  # Birden fazla ders
alms sync -f pdf                   # Sadece PDF
alms sync -f video                 # Sadece video
alms sync --week 7                 # Sadece 7. hafta
alms sync --all                    # Manifest'i yoksay, hepsini indir
alms sync --quiet                  # Sessiz mod (otomasyon için)
```

### Dosya seçici (interaktif)

`alms download` komutunda:

```
↑↓ hareket   SPACE seç   G grup seç   A hepsi   N temizle   F filtrele   ENTER onayla   Q iptal

  ▶ FIZ108  2/18
      ○ W01  fizik_2_1_hafta.pdf         4.1 MB
      ● W07  Fizik_2_Bolum_6.pdf         4.8 MB
    YZM102  0/4
      ○ W04  Pointers2.pdf               0.3 MB
```

`F` tuşuna basarak dosya adı veya ders kodu ile filtrele.

---

## Otomatik İndirme

`alms` menüsünden **Otomatik Çalıştırma** seçeneği ile ayarlanır:
- Saat/dakika belirle
- İndirilecek dersleri seç (boş = tüm dersler)

| Platform | Yöntem |
|----------|--------|
| Linux | crontab + shell wrapper |
| macOS | launchd .plist |
| Windows | Task Scheduler |

Log: `~/.config/alms/cron.log`

---

## Güvenlik

- Giriş bilgileri **AES-256** (Fernet) ile şifrelenir
- Şifreleme anahtarı makineye özel — dosya başka bilgisayarda açılamaz
- Config dizini `chmod 700`
- Token ve şifre log'a yazılmaz
- SSL doğrulama her zaman açık

---

## Bağımlılıklar

```
requests>=2.31.0
cryptography>=42.0.0
```

`setup.sh` / `setup.bat` otomatik kurar.

---

## Lisans

MIT
