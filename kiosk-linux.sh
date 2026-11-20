#!/usr/bin/env bash
# Buka Chromium layar penuh ke kiosk photobooth (dipanggil otomatis saat login desktop).
URL="${1:-http://localhost:5000/?kiosk=1}"
for i in $(seq 1 60); do               # tunggu server siap (maks ~60 detik)
  curl -s -o /dev/null http://localhost:5000/api/status && break
  sleep 1
done
# Google Chrome (.deb) didahulukan: Chromium versi snap di Ubuntu sering bermasalah dengan profil & USB
BROWSER="$(command -v google-chrome-stable || command -v google-chrome || command -v chromium-browser || command -v chromium)"
command -v unclutter >/dev/null && (unclutter -idle 3 >/dev/null 2>&1 &)
exec "$BROWSER" --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 --overscroll-history-navigation=0 --disable-pinch \
  --password-store=basic --use-fake-ui-for-media-stream --autoplay-policy=no-user-gesture-required \
  --user-data-dir="$HOME/.photobooth-kiosk" "$URL"
