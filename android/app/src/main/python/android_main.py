"""Entry Python untuk APK AdsBooth (Tahap 1b).

Menjalankan server AdsBooth yang sesungguhnya (app.py). Jika app.py gagal
di-import/start, server pengganti menampilkan traceback-nya di layar HP,
supaya mudah didiagnosis tanpa perlu adb logcat.

Catatan path:
- BASE (kode, static, fonts) otomatis = folder tempat app.py berada di HP
  (Chaquopy mengekstrak folder python ke penyimpanan, jadi static/ & fonts/
  yang disalin saat build ikut ada di sebelah app.py).
- DATA (config, foto tamu, database) diarahkan ke folder privat aplikasi
  lewat variabel ADSBOOTH_DATA, karena harus bisa ditulisi.
"""
import os
import traceback

_started = False


def _diagnostic_app(err_text):
    """Server kecil yang menampilkan error di layar, dipakai kalau app.py gagal."""
    from flask import Flask
    app = Flask(__name__)
    page = (
        "<!doctype html><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<body style='background:#111;color:#eee;font-family:monospace;margin:0;padding:14px'>"
        "<h3 style='color:#ff6b4a;margin:0 0 10px'>AdsBooth gagal start</h3>"
        "<pre style='white-space:pre-wrap;word-break:break-word;font-size:12px;line-height:1.4'>"
        + (err_text or "") +
        "</pre></body>"
    )

    @app.get("/api/config")
    def _cfg():
        return {"ok": False, "error": "app.py gagal start"}

    @app.route("/", defaults={"p": ""})
    @app.route("/<path:p>")
    def _any(p):
        return page

    return app


def start_server(data_dir):
    global _started
    if _started:
        return
    _started = True

    os.environ["ADSBOOTH_DATA"] = data_dir
    os.environ.setdefault("PHOTOBOOTH_DATA", data_dir)

    try:
        import app as adsbooth
        flask_app = adsbooth.app
    except Exception:
        flask_app = _diagnostic_app(traceback.format_exc())

    from waitress import serve
    serve(flask_app, host="127.0.0.1", port=5000, threads=6)
