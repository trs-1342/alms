# ALMS İndirici

IGU (İstanbul Gelişim Üniversitesi) ALMS sistemindeki ders materyallerini — PDF, döküman ve videoları — otomatik olarak bilgisayarına indiren komut satırı aracı.

## Amaç

ALMS web arayüzüne her girmeden, tek komutla tüm ders materyallerini senkronize etmek. Dosyalar ders koduna ve haftaya göre düzenli klasörlere kaydedilir. Zamanlama kurulursa her gün otomatik çalışır.

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

## Kullanım

### Komutlar

| Komut | Açıklama |
|-------|----------|
| `alms` | İnteraktif menü |
| `alms setup` | İlk kurulum sihirbazı |
| `alms sync` | Yeni dosyaları indir |
| `alms list` | Dersleri ve kodları listele |
| `alms download` | Dosya seçerek indir |
| `alms today` | Yaklaşan aktiviteler / takvim |
| `alms open` | İndirme klasörünü aç |
| `alms status` | Token, indirme ve otomasyon durumu |
| `alms logout` | Kayıtlı kimlik bilgilerini sil |
| `alms config` | Mevcut ayarları göster |

### Filtreler

```bash
alms sync --course FIZ108      # Sadece Fizik 2
alms sync --course YZM         # YZM içeren tüm dersler
alms sync -f pdf               # Sadece PDF / dökümanlar
alms sync -f video             # Sadece videolar
alms sync --week 7             # Sadece 7. hafta
alms sync --all                # Daha önce indirilenler dahil hepsini yeniden al
alms sync --quiet              # Sessiz mod (cron için)
```

### Dosya seçici (interaktif)

`alms download` komutunda ok tuşları ve Space ile dosya seçilir:

```
↑↓ hareket   SPACE seç   G grubu seç   A hepsi   N hiçbiri   ENTER onayla   Q iptal

  ▶ FIZ108  2/18
      ○ W01  fizik_2_1_hafta.pdf         4.1 MB
      ● W07  Fizik_2_Bolum_6.pdf         4.8 MB

    YZM102  0/4
      ○ W04  Pointers2.pdf               0.3 MB
```

---

## Kurulum

### Gereksinimler

- Python 3.10 veya üzeri
- Git

---

### Linux

```bash
git clone https://github.com/trs-1342/alms
cd alms
chmod +x setup.sh && ./setup.sh
```

Kurulum sonrası yeni terminal aç:

```bash
alms setup    # ilk giriş ve ayarlar
alms          # menüyü aç
```

`setup.sh` şunları yapar: sanal ortam oluşturur, paketleri yükler, `~/.local/bin/alms` kısayolunu ekler, config dizinini güvenli hale getirir (`chmod 700`).

---

### macOS

```bash
git clone https://github.com/trs-1342/alms
cd alms
chmod +x setup.sh && ./setup.sh
```

Kurulum sonrası:

```bash
alms setup
alms
```

> **Not:** Eğer `alms` komutu tanınmıyorsa terminali kapat/aç ya da `source ~/.zshrc` çalıştır.

---

### Windows

**Gereksinimler:**
- [Python 3.10+](https://www.python.org/downloads/) — kurulumda **"Add to PATH"** işaretli olmalı
- [Git for Windows](https://git-scm.com/download/win)

```bat
git clone https://github.com/trs-1342/alms
cd alms
setup.bat
```

Kurulum sonrası yeni terminal (CMD veya PowerShell):

```bat
alms_run.bat setup
alms_run.bat
```

> **Not:** `setup.bat` yönetici olarak çalıştırılırsa PATH'e otomatik eklenir. Aksi halde `alms_run.bat` tam yolu ile çağırılmalıdır.

---

## Güvenlik

- Giriş bilgileri **AES-256** ile şifrelenir (Fernet)
- Şifreleme anahtarı makineye özel türetilir — `credentials.enc` dosyası başka bilgisayarda açılamaz
- Config dizini `chmod 700` (sadece sen okuyabilirsin)
- Token ve şifre log dosyasına yazılmaz
- Aynı anda iki instance çalışmasını lock dosyası engeller
- SSL doğrulama her zaman açık

---

## Bağımlılıklar

```
requests>=2.31.0
cryptography>=42.0.0
```

`setup.sh` / `setup.bat` bunları otomatik kurar.

---

## Lisans

MIT
