#!/usr/bin/env bash
# Pasang photobooth di Raspberry Pi (Raspberry Pi OS Desktop 64-bit). Jalankan sekali sebagai user biasa:
#   bash install-autostart.sh
# - server jalan otomatis saat boot (systemd: photobooth.service)
# - Chromium kiosk terbuka otomatis saat desktop login
# - izin printer USB (/dev/usb/lp0) tanpa sudo
# - layar tidak mati sendiri
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
USER_NAME="$(id -un)"
if [ "$(id -u)" = "0" ]; then echo "Jalankan sebagai user biasa (bukan root/sudo)."; exit 1; fi

echo "== 1/5 Paket sistem =="
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev curl unclutter
command -v chromium-browser >/dev/null || command -v chromium >/dev/null || sudo apt-get install -y chromium-browser || sudo apt-get install -y chromium

echo "== 2/5 Modul Python =="
bash run-linux.sh --setup

echo "== 3/5 Izin printer USB =="
sudo tee /etc/udev/rules.d/99-photobooth-printer.rules >/dev/null <<RULES
# Printer thermal USB untuk photobooth (Epson = 04b8)
SUBSYSTEM=="usbmisc", KERNEL=="lp[0-9]*", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="04b8", MODE="0666"
RULES
sudo usermod -aG lp "$USER_NAME" || true
sudo udevadm control --reload-rules && sudo udevadm trigger || true

echo "== 4/5 Server otomatis saat boot =="
sudo tee /etc/systemd/system/photobooth.service >/dev/null <<UNIT
[Unit]
Description=Photobooth thermal server
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now photobooth.service

echo "== 5/5 Kiosk otomatis + layar tidak mati =="
chmod +x "$DIR/kiosk-linux.sh"
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/photobooth-kiosk.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Photobooth Kiosk
Exec=$DIR/kiosk-linux.sh
X-GNOME-Autostart-enabled=true
DESK
# labwc (Raspberry Pi OS Bookworm terbaru)
mkdir -p "$HOME/.config/labwc"
touch "$HOME/.config/labwc/autostart"
grep -q "kiosk-linux.sh" "$HOME/.config/labwc/autostart" || echo "$DIR/kiosk-linux.sh &" >> "$HOME/.config/labwc/autostart"
command -v raspi-config >/dev/null && sudo raspi-config nonint do_blanking 1 || true

IP="$(hostname -I | awk '{print $1}')"
echo
echo "== Selesai =="
echo "Server : sudo systemctl status photobooth   (log: journalctl -u photobooth -f)"
echo "Studio : http://localhost:5000/studio   atau dari laptop: http://$IP:5000/studio"
echo "Printer: Studio -> Printer & tablet -> 'Raspberry Pi / Linux (USB, /dev/usb/lp0)' -> Cetak tes"
echo "Reboot sekarang supaya kiosk terbuka otomatis:  sudo reboot"
