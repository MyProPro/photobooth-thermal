"""Lisensi offline (tahap 1): token bertanda tangan Ed25519, terkunci ke 1 perangkat.

Format token:  AB1.<payload base64url>.<tanda tangan base64url>
payload (JSON): {"v":1, "lic":"L-xxxx", "dev":"AB-XXXX-XXXX-XXXX-XXXX", "plan":"complete",
                 "feat":["thermal","photo","living"], "name":"Nama pelanggan",
                 "iat":1700000000, "exp":1702592000}

- Token dibuat dengan license_admin.py (kunci privat HANYA ada di PC penjual).
- Aplikasi cuma menyimpan kunci publik -> bisa memeriksa, tidak bisa membuat token.
- Tanpa lisensi: masa coba TRIAL_DAYS hari (semua fitur, hasil cetak ada tanda DEMO), lalu terkunci.
- Lisensi habis: masih jalan GRACE_DAYS hari (peringatan di Studio), lalu terkunci.
"""
import base64
import hashlib
import hmac
import json
import os
import platform
import threading
import time
import uuid

import paths as P

# Diisi otomatis oleh:  python license_admin.py init
PUBLIC_KEY = "4VJHiYXiprgtEQJC-__WPr_guzaoXJ40fL-uN-hyEQE"

TRIAL_DAYS = 7
GRACE_DAYS = 3
PREFIX = "AB1"

PLANS = {
    "thermal": {"name": "Receipt Photobooth", "feat": ["thermal"]},
    "photo": {"name": "Foto 4R", "feat": ["photo"]},
    "complete": {"name": "Lengkap", "feat": ["thermal", "photo", "living"]},
}
ALL_FEATURES = ["thermal", "photo", "living"]
FEATURE_NAMES = {"thermal": "Receipt Photobooth", "photo": "Foto 4R", "living": "Living Photo"}

LICENSE_FILE = os.path.join(P.DATA, "license.key")
STATE_FILE = os.path.join(P.DATA, ".license_state")
_LOCK = threading.Lock()
_CACHE = {"t": 0, "status": None}


# ---------------------------------------------------------------- utilitas
def _b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s):
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _state_mirror():
    """Salinan status kedua di luar folder data (supaya masa coba tidak ter-reset hanya dengan hapus folder data)."""
    if os.name == "nt":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, "AdsBoothRT", "rt.dat")
    return os.path.join(os.path.expanduser("~"), ".config", "adsbooth-rt", "rt.dat")


# ---------------------------------------------------------------- ID perangkat
def _machine_source():
    if os.name == "nt":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                               winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0))
            v, _ = winreg.QueryValueEx(k, "MachineGuid")
            if v:
                return "win:" + str(v).lower()
        except OSError:
            pass
    for f in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            v = open(f, encoding="ascii").read().strip()
            if v:
                return "linux:" + v
        except OSError:
            pass
    return "mac:%012x" % uuid.getnode()


_DEVICE = None


def device_id():
    """ID perangkat yang stabil, mis. AB-7KQ2-M9XD-4HTA-PZ3C (dari MachineGuid Windows / machine-id Linux)."""
    global _DEVICE
    if _DEVICE is None:
        h = hashlib.sha256(("photobooth-device:" + _machine_source()).encode()).digest()
        s = base64.b32encode(h).decode()[:16]
        _DEVICE = "AB-" + "-".join(s[i:i + 4] for i in range(0, 16, 4))
    return _DEVICE


# ---------------------------------------------------------------- token
def _verify_sig(payload_b, sig_b):
    if not PUBLIC_KEY:
        raise ValueError("Aplikasi ini belum disiapkan untuk lisensi (kunci publik kosong).")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as e:
        raise ValueError("Modul 'cryptography' belum terpasang (pip install -r requirements.txt).") from e
    key = Ed25519PublicKey.from_public_bytes(_b64d(PUBLIC_KEY))
    try:
        key.verify(sig_b, payload_b)
    except InvalidSignature as e:
        raise ValueError("Kode lisensi tidak sah (tanda tangan salah).") from e


def parse(token):
    """Periksa token. Return payload (dict) atau raise ValueError dengan pesan yang bisa ditampilkan."""
    token = "".join((token or "").split())        # buang spasi/enter dari copy-paste
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise ValueError("Format kode lisensi salah.")
    try:
        payload_b, sig_b = _b64d(parts[1]), _b64d(parts[2])
    except Exception as e:  # noqa: BLE001
        raise ValueError("Format kode lisensi salah.") from e
    _verify_sig(f"{PREFIX}.{parts[1]}".encode(), sig_b)
    data = json.loads(payload_b.decode())
    if data.get("dev") != device_id():
        raise ValueError(f"Lisensi ini untuk perangkat lain ({data.get('dev')}). ID perangkat ini: {device_id()}.")
    plan = data.get("plan")
    feat = data.get("feat") or PLANS.get(plan, {}).get("feat") or []
    data["feat"] = [f for f in feat if f in ALL_FEATURES]
    if not data["feat"]:
        raise ValueError("Lisensi tidak berisi fitur apa pun.")
    return data


# ---------------------------------------------------------------- status masa coba & jam
def _mac(d):
    msg = f"{d.get('trial_start')}|{d.get('last_seen')}|{device_id()}".encode()
    return hmac.new(b"pb-state-v1:" + device_id().encode(), msg, hashlib.sha256).hexdigest()[:24]


def _read_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("mac") == _mac(d):
            return d
        return {"tampered": True}
    except (OSError, ValueError):
        return None


def _write_state(d):
    d = {"trial_start": int(d["trial_start"]), "last_seen": int(d["last_seen"])}
    d["mac"] = _mac(d)
    for path in (STATE_FILE, _state_mirror()):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f)
            os.replace(tmp, path)
        except OSError:
            pass


def _state(now):
    """Gabungkan dua salinan status: mulai coba = paling awal, terakhir terlihat = paling akhir."""
    a, b = _read_state(STATE_FILE), _read_state(_state_mirror())
    good = [x for x in (a, b) if x and not x.get("tampered")]
    tampered = any(x and x.get("tampered") for x in (a, b))
    if good:
        st = {"trial_start": min(x["trial_start"] for x in good), "last_seen": max(x["last_seen"] for x in good)}
    elif tampered:
        st = {"trial_start": 0, "last_seen": int(now)}       # file diutak-atik -> masa coba dianggap habis
    else:
        st = {"trial_start": int(now), "last_seen": int(now)}
    clock_back = now + 6 * 3600 < st["last_seen"]            # jam dimundurkan > 6 jam
    if not clock_back and (now - st["last_seen"] > 600 or not good or len(good) < 2):
        st["last_seen"] = int(max(now, st["last_seen"]))
        _write_state(st)
    return st, clock_back


# ---------------------------------------------------------------- status utama
def _read_token():
    try:
        with open(LICENSE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def status(force=False):
    """Status lisensi (di-cache 30 detik). Kunci penting:
    state: active | grace | trial | expired | trial_over | clock
    ok (boleh cetak), demo (cetak pakai tanda DEMO), feat (fitur yang boleh)."""
    now = time.time()
    with _LOCK:
        if not force and _CACHE["status"] and now - _CACHE["t"] < 30:
            return _CACHE["status"]
        st, clock_back = _state(now)
        s = {"deviceId": device_id(), "trialDays": TRIAL_DAYS, "graceDays": GRACE_DAYS,
             "plans": {k: v["name"] for k, v in PLANS.items()}, "keyReady": bool(PUBLIC_KEY), "error": ""}
        lic = None
        tok = _read_token()
        if tok:
            try:
                lic = parse(tok)
            except ValueError as e:
                s["error"] = str(e)
        if clock_back:
            s.update(state="clock", ok=False, demo=False, feat=[],
                     message="Jam perangkat mundur. Perbaiki tanggal & jam sistem, lalu muat ulang.")
        elif lic:
            exp = int(lic.get("exp") or 0)
            s.update(plan=lic.get("plan"), planName=PLANS.get(lic.get("plan"), {}).get("name", lic.get("plan")),
                     customer=lic.get("name", ""), licenseId=lic.get("lic", ""), expires=exp,
                     feat=lic["feat"], daysLeft=int((exp - now) // 86400) if exp else None)
            if not exp or now <= exp:
                s.update(state="active", ok=True, demo=False, message="")
            elif now <= exp + GRACE_DAYS * 86400:
                left = int((exp + GRACE_DAYS * 86400 - now) // 86400) + 1
                s.update(state="grace", ok=True, demo=False,
                         message=f"Lisensi sudah habis. Masih bisa dipakai {left} hari lagi, segera perpanjang.")
            else:
                s.update(state="expired", ok=False, demo=False, message="Lisensi sudah habis. Perpanjang untuk mencetak lagi.")
        else:
            end = st["trial_start"] + TRIAL_DAYS * 86400
            left = max(0, int((end - now + 86399) // 86400))
            s.update(trialEnds=end, trialDaysLeft=left, feat=list(ALL_FEATURES))
            if now <= end:
                s.update(state="trial", ok=True, demo=True,
                         message=f"Versi coba: sisa {left} hari. Hasil cetak diberi tanda DEMO.")
            else:
                s.update(state="trial_over", ok=False, demo=False, feat=[],
                         message="Masa coba sudah habis. Masukkan kode lisensi untuk mencetak.")
        s["stamp"] = hashlib.sha1(f"{s['state']}|{','.join(s['feat'])}|{s.get('expires')}".encode()).hexdigest()[:8]
        _CACHE.update(t=now, status=s)
        return s


def has(feature):
    s = status()
    return s["ok"] and feature in s["feat"]


def install(token):
    """Simpan token baru (setelah diperiksa). Return status baru atau raise ValueError."""
    data = parse(token)
    exp = int(data.get("exp") or 0)
    if exp and time.time() > exp + GRACE_DAYS * 86400:
        raise ValueError("Kode lisensi ini sudah kedaluwarsa. Minta kode perpanjangan ke penjual.")
    now = time.time()
    iat = int(data.get("iat") or 0)
    if iat and now - 2 * 86400 <= iat <= now + 86400:
        # kode baru diterbitkan = bukti jam sekarang benar -> pulihkan status "jam mundur"
        # (mis. jam PC pernah lompat ke depan karena baterai CMOS lalu dibetulkan)
        with _LOCK:
            st, back = _state(now)
            if back:
                st["last_seen"] = int(now)
                _write_state(st)
    os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        f.write("".join(token.split()))
    status(force=True)
    return data


def remove():
    try:
        os.remove(LICENSE_FILE)
    except OSError:
        pass
    return status(force=True)


def public_summary():
    """Ringkasan untuk kiosk (tanpa data pelanggan)."""
    s = status()
    return {"state": s["state"], "ok": s["ok"], "demo": s["demo"], "feat": s["feat"],
            "message": s.get("message", ""), "deviceId": s["deviceId"], "stamp": s["stamp"]}


# ---------------------------------------------------------------- tanda DEMO di hasil cetak
def watermark(img):
    """Tanda pita DEMO di bagian bawah template (isi template tetap bersih & terlihat jelas)."""
    from PIL import Image, ImageDraw
    import templates as T
    mode = img.mode
    W, H = img.size
    band = max(44, int(W * 0.08))

    if mode in ("1", "L"):
        ext = Image.new("L", (W, H + band), 255)
        ext.paste(img.convert("L"), (0, 0))
        d = ImageDraw.Draw(ext)
        d.rectangle((0, H, W, H + band), fill=0)
        fb = T.F("monob", max(16, int(band * 0.42)))
        msg = "ADSBOOTH DEMO"
        tw = d.textlength(msg, font=fb)
        bb = fb.getbbox(msg)
        th = bb[3] - bb[1]
        d.text(((W - tw) / 2, H + (band - th) / 2 - bb[1]), msg, font=fb, fill=255)
        return ext.convert(mode)
    else:
        ext = Image.new("RGB", (W, H + band), (255, 255, 255))
        ext.paste(img.convert("RGB"), (0, 0))
        d = ImageDraw.Draw(ext)
        d.rectangle((0, H, W, H + band), fill=(0, 0, 0))
        fb = T.F("monob", max(16, int(band * 0.42)))
        msg = "ADSBOOTH DEMO"
        tw = d.textlength(msg, font=fb)
        bb = fb.getbbox(msg)
        th = bb[3] - bb[1]
        d.text(((W - tw) / 2, H + (band - th) / 2 - bb[1]), msg, font=fb, fill=(255, 255, 255))
        return ext.convert(mode) if mode != "RGB" else ext


def powered_by(img):
    """Tanda branding 'powered by adsbooth' kecil di kanan bawah untuk versi berlisensi."""
    from PIL import Image, ImageDraw
    import templates as T
    mode = img.mode
    W, H = img.size
    msg = "powered by adsbooth"
    if mode in ("1", "L"):
        pad = 24
        ext = Image.new("L", (W, H + pad), 255)
        ext.paste(img.convert("L"), (0, 0))
        d = ImageDraw.Draw(ext)
        f = T.F("sans", 13)
        tw = d.textlength(msg, font=f)
        bb = f.getbbox(msg)
        th = bb[3] - bb[1]
        d.text((W - tw - 16, H + (pad - th) // 2 - bb[1]), msg, font=f, fill=0)
        return ext.convert(mode)
    else:
        out = img.copy()
        d = ImageDraw.Draw(out)
        f = T.F("sans", max(14, int(W * 0.016)))
        tw = d.textlength(msg, font=f)
        bb = f.getbbox(msg)
        th = bb[3] - bb[1]
        x = W - tw - int(W * 0.025)
        y = H - th - int(W * 0.02)
        for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            d.text((x + ox, y + oy), msg, font=f, fill=(255, 255, 255))
        d.text((x, y), msg, font=f, fill=(80, 80, 80))
        return out
