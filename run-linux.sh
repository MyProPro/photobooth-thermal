#!/usr/bin/env bash
# Jalankan server photobooth di Linux / Raspberry Pi.
#   bash run-linux.sh          -> pasang (sekali) lalu jalankan server
#   bash run-linux.sh --setup  -> hanya pasang dependensi
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "-> Membuat virtualenv..."
  python3 -m venv .venv
fi
. .venv/bin/activate
echo "-> Memasang/cek modul Python (pertama kali agak lama)..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
[ "$1" = "--setup" ] && exit 0
exec python app.py
