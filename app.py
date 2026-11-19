"""Thermal Photobooth 80mm — server Flask.

Jalankan:  python app.py
  Kiosk  : http://localhost:5000
  Studio : http://localhost:5000/studio   (kelola event & template)
"""
import base64
import functools
import io
import json
import os
import socket
import threading
import time
import uuid

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from PIL import Image

import events as EV
import templates as TPL
from imaging import LAYOUTS, append_extras, compose_receipt, host_copy, stylize_sample
from printer import TYPES as PRINTER_TYPES, PaperCounter, ThermalPrinter, discover as discover_printers
from samples import _illustration, sample_photos

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "output")
os.makedirs(os.path.join(OUT, "sessions"), exist_ok=True)


def load_config():
    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
        return json.load(f)


CFG = load_config()
PAPER = PaperCounter(OUT)
PRINTER = ThermalPrinter(CFG.get("printer", {}), OUT, counter=PAPER)
_counter_lock = threading.Lock()

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024


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


def to_data_url(img, fmt="PNG"):
    buf = io.BytesIO()
    img.save(buf, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


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
    return ev, BASE


def template_list(ev, layout=None):
    """[(id, nama, spec|None)] sesuai pilihan event."""
    allt = [(t[0], t[1], None) for t in TPL.TEMPLATES]
    allt += [("c:" + t["id"], t.get("name", "Custom"), t) for t in ev.get("custom_templates", [])]
    by = {t[0]: t for t in allt}
    ids = ev.get("templates") or [t[0] for t in allt]
    out = [by[i] for i in ids if i in by]
    if layout:
        out = [t for t in out if TPL.supports(t[2], layout, t[0])]
    return out


def render_receipt(photos, p, ev, asset_dir, qr_url=None, number=None, spec_override=None, ph_cache=None):
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
        event_name=ev.get("event_name") or "NAMA EVENT",
        logo_path=os.path.join(asset_dir, logo) if logo else None,
        qr_url=qr_url,
        number=number,
        width=int(CFG.get("paper_px", 576)),
        brightness=float(CFG.get("brightness", 1.0)),
        footer=ev.get("footer", "TERIMA KASIH"),
        template=p.get("template") or ev.get("default_template", "klasik"),
        custom=custom,
        asset_dir=asset_dir,
        social=ev.get("social"),
        opts=template_opts(ev, p),
        ph_cache=ph_cache,
    )


def cert_titles(ev):
    t = ev.get("cert_titles")
    return [x for x in (t if isinstance(t, list) else []) if x.strip()] or TPL.GELAR


def template_opts(ev, p):
    b = ev.get("boarding") or {}
    return {"cert_titles": cert_titles(ev), "cert_title": (p.get("certTitle") or "")[:80],
            "board_from_code": b.get("from_code"), "board_from": b.get("from"),
            "board_to_code": b.get("to_code"), "board_to": b.get("to")}


POSES = [
    "Pura-pura kaget", "Gaya boyband / girlband", "Semua lihat ke kiri", "Muka paling serius",
    "Peluk teman di sebelah", "Pose superhero", "Ketawa paling lebar", "Pura-pura jadi patung",
    "Tunjuk kamera bareng-bareng", "Gaya model majalah", "Muka ngantuk", "Pose love dengan tangan",
    "Lompat (kalau berani)", "Pura-pura bisik-bisik", "Gaya foto KTP", "Salam metal",
    "Pose dadah ke kamera", "Pura-pura nangis bahagia",
]


def features(ev):
    f = ev.get("features") or {}
    return {k: bool(f.get(k)) for k in ("guestbook", "lucky_draw", "pose_challenge", "host_copy")}


def extras_from_payload(p, ev, lucky=None):
    ft = features(ev)
    ex = {}
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


def receipt_from_payload(p, qr_url=None, number=None, lucky=None, with_extras=True):
    ev, asset_dir = current_event()
    photos = [decode_image(x) for x in p.get("photos", [])]
    img = render_receipt(photos, p, ev, asset_dir, qr_url, number)
    ex = extras_from_payload(p, ev, lucky) if with_extras else {}
    if ex:
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
        "eventVersion": f"{ev.get('id', '')}:{ev.get('updated', 0)}",
        "eventName": ev.get("event_name") or "NAMA EVENT",
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
        "features": features(ev),
        "printerMode": PRINTER.mode,
        "renderWorkers": int(CFG.get("render_workers", 3)),
        "certTitles": cert_titles(ev),
        "poses": POSES,
        "templates": [{"id": t[0], "name": t[1]} for t in template_list(ev)],
        "defaultTemplate": ev.get("default_template", "klasik"),
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


@app.get("/api/status")
def api_status():
    st = PRINTER.status()
    ev, _ = current_event()
    st["eventVersion"] = f"{ev.get('id', '')}:{ev.get('updated', 0)}"
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
    img = stylize_sample(decode_image(p["photo"]), p.get("style", "dither"),
                         int(CFG.get("paper_px", 576)), float(CFG.get("brightness", 1.0)))
    return jsonify({"image": to_data_url(img)})


@app.post("/api/preview")
def api_preview():
    p = request.get_json(force=True)
    img, _, _ = receipt_from_payload(p, qr_url=preview_qr(), number=None)
    return jsonify({"image": to_data_url(img)})


@app.post("/api/templates")
def api_templates():
    """Render semua template event aktif dengan foto tamu (layar Pilih Template)."""
    p = request.get_json(force=True)
    ev, asset_dir = current_event()
    photos = [decode_image(x) for x in p.get("photos", [])]
    out = []
    for tid, name, _ in template_list(ev, p.get("layout")):
        img = render_receipt(photos, dict(p, template=tid), ev, asset_dir, preview_qr(ev))
        out.append({"id": tid, "name": name, "image": to_data_url(img)})
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
    return jsonify({"id": tid, "image": to_data_url(img)})


@app.post("/api/print")
def api_print():
    p = request.get_json(force=True)
    sid = uuid.uuid4().hex[:10]
    number = next_number()
    ev, _ = current_event()
    ft = features(ev)
    lucky = f"{number:04d}" if ft["lucky_draw"] else None
    qr = f"{base_url()}/d/{sid}" if qr_on(ev) else None
    try:
        img, photos, ex = receipt_from_payload(p, qr_url=qr, number=number, lucky=lucky)
        folder = os.path.join(OUT, "sessions", sid)
        os.makedirs(folder, exist_ok=True)
        for i, ph in enumerate(photos, 1):
            ph.save(os.path.join(folder, f"foto_{i}.jpg"), quality=92)
        img.save(os.path.join(folder, "struk.png"))
        gb = ex.get("guestbook") or {}
        if gb.get("signature") is not None:
            gb["signature"].convert("RGBA").save(os.path.join(folder, "ttd.png"))
        meta = {"id": sid, "event": ev.get("id", ""), "number": number, "time": int(time.time()),
                "template": p.get("template"), "layout": p.get("layout"), "lucky": lucky,
                "poses": ex.get("poses") or [], "caption": p.get("caption", ""),
                "guestbook": {"name": gb.get("name", ""), "message": gb.get("message", ""),
                              "signature": gb.get("signature") is not None} if gb else None}
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        copies = max(1, min(int(p.get("copies", 1)), int(CFG.get("max_copies", 2))))
        jobs = []
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
    path = os.path.join(OUT, "sessions", os.path.basename(sid), "struk.png")
    if not os.path.exists(path):
        abort(404)
    jobs = []
    try:
        PRINTER.print_image(Image.open(path).convert("1"), copies=1, sink=jobs)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "jobs": [base64.b64encode(j).decode() for j in jobs]})


# ---------- Template Studio ----------

def studio_auth(fn):
    @functools.wraps(fn)
    def wrap(*a, **kw):
        pin = str(CFG.get("studio_pin", "") or "")
        if pin and request.headers.get("X-Studio-Pin", request.args.get("pin", "")) != pin:
            return jsonify({"ok": False, "error": "PIN salah"}), 401
        return fn(*a, **kw)
    return wrap


def need_event(eid):
    if not EV.exists(eid):
        abort(404)


@app.get("/studio")
def studio_page():
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
    else:
        im.convert("RGBA").save(EV.path(eid, name))
    return jsonify(resp)


@app.get("/api/studio/events/<eid>/asset/<fname>")
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
    img = render_receipt(sample_photos(9), {"layout": layout, "template": tid,
                                            "caption": p.get("caption", "Happy birthday!"),
                                            "showLogo": True, "style": p.get("style", "dither")},
                         ev, EV.path(eid), preview_qr(ev), number=127, spec_override=spec)
    return jsonify({"image": to_data_url(img), "height": img.height})


# ---------- Studio: printer & koneksi ----------

PRINTER_KEYS = ["type", "name", "vendor_id", "product_id", "out_ep", "host", "port", "serial_port", "baudrate", "device_path",
                "impl", "fragment_height", "feed_lines", "cut", "profile"]


def save_config():
    tmp = os.path.join(BASE, "config.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(CFG, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(BASE, "config.json"))


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
    return jsonify({"ok": True, "saved": os.path.relpath(path, BASE), "image": to_data_url(img),
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
    return jsonify({"ok": True, "winner": win, "left": len(pool) - 1})


@app.delete("/api/studio/events/<eid>/draw")
@studio_auth
def studio_draw_reset(eid):
    need_event(eid)
    with open(_draw_path(eid), "w", encoding="utf-8") as f:
        json.dump({"drawn": []}, f)
    return jsonify({"ok": True})


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
        return "<h2 style='font-family:sans-serif'>Foto tidak ditemukan.</h2>", 404
    ev, _ = current_event()
    title = ev.get("event_name", "")
    files = sorted(f for f in os.listdir(folder) if f.startswith("foto_"))
    items = "".join(
        f"<a href='/d/{sid}/{f}' download><img src='/d/{sid}/{f}' alt='{f}'></a>" for f in files)
    return f"""<!doctype html><html lang="id"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Foto kamu — {title}</title>
<style>body{{margin:0;font-family:system-ui,sans-serif;background:#F2EFE8;color:#121212;padding:20px}}
h1{{font-size:24px}}img{{width:100%;border-radius:12px;margin:0 0 12px;display:block}}
p{{color:#3F3B36}}</style>
<h1>{title} · Photobooth</h1><p>Tekan lama / ketuk foto untuk menyimpan.</p>{items}</html>"""


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

    folder = os.path.join(BASE, "certs")
    os.makedirs(folder, exist_ok=True)
    cert, key, stamp = (os.path.join(folder, n) for n in ("cert.pem", "key.pem", "ip.txt"))
    if os.path.exists(cert) and os.path.exists(key) and os.path.exists(stamp) and open(stamp).read() == ip:
        return cert, key
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Photobooth Lokal")])
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


if __name__ == "__main__":
    from werkzeug.serving import make_server

    port = int(CFG.get("port", 5000))
    ip = lan_ip()
    https = CFG.get("https") or {}
    print("=" * 60)
    print(f" Kiosk  : http://localhost:{port}        Studio: http://localhost:{port}/studio")
    print(f" Jaringan: http://{ip}:{port}")
    if https.get("enabled"):
        hport = int(https.get("port", 5443))
        cert, key = ensure_cert(ip)
        print(f" Tablet (HTTPS, kamera): https://{ip}:{hport}/?kiosk=1")
        srv = make_server("0.0.0.0", hport, app, threaded=True, ssl_context=(cert, key))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f" QR tamu: {base_url()}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, threaded=True)
