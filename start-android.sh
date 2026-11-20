#!/data/data/com.termux/files/usr/bin/bash
# Jalankan server photobooth di tablet Android (Termux).
# Biarkan Termux tetap terbuka di latar belakang.
termux-wake-lock 2>/dev/null || true
cd "$(dirname "$0")"
echo "Kiosk : http://localhost:5000/?kiosk=1"
echo "Studio: http://localhost:5000/studio"
python app.py
