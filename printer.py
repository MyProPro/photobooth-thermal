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

TYPES = ["file", "win32", "usb", "network", "serial", "device", "webusb"]


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


class ThermalPrinter:
    def __init__(self, cfg, out_dir="output", counter=None):
        self.out_dir = out_dir
        self.lock = threading.Lock()
        self.counter = counter
        self.configure(cfg)

    def configure(self, cfg):
        self.cfg = dict(cfg or {})
        self.mode = self.cfg.get("type", "file")

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
        if self.mode == "file":
            return {"ok": True, "mode": "file", "message": "Mode tes (tanpa printer)"}
        if self.mode == "webusb":
            return {"ok": True, "mode": "webusb", "message": "Dicetak lewat Chrome di tablet (USB OTG)"}
        try:
            if self.mode == "win32":
                import win32print
                ok = self.cfg.get("name") in list_windows_printers_raw(win32print)
                return {"ok": ok, "mode": "win32",
                        "message": "Printer siap" if ok else f"Printer '{self.cfg.get('name')}' tidak ditemukan"}
            if self.mode == "device":
                path = self.cfg.get("device_path") or "/dev/usb/lp0"
                if not os.path.exists(path):
                    return {"ok": False, "mode": "device", "message": f"{path} tidak ada (printer belum dicolok / modul usblp)"}
                if not os.access(path, os.W_OK):
                    return {"ok": False, "mode": "device", "message": f"Tidak ada izin tulis ke {path} (jalankan install-autostart.sh / udev)"}
                return {"ok": True, "mode": "device", "message": "Printer siap"}
            if self.mode == "network":
                with socket.create_connection((self.cfg["host"], int(self.cfg.get("port", 9100))), timeout=3):
                    pass
                return {"ok": True, "mode": "network", "message": "Printer siap"}
            with self.lock:
                p = self._make()
                p.open()
                p.close()
            return {"ok": True, "mode": self.mode, "message": "Printer siap"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "mode": self.mode, "message": str(e) or e.__class__.__name__}

    def escpos_bytes(self, img, copies=1):
        """Data ESC/POS mentah untuk gambar ini (dipakai mode webusb)."""
        from escpos.printer import Dummy
        p = Dummy(profile=self.cfg.get("profile") or None)
        for _ in range(max(1, copies)):
            p.image(img, impl=self.cfg.get("impl", "bitImageRaster"),
                    fragment_height=int(self.cfg.get("fragment_height", 256)))
            p.text("\n" * int(self.cfg.get("feed_lines", 3)))
            if self.cfg.get("cut", True):
                p.cut()
        return p.output

    def print_image(self, img, copies=1, sink=None):
        """img: PIL Image mode '1'. Selalu simpan salinan PNG di output/prints.
        Mode webusb: data ESC/POS dimasukkan ke `sink` (list) untuk dikirim browser."""
        os.makedirs(os.path.join(self.out_dir, "prints"), exist_ok=True)
        path = os.path.join(self.out_dir, "prints", datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png")
        img.save(path)
        if self.counter:
            for _ in range(max(1, copies)):
                self.counter.add(img.height, int(self.cfg.get("feed_lines", 3)))
        if self.mode == "file":
            return path
        if self.mode == "webusb":
            if sink is not None:
                sink.append(self.escpos_bytes(img, copies))
            return path
        with self.lock:
            p = self._make()
            try:
                for _ in range(max(1, copies)):
                    p.image(img, impl=self.cfg.get("impl", "bitImageRaster"),
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


def discover():
    out = {"windows": [], "serial": [], "usb": [], "devices": [], "notes": []}
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
