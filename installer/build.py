"""Buat paket instalasi AdsBooth.

Windows (di PC Windows):   installer\\build-windows.bat
                            -> dist\\AdsBooth-Setup-<versi>.exe   (butuh Inno Setup 6)
Linux   (di PC Ubuntu):     bash installer/build-linux.sh
                            -> dist/adsbooth_<versi>_amd64.deb

Langkah:
  1. Nuitka mengompilasi kode Python jadi program C (folder build/app).
     Kode sumber .py TIDAK ikut dikirim -> jauh lebih sulit dibongkar / diubah.
  2. Folder hasil dibungkus jadi installer (Inno Setup) atau paket .deb.

Opsi:  python installer/build.py [--skip-compile] [--no-package]
"""
import os
import platform
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INST = os.path.join(ROOT, "installer")
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
IS_WIN = os.name == "nt"
EXE = "adsbooth.exe" if IS_WIN else "adsbooth"

sys.path.insert(0, ROOT)
from version import APP_NAME, VERSION  # noqa: E402

# file program yang ikut dikemas (selain kode yang dikompilasi)
DATA_DIRS = ["static", "fonts"]
DATA_FILES = ["config.example.json"]
# modul yang TIDAK boleh ikut ke pelanggan
EXCLUDE = ["license_admin", "pytest", "tkinter", "unittest", "test", "IPython", "matplotlib", "numpy.tests"]


def log(msg):
    print(f"\n=== {msg}", flush=True)


def run(cmd, **kw):
    print("> " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd), flush=True)
    subprocess.check_call(cmd, **kw)


def ensure_icon():
    """Buat ikon sederhana (kamera) kalau belum ada: installer/icon.ico + icon.png."""
    ico, png = os.path.join(INST, "icon.ico"), os.path.join(INST, "icon.png")
    if os.path.exists(ico) and os.path.exists(png):
        return ico, png
    from PIL import Image, ImageDraw
    S = 512
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((16, 16, S - 16, S - 16), radius=110, fill=(18, 18, 18, 255))
    d.rounded_rectangle((96, 170, S - 96, 390), radius=40, fill=(242, 239, 232, 255))
    d.rounded_rectangle((190, 128, 322, 190), radius=20, fill=(242, 239, 232, 255))
    d.ellipse((176, 196, 336, 356), fill=(18, 18, 18, 255))
    d.ellipse((206, 226, 306, 326), fill=(200, 65, 15, 255))
    d.ellipse((350, 196, 380, 226), fill=(200, 65, 15, 255))
    im.save(png)
    im.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico, png


def compile_nuitka(ico):
    log(f"Kompilasi Nuitka ({platform.system()}, Python {platform.python_version()})")
    out = os.path.join(BUILD, "nuitka")
    cmd = [sys.executable, "-m", "nuitka", "--mode=standalone", f"--output-dir={out}",
           f"--output-filename={EXE}", "--assume-yes-for-downloads", "--remove-output",
           "--python-flag=no_docstrings", "--python-flag=-O",
           "--include-module=waitress", "--include-package=waitress",
           "--include-module=werkzeug.serving",
           "--include-module=cryptography.hazmat.primitives.asymmetric.ed25519",
           "--include-package=escpos", "--include-package-data=escpos",
           "--include-package=qrcode"]
    for d in DATA_DIRS:
        cmd.append(f"--include-data-dir={os.path.join(ROOT, d)}={d}")
    for f in DATA_FILES:
        cmd.append(f"--include-data-files={os.path.join(ROOT, f)}={f}")
    for m in EXCLUDE:
        cmd.append(f"--nofollow-import-to={m}")
    if IS_WIN:
        cmd += ["--windows-console-mode=attach", f"--windows-icon-from-ico={ico}",
                f"--company-name={APP_NAME}", f"--product-name={APP_NAME}",
                f"--file-version={VERSION}", f"--product-version={VERSION}",
                f"--file-description={APP_NAME} kiosk"]
    cmd.append(os.path.join(ROOT, "launcher.py"))
    run(cmd, cwd=ROOT)
    src = os.path.join(out, "launcher.dist")
    app_dir = os.path.join(BUILD, "app")
    shutil.rmtree(app_dir, ignore_errors=True)
    shutil.move(src, app_dir)
    # jaga-jaga: pastikan tidak ada kode sumber / alat penjual yang ikut
    for root, _, files in os.walk(app_dir):
        for f in files:
            if f.endswith(".py") or f.startswith("license_admin"):
                os.remove(os.path.join(root, f))
    print(f"Hasil: {app_dir}")
    return app_dir


def find_iscc():
    cands = [shutil.which("ISCC.exe"), shutil.which("iscc")]
    for k in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        r = os.environ.get(k)
        if r:
            cands += [os.path.join(r, "Inno Setup 6", "ISCC.exe"), os.path.join(r, "Programs", "Inno Setup 6", "ISCC.exe")]
    return next((c for c in cands if c and os.path.exists(c)), None)


def package_windows(app_dir):
    log("Membuat installer Windows (Inno Setup)")
    iscc = find_iscc()
    if not iscc:
        sys.exit("Inno Setup 6 belum terpasang. Unduh gratis: https://jrsoftware.org/isdl.php lalu jalankan lagi.")
    os.makedirs(DIST, exist_ok=True)
    run([iscc, f"/DAppVersion={VERSION}", f"/DAppName={APP_NAME}", f"/DSourceDir={app_dir}",
         f"/DOutputDir={DIST}", f"/DIconFile={os.path.join(INST, 'icon.ico')}",
         os.path.join(INST, "adsbooth.iss")])
    print(f"\nSelesai: {os.path.join(DIST, f'AdsBooth-Setup-{VERSION}.exe')}")


def package_deb(app_dir, png):
    log("Membuat paket .deb")
    arch = {"x86_64": "amd64", "aarch64": "arm64", "armv7l": "armhf"}.get(platform.machine(), platform.machine())
    stage = os.path.join(BUILD, "deb")
    shutil.rmtree(stage, ignore_errors=True)
    lin = os.path.join(INST, "linux")

    def put(src, dst, mode=0o644):
        dst = os.path.join(stage, dst.lstrip("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        os.chmod(dst, mode)

    shutil.copytree(app_dir, os.path.join(stage, "opt", "adsbooth"))
    os.chmod(os.path.join(stage, "opt", "adsbooth", EXE), 0o755)
    put(os.path.join(lin, "adsbooth"), "/usr/bin/adsbooth", 0o755)
    put(os.path.join(lin, "adsbooth-setup"), "/usr/bin/adsbooth-setup", 0o755)
    put(os.path.join(lin, "adsbooth@.service"), "/lib/systemd/system/adsbooth@.service")
    put(os.path.join(lin, "99-adsbooth-printer.rules"), "/lib/udev/rules.d/99-adsbooth-printer.rules")
    put(os.path.join(lin, "adsbooth.desktop"), "/usr/share/applications/adsbooth.desktop")
    put(os.path.join(lin, "adsbooth-studio.desktop"), "/usr/share/applications/adsbooth-studio.desktop")
    put(png, "/usr/share/icons/hicolor/256x256/apps/adsbooth.png")
    os.makedirs(os.path.join(stage, "DEBIAN"))
    size_kb = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(stage) for f in fs) // 1024
    ctl = open(os.path.join(lin, "control"), encoding="utf-8").read()
    ctl = ctl.replace("@VERSION@", VERSION).replace("@ARCH@", arch).replace("@SIZE@", str(size_kb))
    with open(os.path.join(stage, "DEBIAN", "control"), "w", encoding="utf-8") as f:
        f.write(ctl)
    for s in ("postinst", "prerm", "postrm"):
        put(os.path.join(lin, s), f"/DEBIAN/{s}", 0o755)
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"adsbooth_{VERSION}_{arch}.deb")
    run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", stage, out])
    print(f"\nSelesai: {out}")


def main():
    if not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
        sys.exit(f"VERSION di version.py harus format 1.2.3 (sekarang: {VERSION})")
    lic = open(os.path.join(ROOT, "licensing.py"), encoding="utf-8").read()
    if re.search(r'^PUBLIC_KEY = ""', lic, re.M):
        sys.exit("PUBLIC_KEY di licensing.py masih kosong. Jalankan dulu: python license_admin.py init")
    ico, png = ensure_icon()
    app_dir = os.path.join(BUILD, "app")
    if "--skip-compile" not in sys.argv or not os.path.exists(app_dir):
        app_dir = compile_nuitka(ico)
    if "--no-package" in sys.argv:
        return
    if IS_WIN:
        package_windows(app_dir)
    else:
        package_deb(app_dir, png)


if __name__ == "__main__":
    main()
