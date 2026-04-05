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

:: ── Yonetici izni kontrolu ────────────────────────────────────
set "IS_ADMIN=0"
net session >nul 2>&1
if not errorlevel 1 (
    set "IS_ADMIN=1"
    echo   [OK] Yonetici izniyle calistirilıyor.
) else (
    echo   [UYARI] Bu betik yonetici izni olmadan calisiyor.
    echo.
    echo   Task Scheduler (otomatik indirme) icin yonetici izni gereklidir.
    echo   Diger adımlar yonetici izni olmadan tamamlanabilir.
    echo.
    echo   Yonetici olarak yeniden calistirmak icin:
    echo   Bu dosyaya sag tiklayip "Yonetici olarak calistir" seceneğini secin.
    echo.
    echo   Devam etmek icin herhangi bir tusa basin, cıkmak icin Ctrl+C...
    pause >nul
    echo.
)

:: ── Python kontrolu ───────────────────────────────────────────
set "PYTHON_FOUND=0"
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
        set PY_MAJOR=%%a
        set PY_MINOR=%%b
    )
    if !PY_MAJOR! GEQ 3 (
        if !PY_MINOR! GEQ 10 (
            echo   [OK] Python !PY_VER! bulundu.
            set "PYTHON_FOUND=1"
        ) else (
            echo   [UYARI] Python !PY_VER! bulundu ancak 3.10+ gerekli.
        )
    )
)

if "!PYTHON_FOUND!"=="0" (
    echo   [UYARI] Python 3.10+ bulunamadi.

    :: winget ile otomatik kur
    where winget >nul 2>&1
    if not errorlevel 1 (
        echo   winget ile Python 3.12 kuruluyor...
        echo   ^(Bu islem birkaç dakika surebilir^)
        echo.
        winget install Python.Python.3.12 --silent ^
            --accept-package-agreements ^
            --accept-source-agreements
        if not errorlevel 1 (
            echo.
            echo   [OK] Python kuruldu.
            :: PATH'i yenile
            for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "CURRENT_PATH=%%b"
            set "PATH=!CURRENT_PATH!;%PATH%"
            :: Python'u tekrar bul
            python --version >nul 2>&1
            if not errorlevel 1 (
                for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
                echo   [OK] Python !PY_VER! aktif.
                set "PYTHON_FOUND=1"
            ) else (
                echo   [!] Python kuruldu fakat PATH henuz guncellenmedi.
                echo   Yeni terminal acp tekrar calistirin: setup.bat
                pause
                exit /b 1
            )
        ) else (
            echo   [HATA] winget ile Python kurulamadi.
            goto :python_manual
        )
    ) else (
        :python_manual
        echo.
        echo   Python 3.10+ indirin ve kurun:
        echo   https://www.python.org/downloads/
        echo.
        echo   ONEMLI: Kurulumda "Add Python to PATH" secenegini isaretleyin!
        echo.
        start https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

:: ── Proje dizini ──────────────────────────────────────────────
set SCRIPT_DIR=%~dp0
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

set VENV_DIR=%SCRIPT_DIR%\.venv
set PY=%VENV_DIR%\Scripts\python.exe
set PIP=%VENV_DIR%\Scripts\pip.exe

:: ── Sanal ortam ───────────────────────────────────────────────
if not exist "%VENV_DIR%" (
    echo   Sanal ortam olusturuluyor...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo   [HATA] Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
)

:: ── Paket kurulumu ────────────────────────────────────────────
echo   Paketler yukleniyor...
"%PY%" -m pip install --quiet --upgrade pip
"%PY%" -m pip install --quiet -r "%SCRIPT_DIR%\requirements.txt"
if errorlevel 1 (
    echo   [HATA] Paketler yuklenemedi.
    echo   Manuel: "%PY%" -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo   [OK] Paketler yuklendi.

:: ── alms.bat wrapper (venv Python kullanir) ──────────────────
set WRAPPER=%SCRIPT_DIR%\alms.bat
echo @echo off > "%WRAPPER%"
echo setlocal >> "%WRAPPER%"
echo "%PY%" "%SCRIPT_DIR%\alms.py" %%* >> "%WRAPPER%"
echo   [OK] alms.bat olusturuldu.

:: ── PATH'e ekle ───────────────────────────────────────────────
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do (
    set "CURRENT_PATH=%%b"
)

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

:: ── Config dizini ─────────────────────────────────────────────
set CONFIG_DIR=%APPDATA%\alms
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
icacls "%CONFIG_DIR%" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F" >nul 2>&1
echo   [OK] Config dizini: %CONFIG_DIR%

:: ── Task Scheduler erisim kontrolu ───────────────────────────
if "%IS_ADMIN%"=="1" (
    schtasks /Query >nul 2>&1
    if errorlevel 1 (
        echo   [UYARI] Task Scheduler'a erisim yok.
        echo           Otomatik indirme icin yonetici olarak calistirin.
    ) else (
        echo   [OK] Task Scheduler erisimi mevcut.
    )
) else (
    echo   [UYARI] Task Scheduler kontrolu atlandi ^(yonetici izni yok^).
    echo           Otomatik indirme kurmak icin yonetici olarak yeniden calistirin.
)

:: ── PowerShell ExecutionPolicy kontrolu ──────────────────────
powershell -Command "Get-ExecutionPolicy" 2>nul | findstr /i "Restricted" >nul
if not errorlevel 1 (
    echo.
    echo   [UYARI] PowerShell ExecutionPolicy kisitli.
    if "%IS_ADMIN%"=="1" (
        echo   Duzeltiliyor...
        powershell -Command "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force" 2>nul
        if not errorlevel 1 (
            echo   [OK] ExecutionPolicy guncellendi.
        ) else (
            echo   [!] Manuel: PowerShell'de calistirin:
            echo       Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
        )
    ) else (
        echo   [!] Duzeltmek icin PowerShell'i yonetici olarak acip calistirin:
        echo       Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    )
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
