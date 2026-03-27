# ALMS İndirici

IGU (İstanbul Gelişim Üniversitesi) ALMS sisteminden ders materyallerini otomatik indiren araç.

## Hızlı Kurulum

```bash
git clone https://github.com/trs-1342/alms
cd alms

# Linux / macOS
chmod +x setup.sh && ./setup.sh

# Windows
setup.bat
```

Kurulumdan sonra:
```bash
alms setup   # ilk giriş ve ayarlar
alms         # interaktif menü
```

## Komutlar

| Komut | Açıklama |
|-------|----------|
| `alms` | İnteraktif menü |
| `alms setup` | İlk kurulum sihirbazı |
| `alms sync` | Yeni dosyaları indir |
| `alms list` | Dersleri listele |
| `alms download` | İnteraktif indirme |
| `alms status` | Sistem durumu |
| `alms logout` | Kimlik bilgilerini sil |
| `alms config` | Ayarları göster |

### Filtreler

```bash
alms sync --course FIZ108      # Sadece Fizik 2
alms sync -f pdf               # Sadece PDF'ler
alms sync --week 7             # Sadece 7. hafta
alms sync --all                # Daha önce indirilenler dahil
alms download -f video --course YZM102
```

## İndirme Klasörü

| Platform | Konum |
|----------|-------|
| Linux | `~/ALMS/` |
| macOS | `~/Documents/ALMS/` |
| Windows | `C:\Users\...\Documents\ALMS\` |

```
ALMS/
├── FİZİK II (FIZ108)/
│   ├── Hafta_01/
│   │   ├── fizik_2_1_hafta.pdf
│   │   └── fizik_2_video.mp4
│   └── Hafta_07/
│       └── Fizik_2_Bolum_6.pdf
└── MATEMATİK II (MAT106)/
    └── ...
```

## Gereksinimler

- Python 3.10+
- `requests`, `cryptography` (setup.sh otomatik kurar)

## Güvenlik

- Kimlik bilgileri AES-256 (Fernet) ile şifrelenir
- Şifreleme anahtarı makineye özel türetilir (PBKDF2, 600k iterasyon)
- Config dizini `chmod 700` (sadece kullanıcı erişebilir)
- Credential dosyası `chmod 600`
- Token ve şifreler log dosyasına yazılmaz
- Tek instance garantisi (lock dosyası)
- SSL doğrulama her zaman açık
- Her indirilen dosya boyut doğrulamasından geçer

## Otomatik Çalıştırma

`alms` menüsünden ya da:
```bash
alms setup   # kurulum sırasında ayarlanabilir
```

Platform desteği: Linux (crontab), macOS (launchd), Windows (Task Scheduler).

## Lisans

MIT
