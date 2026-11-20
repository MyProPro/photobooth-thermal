@echo off
REM Jalankan server AdsBooth (dari kode sumber) + buka Chrome mode kiosk
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
  pip install -q -r requirements.txt
)
start "adsbooth-server" cmd /k python app.py
timeout /t 3 /nobreak >nul
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
start "" %CHROME% --kiosk --app=http://localhost:5000/?kiosk=1 --use-fake-ui-for-media-stream --disable-pinch --overscroll-history-navigation=0 --user-data-dir="%~dp0.chrome-kiosk"
