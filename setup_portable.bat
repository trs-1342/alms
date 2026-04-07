@echo off
:: setup_portable.bat — ALMS Indirici Portable Kurulum (Admin izni gerekmez)
:: Kullanim: .\setup_portable.bat
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo.
echo ============================================================
echo   ALMS Indirici - Portable Kurulum (Admin gerekmez)
echo ============================================================
echo.

:: ── Dizinler ─────────────────────────────────────────────────
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"

set "PORTABLE_DIR=!SCRIPT_DIR!\portable"
set "PY_DIR=!PORTABLE_DIR!\python"
set "PY=!PY_DIR!\python.exe"

:: ── Mimari tespiti ────────────────────────────────────────────
set "ARCH=amd64"
if "%PROCESSOR_ARCHITECTURE%"=="x86" (
    if not defined PROCESSOR_ARCHITEW6432 (
        set "ARCH=win32"
    )
)

:: ── Python surumu ─────────────────────────────────────────────
set "PY_VER=3.12.9"
set "PY_ZIP=python-%PY_VER%-embed-%ARCH%.zip"
set "PY_URL=https://www.python.org/ftp/python/%PY_VER%/%PY_ZIP%"
set "PY_PTH=!PY_DIR!\python312._pth"

:: ── Python zaten kurulu mu? ───────────────────────────────────
if exist "!PY!" (
    echo   [OK] Portable Python zaten mevcut, atlanıyor.
    goto :install_deps
)

:: ── Portable Python indir ─────────────────────────────────────
if not exist "!PORTABLE_DIR!" mkdir "!PORTABLE_DIR!"

echo   Python %PY_VER% (%ARCH%) indiriliyor...
echo   ^(Lütfen bekleyin, boyut ~15 MB^)
echo.
powershell -NoProfile -Command ^
    "Invoke-WebRequest -Uri '!PY_URL!' -OutFile '!PORTABLE_DIR!\!PY_ZIP!' -UseBasicParsing"
if errorlevel 1 (
    echo.
    echo   [HATA] Python indirilemedi. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)
echo   [OK] Indirildi.

:: ── Zip'i ac ──────────────────────────────────────────────────
echo   Cikartiliyor...
powershell -NoProfile -Command ^
    "Expand-Archive -Path '!PORTABLE_DIR!\!PY_ZIP!' -DestinationPath '!PY_DIR!' -Force"
if errorlevel 1 (
    echo   [HATA] Zip acilamadi.
    pause
    exit /b 1
)
del "!PORTABLE_DIR!\!PY_ZIP!" >nul 2>&1
echo   [OK] Python cikartildi.

:: ── site-packages'i etkinlestir ───────────────────────────────
:: Embedded Python'da pip/paketlerin calismasi icin gerekli
powershell -NoProfile -Command ^
    "(Get-Content '!PY_PTH!') -replace '#import site', 'import site' | Set-Content '!PY_PTH!'"
echo   [OK] site-packages etkinlestirildi.

:: ── pip indir ve kur ──────────────────────────────────────────
echo   pip indiriliyor...
powershell -NoProfile -Command ^
    "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '!PORTABLE_DIR!\get-pip.py' -UseBasicParsing"
if errorlevel 1 (
    echo   [HATA] pip indirilemedi.
    pause
    exit /b 1
)

echo   pip kuruluyor...
"!PY!" "!PORTABLE_DIR!\get-pip.py" --no-warn-script-location --quiet
if errorlevel 1 (
    echo   [HATA] pip kurulamadi.
    pause
    exit /b 1
)
del "!PORTABLE_DIR!\get-pip.py" >nul 2>&1
echo   [OK] pip kuruldu.

:install_deps
:: ── Bagimliliklari kur ────────────────────────────────────────
echo   Paketler yukleniyor...
"!PY!" -m pip install --quiet --no-warn-script-location ^
    -r "!SCRIPT_DIR!\requirements.txt"
if errorlevel 1 (
    echo   [HATA] Paketler yuklenemedi.
    echo   Manuel: "!PY!" -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo   [OK] Paketler yuklendi.

:: ── Konsol font ayarı (Consolas, yonetici gerektirmez) ────────
:: HKCU\Console\ALMS → sadece "ALMS" baslikli pencerelere uygulanir
echo   Konsol font ayarlaniyor (Consolas)...
reg add "HKCU\Console\ALMS" /v "FaceName"   /t REG_SZ    /d "Consolas"  /f >nul 2>&1
reg add "HKCU\Console\ALMS" /v "FontSize"   /t REG_DWORD /d 0x000E0000  /f >nul 2>&1
reg add "HKCU\Console\ALMS" /v "FontWeight" /t REG_DWORD /d 400         /f >nul 2>&1
reg add "HKCU\Console\ALMS" /v "FontFamily" /t REG_DWORD /d 54          /f >nul 2>&1
:: UTF-8 ve VT100 (ANSI renk) destegi
reg add "HKCU\Console\ALMS" /v "CodePage"   /t REG_DWORD /d 65001       /f >nul 2>&1
reg add "HKCU\Console\ALMS" /v "VirtualTerminalLevel" /t REG_DWORD /d 1 /f >nul 2>&1
echo   [OK] Font ayarlandi (bir sonraki acilista gecerli).

:: ── Launcher olustur ──────────────────────────────────────────
set "WRAPPER=!SCRIPT_DIR!\alms.bat"
(
    echo @echo off
    echo title ALMS
    echo chcp 65001 ^>nul 2^>^&1
    echo "!PY!" "!SCRIPT_DIR!\alms.py" %%*
) > "!WRAPPER!"
echo   [OK] alms.bat olusturuldu.

:: ── Config dizini ─────────────────────────────────────────────
:: AppData kullaniciya ozel oldugundan admin gerekmez
if not exist "%APPDATA%\alms" mkdir "%APPDATA%\alms"
echo   [OK] Config dizini: %APPDATA%\alms

echo.
echo ============================================================
echo   Portable kurulum tamamlandi!
echo ============================================================
echo.
echo   Calistirmak icin bu klasorde:
echo     alms.bat setup
echo.
echo   Veya tam yol ile:
echo     "!WRAPPER!" setup
echo.
echo   NOT: Bu kurulum yalnizca bu klasore ozeldir.
echo        Klasoru tasirsan alms.bat icindeki yolu guncelle.
echo.
pause
