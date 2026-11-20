"""Lokasi folder program vs folder data.

Program (kode, static/, fonts/, config.example.json) bisa ditimpa saat update.
Data (config.json, events/, output/ foto tamu & database, certs/, logs/) TIDAK boleh ikut tertimpa.

Urutan penentuan folder data:
  1. variabel lingkungan ADSBOOTH_DATA / PHOTOBOOTH_DATA (kalau diisi)
  2. mode portabel: kalau di folder program sudah ada config.json / events / output, atau file portable.txt
     (cara lama: semua di satu folder; tetap jalan seperti sebelumnya)
  3. folder data sistem:
       Windows : C:\\ProgramData\\AdsBooth
       Linux   : ~/.local/share/adsbooth
       macOS   : ~/Library/Application Support/AdsBooth
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def _system_data_dir():
    if os.name == "nt":
        root = os.environ.get("PROGRAMDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(root, "AdsBooth")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/AdsBooth")
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(xdg, "adsbooth")


def _resolve():
    env = (os.environ.get("ADSBOOTH_DATA") or os.environ.get("PHOTOBOOTH_DATA") or "").strip()
    if env:
        return os.path.abspath(os.path.expanduser(env)), "env"
    if os.path.exists(os.path.join(BASE, "portable.txt")) or any(
            os.path.exists(os.path.join(BASE, n)) for n in ("config.json", "events", "output")):
        return BASE, "portable"
    return _system_data_dir(), "system"


DATA, MODE = _resolve()
OUT = os.path.join(DATA, "output")
EVENTS = os.path.join(DATA, "events")
CERTS = os.path.join(DATA, "certs")
LOGS = os.path.join(DATA, "logs")
CONFIG = os.path.join(DATA, "config.json")
SECRET = os.path.join(DATA, ".secret_key")

for _d in (DATA, OUT, EVENTS, LOGS):
    os.makedirs(_d, exist_ok=True)
