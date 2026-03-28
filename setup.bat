@echo off
:: setup.bat — ALMS Indirici Kurulum Scripti (Windows)
:: Calistirma: Cift tiklayın veya sag tik > "Yonetici olarak calistir"
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo.
echo ============================================================
echo   ALMS Indirici - Kurulum (Windows)
echo ============================================================
echo.

:: ── Python kontrolü ──────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo   [HATA] Python bulunamadi.
    echo.
    echo   Python 3.10+ indirin:
    echo   https://www.python.org/downloads/
    echo.
    echo   ONEMLI: Kurulumda "Add Python to PATH" secenegini isaretleyin!
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo   [OK] Python %PY_VER% bulundu.

:: Python 3.10+ kontrolu
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 (
    echo   [HATA] Python 3.10+ gerekli, bulunan: %PY_VER%
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo   [HATA] Python 3.10+ gerekli, bulunan: %PY_VER%
    pause
    exit /b 1
)

:: ── Proje dizini ─────────────────────────────────────────────
set SCRIPT_DIR=%~dp0
:: Sondaki \ kaldir
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

set VENV_DIR=%SCRIPT_DIR%\.venv
set PY=%VENV_DIR%\Scripts\python.exe
set PIP=%VENV_DIR%\Scripts\pip.exe

:: ── Sanal ortam ──────────────────────────────────────────────
if not exist "%VENV_DIR%" (
    echo   Sanal ortam olusturuluyor...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo   [HATA] Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
)

echo   Paketler yukleniyor...
"%PIP%" install --quiet --upgrade pip
"%PIP%" install --quiet -r "%SCRIPT_DIR%\requirements.txt"
if errorlevel 1 (
    echo   [HATA] Paketler yuklenemedi.
    pause
    exit /b 1
)
echo   [OK] Paketler yuklendi.

:: ── alms.bat wrapper — "alms" komutu olarak calissin ─────────
set WRAPPER=%SCRIPT_DIR%\alms.bat
echo @echo off > "%WRAPPER%"
echo setlocal >> "%WRAPPER%"
echo "%PY%" "%SCRIPT_DIR%\alms.py" %%* >> "%WRAPPER%"
echo   [OK] alms.bat olusturuldu.

:: ── PATH'e ekle ───────────────────────────────────────────────
:: Kullanici PATH'ini oku
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do (
    set "CURRENT_PATH=%%b"
)

:: Zaten PATH'de mi?
echo !CURRENT_PATH! | findstr /i /c:"%SCRIPT_DIR%" >nul 2>&1
if errorlevel 1 (
    if defined CURRENT_PATH (
        setx PATH "!CURRENT_PATH!;%SCRIPT_DIR%" >nul
    ) else (
        setx PATH "%SCRIPT_DIR%" >nul
    )
    echo   [OK] PATH'e eklendi: %SCRIPT_DIR%
    echo   [!] Degisiklik icin yeni terminal acin.
) else (
    echo   [OK] PATH zaten dogru.
)

:: ── Config dizini ────────────────────────────────────────────
set CONFIG_DIR=%APPDATA%\alms
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
icacls "%CONFIG_DIR%" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F" >nul 2>&1
echo   [OK] Config dizini: %CONFIG_DIR%

:: ── Task Scheduler: otomatik calistirma altyapisi hazir ──────
:: Gercek zamanlama "alms setup" veya menu ile yapilir.
:: Burada sadece schtasks erisimini test et.
schtasks /Query >nul 2>&1
if errorlevel 1 (
    echo   [UYARI] Task Scheduler'a erisim yok.
    echo           Otomatik indirme icin yonetici olarak calistirin.
) else (
    echo   [OK] Task Scheduler erisimi mevcut.
)

:: ── PowerShell ExecutionPolicy kontrolu ──────────────────────
powershell -Command "Get-ExecutionPolicy" 2>nul | findstr /i "Restricted" >nul
if not errorlevel 1 (
    echo.
    echo   [UYARI] PowerShell ExecutionPolicy kisitli.
    echo           Gerekirse: PowerShell'i yonetici olarak ac ve calistir:
    echo           Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
)

echo.
echo ============================================================
echo   Kurulum tamamlandi!
echo ============================================================
echo.
echo   Yeni bir terminal (CMD veya PowerShell) acin ve calistirin:
echo.
echo     alms setup
echo.
echo   Eger "alms" taninmiyorsa (PATH henuz yuklenmedi):
echo     %SCRIPT_DIR%\alms.bat setup
echo.
pause
