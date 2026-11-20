#!/usr/bin/env bash
# Buat paket Ubuntu: dist/adsbooth_<versi>_<arch>.deb  (jalankan di Ubuntu 22.04, hasilnya jalan di 22.04/24.04)
set -e
cd "$(dirname "$0")/.."
sudo apt-get install -y python3-venv python3-dev gcc patchelf ccache dpkg-dev >/dev/null
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt -r installer/requirements-build.txt
python installer/build.py "$@"
