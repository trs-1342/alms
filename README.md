# ALMS İndirici

IGU (İstanbul Gelişim Üniversitesi) ALMS ve OBİS sistemlerine tek komutla erişim.
Ders materyallerini otomatik indirir, sınav tarihlerini gösterir.

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

### Linux

```bash
git clone https://github.com/trs-1342/alms
cd alms
chmod +x setup.sh && ./setup.sh
alms setup
```

> `cronie` gereklidir (otomasyon için):
> ```bash
> sudo pacman -S cronie && sudo systemctl enable --now cronie   # Arch
> sudo apt install cron                                          # Ubuntu
> ```

### macOS

```bash
brew install python3 git
git clone https://github.com/trs-1342/alms
cd alms
chmod +x setup.sh && ./setup.sh
alms setup
```

### Windows

1. [Python 3.10+](https://www.python.org/downloads/) — kurulumda **"Add Python to PATH"** işaretle
2. [Git for Windows](https://git-scm.com/download/win) kur

```bat
git clone https://github.com/trs-1342/alms
cd alms
setup.bat
alms setup
```

---

## Temel Kullanım

```bash
alms                # Menü
alms sync           # Yeni dosyaları indir
alms download       # Dosya seçerek indir
alms obis --sinav   # Sınav takvimi
alms update         # Güncelleme yükle
alms --version      # Sürüm + güncelleme kontrolü
```

Tam kullanım rehberi: **[KULLANIM.md](KULLANIM.md)**

---

## Komut Özeti

| Komut | Açıklama |
|-------|----------|
| `alms` | İnteraktif menü |
| `alms setup` | İlk kurulum |
| `alms sync` | Yeni dosyaları indir |
| `alms sync --courses FIZ108,MAT106` | Belirli dersleri indir |
| `alms sync -f pdf` | Sadece PDF |
| `alms sync --quiet` | Sessiz mod (otomasyon) |
| `alms download` | Dosya seçici |
| `alms list` | Dersleri listele |
| `alms today` | Yaklaşan aktiviteler |
| `alms status` | Sistem durumu |
| `alms stats` | İstatistikler |
| `alms log` | Aktivite logu |
| `alms export` | Ders indexini dışa aktar |
| `alms open` | İndirme klasörünü aç |
| `alms obis --setup` | OBİS oturumu kur |
| `alms obis --sinav` | Sınav takvimi |
| `alms obis notlar` | Ders notları |
| `alms obis devamsizlik` | Devamsızlık |
| `alms update` | Güncelleme yükle |
| `alms --version` | Sürüm bilgisi |
| `alms logout` | Kimlik bilgilerini sil |

---

## OBİS Kurulumu

Tarayıcıda OBİS'e giriş yaptıktan sonra **bir kez** yapılır:

```bash
alms obis --setup
# F12 → Storage → Cookies → ASP.NET_SessionId değerini kopyala yapıştır
```

Oturum kapatılmadığı sürece token geçerli kalır.

---

## Otomatik İndirme

Menüden **[12] Otomatik Çalıştırma** ile ayarlanır.

| Platform | Yöntem |
|----------|--------|
| Linux | crontab |
| macOS | launchd |
| Windows | Task Scheduler |

---

## Güvenlik

- Kimlik bilgileri **AES-256** ile şifrelenir, makineye özel
- OBİS token şifreli saklanır
- SSL doğrulama her zaman açık
- Token/şifre log dosyasına yazılmaz

---

## Güncelleme Sistemi

```bash
alms update
```

- Config dosyaları yedeklenir
- `git pull` + bağımlılık güncellemesi
- Hata durumunda otomatik rollback
- Menü açılışında güncelleme varsa bildirim gösterilir

Versiyon tag ile (`v1.5.0`) veya commit sayısından otomatik belirlenir.

---

## Bağımlılıklar

```
requests>=2.31.0,<3.0.0
cryptography>=42.0.0,<45.0.0
beautifulsoup4>=4.12.0,<5.0.0
```

`setup.sh` / `setup.bat` otomatik kurar.

---

## Lisans

MIT
