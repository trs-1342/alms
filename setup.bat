@echo off
:: setup.bat — ALMS Indirici Kurulum Scripti (Windows)
:: Calistirma: Sag tik > "Yonetici olarak calistir" (PATH icin)
setlocal EnableDelayedExpansion

echo.
echo ============================================================
echo   ALMS Indirici - Kurulum (Windows)
echo ============================================================
echo.

:: Python kontrolu
python --version >nul 2>&1
if errorlevel 1 (
    echo   [HATA] Python bulunamadi.
    echo   Python 3.10+ indirin: https://www.python.org/downloads/
    echo   Kurulumda "Add to PATH" secenegini isaretleyin.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo   Python %PY_VER% bulundu.

:: Sanal ortam
set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%.venv

if not exist "%VENV_DIR%" (
    echo   Sanal ortam olusturuluyor...
    python -m venv "%VENV_DIR%"
)

set PIP=%VENV_DIR%\Scripts\pip.exe
set PY=%VENV_DIR%\Scripts\python.exe

echo   Paketler yukleniyor...
"%PIP%" install --quiet --upgrade pip
"%PIP%" install --quiet -r "%SCRIPT_DIR%requirements.txt"
echo   [OK] Paketler yuklendi.

:: alms.bat wrapper
set BAT_PATH=%SCRIPT_DIR%alms_run.bat
echo @echo off > "%BAT_PATH%"
echo "%PY%" "%SCRIPT_DIR%alms.py" %%* >> "%BAT_PATH%"
echo   [OK] alms_run.bat olusturuldu.

:: PATH'e ekle (kullanici PATH'i)
set "NEW_PATH=%SCRIPT_DIR%"
for /f "tokens=3*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do (
    set "CURRENT_PATH=%%a %%b"
)
if defined CURRENT_PATH (
    echo !CURRENT_PATH! | find /i "%SCRIPT_DIR%" >nul || (
        setx PATH "!CURRENT_PATH!;%NEW_PATH%" >nul
        echo   [OK] PATH guncellendi.
    )
) else (
    setx PATH "%NEW_PATH%" >nul
    echo   [OK] PATH olusturuldu.
)

:: Config dizini (AppData)
set CONFIG_DIR=%APPDATA%\alms
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
:: Yalnizca kullaniciya okuma/yazma izni ver
icacls "%CONFIG_DIR%" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F" >nul 2>&1
echo   [OK] Config dizini: %CONFIG_DIR%

echo.
echo   Kurulum tamamlandi!
echo.
echo   Ilk calistirma (yeni terminal acin):
echo     alms_run.bat setup
echo.
pause
