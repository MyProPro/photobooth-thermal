"""Penyimpanan event (folder events/<id>/event.json + aset logo & frame)."""
import json
import os
import re
import shutil
import time
import uuid

import paths as P

BASE = P.BASE
EVENTS_DIR = P.EVENTS          # di folder data (tidak tertimpa saat update)
ACTIVE_FILE = os.path.join(EVENTS_DIR, "active.txt")
os.makedirs(EVENTS_DIR, exist_ok=True)

ALL_LAYOUTS = ["solo", "duo", "strip", "grid"]

DEFAULT = {
    "name": "Event baru",
    "event_name": "NAMA EVENT",
    "footer": "TERIMA KASIH",
    "logo": "",
    "intro_photo": "",         # foto untuk animasi layar awal kiosk
    "intro_photos": [],        # daftar foto intro & gaya (hingga 3 foto)
    "theme": {},
    "output": "thermal",
    "intro_style": "auto",     # animasi layar awal: auto (mengikuti output thermal/photo/both) | thermal | instan | strip
    "photo_templates": [],     # template mode foto yang tampil (kosong = semua)
    "photo_default_template": "klasik",
    "photo_frames": {},        # bingkai PNG mode foto per layout: {"solo": "file.png", ...}               # warna & font kiosk (kosong = tema bawaan krem)
    "layouts": list(ALL_LAYOUTS),
    "default_layout": "strip",
    "templates": [],           # kosong = semua template bawaan + custom
    "default_template": "klasik",
    "custom_templates": [],    # [{id, name, kind: builder|overlay, ...}]
    "social": {"username": "", "display": "{event}", "website": "", "bio": "{date_long}"},  # template Profil Sosmed
    "payment": {
        "enabled": False,
        "method": "qr",           # qr | manual | both
        "price_receipt": 15000,
        "price_photo": 30000,
        "timeout_seconds": 120,
        "gateway": "simulator",   # simulator | qris_static | midtrans
        "qris_image": "",
    },
    "download_auto_delete": 3, # menit auto-delete di server
    "qr_download": True,       # QR unduh foto digital (tamu harus satu Wi-Fi dengan server)
    "print_qr": False,         # Cetak QR download di kertas foto/struk (bawaan: False, bersih tanpa QR)
    "features": {"guestbook": False, "lucky_draw": False, "pose_challenge": False, "host_copy": False,
                 "living_photo": False},
    "living_url": "",          # alamat halaman Living Photo (kosong = bawaan produk / config)
    "print_lang": "id",        # bahasa teks yang tercetak: id | en
    "cert_titles": [],         # kosong = daftar gelar bawaan (templates.GELAR)
    "boarding": {"from_code": "SNI", "from": "Sini", "to_code": "BHG", "to": "Bahagia"},
}


def _safe_id(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:40] or "event"


def path(eid, *parts):
    eid = os.path.basename(eid)
    return os.path.join(EVENTS_DIR, eid, *[os.path.basename(p) for p in parts])


def exists(eid):
    return bool(eid) and os.path.exists(path(eid, "event.json"))


def load(eid):
    with open(path(eid, "event.json"), encoding="utf-8") as f:
        data = json.load(f)
    out = json.loads(json.dumps(DEFAULT))
    out.update(data)
    out["id"] = eid
    return normalize(out)


def normalize(ev):
    """Bersihkan data lama: layout yang sudah dihapus (mis. 'feed'), nilai tak dikenal."""
    lay = [x for x in (ev.get("layouts") or []) if x in ALL_LAYOUTS]
    ev["layouts"] = list(dict.fromkeys(lay)) or list(ALL_LAYOUTS)
    if ev.get("default_layout") not in ev["layouts"]:
        ev["default_layout"] = "strip" if "strip" in ev["layouts"] else ev["layouts"][0]
    if ev.get("print_lang") not in ("id", "en"):
        ev["print_lang"] = "id"
    return ev


def save(eid, data):
    data = normalize(dict(data))
    data.pop("id", None)
    data["updated"] = int(time.time())
    os.makedirs(path(eid), exist_ok=True)
    tmp = path(eid, "event.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path(eid, "event.json"))
    return load(eid)


def list_all():
    act = get_active()
    out = []
    for d in sorted(os.listdir(EVENTS_DIR)):
        if d.startswith("_") or not exists(d):
            continue
        e = load(d)
        out.append({"id": d, "name": e.get("name"), "event_name": e.get("event_name"),
                    "updated": e.get("updated", 0), "active": d == act,
                    "custom_count": len(e.get("custom_templates", []))})
    out.sort(key=lambda x: -x["updated"])
    return out


def create(name, from_id=None):
    base = _safe_id(name)
    eid, k = base, 2
    while os.path.exists(path(eid)):
        eid, k = f"{base}-{k}", k + 1
    if from_id and exists(from_id):
        shutil.copytree(path(from_id), path(eid))
        data = load(eid)
        data["name"] = name
    else:
        data = json.loads(json.dumps(DEFAULT))
        data["name"] = name
        data["event_name"] = name
    return save(eid, data)


def delete(eid):
    """Tidak benar-benar dihapus: dipindah ke events/_trash/."""
    if not exists(eid):
        return
    trash = os.path.join(EVENTS_DIR, "_trash")
    os.makedirs(trash, exist_ok=True)
    shutil.move(path(eid), os.path.join(trash, f"{eid}-{int(time.time())}"))
    if get_active() == eid:
        set_active("")


def get_active():
    try:
        eid = open(ACTIVE_FILE, encoding="utf-8").read().strip()
    except OSError:
        return ""
    return eid if exists(eid) else ""


def set_active(eid):
    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        f.write(eid or "")


def new_asset_name(ext):
    return f"{uuid.uuid4().hex[:8]}{ext}"
