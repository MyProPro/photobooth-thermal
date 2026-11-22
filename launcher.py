"""Titik masuk versi terinstal AdsBooth (adsbooth.exe / /usr/bin/adsbooth).

  adsbooth                 jalankan server + buka kiosk layar penuh mandiri (berdiri sendiri)
  adsbooth --studio        jalankan server + buka Studio di jendela aplikasi mandiri (1280x820)
  adsbooth --server        server saja, tanpa browser (Linux: dipakai systemd)
  adsbooth --browser       buka kiosk saja, tunggu server yang sudah jalan (Linux: autostart desktop)
  adsbooth --set-pin 1234  atur ulang PIN Studio
  adsbooth --version

Semua jendela aplikasi menggunakan Chromium App Mode (--app=URL), sehingga berjalan
berdiri sendiri tanpa tab, tanpa address bar, dan tanpa kontrol browser Google Chrome.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

import paths as P
from version import APP_NAME, VERSION

# Logging ke file launcher.log di folder DATA supaya bisa ditelusuri jika ada masalah
try:
    os.makedirs(P.LOGS, exist_ok=True)
    _log_f = open(os.path.join(P.LOGS, "launcher.log"), "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _log_f
    if sys.stderr is None:
        sys.stderr = _log_f
except Exception:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

HELP = """adsbooth             server + kiosk layar penuh (aplikasi mandiri)
adsbooth --studio    buka AdsBooth Studio (jendela aplikasi mandiri)
adsbooth --server    server saja (tanpa antarmuka layar)
adsbooth --browser   buka kiosk saja (server sudah jalan)
adsbooth --set-pin 1234
adsbooth --version"""

COMMON_APP_FLAGS = [
    "--noerrdialogs",
    "--disable-infobars",
    "--disable-session-crashed-bubble",
    "--check-for-update-interval=31536000",
    "--overscroll-history-navigation=0",
    "--disable-pinch",
    "--use-fake-ui-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
    "--no-first-run",
    "--no-default-browser-check",
]


def port():
    try:
        with open(P.CONFIG, encoding="utf-8") as f:
            return int(json.load(f).get("port", 5000))
    except (OSError, ValueError):
        return 5000


def server_up(timeout=1.0):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port()}/api/status", timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def wait_server(seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        if server_up():
            return True
        time.sleep(0.3)
    return False


def find_browser():
    """Cari browser Chromium (Chrome atau Edge di Windows).
    Chrome diprioritaskan karena paling stabil untuk WebRTC kamera dan kiosk tanpa batasan policy.
    Edge digunakan otomatis sebagai cadangan jika Chrome tidak terpasang.
    """
    if os.name == "nt":
        roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        cands = [os.path.join(r, "Google", "Chrome", "Application", "chrome.exe") for r in roots if r]
        cands += [os.path.join(r, "Microsoft", "Edge", "Application", "msedge.exe") for r in roots if r]
        return next((c for c in cands if os.path.exists(c)), None)
    for name in ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium", "microsoft-edge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def open_kiosk():
    """Buka Kiosk dalam mode jendela aplikasi layar penuh berdiri sendiri (--app + fullscreen)."""
    url = f"http://localhost:{port()}/?kiosk=1"
    exe = find_browser()
    if not exe:
        import webbrowser
        webbrowser.open(url)
        return
    profile = os.path.join(P.DATA, "browser-kiosk")
    os.makedirs(profile, exist_ok=True)
    # Catatan: --kiosk dihapus karena pada sebagian konfigurasi Windows menyebabkan Chrome
    # crash diam-diam. Kita pakai --start-fullscreen saja (efek layar penuh tanpa crash).
    args = [
        exe,
        f"--app={url}",
        f"--user-data-dir={profile}",
        "--start-fullscreen",
        "--start-maximized",
    ] + COMMON_APP_FLAGS
    if os.name != "nt":
        args.append("--password-store=basic")
        if shutil.which("unclutter"):
            subprocess.Popen(["unclutter", "-idle", "3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    flags = subprocess.DETACHED_PROCESS if os.name == "nt" else 0
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags, start_new_session=(os.name != "nt"))


def open_studio():
    """Buka Studio dalam jendela aplikasi desktop mandiri ukuran 1280x820 (--app)."""
    url = f"http://localhost:{port()}/studio"
    exe = find_browser()
    if not exe:
        import webbrowser
        webbrowser.open(url)
        return
    profile = os.path.join(P.DATA, "browser-studio")
    os.makedirs(profile, exist_ok=True)
    args = [
        exe,
        f"--app={url}",
        f"--user-data-dir={profile}",
        "--window-size=1280,820",
        "--window-position=center",
    ] + COMMON_APP_FLAGS
    flags = subprocess.DETACHED_PROCESS if os.name == "nt" else 0
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags, start_new_session=(os.name != "nt"))


def run_server():
    import app
    sys.argv = [sys.argv[0]]          # opsi launcher jangan terbaca app.main()
    app.main()


def main():
    args = sys.argv[1:]
    if "--version" in args or "-v" in args:
        print(f"{APP_NAME} {VERSION}")
        return
    if "--set-pin" in args:
        import app
        sys.argv = [sys.argv[0]] + args[args.index("--set-pin"):]
        app.main()
        return
    if "--help" in args or "-h" in args:
        print(HELP)
        return
    if "--browser" in args:                       # server dijalankan terpisah (systemd)
        wait_server(90)
        open_kiosk()
        return
    want = "studio" if "--studio" in args else ("server" if "--server" in args else "kiosk")
    if want != "server" and server_up():
        (open_studio if want == "studio" else open_kiosk)()
        return
    if want != "server":
        def opener():
            if wait_server(90):
                (open_studio if want == "studio" else open_kiosk)()
        threading.Thread(target=opener, daemon=True).start()
    run_server()


if __name__ == "__main__":
    main()
