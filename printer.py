"""Pembungkus printer ESC/POS.

Jenis koneksi (config.json -> printer.type):
  file     : tidak mencetak, hanya simpan PNG (untuk tes)
  win32    : printer terpasang di Windows (driver) — termasuk Bluetooth/USB yang sudah ada driver-nya
  usb      : USB langsung (vendor_id / product_id), perlu driver WinUSB/libusb
  network  : printer LAN / Wi-Fi (host, port 9100)
  serial   : COM port — termasuk printer Bluetooth (SPP) yang muncul sebagai COMx
  device   : file perangkat Linux, mis. /dev/usb/lp0 (Raspberry Pi / Linux, printer USB)
  webusb   : printer USB dicolok ke tablet Android (kabel OTG). Server membuat data ESC/POS,
             Chrome di tablet yang mengirimkannya ke printer lewat WebUSB (static/webusb.js).
"""
import json
import os
import socket
import threading
from datetime import datetime

TYPES = ["file", "win32", "usb", "network", "serial", "device", "webusb", "android_usb"]


def is_android():
    """Deteksi apakah berjalan di lingkungan Android (APK Chaquopy)."""
    import sys
    return bool(
        os.environ.get("ADSBOOTH_DATA") or
        os.environ.get("PHOTOBOOTH_DATA") or
        "ANDROID_ROOT" in os.environ or
        "ANDROID_DATA" in os.environ or
        hasattr(sys, "getandroidapilevel") or
        get_android_usb_bridge() is not None
    )


def get_android_usb_bridge():
    """Ambil jembatan Kotlin UsbPrinterBridge saat dijalankan di dalam APK Android."""
    try:
        from java import jclass
        return jclass("id.adsbooth.kiosk.UsbPrinterBridge")
    except Exception:
        return None


class PaperCounter:
    """Hitung panjang kertas terpakai (203 dpi = 8 dot per mm)."""

    def __init__(self, out_dir):
        self.path = os.path.join(out_dir, "paper.json")
        self.lock = threading.Lock()

    def read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"used_mm": 0.0, "prints": 0, "since": datetime.now().strftime("%Y-%m-%d %H:%M")}

    def add(self, height_dots, feed_lines=3):
        with self.lock:
            d = self.read()
            d["used_mm"] = round(d.get("used_mm", 0) + height_dots / 8 + feed_lines * 4 + 8, 1)
            d["prints"] = d.get("prints", 0) + 1
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(d, f)

    def reset(self):
        with self.lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"used_mm": 0.0, "prints": 0, "since": datetime.now().strftime("%Y-%m-%d %H:%M")}, f)


try:
    import numba
    import numpy as np

    @numba.njit(fastmath=True)
    def _atkinson_jit(arr):
        h, w = arr.shape
        out = np.empty((h, w), dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                old = arr[y, x]
                new = 255.0 if old > 128.0 else 0.0
                out[y, x] = 255 if new > 128.0 else 0
                err = (old - new) * 0.125
                if x + 1 < w: arr[y, x + 1] += err
                if x + 2 < w: arr[y, x + 2] += err
                if y + 1 < h:
                    if x - 1 >= 0: arr[y + 1, x - 1] += err
                    arr[y + 1, x] += err
                    if x + 1 < w: arr[y + 1, x + 1] += err
                if y + 2 < h: arr[y + 2, x] += err
        return out
except Exception:
    _atkinson_jit = None


def to_thermal_1bit(img):
    """Konversi gambar ke mode '1' menggunakan Atkinson Studio Clean yang tajam dan bersih untuk printer thermal."""
    if img.mode == "1":
        return img
    from PIL import Image as PImg
    im = img.convert("L")
    if _atkinson_jit is not None:
        try:
            arr = np.array(im, dtype=np.float32)
            out_arr = _atkinson_jit(arr)
            return PImg.fromarray(out_arr, mode="L").convert("1")
        except Exception:
            pass
    return im.convert("1")


class ThermalPrinter:
    def __init__(self, cfg, out_dir="output", counter=None):
        self.out_dir = out_dir
        self.lock = threading.Lock()
        self.counter = counter
        self.configure(cfg)

    def configure(self, cfg):
        self.cfg = dict(cfg or {})
        self.mode = self.cfg.get("type", "file")
        if self.mode == "win32" and is_android():
            self.mode = "webusb"

    def _make(self):
        c = self.cfg
        profile = c.get("profile") or None
        if self.mode == "win32":
            from escpos.printer import Win32Raw
            return Win32Raw(c["name"], profile=profile)
        if self.mode == "usb":
            from escpos.printer import Usb
            kw = {"out_ep": int(str(c["out_ep"]), 16)} if c.get("out_ep") else {}
            return Usb(int(str(c["vendor_id"]), 16), int(str(c["product_id"]), 16), profile=profile, **kw)
        if self.mode == "network":
            from escpos.printer import Network
            return Network(c["host"], port=int(c.get("port", 9100)), timeout=10, profile=profile)
        if self.mode == "device":
            from escpos.printer import File
            return File(c.get("device_path") or "/dev/usb/lp0", profile=profile)
        if self.mode == "serial":
            from escpos.printer import Serial
            return Serial(c.get("serial_port") or c.get("port"), baudrate=int(c.get("baudrate", 9600)),
                          profile=profile)
        return None

    def status(self):
        if self.mode == "win32" and is_android():
            self.mode = "webusb"
        if self.mode == "file":
            return {"ok": True, "mode": "file", "message": "Mode tes (tanpa printer)"}
        if self.mode in ("webusb", "android_usb"):
            bridge = get_android_usb_bridge()
            if bridge:
                try:
                    st = json.loads(str(bridge.getStatusJson()))
                    return {
                        "ok": bool(st.get("ok")),
                        "mode": self.mode,
                        "connected": bool(st.get("connected")),
                        "has_permission": bool(st.get("has_permission")),
                        "device_name": st.get("device_name", ""),
                        "device_count": st.get("device_count", 0),
                        "message": st.get("message", "Status USB Android")
                    }
                except Exception as e:  # noqa: BLE001
                    return {"ok": False, "mode": self.mode, "message": f"Error status USB Android: {e}"}
            return {"ok": True, "mode": "webusb", "message": "Dicetak lewat Chrome di tablet (USB OTG)"}
        try:
            if self.mode == "win32":
                import win32print
                ok, msg = check_windows_printer_status(win32print, self.cfg.get("name"))
                return {"ok": ok, "mode": "win32", "message": msg}
            if self.mode == "device":
                path = self.cfg.get("device_path") or "/dev/usb/lp0"
                if not os.path.exists(path):
                    return {"ok": False, "mode": "device", "message": f"{path} tidak ada (printer belum dicolok / modul usblp)"}
                if not os.access(path, os.W_OK):
                    return {"ok": False, "mode": "device", "message": f"Tidak ada izin tulis ke {path} (jalankan install-autostart.sh / udev)"}
                return {"ok": True, "mode": "device", "message": "Printer siap"}
            if self.mode == "network":
                host = self.cfg.get("host")
                if not host:
                    return {"ok": False, "mode": "network", "message": "IP printer LAN/Wi-Fi belum diisi"}
                with socket.create_connection((host, int(self.cfg.get("port", 9100))), timeout=3):
                    pass
                return {"ok": True, "mode": "network", "message": f"Printer LAN/Wi-Fi siap ({host}:9100)"}
            with self.lock:
                p = self._make()
                p.open()
                p.close()
            return {"ok": True, "mode": self.mode, "message": "Printer siap"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "mode": self.mode, "message": str(e) or e.__class__.__name__}

    def _escpos_raster_builtin(self, img, copies=1):
        """Generator ESC/POS murni (GS v 0) tanpa dependensi library eksternal.
        Sangat andal untuk Epson TM-T82/TM-T82X/TM-m30 di Android/Linux/Windows."""
        im = to_thermal_1bit(img)
        w, h = im.size
        w_bytes = (w + 7) // 8
        if w % 8 != 0:
            from PIL import Image as PImg
            pad = PImg.new("1", (w_bytes * 8, h), 1)
            pad.paste(im, (0, 0))
            im = pad

        raw = im.tobytes()
        # Invert: di PIL mode 1, 0=hitam 1=putih. Di ESC/POS thermal, bit 1 = bakar dot hitam.
        inv = bytes((~b) & 0xFF for b in raw)
        feed = int(self.cfg.get("feed_lines", 3))
        cut = bool(self.cfg.get("cut", True))
        frag_h = int(self.cfg.get("fragment_height", 256))

        single = bytearray(b"\x1b@")  # ESC @ (init)
        for y in range(0, h, frag_h):
            lines = min(frag_h, h - y)
            start = y * w_bytes
            end = start + lines * w_bytes
            chunk = inv[start:end]
            xL = w_bytes & 0xFF
            xH = (w_bytes >> 8) & 0xFF
            yL = lines & 0xFF
            yH = (lines >> 8) & 0xFF
            single.extend(b"\x1dv0\x00" + bytes([xL, xH, yL, yH]) + chunk)

        if feed > 0:
            single.extend(b"\n" * feed)
        if cut:
            single.extend(b"\x1dV\x41\x03")  # GS V 65 3 (feed & partial cut)

        out = bytearray()
        for _ in range(max(1, copies)):
            out.extend(single)
        return bytes(out)

    def escpos_bytes(self, img, copies=1):
        """Data ESC/POS mentah untuk gambar ini (dipakai mode webusb, android_usb, network)."""
        im = to_thermal_1bit(img)
        try:
            from escpos.printer import Dummy
            p = Dummy(profile=self.cfg.get("profile") or None)
            for _ in range(max(1, copies)):
                p.image(im, impl=self.cfg.get("impl", "bitImageRaster"),
                        fragment_height=int(self.cfg.get("fragment_height", 256)))
                p.text("\n" * int(self.cfg.get("feed_lines", 3)))
                if self.cfg.get("cut", True):
                    p.cut()
            return p.output
        except Exception:
            return self._escpos_raster_builtin(im, copies)

    def print_image(self, img, copies=1, sink=None):
        """img: PIL Image mode '1' atau 'L'. Selalu simpan salinan PNG di output/prints.
        Mode webusb & android_usb: data ESC/POS disalurkan ke USB printer."""
        os.makedirs(os.path.join(self.out_dir, "prints"), exist_ok=True)
        path = os.path.join(self.out_dir, "prints", datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png")
        img.save(path)
        im_print = to_thermal_1bit(img)
        if self.counter:
            for _ in range(max(1, copies)):
                self.counter.add(im_print.height, int(self.cfg.get("feed_lines", 3)))
        if self.mode == "file":
            return path
        if self.mode in ("webusb", "android_usb"):
            data = self.escpos_bytes(im_print, copies)
            bridge = get_android_usb_bridge()
            if bridge:
                import base64
                b64 = base64.b64encode(data).decode("ascii")
                ok = bool(bridge.printBase64(b64))
                if not ok:
                    st_msg = ""
                    try:
                        st_msg = json.loads(str(bridge.getStatusJson())).get("message", "")
                    except Exception:
                        pass
                    raise RuntimeError(f"Gagal mencetak ke USB Android ({st_msg or 'periksa kabel OTG atau izin USB'})")
            elif sink is not None:
                sink.append(data)
            return path
        if self.mode == "network":
            data = self.escpos_bytes(im_print, copies)
            host = self.cfg.get("host")
            port = int(self.cfg.get("port", 9100))
            if not host:
                raise RuntimeError("IP printer LAN/Wi-Fi belum diisi di konfigurasi")
            with socket.create_connection((host, port), timeout=10) as s:
                s.sendall(data)
            return path
        with self.lock:
            p = self._make()
            try:
                for _ in range(max(1, copies)):
                    p.image(im_print, impl=self.cfg.get("impl", "bitImageRaster"),
                            fragment_height=int(self.cfg.get("fragment_height", 256)))
                    p.text("\n" * int(self.cfg.get("feed_lines", 3)))
                    if self.cfg.get("cut", True):
                        p.cut()
            finally:
                try:
                    p.close()
                except Exception:  # noqa: BLE001
                    pass
        return path


# ---------- deteksi perangkat (untuk Studio) ----------

def list_windows_printers_raw(win32print):
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in win32print.EnumPrinters(flags)]


def check_windows_printer_status(win32print, name):
    """Check actual status of Windows printer (online, offline, error, out of paper)."""
    if not name or name not in list_windows_printers_raw(win32print):
        return False, f"Printer '{name}' not found in Windows"
    try:
        h = win32print.OpenPrinter(name)
        try:
            info = win32print.GetPrinter(h, 2)
            st = info.get("Status", 0)
            attr = info.get("Attributes", 0)

            # Windows printer status constant masks
            PRINTER_STATUS_ERROR = 0x00000002
            PRINTER_STATUS_PAPER_JAM = 0x00000008
            PRINTER_STATUS_PAPER_OUT = 0x00000010
            PRINTER_STATUS_PAPER_PROBLEM = 0x00000040
            PRINTER_STATUS_OFFLINE = 0x00000080
            PRINTER_STATUS_DOOR_OPEN = 0x00000400
            PRINTER_STATUS_NOT_AVAILABLE = 0x00001000
            PRINTER_ATTRIBUTE_WORK_OFFLINE = 0x00000400

            if (attr & PRINTER_ATTRIBUTE_WORK_OFFLINE) or (st & PRINTER_STATUS_NOT_AVAILABLE) or (st & PRINTER_STATUS_OFFLINE):
                return False, f"Printer '{name}' is offline or disconnected"
            if st & PRINTER_STATUS_PAPER_OUT:
                return False, f"Printer '{name}' out of paper"
            if st & PRINTER_STATUS_DOOR_OPEN:
                return False, f"Printer '{name}' cover open"
            if st & PRINTER_STATUS_PAPER_JAM:
                return False, f"Printer '{name}' paper jam"
            if st & (PRINTER_STATUS_ERROR | PRINTER_STATUS_PAPER_PROBLEM):
                return False, f"Printer '{name}' error"
            return True, "Printer ready"
        finally:
            win32print.ClosePrinter(h)
    except Exception as e:
        return False, f"Failed to read printer status: {e}"


def discover():
    out = {"windows": [], "serial": [], "usb": [], "devices": [], "notes": [], "android_usb": None}
    bridge = get_android_usb_bridge()
    if bridge:
        try:
            out["android_usb"] = json.loads(str(bridge.getStatusJson()))
        except Exception:
            pass
    import glob
    out["devices"] = sorted(glob.glob("/dev/usb/lp*"))
    try:
        import win32print
        out["windows"] = list_windows_printers_raw(win32print)
    except ImportError:
        out["notes"].append("Daftar printer Windows hanya tersedia di Windows (pywin32).")
    except Exception as e:  # noqa: BLE001
        out["notes"].append(f"Printer Windows: {e}")
    try:
        from serial.tools import list_ports
        out["serial"] = [{"port": p.device, "desc": p.description or ""} for p in list_ports.comports()]
    except ImportError:
        out["notes"].append("Pasang pyserial untuk melihat daftar COM port.")
    try:
        import usb.core
        for d in usb.core.find(find_all=True):
            out["usb"].append({"vendor_id": f"0x{d.idVendor:04x}", "product_id": f"0x{d.idProduct:04x}"})
    except Exception as e:  # noqa: BLE001
        out["notes"].append(f"Daftar USB langsung tidak tersedia ({e.__class__.__name__}). "
                            "Biasanya lebih mudah pakai mode Windows.")
    return out


# ================= printer FOTO (mode cetak 4R berwarna) =================
PHOTO_TYPES = ["file", "windows", "cups", "android"]


class PhotoPrinter:
    """Cetak foto berwarna lewat driver printer biasa.

    type (config.json -> photo_printer.type):
      file    : tidak mencetak, hanya simpan JPG di output/prints (tes)
      windows : printer foto yang terpasang di Windows (Canon Selphy, DNP, Citizen, Epson, dll.)
      cups    : Linux / Raspberry Pi lewat CUPS (perintah `lp`)
    Ukuran kertas 4R diatur di driver printer (Preferences -> 4x6 / 10x15 cm, borderless kalau ada).
    """

    def __init__(self, cfg, out_dir="output"):
        self.out_dir = out_dir
        self.lock = threading.Lock()
        self.configure(cfg)

    def configure(self, cfg):
        self.cfg = dict(cfg or {})
        self.mode = self.cfg.get("type", "file")
        if self.mode == "win32" and is_android():
            self.mode = "webusb"

    def status(self):
        if self.mode == "android":
            return {"ok": True, "mode": "android", "message": "Cetak lewat Android (Mopria/AirPrint/Epson/Canon) di tablet"}
        if self.mode == "file":
            return {"ok": True, "mode": "file", "message": "Mode tes foto (simpan file, tanpa printer)"}
        try:
            if self.mode == "windows":
                import win32print
                ok, msg = check_windows_printer_status(win32print, self.cfg.get("name"))
                return {"ok": ok, "mode": "windows", "message": msg}
            names = list_photo_printers().get(self.mode, [])
            ok = self.cfg.get("name") in names
            return {"ok": ok, "mode": self.mode,
                    "message": "Printer foto siap" if ok else f"Printer '{self.cfg.get('name')}' tidak ditemukan"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "mode": self.mode, "message": str(e) or e.__class__.__name__}

    def print_image(self, img, copies=1, sink=None):
        os.makedirs(os.path.join(self.out_dir, "prints"), exist_ok=True)
        path = os.path.join(self.out_dir, "prints", datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".jpg")
        img.convert("RGB").save(path, quality=95, dpi=(300, 300))
        if self.mode in ("file", "android"):
            return path
        with self.lock:
            for _ in range(max(1, copies)):
                if self.mode == "windows":
                    _print_windows(img, self.cfg.get("name"), bool(self.cfg.get("borderless", True)))
                elif self.mode == "cups":
                    import subprocess
                    cmd = ["lp"] + (["-d", self.cfg["name"]] if self.cfg.get("name") else [])
                    cmd += ["-o", "media=" + (self.cfg.get("media") or "4x6"), "-o", "fit-to-page", path]
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if r.returncode != 0:
                        raise RuntimeError(r.stderr.strip() or "lp gagal")
        return path


def _print_windows(img, name, borderless=True):
    """Gambar ke printer Windows lewat GDI (memakai pengaturan kertas di driver)."""
    import win32print
    import win32ui
    from PIL import ImageWin
    name = name or win32print.GetDefaultPrinter()
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(name)
    try:
        HORZRES, VERTRES, PHYSW, PHYSH, OFFX, OFFY = 8, 10, 110, 111, 112, 113
        if borderless:
            pw, ph = hdc.GetDeviceCaps(PHYSW), hdc.GetDeviceCaps(PHYSH)
            ox, oy = -hdc.GetDeviceCaps(OFFX), -hdc.GetDeviceCaps(OFFY)
        else:
            pw, ph = hdc.GetDeviceCaps(HORZRES), hdc.GetDeviceCaps(VERTRES)
            ox = oy = 0
        im = img.convert("RGB")
        if (im.width > im.height) != (pw > ph):
            im = im.rotate(90, expand=True)
        # isi penuh kertas (cover), potong sedikit kalau rasio beda
        k = max(pw / im.width, ph / im.height)
        w, h = int(im.width * k), int(im.height * k)
        x, y = ox + (pw - w) // 2, oy + (ph - h) // 2
        hdc.StartDoc("AdsBooth")
        hdc.StartPage()
        ImageWin.Dib(im).draw(hdc.GetHandleOutput(), (x, y, x + w, y + h))
        hdc.EndPage()
        hdc.EndDoc()
    finally:
        hdc.DeleteDC()


def list_photo_printers():
    out = {"windows": [], "cups": [], "notes": []}
    try:
        import win32print
        out["windows"] = list_windows_printers_raw(win32print)
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        out["notes"].append(f"Printer Windows: {e}")
    try:
        import shutil
        import subprocess
        if shutil.which("lpstat"):
            r = subprocess.run(["lpstat", "-a"], capture_output=True, text=True, timeout=5)
            out["cups"] = [ln.split()[0] for ln in r.stdout.splitlines() if ln.strip()]
    except Exception as e:  # noqa: BLE001
        out["notes"].append(f"CUPS: {e}")
    return out
