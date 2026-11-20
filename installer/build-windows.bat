@echo off
REM Buat installer Windows: dist\AdsBooth-Setup-<versi>.exe
REM Syarat: Python 3.11 (.venv), Inno Setup 6 (https://jrsoftware.org/isdl.php)
cd /d "%~dp0.."
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt -r installer\requirements-build.txt || goto :err
python installer\build.py %* || goto :err
echo.
echo Selesai. Lihat folder dist\
pause
exit /b 0
:err
echo.
echo GAGAL. Baca pesan di atas.
pause
exit /b 1
