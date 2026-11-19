#!/data/data/com.termux/files/usr/bin/bash
# Setup Photobooth di tablet Android (Termux). Jalankan sekali:  bash setup-android.sh
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"

echo "== Photobooth: setup Android (Termux) =="
echo "-> Memperbarui paket Termux..."
pkg update -y
echo "-> Memasang Python + Pillow..."
pkg install -y python python-pillow
echo "-> Memasang modul Python..."
pip install flask qrcode python-escpos

# skrip untuk menjalankan server
cat > start-android.sh <<EOS
#!/data/data/com.termux/files/usr/bin/bash
# Jalankan server photobooth. Biarkan Termux tetap terbuka di latar belakang.
termux-wake-lock 2>/dev/null || true
cd "$DIR"
echo "Kiosk : http://localhost:5000/?kiosk=1"
echo "Studio: http://localhost:5000/studio"
python app.py
EOS
chmod +x start-android.sh

echo
echo "== Selesai =="
echo "Jalankan server :  bash $DIR/start-android.sh"
echo "Lalu buka Chrome:  http://localhost:5000/studio  -> Printer & tablet -> 'USB di tablet Android (kabel OTG)'"
echo "                   -> Sambungkan printer USB -> Simpan -> Cetak tes"
echo "Kiosk           :  http://localhost:5000/?kiosk=1  (menu Chrome -> Tambahkan ke layar utama)"
