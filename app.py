"""AdsBooth (struk thermal 80mm & foto 4R) — server Flask.

Jalankan:  python app.py
  Kiosk  : http://localhost:5000
  Studio : http://localhost:5000/studio   (kelola event & template)
"""
import base64
import functools
import hashlib
import hmac
import io
import json
import logging
import logging.handlers
import os
import secrets
import sys
import random
import socket
import threading
import time
import uuid

from datetime import timedelta

from flask import Flask, abort, jsonify, request, send_file, send_from_directory, session
from PIL import Image

import paths as P
import db as DB
import events as EV
import licensing as LIC
import photo as PH
import templates as TPL
from imaging import LAYOUTS, append_extras, compose_receipt, host_copy, stylize, stylize_sample
from printer import TYPES as PRINTER_TYPES, PaperCounter, ThermalPrinter, discover as discover_printers
from printer import PHOTO_TYPES, PhotoPrinter, list_photo_printers
from samples import _illustration, sample_photos
from version import APP_NAME, LIVING_BASE_URL, VERSION

BASE = P.BASE          # folder program (kode, static, fonts) - boleh ditimpa saat update
DATA = P.DATA          # folder data (config, event, foto, database, log) - tidak tersentuh update
OUT = P.OUT
os.makedirs(os.path.join(OUT, "sessions"), exist_ok=True)


def setup_logging():
    """Log ke layar + file berputar di <data>/logs/photobooth.log (maks 5 x 1 MB)."""
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        return
    root.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(os.path.join(P.LOGS, "photobooth.log"), maxBytes=1_000_000,
                                              backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    logging.getLogger("waitress.queue").setLevel(logging.ERROR)


setup_logging()
log = logging.getLogger("photobooth")


def load_config():
    path = P.CONFIG
    if not os.path.exists(path):  # perangkat baru / instalasi baru: buat dari contoh
        import shutil
        shutil.copyfile(os.path.join(BASE, "config.example.json"), path)
        log.info("config.json dibuat dari config.example.json di %s", DATA)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


CFG = load_config()
PAPER = PaperCounter(OUT)
PRINTER = ThermalPrinter(CFG.get("printer", {}), OUT, counter=PAPER)
PHOTO_PRINTER = PhotoPrinter(CFG.get("photo_printer", {}), OUT)


def is_photo(ev):
    """Event diset 'Foto 4R berwarna' (bukan thermal)."""
    return (ev or {}).get("output") == "photo"


def printer_for(ev):
    return PHOTO_PRINTER if is_photo(ev) else PRINTER
_counter_lock = threading.Lock()

# SQLite: catatan tambahan untuk statistik/ekspor (file tetap sumber utama)
try:
    DB.init()
    threading.Thread(target=DB.backfill, args=(os.path.join(OUT, "sessions"),), daemon=True).start()
except Exception as _e:  # noqa: BLE001
    print("SQLite tidak aktif:", _e)


def db_safe(fn, *a):
    """Database tidak boleh menggagalkan proses cetak."""
    try:
        fn(*a)
    except Exception as e:  # noqa: BLE001
        app.logger.warning("SQLite: %s", e)

app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024


def _secret_key():
    """Kunci sesi Studio, dibuat sekali per perangkat (disimpan di folder data)."""
    try:
        with open(P.SECRET, "rb") as f:
            k = f.read()
        if len(k) >= 32:
            return k
    except OSError:
        pass
    k = secrets.token_bytes(48)
    with open(P.SECRET, "wb") as f:
        f.write(k)
    return k


app.secret_key = _secret_key()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_NAME="pb_studio", PERMANENT_SESSION_LIFETIME=timedelta(hours=12))


# ---------- helper ----------

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def base_url():
    return (CFG.get("public_base_url") or f"http://{lan_ip()}:{CFG.get('port', 5000)}").rstrip("/")


def decode_image(data_url):
    raw = data_url.split(",", 1)[1] if "," in data_url else data_url
    return Image.open(io.BytesIO(base64.b64decode(raw))).convert("RGB")


def preview_url(img):
    """Preview ringan: struk thermal tetap PNG, foto 4R jadi JPEG kecil."""
    if img.mode == "RGB" and img.width >= 1000:
        im = img.copy()
        im.thumbnail((640, 960))
        return to_data_url(im, "JPEG")
    return to_data_url(img)


def to_data_url(img, fmt="PNG"):
    buf = io.BytesIO()
    img.save(buf, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


_LUCKY_LOCK = threading.Lock()
_LUCKY_RES = {}   # nomor undian yang sedang ditampilkan di preview: {"eid:nomor": waktu}


def pick_lucky(ev, prefer=None, reserve=True):
    """Nomor undian ACAK 4 digit (0001-9999), unik per event.
    prefer = nomor yang sudah tampil di preview tamu (dipakai lagi kalau masih kosong)."""
    eid = ev.get("id", "")
    with _LUCKY_LOCK:
        now = time.time()
        for k in [k for k, t in _LUCKY_RES.items() if now - t > 1800]:
            del _LUCKY_RES[k]
        used = {m.get("lucky") for m in sessions(eid) if m.get("lucky")}
        held = {k.split(":", 1)[1] for k in _LUCKY_RES if k.startswith(eid + ":")}
        p = str(prefer or "")
        if p.isdigit() and len(p) == 4 and p != "0000" and p not in used:
            val = p
        else:
            free = [f"{n:04d}" for n in range(1, 10000) if f"{n:04d}" not in used and f"{n:04d}" not in held]
            val = random.choice(free) if free else f"{random.randint(1, 9999):04d}"
        if reserve:
            _LUCKY_RES[f"{eid}:{val}"] = now
        else:
            _LUCKY_RES.pop(f"{eid}:{val}", None)
        return val


def peek_number():
    """Nomor yang AKAN didapat cetakan berikutnya (untuk preview, tidak menaikkan counter)."""
    path = os.path.join(OUT, "counter.txt")
    try:
        return int(open(path).read().strip() or 0) + 1
    except (OSError, ValueError):
        return 1


def next_number():
    path = os.path.join(OUT, "counter.txt")
    with _counter_lock:
        n = 0
        if os.path.exists(path):
            try:
                n = int(open(path).read().strip() or 0)
            except ValueError:
                n = 0
        n += 1
        with open(path, "w") as f:
            f.write(str(n))
    return n


# ---------- event aktif ----------

def current_event():
    """(event dict, folder aset). Tanpa event aktif: pakai config.json."""
    eid = EV.get_active()
    if eid:
        return EV.load(eid), EV.path(eid)
    ev = json.loads(json.dumps(EV.DEFAULT))
    ev.update({"id": "", "name": "(config.json)", "event_name": CFG.get("event_name", "NAMA EVENT"),
               "footer": CFG.get("footer", "TERIMA KASIH"), "logo": CFG.get("logo_path", ""),
               "templates": CFG.get("templates") or [],
               "social": CFG.get("social") or EV.DEFAULT["social"],
               "default_template": CFG.get("default_template", "klasik")})
    return ev, DATA


def template_list(ev, layout=None):
    """[(id, nama, spec|None)] sesuai pilihan event."""
    if is_photo(ev):
        frames = ev.get("photo_frames") or {}
        allp = [(t[0], t[1], None) for t in PH.TEMPLATES]
        by = {t[0]: t for t in allp}
        ids = ev.get("photo_templates") or [t[0] for t in allp]
        out = [by[i] for i in ids if i in by]
        return [t for t in out if t[0] != "bingkai" or (frames.get(layout) if layout else frames)]
    allt = [(t[0], t[1], None) for t in TPL.TEMPLATES]
    allt += [("c:" + t["id"], t.get("name", "Custom"), t) for t in ev.get("custom_templates", [])]
    by = {t[0]: t for t in allt}
    ids = ev.get("templates") or [t[0] for t in allt]
    out = [by[i] for i in ids if i in by]
    if layout:
        out = [t for t in out if TPL.supports(t[2], layout, t[0])]
    return out


def print_lang(ev):
    """Bahasa teks yang tercetak (per event): 'id' atau 'en'."""
    return "en" if str(ev.get("print_lang") or "").lower() == "en" else "id"


def render_receipt(*a, **kw):
    """Render hasil cetak; versi coba (belum berlisensi) diberi tanda DEMO."""
    img = _render_receipt(*a, **kw)
    return LIC.watermark(img) if LIC.status()["demo"] else img


def license_block(ev):
    """None kalau boleh cetak; kalau tidak, pesan alasannya (lisensi habis / paket tidak mencakup mode ini)."""
    s = LIC.status()
    if not s["ok"]:
        return s.get("message") or "Perangkat ini belum berlisensi."
    need = "photo" if is_photo(ev) else "thermal"
    if need not in s["feat"]:
        return ("Paket lisensi tidak mencakup mode foto 4R." if need == "photo"
                else "Paket lisensi tidak mencakup mode struk thermal.")
    return None


def _render_receipt(photos, p, ev, asset_dir, qr_url=None, number=None, spec_override=None, ph_cache=None,
                    lucky=None):
    TPL.set_lang(print_lang(ev))   # dipakai template, blok tambahan & arsip di thread ini
    event_name = p.get("event_name") if p.get("event_name") is not None and str(p.get("event_name")).strip() else (ev.get("event_name") or "NAMA EVENT")
    footer = p.get("footer") if p.get("footer") is not None else ev.get("footer", "TERIMA KASIH")
    brightness = float(p.get("brightness") if p.get("brightness") is not None else CFG.get("brightness", 1.0))
    social = dict(ev.get("social") or {})
    if p.get("social") and isinstance(p["social"], dict):
        social.update(p["social"])
    if p.get("username") is not None:
        social["username"] = p["username"]
    if p.get("website") is not None:
        social["website"] = p["website"]
    if is_photo(ev):
        logo = ev.get("logo")
        style = p.get("style") if p.get("style") in PH.STYLE_IDS else "warna"
        return PH.compose_photo(
            photos, layout=p.get("layout") if p.get("layout") in LAYOUTS else "strip", style=style,
            caption=p.get("caption", ""), show_logo=bool(p.get("showLogo", True)),
            event_name=event_name,
            logo_path=os.path.join(asset_dir, logo) if logo else None, qr_url=qr_url,
            template=p.get("template") or ev.get("photo_default_template", "klasik"), theme=ev.get("theme"),
            lucky=lucky, number=number, frames=ev.get("photo_frames"), asset_dir=asset_dir,
            footer=footer, brightness=brightness)
    layout = p.get("layout") if p.get("layout") in LAYOUTS else "strip"
    custom = {t["id"]: t for t in ev.get("custom_templates", [])}
    if spec_override:
        custom[spec_override["id"]] = spec_override
    logo = ev.get("logo")
    return compose_receipt(
        photos,
        layout=layout,
        style=p.get("style", "dither"),
        caption=p.get("caption", ""),
        show_logo=bool(p.get("showLogo", True)),
        event_name=event_name,
        logo_path=os.path.join(asset_dir, logo) if logo else None,
        qr_url=qr_url,
        number=number,
        width=int(CFG.get("paper_px", 576)),
        brightness=brightness,
        footer=footer,
        template=p.get("template") or ev.get("default_template", "klasik"),
        custom=custom,
        asset_dir=asset_dir,
        social=social,
        opts=template_opts(ev, p),
        ph_cache=ph_cache,
    )


def cert_titles(ev):
    t = ev.get("cert_titles")
    return [x for x in (t if isinstance(t, list) else []) if x.strip()] or TPL.GELAR


def template_opts(ev, p):
    b = ev.get("boarding") or {}
    return {"lang": print_lang(ev), "cert_titles": cert_titles(ev), "cert_title": (p.get("certTitle") or "")[:80],
            "board_from_code": b.get("from_code"), "board_from": b.get("from"),
            "board_to_code": b.get("to_code"), "board_to": b.get("to"),
            "newspaper_name": (p.get("newspaper_name") or p.get("koran_title") or "")[:50]}


POSES = [
    "Act surprised", "Boyband / girlband pose", "Everyone look left", "Most serious face",
    "Hug the person next to you", "Superhero pose", "Biggest laugh", "Freeze like a statue",
    "Everyone point at the camera", "Magazine model pose", "Sleepy face", "Make a heart with your hands",
    "Jump (if you dare)", "Pretend to whisper", "Passport photo face", "Rock on!",
    "Wave at the camera", "Happy tears",
]


def features(ev):
    f = ev.get("features") or {}
    out = {k: bool(f.get(k)) for k in ("guestbook", "lucky_draw", "pose_challenge", "host_copy", "living_photo")}
    if out["living_photo"] and "living" not in LIC.status()["feat"]:
        out["living_photo"] = False          # Living Photo = fitur paket Lengkap / add-on
    return out


LIVING_DEFAULT = LIVING_BASE_URL     # bawaan produk (version.py)


def sign_living_code(code: str) -> str:
    """Tambahkan signature checksum agar kode cetakan resmi AdsBooth tidak bisa dikarang bebas."""
    if not code or code == "preview":
        return code or "preview"
    salt = "adsbooth_living_key_2026"
    h = 0x811c9dc5
    for ch in f"{code}:{salt}":
        h = ((h ^ ord(ch)) * 0x01000193) & 0xFFFFFFFF
    sig = f"{h:08x}"[:6]
    return f"{code}-{sig}"


def living_url(ev, code):
    """Link QR Living Photo: halaman statis (GitHub Pages) + kode unik cetakan di bagian #."""
    base = (ev.get("living_url") or CFG.get("living_base_url") or LIVING_DEFAULT).strip()
    if base.endswith("/index.html"):
        base = base[:-10]
    elif base.endswith("index.html"):
        base = base[:-10]
    if not base.endswith("/") and "#" not in base:
        base += "/"
    signed = sign_living_code(code)
    return f"{base}#{signed}"


def extras_from_payload(p, ev, lucky=None, code=None):
    ft = features(ev)
    ex = {}
    if ft["living_photo"]:
        ex["living"] = living_url(ev, code or "preview")
    if ft["pose_challenge"]:
        ex["poses"] = [str(x)[:60] for x in (p.get("poses") or []) if x]
    if ft["lucky_draw"]:
        ex["lucky"] = lucky or "----"
    gb = p.get("guestbook") or {}
    if ft["guestbook"] and (gb.get("message") or gb.get("signature") or gb.get("name")):
        sig = None
        if gb.get("signature"):
            raw = gb["signature"].split(",", 1)[-1]
            sig = Image.open(io.BytesIO(base64.b64decode(raw)))
        ex["guestbook"] = {"name": (gb.get("name") or "")[:40], "message": (gb.get("message") or "")[:160],
                           "signature": sig}
    return ex


def receipt_from_payload(p, qr_url=None, number=None, lucky=None, with_extras=True, code=None):
    ev, asset_dir = current_event()
    photos = [decode_image(x) for x in p.get("photos", [])]
    if is_photo(ev) and features(ev)["living_photo"]:
        qr_url = living_url(ev, code or "preview")     # foto 4R: QR video di pojok kanan bawah
    img = render_receipt(photos, p, ev, asset_dir, qr_url, number, lucky=lucky)
    ex = extras_from_payload(p, ev, lucky, code) if with_extras else {}
    if ex and not is_photo(ev):   # mode foto: buku tamu tetap tersimpan, tidak ikut dicetak
        img = append_extras(img, ex, int(CFG.get("paper_px", 576)))
    return img, photos, ex


def qr_on(ev):
    """QR unduh: config.json = saklar utama; event bisa mematikan untuk event itu saja."""
    if not CFG.get("qr_download", True):
        return False
    return (ev or {}).get("qr_download", True) is not False


def preview_qr(ev=None):
    if ev is None:
        ev, _ = current_event()
    return base_url() + "/d/preview" if qr_on(ev) else None


# ---------- kiosk ----------

@app.get("/")
def index():
    return send_from_directory(os.path.join(BASE, "static"), "index.html")


@app.get("/api/config")
def api_config():
    ev, _ = current_event()
    layouts = [l for l in ev.get("layouts") or EV.ALL_LAYOUTS if l in LAYOUTS] or ["strip"]
    return jsonify({
        "eventId": ev.get("id", ""),
        "eventVersion": f"{ev.get('id', '')}:{ev.get('updated', 0)}:{LIC.status()['stamp']}",
        "license": dict(LIC.public_summary(), blocked=license_block(ev)),
        "eventName": ev.get("event_name") or "NAMA EVENT",
        "footer": ev.get("footer", "TERIMA KASIH"),
        "social": ev.get("social") or {},
        "brightness": float(CFG.get("brightness", 1.0)),
        "layouts": layouts,
        "defaultLayout": ev.get("default_layout") if ev.get("default_layout") in layouts else layouts[0],
        "maxCopies": int(CFG.get("max_copies", 2)),
        "countdown": int(CFG.get("countdown_seconds", 3)),
        "resetSeconds": int(CFG.get("reset_seconds", 15)),
        "idleSeconds": int(CFG.get("idle_seconds", 90)),
        "mirror": bool(CFG.get("mirror", True)),
        "qr": qr_on(ev),
        "dummyCamera": bool(CFG.get("dummy_camera", False)),
        "cameraFacing": CFG.get("camera_facing", "user"),
        "cameraLabel": CFG.get("camera_label", ""),
        "cameraRes": CFG.get("camera_resolution", "1080"),
        "shotReviewMs": int(CFG.get("shot_review_ms", 1000)),
        "hiresTimeoutMs": int(CFG.get("hires_timeout_ms", 1500)),
        "features": features(ev),
        "printerMode": printer_for(ev).mode,
        "output": "photo" if is_photo(ev) else "thermal",
        "introStyle": ev.get("intro_style") or "auto",
        "version": VERSION,
        "styles": ([{"id": s[0], "name": s[1], "desc": s[2]} for s in PH.STYLES] if is_photo(ev) else None),
        "renderWorkers": int(CFG.get("render_workers", 3)),
        "certTitles": cert_titles(ev),
        "theme": ev.get("theme") or {},
        "poses": POSES,
        "templates": [{"id": t[0], "name": t[1]} for t in template_list(ev)],
        "defaultTemplate": ev.get("photo_default_template", "klasik") if is_photo(ev)
        else ev.get("default_template", "klasik"),
    })


_dummy_cache = {}


@app.get("/api/dummy/<int:i>.jpg")
def api_dummy(i):
    """Foto contoh untuk mode tanpa kamera."""
    i = i % 4
    if i not in _dummy_cache:
        buf = io.BytesIO()
        _illustration(i).save(buf, "JPEG", quality=88)
        _dummy_cache[i] = buf.getvalue()
    return send_file(io.BytesIO(_dummy_cache[i]), mimetype="image/jpeg")


# ---------- layar intro (animasi foto -> dither -> struk) ----------
_intro_cache = {}
INTRO_STYLE = "bw2"   # ganti kalau cara olah gambar intro berubah (supaya browser tidak pakai cache lama)


def intro_sources(ev, asset_dir):
    """Daftar sumber foto intro: foto intro event, kalau tidak ada foto sesi terakhir, kalau tidak ada ilustrasi."""
    src = []
    photos = ev.get("intro_photos") or []
    if isinstance(photos, str):
        photos = [photos] if photos else []
    if not photos and ev.get("intro_photo"):
        photos = [ev["intro_photo"]]
    for f in photos:
        p = os.path.join(asset_dir, os.path.basename(f))
        if f and os.path.exists(p):
            src.append(("file", p))
    if not src:
        for m in sessions(ev.get("id", ""), limit=5):
            if m.get("photos"):
                src.append(("file", os.path.join(OUT, "sessions", m["id"], m["photos"][0])))
    if not src:
        src = [("demo", i) for i in range(4)]
    return src


def _intro_img(src):
    kind, v = src
    if kind == "file":
        return Image.open(v).convert("RGB")
    return _illustration(v)


@app.get("/api/intro")
def api_intro():
    ev, asset_dir = current_event()
    n = len(intro_sources(ev, asset_dir))
    logo = ev.get("logo")
    return jsonify({
        "eventName": ev.get("event_name") or "",
        "logo": f"/api/event-asset/{logo}" if (logo and ev.get("id")) else None,
        "date": time.strftime("%d.%m.%Y"),
        "photos": [{"color": f"/api/intro/{i}.jpg?v={ev.get('updated', 0)}-{INTRO_STYLE}",
                    "dither": f"/api/intro/{i}.png?v={ev.get('updated', 0)}-{INTRO_STYLE}"} for i in range(n)],
    })


@app.get("/api/intro/<int:i>.<ext>")
def api_intro_img(i, ext):
    ev, asset_dir = current_event()
    srcs = intro_sources(ev, asset_dir)
    src = srcs[i % len(srcs)]
    key = (str(src), ext, INTRO_STYLE)
    if key not in _intro_cache:
        img = ImageOps_fit(_intro_img(src), (720, 540))
        buf = io.BytesIO()
        if ext == "png":
            intro_bw(img).save(buf, "PNG")
        else:
            img.save(buf, "JPEG", quality=85)
        if len(_intro_cache) > 40:
            _intro_cache.clear()
        _intro_cache[key] = buf.getvalue()
    resp = send_file(io.BytesIO(_intro_cache[key]), mimetype="image/png" if ext == "png" else "image/jpeg")
    resp.headers["Cache-Control"] = "no-store"
    return resp


def intro_bw(img, w=240):
    """Versi hitam-putih untuk animasi intro: kontras tinggi + titik dither tegas (dibesarkan 3x)."""
    from PIL import ImageEnhance, ImageFilter, ImageOps
    h = int(w * img.height / img.width)
    g = ImageOps.grayscale(img.resize((w, h), Image.LANCZOS))
    g = ImageOps.autocontrast(g, cutoff=3)
    g = ImageEnhance.Brightness(g).enhance(1.04)
    g = ImageEnhance.Contrast(g).enhance(1.25)
    g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
    bw = g.convert("1")
    return bw.resize((w * 2, h * 2), Image.NEAREST)


def ImageOps_fit(img, size):  # noqa: N802
    from PIL import ImageOps
    return ImageOps.fit(ImageOps.exif_transpose(img), size, Image.LANCZOS)


@app.get("/api/status")
def api_status():
    ev, _ = current_event()
    st = printer_for(ev).status()
    st["eventVersion"] = f"{ev.get('id', '')}:{ev.get('updated', 0)}:{LIC.status()['stamp']}"
    st["paper"] = paper_info()
    return jsonify(st)


def paper_info():
    d = PAPER.read()
    roll_mm = float(CFG.get("paper_roll_m", 50)) * 1000
    left = max(0.0, roll_mm - d.get("used_mm", 0))
    warn_mm = float(CFG.get("paper_warn_m", 3)) * 1000
    return {"used_m": round(d.get("used_mm", 0) / 1000, 2), "roll_m": roll_mm / 1000,
            "left_m": round(left / 1000, 2), "prints": d.get("prints", 0), "since": d.get("since"),
            "low": left <= warn_mm, "pct_left": round(100 * left / roll_mm, 1) if roll_mm else 0}


@app.post("/api/stylize")
def api_stylize():
    p = request.get_json(force=True)
    ev, _ = current_event()
    if is_photo(ev):
        im = PH.style_photo(decode_image(p["photo"]), p.get("style", "warna"))
        im.thumbnail((900, 900))
        return jsonify({"image": to_data_url(im, "JPEG")})
    img = stylize_sample(decode_image(p["photo"]), p.get("style", "dither"),
                         int(CFG.get("paper_px", 576)), float(CFG.get("brightness", 1.0)))
    return jsonify({"image": to_data_url(img)})


_STYLE_SAMPLE_CACHE = {}


@app.get("/api/sample-styles")
def api_sample_styles():
    ev, asset_dir = current_event()
    mode = "photo" if is_photo(ev) else "thermal"
    brightness = float(CFG.get("brightness", 1.0))

    # Cek apakah ada foto intro dari event aktif
    intro_files = []
    photos = ev.get("intro_photos") or []
    if isinstance(photos, str):
        photos = [photos] if photos else []
    if not photos and ev.get("intro_photo"):
        photos = [ev["intro_photo"]]
    for f in photos:
        p = os.path.join(asset_dir, os.path.basename(f))
        if f and os.path.exists(p):
            intro_files.append(p)

    sample_param = request.args.get("sample", "random")

    if intro_files:
        # Pakai foto intro yang diupload untuk event aktif
        if sample_param == "random":
            chosen_path = random.choice(intro_files)
        else:
            try:
                idx = int(sample_param) % len(intro_files)
                chosen_path = intro_files[idx]
            except ValueError:
                chosen_path = random.choice(intro_files)
        sample_key = os.path.basename(chosen_path)
        cache_key = (ev.get("id"), sample_key, mode, brightness)
        img_path = chosen_path
    else:
        # Default: fallback ke contoh model cewe / cowo statis
        if sample_param == "random":
            sample_key = random.choice(["cewe", "cowo"])
        elif sample_param in ("cewe", "cowo"):
            sample_key = sample_param
        else:
            sample_key = "cewe"
        cache_key = ("default", sample_key, mode, brightness)
        img_path = os.path.join(BASE, "static", f"sample_{sample_key}.jpg")
        if not os.path.exists(img_path):
            img_path = os.path.join(BASE, "static", "sample_cewe.jpg")

    if cache_key in _STYLE_SAMPLE_CACHE:
        return jsonify(_STYLE_SAMPLE_CACHE[cache_key])

    im = Image.open(img_path).convert("RGB")

    out = {}
    if mode == "photo":
        for sid, _, _ in PH.STYLES:
            styled = PH.style_photo(im, sid)
            styled = ImageOps_fit(styled, (360, 640))
            out[sid] = to_data_url(styled, "JPEG")
    else:
        for sid in ["dither", "halftone", "kontras", "sketsa", "ascii", "mewarnai"]:
            styled = stylize(im, (360, 640), sid, brightness=brightness)
            out[sid] = to_data_url(styled, "PNG")

    data = {"sample": sample_key, "styles": out}
    _STYLE_SAMPLE_CACHE[cache_key] = data
    return jsonify(data)


@app.post("/api/preview")
def api_preview():
    p = request.get_json(force=True)
    ev, _ = current_event()
    n = peek_number()
    lucky = pick_lucky(ev, p.get("lucky")) if features(ev)["lucky_draw"] else None
    img, _, _ = receipt_from_payload(p, qr_url=preview_qr(), number=n, lucky=lucky)
    return jsonify({"image": preview_url(img), "lucky": lucky})


@app.post("/api/templates")
def api_templates():
    """Render semua template event aktif dengan foto tamu (layar Pilih Template)."""
    p = request.get_json(force=True)
    ev, asset_dir = current_event()
    photos = [decode_image(x) for x in p.get("photos", [])]
    out = []
    for tid, name, _ in template_list(ev, p.get("layout")):
        img = render_receipt(photos, dict(p, template=tid), ev, asset_dir, preview_qr(ev))
        out.append({"id": tid, "name": name, "image": preview_url(img)})
    return jsonify({"templates": out})


# --- render template satu per satu (layar Pilih Template muncul bertahap) ---
from collections import OrderedDict  # noqa: E402

_TPL_SESS = OrderedDict()
_TPL_LOCK = threading.Lock()


@app.post("/api/templates/prepare")
def api_templates_prepare():
    """Upload foto sekali, dapat token + daftar template. Lalu render per template via /api/templates/render."""
    p = request.get_json(force=True)
    ev, asset_dir = current_event()
    photos = [decode_image(x) for x in p.get("photos", [])]
    token = uuid.uuid4().hex[:12]
    base = {k: v for k, v in p.items() if k != "photos"}
    with _TPL_LOCK:
        _TPL_SESS[token] = {"p": base, "photos": photos, "ev": ev, "dir": asset_dir, "cache": {}}
        while len(_TPL_SESS) > 6:
            _TPL_SESS.popitem(last=False)
    lst = [{"id": t[0], "name": t[1]} for t in template_list(ev, p.get("layout"))]
    return jsonify({"token": token, "templates": lst})


@app.get("/api/templates/render")
def api_templates_render():
    with _TPL_LOCK:
        s = _TPL_SESS.get(request.args.get("token", ""))
    if not s:
        return jsonify({"ok": False, "error": "token kedaluwarsa"}), 404
    tid = request.args.get("id", "")
    img = render_receipt(s["photos"], dict(s["p"], template=tid), s["ev"], s["dir"], preview_qr(s["ev"]),
                         ph_cache=s["cache"])
    return jsonify({"id": tid, "image": preview_url(img)})


@app.post("/api/print")
def api_print():
    p = request.get_json(force=True)
    ev, _ = current_event()
    blocked = license_block(ev)
    if blocked:
        return jsonify({"ok": False, "error": blocked, "license": True}), 403
    sid = uuid.uuid4().hex[:10]
    number = next_number()
    ft = features(ev)
    lucky = pick_lucky(ev, p.get("lucky"), reserve=False) if ft["lucky_draw"] else None
    qr = f"{base_url()}/d/{sid}" if qr_on(ev) else None
    try:
        img, photos, ex = receipt_from_payload(p, qr_url=qr, number=number, lucky=lucky, code=sid)
        folder = os.path.join(OUT, "sessions", sid)
        os.makedirs(folder, exist_ok=True)
        for i, ph in enumerate(photos, 1):
            ph.save(os.path.join(folder, f"foto_{i}.jpg"), quality=92)
        img.save(os.path.join(folder, "struk.png"))
        if is_photo(ev):
            img.save(os.path.join(folder, "hasil_cetak.jpg"), quality=93)
        gb = ex.get("guestbook") or {}
        if gb.get("signature") is not None:
            gb["signature"].convert("RGBA").save(os.path.join(folder, "ttd.png"))
        meta = {"id": sid, "event": ev.get("id", ""), "number": number, "time": int(time.time()),
                "template": p.get("template"), "layout": p.get("layout"), "lucky": lucky,
                "living": ex.get("living"),
                "poses": ex.get("poses") or [], "caption": p.get("caption", ""),
                "guestbook": {"name": gb.get("name", ""), "message": gb.get("message", ""),
                              "signature": gb.get("signature") is not None} if gb else None}
        copies = max(1, min(int(p.get("copies", 1)), int(CFG.get("max_copies", 2))))
        meta.update({"style": p.get("style", "dither"), "copies": copies, "host_copy": ft["host_copy"]})
        if p.get("event_name"):
            meta["event_name"] = p["event_name"]
        if p.get("footer"):
            meta["footer"] = p["footer"]
        if p.get("brightness"):
            meta["brightness"] = float(p["brightness"])
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        db_safe(DB.add_session, meta)
        jobs = []
        if is_photo(ev):
            PHOTO_PRINTER.print_image(img, copies=copies + (1 if ft["host_copy"] else 0))
        else:
            PRINTER.print_image(img, copies=copies, sink=jobs)
            if ft["host_copy"]:
                PRINTER.print_image(host_copy(img, int(CFG.get("paper_px", 576))), copies=1, sink=jobs)
    except Exception as e:  # noqa: BLE001
        app.logger.exception("print gagal")
        return jsonify({"ok": False, "error": str(e)}), 500

    resp = {"ok": True, "id": sid, "number": number, "lucky": lucky,
            "jobs": [base64.b64encode(j).decode() for j in jobs]}
    if qr:
        import qrcode
        resp["qr"] = to_data_url(qrcode.make(qr, border=2).convert("RGB"))
        resp["url"] = qr
    return jsonify(resp)


@app.post("/api/reprint/<sid>")
def api_reprint(sid):
    if not LIC.status()["ok"]:
        return jsonify({"ok": False, "error": LIC.status().get("message"), "license": True}), 403
    path = os.path.join(OUT, "sessions", os.path.basename(sid), "struk.png")
    if not os.path.exists(path):
        abort(404)
    jobs = []
    try:
        im = Image.open(path)
        if im.mode == "RGB" and im.width >= 1000:      # hasil mode foto 4R
            PHOTO_PRINTER.print_image(im, copies=1)
        else:
            PRINTER.print_image(im.convert("1"), copies=1, sink=jobs)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "jobs": [base64.b64encode(j).decode() for j in jobs]})


# ---------- AdsBooth Studio ----------

# PIN Studio disimpan sebagai hash (PBKDF2), bukan teks biasa.
def hash_pin(pin):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), salt.encode(), 200_000).hex()
    return f"pbkdf2${200_000}${salt}${h}"


def check_pin(pin):
    stored = str(CFG.get("studio_pin_hash") or "")
    try:
        _, it, salt, h = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), salt.encode(), int(it)).hex()
        return hmac.compare_digest(got, h)
    except ValueError:
        return False


def pin_is_set():
    return bool(CFG.get("studio_pin_hash"))


def _migrate_plain_pin():
    """PIN lama di config.json ("studio_pin": "1234") -> diubah jadi hash."""
    old = str(CFG.get("studio_pin") or "")
    if old and not pin_is_set():
        CFG["studio_pin_hash"] = hash_pin(old)
    if "studio_pin" in CFG:
        CFG.pop("studio_pin", None)
        if old:
            save_config()


def is_local_request():
    return (request.remote_addr or "") in ("127.0.0.1", "::1", "::ffff:127.0.0.1")


_FAILS = {}          # ip -> [jumlah gagal, terkunci sampai]
_FAILS_LOCK = threading.Lock()


def _locked(ip):
    with _FAILS_LOCK:
        n, until = _FAILS.get(ip, (0, 0))
        return until > time.time()


def _register_fail(ip):
    with _FAILS_LOCK:
        n, until = _FAILS.get(ip, (0, 0))
        n += 1
        _FAILS[ip] = (0, time.time() + 300) if n >= 5 else (n, until)   # 5x salah = kunci 5 menit
    log.warning("PIN Studio salah dari %s", ip)


def studio_allowed():
    """(boleh, kode_http, pesan)"""
    if CFG.get("studio_local_only") and not is_local_request():
        return False, 403, "Studio hanya bisa dibuka dari perangkat ini (pengaturan keamanan)."
    if not pin_is_set():
        return False, 403, "Buat PIN Studio dulu."
    if session.get("studio") and session.get("pin_ver") == CFG.get("studio_pin_hash", "")[-12:]:
        return True, 200, ""
    hdr = request.headers.get("X-Studio-Pin", "")        # untuk skrip/otomasi
    if hdr and not _locked(request.remote_addr) and check_pin(hdr):
        return True, 200, ""
    return False, 401, "Masukkan PIN Studio."


def studio_auth(fn):
    @functools.wraps(fn)
    def wrap(*a, **kw):
        ok, code, msg = studio_allowed()
        if not ok:
            return jsonify({"ok": False, "error": msg, "needSetup": not pin_is_set(),
                            "localOnly": bool(CFG.get("studio_local_only"))}), code
        return fn(*a, **kw)
    return wrap


@app.get("/api/studio/session")
def studio_session():
    ok, code, msg = studio_allowed()
    return jsonify({"loggedIn": ok, "needSetup": not pin_is_set(), "local": is_local_request(),
                    "localOnly": bool(CFG.get("studio_local_only")), "message": msg, "version": VERSION})


def _login():
    session.permanent = True
    session["studio"] = True
    session["pin_ver"] = CFG.get("studio_pin_hash", "")[-12:]


@app.post("/api/studio/setup-pin")
def studio_setup_pin():
    """PIN pertama: hanya dari perangkat yang menjalankan server."""
    if pin_is_set():
        return jsonify({"ok": False, "error": "PIN sudah dibuat. Masuk dengan PIN."}), 400
    if not is_local_request():
        return jsonify({"ok": False, "error": "PIN pertama hanya bisa dibuat dari perangkat ini (localhost)."}), 403
    pin = str((request.get_json(force=True) or {}).get("pin", ""))
    if not (pin.isdigit() and 4 <= len(pin) <= 12):
        return jsonify({"ok": False, "error": "PIN harus 4-12 angka."}), 400
    CFG["studio_pin_hash"] = hash_pin(pin)
    save_config()
    _login()
    log.info("PIN Studio dibuat")
    return jsonify({"ok": True})


@app.post("/api/studio/login")
def studio_login():
    ip = request.remote_addr or ""
    if CFG.get("studio_local_only") and not is_local_request():
        return jsonify({"ok": False, "error": "Studio hanya bisa dibuka dari perangkat ini."}), 403
    if _locked(ip):
        return jsonify({"ok": False, "error": "Terlalu banyak PIN salah. Coba lagi 5 menit lagi."}), 429
    pin = str((request.get_json(force=True) or {}).get("pin", ""))
    if not pin_is_set() or not check_pin(pin):
        _register_fail(ip)
        return jsonify({"ok": False, "error": "PIN salah."}), 401
    with _FAILS_LOCK:
        _FAILS.pop(ip, None)
    _login()
    return jsonify({"ok": True})


@app.post("/api/studio/logout")
def studio_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/studio/security")
@studio_auth
def studio_security_get():
    return jsonify({"localOnly": bool(CFG.get("studio_local_only"))})


@app.put("/api/studio/security")
@studio_auth
def studio_security_save():
    p = request.get_json(force=True) or {}
    if "localOnly" in p:
        if p["localOnly"] and not is_local_request():
            return jsonify({"ok": False, "error": "Aktifkan dari perangkat ini supaya Anda tidak terkunci."}), 400
        CFG["studio_local_only"] = bool(p["localOnly"])
    if p.get("newPin") is not None:
        if not check_pin(str(p.get("oldPin", ""))):
            return jsonify({"ok": False, "error": "PIN lama salah."}), 400
        pin = str(p["newPin"])
        if not (pin.isdigit() and 4 <= len(pin) <= 12):
            return jsonify({"ok": False, "error": "PIN baru harus 4-12 angka."}), 400
        CFG["studio_pin_hash"] = hash_pin(pin)
        _login()                                    # sesi lain otomatis keluar (pin_ver berubah)
        log.info("PIN Studio diganti")
    save_config()
    return jsonify({"ok": True, "localOnly": bool(CFG.get("studio_local_only"))})


@app.get("/api/studio/about")
@studio_auth
def studio_about():
    import platform
    return jsonify({"app": APP_NAME, "version": VERSION, "dataDir": DATA, "programDir": BASE, "mode": P.MODE,
                    "python": platform.python_version(), "os": f"{platform.system()} {platform.release()}",
                    "server": SERVER_NAME, "livingBaseUrl": CFG.get("living_base_url", ""),
                    "livingDefault": LIVING_DEFAULT})


@app.put("/api/studio/living-url")
@studio_auth
def studio_living_url():
    p = request.get_json(force=True)
    url = (p.get("url") or "").strip()
    if url:
        CFG["living_base_url"] = url
    else:
        CFG.pop("living_base_url", None)
    save_config()
    return jsonify({"ok": True, "livingBaseUrl": CFG.get("living_base_url", ""), "livingDefault": LIVING_DEFAULT})


@app.get("/api/studio/license")
@studio_auth
def studio_license():
    s = dict(LIC.status(force=True))
    ev, _ = current_event()
    s["blocked"] = license_block(ev)
    return jsonify(s)


@app.post("/api/studio/license")
@studio_auth
def studio_license_install():
    token = (request.get_json(force=True) or {}).get("token", "")
    try:
        data = LIC.install(token)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    app.logger.info("lisensi dipasang: %s %s", data.get("lic"), data.get("plan"))
    return jsonify({"ok": True})


@app.delete("/api/studio/license")
@studio_auth
def studio_license_remove():
    LIC.remove()
    app.logger.info("lisensi dihapus dari perangkat")
    return jsonify({"ok": True})


@app.get("/api/studio/log")
@studio_auth
def studio_log():
    path = os.path.join(P.LOGS, "photobooth.log")
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=f"adsbooth-log-{time.strftime('%Y%m%d-%H%M')}.txt",
                     mimetype="text/plain")


def need_event(eid):
    if not EV.exists(eid):
        abort(404)


@app.get("/studio")
def studio_page():
    if CFG.get("studio_local_only") and not is_local_request():
        return ("<h2 style='font-family:sans-serif;padding:40px'>Studio hanya bisa dibuka dari perangkat photobooth ini.</h2>", 403)
    return send_from_directory(os.path.join(BASE, "static"), "studio.html")


@app.get("/api/studio/meta")
@studio_auth
def studio_meta():
    return jsonify({
        "pinRequired": bool(CFG.get("studio_pin")),
        "builtins": [{"id": t[0], "name": t[1]} for t in TPL.TEMPLATES],
        "fonts": TPL.FONT_CHOICES,
        "shapes": list(TPL.SHAPES.keys()),
        "ratios": list(TPL.RATIOS.keys()),
        "layouts": EV.ALL_LAYOUTS,
        "paperPx": int(CFG.get("paper_px", 576)),
        "certTitles": TPL.GELAR,
        "photoTemplates": [{"id": t[0], "name": t[1]} for t in PH.TEMPLATES],
    })


@app.get("/api/studio/events")
@studio_auth
def studio_events():
    return jsonify({"events": EV.list_all(), "active": EV.get_active()})


@app.post("/api/studio/events")
@studio_auth
def studio_create():
    p = request.get_json(force=True)
    name = (p.get("name") or "").strip() or "Event baru"
    return jsonify({"ok": True, "event": EV.create(name, p.get("from"))})


@app.get("/api/studio/events/<eid>")
@studio_auth
def studio_get(eid):
    need_event(eid)
    return jsonify({"event": EV.load(eid)})


@app.put("/api/studio/events/<eid>")
@studio_auth
def studio_save(eid):
    need_event(eid)
    data = request.get_json(force=True)
    return jsonify({"ok": True, "event": EV.save(eid, data)})


@app.delete("/api/studio/events/<eid>")
@studio_auth
def studio_delete(eid):
    need_event(eid)
    EV.delete(eid)
    return jsonify({"ok": True})


@app.post("/api/studio/events/<eid>/activate")
@studio_auth
def studio_activate(eid):
    if eid != "-":
        need_event(eid)
    EV.set_active("" if eid == "-" else eid)
    return jsonify({"ok": True, "active": EV.get_active()})


@app.post("/api/studio/events/<eid>/upload")
@studio_auth
def studio_upload(eid):
    need_event(eid)
    f = request.files.get("file")
    kind = request.form.get("kind", "logo")
    if not f:
        return jsonify({"ok": False, "error": "file kosong"}), 400
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        return jsonify({"ok": False, "error": "harus PNG/JPG"}), 400
    try:
        im = Image.open(f.stream)
        im.load()
    except Exception:  # noqa: BLE001
        return jsonify({"ok": False, "error": "gambar tidak valid"}), 400
    name = EV.new_asset_name(".png")
    resp = {"ok": True, "file": name, "w": im.width, "h": im.height}
    if kind == "frame":
        if im.mode not in ("RGBA", "LA", "P") or "A" not in im.convert("RGBA").getbands():
            return jsonify({"ok": False, "error": "frame harus PNG transparan"}), 400
        fr = im.convert("RGBA")
        slots = TPL.detect_slots(TPL.load_frame_img(fr, int(CFG.get("paper_px", 576))).split()[3])
        resp["slots"] = len(slots)
        if not slots:
            return jsonify({"ok": False, "error": "tidak ada area transparan untuk foto"}), 400
        fr.save(EV.path(eid, name))
    elif kind == "photoframe":
        if "A" not in im.convert("RGBA").getbands() or im.convert("RGBA").split()[3].getextrema()[0] >= 128:
            return jsonify({"ok": False, "error": "bingkai harus PNG dengan area transparan untuk foto"}), 400
        fr = im.convert("RGBA")
        small = fr.resize((600, max(1, fr.height * 600 // fr.width)))
        slots = TPL.detect_slots(small.split()[3])
        resp["slots"] = len(slots)
        if not slots:
            return jsonify({"ok": False, "error": "tidak ada area transparan untuk foto"}), 400
        fr.save(EV.path(eid, name))
    elif kind in ("intro", "bg"):
        name = EV.new_asset_name(".jpg")
        resp["file"] = name
        rgb = im.convert("RGB")
        rgb.thumbnail((1600, 1600))
        rgb.save(EV.path(eid, name), quality=90)
    else:
        im.convert("RGBA").save(EV.path(eid, name))
    return jsonify(resp)


@app.get("/api/event-asset/<fname>")
def event_asset_public(fname):
    """Aset event AKTIF untuk layar kiosk (tanpa PIN). Hanya file yang memang dipakai event (logo dll.)."""
    ev, asset_dir = current_event()
    fname = os.path.basename(fname)
    used = {ev.get("logo"), ev.get("intro_photo"), (ev.get("theme") or {}).get("bg_image")}
    used |= set(ev.get("intro_photos") or [])
    used |= set((ev.get("photo_frames") or {}).values())
    if not ev.get("id") or fname not in used:
        abort(404)
    return send_from_directory(asset_dir, fname)


@app.get("/api/studio/events/<eid>/asset/<fname>")
@studio_auth
def studio_asset(eid, fname):
    need_event(eid)
    return send_from_directory(EV.path(eid), os.path.basename(fname))


@app.post("/api/studio/preview")
@studio_auth
def studio_preview():
    """Preview template memakai data event yang belum disimpan + foto contoh."""
    p = request.get_json(force=True)
    eid = p.get("eventId", "")
    need_event(eid)
    ev = p.get("event") or EV.load(eid)
    layout = p.get("layout") if p.get("layout") in LAYOUTS else "strip"
    spec = p.get("spec")
    tid = p.get("template") or ("c:" + spec["id"] if spec else "klasik")
    ft = features(ev)
    asset_dir = EV.path(eid)
    if is_photo(ev):
        n = {"solo": 1, "duo": 2, "strip": 3, "grid": 4}[layout]
        qr = living_url(ev, "preview") if ft["living_photo"] else preview_qr(ev)
        img = render_receipt(sample_photos(9, ev, asset_dir)[:n], {"layout": layout, "template": tid, "showLogo": True,
                                                     "caption": p.get("caption", "Selamat ya!"), "style": "warna"},
                             ev, asset_dir, qr, number=127, lucky="0127" if ft["lucky_draw"] else None)
        img.thumbnail((800, 1200))
        return jsonify({"image": to_data_url(img, "JPEG"), "height": img.height})
    img = render_receipt(sample_photos(9, ev, asset_dir), {"layout": layout, "template": tid,
                                            "caption": p.get("caption", "Happy birthday!"),
                                            "showLogo": True, "style": p.get("style", "dither")},
                         ev, asset_dir, preview_qr(ev), number=127, spec_override=spec)
    # fitur yang ikut tercetak di bawah struk (contoh): nomor undian & QR video
    ex = {}
    if ft["lucky_draw"]:
        ex["lucky"] = "0127"
    if ft["living_photo"]:
        ex["living"] = living_url(ev, "preview")
    if ex:
        img = append_extras(img, ex, int(CFG.get("paper_px", 576)))
    return jsonify({"image": to_data_url(img), "height": img.height})


# ---------- Studio: printer & koneksi ----------

PRINTER_KEYS = ["type", "name", "vendor_id", "product_id", "out_ep", "host", "port", "serial_port", "baudrate", "device_path",
                "impl", "fragment_height", "feed_lines", "cut", "profile"]


def save_config():
    tmp = P.CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(CFG, f, ensure_ascii=False, indent=2)
    os.replace(tmp, P.CONFIG)


def printer_from_body(p):
    cfg = dict(CFG.get("printer", {}))
    cfg.update({k: v for k, v in (p.get("printer") or {}).items() if k in PRINTER_KEYS})
    return cfg


@app.get("/api/studio/printer")
@studio_auth
def studio_printer_get():
    return jsonify({"printer": CFG.get("printer", {}), "types": PRINTER_TYPES,
                    "paper_px": int(CFG.get("paper_px", 576)), "brightness": float(CFG.get("brightness", 1.0)),
                    "status": PRINTER.status()})


@app.post("/api/studio/printer/discover")
@studio_auth
def studio_printer_discover():
    return jsonify(discover_printers())


@app.post("/api/studio/printer/check")
@studio_auth
def studio_printer_check():
    return jsonify(ThermalPrinter(printer_from_body(request.get_json(force=True)), OUT).status())


@app.post("/api/studio/printer/test")
@studio_auth
def studio_printer_test():
    p = request.get_json(force=True)
    width = int(p.get("paper_px") or CFG.get("paper_px", 576))
    img = TPL.test_receipt(width, printer_from_body(p))
    jobs = []
    try:
        path = ThermalPrinter(printer_from_body(p), OUT).print_image(img, sink=jobs)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e) or e.__class__.__name__}), 500
    return jsonify({"ok": True, "saved": os.path.relpath(path, DATA), "image": to_data_url(img),
                    "jobs": [base64.b64encode(j).decode() for j in jobs]})


@app.put("/api/studio/printer")
@studio_auth
def studio_printer_save():
    p = request.get_json(force=True)
    CFG["printer"] = printer_from_body(p)
    if p.get("paper_px"):
        CFG["paper_px"] = int(p["paper_px"])
    if p.get("brightness"):
        CFG["brightness"] = float(p["brightness"])
    save_config()
    PRINTER.configure(CFG["printer"])
    return jsonify({"ok": True, "status": PRINTER.status()})


@app.get("/api/studio/camera")
@studio_auth
def studio_camera_get():
    return jsonify({"camera": {"label": CFG.get("camera_label", ""), "resolution": CFG.get("camera_resolution", "1080"),
                               "facing": CFG.get("camera_facing", "user"), "mirror": bool(CFG.get("mirror", True)),
                               "review_ms": int(CFG.get("shot_review_ms", 1000)),
                               "hires_timeout_ms": int(CFG.get("hires_timeout_ms", 1500))}})


@app.put("/api/studio/camera")
@studio_auth
def studio_camera_save():
    c = request.get_json(force=True).get("camera") or {}
    CFG["camera_label"] = str(c.get("label", "")).strip()[:80]
    CFG["camera_resolution"] = c.get("resolution") if c.get("resolution") in ("720", "1080", "4k", "1080+4k") else "1080"
    try:
        CFG["shot_review_ms"] = max(0, min(3000, int(c.get("review_ms", 1000))))
        CFG["hires_timeout_ms"] = max(500, min(5000, int(c.get("hires_timeout_ms", 1500))))
    except (TypeError, ValueError):
        pass
    CFG["camera_facing"] = "environment" if c.get("facing") == "environment" else "user"
    CFG["mirror"] = bool(c.get("mirror", True))
    save_config()
    return jsonify({"ok": True})


@app.get("/api/studio/photo-printer")
@studio_auth
def studio_photo_printer_get():
    return jsonify({"printer": CFG.get("photo_printer", {"type": "file"}), "types": PHOTO_TYPES,
                    "status": PHOTO_PRINTER.status(), "found": list_photo_printers()})


@app.put("/api/studio/photo-printer")
@studio_auth
def studio_photo_printer_save():
    p = request.get_json(force=True).get("printer") or {}
    CFG["photo_printer"] = {k: p[k] for k in ("type", "name", "borderless", "media") if k in p}
    save_config()
    PHOTO_PRINTER.configure(CFG["photo_printer"])
    return jsonify({"ok": True, "status": PHOTO_PRINTER.status()})


@app.post("/api/studio/photo-printer/test")
@studio_auth
def studio_photo_printer_test():
    p = request.get_json(force=True).get("printer") or CFG.get("photo_printer", {})
    pr = PhotoPrinter(p, OUT)
    img = PH.test_sheet(p.get("name", ""))
    try:
        path = pr.print_image(img)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e) or e.__class__.__name__}), 500
    small = img.copy()
    small.thumbnail((400, 600))
    return jsonify({"ok": True, "saved": os.path.relpath(path, DATA), "image": to_data_url(small, "JPEG")})


@app.get("/api/studio/connect")
@studio_auth
def studio_connect():
    import qrcode
    ip = lan_ip()
    port = int(CFG.get("port", 5000))
    https = CFG.get("https") or {}
    urls = {"lan_ip": ip, "http": f"http://{ip}:{port}",
            "https": f"https://{ip}:{int(https.get('port', 5443))}" if https.get("enabled") else None}
    kiosk = (urls["https"] or urls["http"]) + "/?kiosk=1"
    urls["kiosk"] = kiosk
    urls["kiosk_qr"] = to_data_url(qrcode.make(kiosk, border=2).convert("RGB"))
    urls["https_enabled"] = bool(https.get("enabled"))
    return jsonify(urls)


@app.put("/api/studio/connect")
@studio_auth
def studio_connect_save():
    p = request.get_json(force=True)
    https = dict(CFG.get("https") or {"enabled": False, "port": 5443})
    https["enabled"] = bool(p.get("https_enabled"))
    CFG["https"] = https
    save_config()
    return jsonify({"ok": True, "restart": True})


# ---------- sesi, buku tamu, undian, slideshow, kertas ----------

def sessions(event_id=None, limit=None):
    """Daftar sesi (terbaru dulu) dari output/sessions/*/meta.json."""
    root = os.path.join(OUT, "sessions")
    out = []
    for sid in os.listdir(root):
        mp = os.path.join(root, sid, "meta.json")
        if not os.path.exists(mp):
            continue
        try:
            with open(mp, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            continue
        if event_id is not None and m.get("event", "") != event_id:
            continue
        m["photos"] = sorted(x for x in os.listdir(os.path.join(root, sid)) if x.startswith("foto_"))
        out.append(m)
    out.sort(key=lambda m: -m.get("time", 0))
    return out[:limit] if limit else out


@app.get("/api/studio/events/<eid>/guestbook")
@studio_auth
def studio_guestbook(eid):
    need_event(eid)
    items = [m for m in sessions(eid) if m.get("guestbook")]
    return jsonify({"items": items, "count": len(items)})


@app.get("/studio/guestbook/<eid>")
@studio_auth
def studio_guestbook_page(eid):
    need_event(eid)
    ev = EV.load(eid)
    items = [m for m in sessions(eid) if m.get("guestbook")]
    items.reverse()
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    cards = []
    for m in items:
        g = m["guestbook"]
        sig = f"<img class='sig' src='/d/{m['id']}/ttd.png' alt=''>" if g.get("signature") else ""
        ph = f"<img class='ph' src='/d/{m['id']}/{m['photos'][0]}' alt=''>" if m["photos"] else ""
        when = time.strftime("%d %b %Y %H:%M", time.localtime(m.get("time", 0)))
        cards.append(f"<div class='card'>{ph}<div><p class='msg'>{esc(g.get('message'))}</p>{sig}"
                     f"<p class='name'>{esc(g.get('name'))}</p><p class='meta'>No. {m.get('number')} · {when}</p></div></div>")
    body = "".join(cards) or "<p>Belum ada ucapan.</p>"
    return f"""<!doctype html><html lang="id"><meta charset="utf-8"><title>Buku Tamu — {esc(ev.get('event_name'))}</title>
<style>body{{font-family:Georgia,serif;margin:30px;color:#121212}}h1{{font-size:30px;margin:0}}.sub{{color:#555;margin:4px 0 24px}}
.card{{display:flex;gap:18px;border-bottom:1px solid #ccc;padding:16px 0;break-inside:avoid}}
.ph{{width:160px;height:120px;object-fit:cover;border-radius:6px}}.msg{{font-size:20px;font-style:italic;margin:0 0 6px}}
.sig{{height:70px}}.name{{font-weight:bold;margin:4px 0}}.meta{{color:#777;font-size:13px;margin:0}}
@media print{{button{{display:none}}}}</style>
<button onclick="print()" style="float:right;padding:8px 14px">Cetak / Simpan PDF</button>
<h1>Buku Tamu</h1><p class="sub">{esc(ev.get('event_name'))} · {len(items)} ucapan</p>{body}</html>"""


def _draw_path(eid):
    os.makedirs(os.path.join(OUT, "draws"), exist_ok=True)
    return os.path.join(OUT, "draws", os.path.basename(eid) + ".json")


def _draw_read(eid):
    try:
        with open(_draw_path(eid), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"drawn": []}


@app.get("/api/studio/events/<eid>/draw")
@studio_auth
def studio_draw_get(eid):
    need_event(eid)
    issued = [m for m in sessions(eid) if m.get("lucky")]
    return jsonify({"issued": len(issued), "drawn": _draw_read(eid)["drawn"]})


@app.post("/api/studio/events/<eid>/draw")
@studio_auth
def studio_draw(eid):
    import random
    need_event(eid)
    data = _draw_read(eid)
    done = {d["lucky"] for d in data["drawn"]}
    pool = [m for m in sessions(eid) if m.get("lucky") and m["lucky"] not in done]
    if not pool:
        return jsonify({"ok": False, "error": "Tidak ada nomor undian tersisa"}), 400
    m = random.SystemRandom().choice(pool)
    win = {"lucky": m["lucky"], "session": m["id"], "photo": f"/d/{m['id']}/{m['photos'][0]}" if m["photos"] else "",
           "time": int(time.time())}
    data["drawn"].append(win)
    with open(_draw_path(eid), "w", encoding="utf-8") as f:
        json.dump(data, f)
    db_safe(DB.add_draw, eid, win["lucky"], win["session"], win["time"])
    return jsonify({"ok": True, "winner": win, "left": len(pool) - 1})


@app.delete("/api/studio/events/<eid>/draw")
@studio_auth
def studio_draw_reset(eid):
    need_event(eid)
    with open(_draw_path(eid), "w", encoding="utf-8") as f:
        json.dump({"drawn": []}, f)
    db_safe(DB.reset_draws, eid)
    return jsonify({"ok": True})


@app.get("/api/studio/events/<eid>/stats")
@studio_auth
def studio_stats(eid):
    need_event(eid)
    names = {t[0]: t[1] for t in TPL.TEMPLATES}
    names.update({"c:" + t["id"]: t.get("name", "Custom") for t in EV.load(eid).get("custom_templates", [])})
    s = DB.stats(eid)
    for r in s["templates"]:
        r["name"] = names.get(r["template"], r["template"] or "-")
    return jsonify(s)


@app.get("/studio/export/<eid>.csv")
@studio_auth
def studio_export(eid):
    import csv
    need_event(eid)
    cols, rows = DB.export_rows(eid)
    buf = io.StringIO()
    buf.write("\ufeff")  # supaya Excel membaca UTF-8
    w = csv.writer(buf)
    w.writerow(cols)
    w.writerows([tuple(r) for r in rows])
    from flask import Response
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=adsbooth-{eid}.csv"})


@app.get("/api/theme-bg/<fname>")
def theme_bg(fname):
    ev, asset_dir = current_event()
    if os.path.basename(fname) != (ev.get("theme") or {}).get("bg_image"):
        abort(404)
    return send_from_directory(asset_dir, os.path.basename(fname))


@app.get("/fonts/<path:fname>")
def fonts_file(fname):
    return send_from_directory(os.path.join(BASE, "fonts"), os.path.basename(fname))


@app.get("/slideshow")
def slideshow_page():
    return send_from_directory(os.path.join(BASE, "static"), "slideshow.html")


@app.get("/api/slideshow")
def api_slideshow():
    ev, _ = current_event()
    items = sessions(ev.get("id", ""), limit=int(request.args.get("limit", 60)))
    return jsonify({"event": ev.get("event_name", ""), "items": [
        {"id": m["id"], "number": m.get("number"), "time": m.get("time"), "caption": m.get("caption", ""),
         "photos": [f"/d/{m['id']}/{x}" for x in m["photos"]], "struk": f"/d/{m['id']}/struk.png"} for m in items]})


@app.get("/api/studio/paper")
@studio_auth
def studio_paper():
    return jsonify(paper_info())


@app.post("/api/studio/paper")
@studio_auth
def studio_paper_set():
    p = request.get_json(force=True)
    if p.get("roll_m"):
        CFG["paper_roll_m"] = float(p["roll_m"])
        save_config()
    if p.get("reset"):
        PAPER.reset()
    return jsonify(paper_info())


# ---------- halaman unduh untuk tamu (dibuka dari QR) ----------

@app.get("/d/<sid>")
def download_page(sid):
    sid = os.path.basename(sid)
    folder = os.path.join(OUT, "sessions", sid)
    if not os.path.isdir(folder):
        return "<h2 style='font-family:sans-serif'>Photo not found.</h2>", 404
    ev, _ = current_event()
    title = ev.get("event_name", "")
    files = sorted(f for f in os.listdir(folder) if f.startswith("foto_"))
    if os.path.exists(os.path.join(folder, "hasil_cetak.jpg")):   # mode foto 4R: hasil cetak di paling atas
        files.insert(0, "hasil_cetak.jpg")
    items = "".join(
        f"<a href='/d/{sid}/{f}' download><img src='/d/{sid}/{f}' alt='{f}'></a>" for f in files)
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your photos — {title}</title>
<style>body{{margin:0;font-family:system-ui,sans-serif;background:#F2EFE8;color:#121212;padding:20px}}
h1{{font-size:24px}}img{{width:100%;border-radius:12px;margin:0 0 12px;display:block}}
p{{color:#3F3B36}}</style>
<h1>{title} · AdsBooth</h1><p>Long-press / tap a photo to save it.</p>{items}</html>"""


@app.get("/d/<sid>/<fname>")
def download_file(sid, fname):
    folder = os.path.join(OUT, "sessions", os.path.basename(sid))
    return send_from_directory(folder, os.path.basename(fname))


def ensure_cert(ip):
    """Sertifikat self-signed (disimpan di certs/) untuk HTTPS di jaringan lokal."""
    import datetime as dt
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    folder = P.CERTS
    os.makedirs(folder, exist_ok=True)
    cert, key, stamp = (os.path.join(folder, n) for n in ("cert.pem", "key.pem", "ip.txt"))
    if os.path.exists(cert) and os.path.exists(key) and os.path.exists(stamp) and open(stamp).read() == ip:
        return cert, key
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AdsBooth Lokal")])
    san = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    try:
        san.append(x509.IPAddress(ipaddress.ip_address(ip)))
    except ValueError:
        pass
    now = dt.datetime.now(dt.timezone.utc)
    c = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1))
         .not_valid_after(now + dt.timedelta(days=3650))
         .add_extension(x509.SubjectAlternativeName(san), critical=False)
         .sign(k, hashes.SHA256()))
    with open(cert, "wb") as f:
        f.write(c.public_bytes(serialization.Encoding.PEM))
    with open(key, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                serialization.NoEncryption()))
    with open(stamp, "w") as f:
        f.write(ip)
    return cert, key


SERVER_NAME = "flask-dev"
_migrate_plain_pin()


def main():
    if "--set-pin" in sys.argv:                     # mis. untuk Raspberry Pi tanpa layar: python app.py --set-pin 1234
        pin = sys.argv[sys.argv.index("--set-pin") + 1] if len(sys.argv) > sys.argv.index("--set-pin") + 1 else ""
        if not (pin.isdigit() and 4 <= len(pin) <= 12):
            print("PIN harus 4-12 angka. Contoh: python app.py --set-pin 1234")
            sys.exit(1)
        CFG["studio_pin_hash"] = hash_pin(pin)
        save_config()
        print("PIN Studio disimpan.")
        return
    global SERVER_NAME
    from werkzeug.serving import make_server

    port = int(CFG.get("port", 5000))
    ip = lan_ip()
    https = CFG.get("https") or {}
    print("=" * 60)
    print(f" {APP_NAME} v{VERSION}")
    print(f" Kiosk  : http://localhost:{port}        Studio: http://localhost:{port}/studio")
    print(f" Jaringan: http://{ip}:{port}")
    print(f" Data   : {DATA}  ({P.MODE})")
    if https.get("enabled"):
        hport = int(https.get("port", 5443))
        cert, key = ensure_cert(ip)
        print(f" Tablet (HTTPS, kamera): https://{ip}:{hport}/?kiosk=1")
        srv = make_server("0.0.0.0", hport, app, threaded=True, ssl_context=(cert, key))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f" QR tamu: {base_url()}")
    if not pin_is_set():
        print(f" PIN Studio belum dibuat: buka http://localhost:{port}/studio di perangkat ini.")
    print("=" * 60)
    log.info("%s v%s mulai (data: %s, mode: %s)", APP_NAME, VERSION, DATA, P.MODE)
    try:
        from waitress import serve
        SERVER_NAME = "waitress"
        serve(app, host="0.0.0.0", port=port, threads=12, channel_timeout=120, ident=None)
    except ImportError:
        log.warning("waitress belum terpasang (pip install waitress) - pakai server bawaan Flask")
        app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()
