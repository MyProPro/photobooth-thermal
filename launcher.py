"""Titik masuk versi terinstal AdsBooth (adsbooth.exe / /usr/bin/adsbooth).

  adsbooth                 jalankan server + buka kiosk layar penuh (Chrome, atau Edge di Windows)
  adsbooth --studio        jalankan server (kalau belum) + buka Studio di browser biasa
  adsbooth --server        server saja, tanpa browser (Linux: dipakai systemd)
  adsbooth --browser       buka kiosk saja, tunggu server yang sudah jalan (Linux: autostart desktop)
  adsbooth --set-pin 1234  atur ulang PIN Studio
  adsbooth --version

Kalau server sudah jalan (mis. dobel klik ikon), cukup buka browser-nya saja.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

# Tanpa jendela konsol (Windows): stdout/stderr = None -> arahkan ke devnull supaya print/log tidak error
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import paths as P  # noqa: E402
from version import APP_NAME, VERSION  # noqa: E402

HELP = """adsbooth               server + kiosk layar penuh
adsbooth --studio    buka Studio
adsbooth --server    server saja (tanpa browser)
adsbooth --browser   buka kiosk saja (server sudah jalan)
adsbooth --set-pin 1234
adsbooth --version"""

KIOSK_FLAGS = ["--kiosk", "--noerrdialogs", "--disable-infobars", "--disable-session-crashed-bubble",
               "--check-for-update-interval=31536000", "--overscroll-history-navigation=0", "--disable-pinch",
               "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required",
               "--no-first-run", "--no-default-browser-check"]


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
        time.sleep(0.5)
    return False


def find_browser():
    """Chrome dulu (kamera & kiosk paling stabil); Windows: Edge selalu ada sebagai cadangan."""
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
    url = f"http://localhost:{port()}/?kiosk=1"
    exe = find_browser()
    if not exe:
        import webbrowser
        webbrowser.open(url)
        return
    profile = os.path.join(P.DATA, "browser-kiosk")
    args = [exe] + KIOSK_FLAGS + [f"--user-data-dir={profile}"]
    if "msedge" in os.path.basename(exe).lower():
        args += ["--edge-kiosk-type=fullscreen"]
    if os.name != "nt":
        args += ["--password-store=basic"]
        if shutil.which("unclutter"):
            subprocess.Popen(["unclutter", "-idle", "3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen(args + [url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True, start_new_session=(os.name != "nt"))


def open_studio():
    import webbrowser
    webbrowser.open(f"http://localhost:{port()}/studio")


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
