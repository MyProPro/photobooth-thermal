"""Entry Python untuk APK AdsBooth.

Milestone 1 (sekarang): server bukti-konsep Flask + halaman tes kamera.
Tujuannya memastikan Chaquopy + Flask + WebView + kamera benar-benar jalan
di tablet. BELUM memakai app.py AdsBooth penuh dan belum mencetak.

Milestone 1b nanti: ganti isi start_server() supaya menjalankan app.py asli
(set ADSBOOTH_DATA = data_dir, salin static/fonts ke data_dir, lalu
jalankan waitress serve(app)).
"""
import os

_started = False

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<style>
 html,body{margin:0;height:100%;background:#121212;color:#fff;font-family:sans-serif;text-align:center}
 h2{padding:14px 0 6px;margin:0;font-weight:700}
 video{width:100%;max-height:70vh;object-fit:cover;background:#000}
 #s{padding:12px;font-size:15px}
</style></head><body>
 <h2>AdsBooth - tes kamera</h2>
 <video id="v" autoplay playsinline muted></video>
 <p id="s">Meminta izin kamera...</p>
 <script>
  navigator.mediaDevices.getUserMedia({video:{facingMode:"user"},audio:false})
   .then(function(st){document.getElementById("v").srcObject=st;
     document.getElementById("s").textContent="Kamera jalan (OK)";})
   .catch(function(e){document.getElementById("s").textContent="Kamera gagal: "+e;});
 </script>
</body></html>"""


def start_server(data_dir):
    global _started
    if _started:
        return
    _started = True

    # Semua data AdsBooth (config, foto, dll.) nanti disimpan di folder privat aplikasi.
    os.environ.setdefault("ADSBOOTH_DATA", data_dir)

    from flask import Flask
    app = Flask(__name__)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/")
    def index():
        return PAGE

    from waitress import serve
    serve(app, host="127.0.0.1", port=5000, threads=4)
