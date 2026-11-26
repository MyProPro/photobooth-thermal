"""cloud_sync.py — Manajemen sinkronisasi softcopy untuk AdsBooth:
1. Cloud Storage (Cloudflare R2, AWS S3, Supabase, MinIO compatible)
2. Cloudflare Quick Tunnel (Otomatis online dari laptop tanpa port forwarding)
3. Mode Lokal Wi-Fi (Offline fallback)
"""

import os
import re
import sys
import json
import time
import hmac
import hashlib
import logging
import datetime
import threading
import subprocess
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

log = logging.getLogger("adsbooth.cloud_sync")

# Executor untuk upload background non-blocking
_upload_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="cloud_upload")


# ==============================================================================
# 1. PURE PYTHON S3 / CLOUDFLARE R2 SIGV4 ENGINE
# ==============================================================================

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(key: str, date_stamp: str, region_name: str, service_name: str) -> bytes:
    k_date = _sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region_name)
    k_service = _sign(k_region, service_name)
    k_signing = _sign(k_service, "aws4_request")
    return k_signing


class S3Client:
    """Klien S3 / Cloudflare R2 tanpa dependensi berat boto3."""

    def __init__(self, endpoint_url: str, bucket: str, access_key: str, secret_key: str, region: str = "auto"):
        self.endpoint_url = (endpoint_url or "").rstrip("/")
        self.bucket = (bucket or "").strip()
        self.access_key = (access_key or "").strip()
        self.secret_key = (secret_key or "").strip()
        self.region = (region or "auto").strip()

    def is_configured(self) -> bool:
        return bool(self.endpoint_url and self.bucket and self.access_key and self.secret_key)

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> bool:
        if not self.is_configured():
            return False

        key = key.lstrip("/")
        now = datetime.datetime.now(datetime.timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        # Parse endpoint host & path
        parsed = urllib.parse.urlparse(self.endpoint_url)
        host = parsed.netloc

        # URL path untuk virtual-host style atau path style
        # R2 format: https://<accountid>.r2.cloudflarestorage.com/<bucket>/<key>
        if parsed.path and parsed.path != "/":
            canonical_uri = f"{parsed.path.rstrip('/')}/{self.bucket}/{urllib.parse.quote(key, safe='/~')}"
        else:
            canonical_uri = f"/{self.bucket}/{urllib.parse.quote(key, safe='/~')}"

        request_url = f"{parsed.scheme}://{host}{canonical_uri}"
        payload_hash = hashlib.sha256(data).hexdigest()

        canonical_headers = (
            f"content-type:{content_type}\n"
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
        canonical_request = f"PUT\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

        signing_key = _get_signature_key(self.secret_key, date_stamp, self.region, "s3")
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers = {
            "Content-Type": content_type,
            "Host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization_header,
        }

        try:
            res = requests.put(request_url, data=data, headers=headers, timeout=15)
            if res.status_code in (200, 204):
                return True
            log.warning("S3 upload failed: HTTP %s: %s", res.status_code, res.text[:200])
            return False
        except Exception as e:
            log.error("S3 upload exception for key %s: %s", key, e)
            return False

    def upload_file(self, local_path: str, key: str, content_type: str = None) -> bool:
        if not os.path.exists(local_path):
            return False
        if not content_type:
            ext = os.path.splitext(local_path)[1].lower()
            if ext in (".jpg", ".jpeg"):
                content_type = "image/jpeg"
            elif ext == ".png":
                content_type = "image/png"
            elif ext == ".json":
                content_type = "application/json"
            else:
                content_type = "application/octet-stream"

        with open(local_path, "rb") as f:
            data = f.read()
        return self.upload_bytes(data, key, content_type=content_type)

    def test_connection(self) -> dict:
        """Menguji autentikasi dan izin tulis ke bucket."""
        if not self.is_configured():
            return {"ok": False, "error": "Konfigurasi S3/R2 belum lengkap."}

        test_key = "d/__test_connection__.json"
        test_payload = json.dumps({"test": True, "timestamp": time.time()}).encode("utf-8")
        success = self.upload_bytes(test_payload, test_key, content_type="application/json")
        if success:
            return {"ok": True, "message": "Koneksi ke S3 / Cloudflare R2 berhasil!"}
        return {"ok": False, "error": "Gagal terhubung ke bucket. Periksa Endpoint, Bucket, dan Access Keys."}


# ==============================================================================
# 2. CLOUDFLARE QUICK TUNNEL MANAGER
# ==============================================================================

class TunnelManager:
    """Manajer background process Cloudflare Tunnel (cloudflared)."""

    def __init__(self, bin_dir: str = None):
        self.bin_dir = bin_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
        self.proc = None
        self.public_url = None
        self.is_running = False
        self._lock = threading.Lock()
        self._monitor_thread = None

    def find_cloudflared(self) -> str | None:
        """Mencari lokasi binary cloudflared.exe."""
        exe_name = "cloudflared.exe" if sys.platform == "win32" else "cloudflared"
        # 1. Cek di folder bin/ aplikasi
        local_bin = os.path.join(self.bin_dir, exe_name)
        if os.path.isfile(local_bin):
            return local_bin
        # 2. Cek di root project
        root_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), exe_name)
        if os.path.isfile(root_bin):
            return root_bin
        # 3. Cek di PATH sistem
        import shutil
        return shutil.which(exe_name)

    def is_installed(self) -> bool:
        return bool(self.find_cloudflared())

    def start(self, local_port: int = 5000) -> dict:
        with self._lock:
            if self.is_running and self.public_url:
                return {"ok": True, "url": self.public_url, "already_running": True}

            bin_path = self.find_cloudflared()
            if not bin_path:
                return {
                    "ok": False,
                    "error": "Binary cloudflared tidak ditemukan. Silakan download cloudflared.exe dan simpan di folder bin/."
                }

            self.stop()

            cmd = [
                bin_path,
                "tunnel",
                "--url", f"http://127.0.0.1:{local_port}",
                "--no-autoupdate",
            ]

            try:
                # Sembunyikan jendela console pada Windows
                startupinfo = None
                if sys.platform == "win32":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0

                self.proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    startupinfo=startupinfo
                )
                self.is_running = True
            except Exception as e:
                self.is_running = False
                return {"ok": False, "error": f"Gagal menjalankan cloudflared: {e}"}

            # Pantau output untuk membaca public URL
            found_event = threading.Event()

            def _reader():
                url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
                for line in iter(self.proc.stdout.readline, ""):
                    if not line:
                        break
                    match = url_pattern.search(line)
                    if match:
                        self.public_url = match.group(0).rstrip("/")
                        found_event.set()
                self.is_running = False
                self.public_url = None

            self._monitor_thread = threading.Thread(target=_reader, daemon=True)
            self._monitor_thread.start()

            # Tunggu hingga URL ditemukan (maksimal 12 detik)
            if found_event.wait(timeout=12):
                return {"ok": True, "url": self.public_url}
            else:
                return {"ok": False, "error": "Batas waktu tunggu koneksi Cloudflare Tunnel habis."}

    def stop(self):
        with self._lock:
            if self.proc:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=2)
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
                self.proc = None
            self.is_running = False
            self.public_url = None

    def get_status(self) -> dict:
        return {
            "installed": self.is_installed(),
            "running": self.is_running and bool(self.public_url),
            "url": self.public_url or "",
        }


# Global Tunnel Manager instance
tunnel = TunnelManager()


# ==============================================================================
# 3. UNIFIED SOFTCOPY SYNC & HELPER FUNCTIONS
# ==============================================================================

def get_softcopy_config(cfg: dict) -> dict:
    """Mengambil konfigurasi softcopy yang tersimpan di config.json."""
    sc = cfg.get("softcopy") or {}
    mode = sc.get("mode") or cfg.get("softcopy_mode") or "local"
    return {
        "mode": mode,  # "local", "tunnel", "cloud"
        "wifi_ssid": sc.get("wifi_ssid") or cfg.get("wifi_ssid") or "",
        "cloud": sc.get("cloud") or {
            "provider": "r2",
            "endpoint_url": "",
            "bucket": "",
            "access_key_id": "",
            "secret_access_key": "",
            "public_url": "",
            "auto_delete_days": 7,
        },
        "tunnel": sc.get("tunnel") or {
            "auto_start": False
        }
    }


def get_s3_client(cfg: dict) -> S3Client:
    sc = get_softcopy_config(cfg)
    cc = sc["cloud"]
    return S3Client(
        endpoint_url=cc.get("endpoint_url", ""),
        bucket=cc.get("bucket", ""),
        access_key=cc.get("access_key_id", ""),
        secret_key=cc.get("secret_access_key", ""),
        region=cc.get("region", "auto"),
    )


def sync_session_async(session_dir: str, sid: str, cfg: dict, ev: dict = None):
    """Menjadwalkan upload file sesi ke cloud storage di thread background."""
    sc = get_softcopy_config(cfg)
    if sc["mode"] != "cloud":
        return

    s3 = get_s3_client(cfg)
    if not s3.is_configured():
        log.warning("Softcopy mode is 'cloud' but S3/R2 is not fully configured.")
        return

    def _worker():
        try:
            if not os.path.isdir(session_dir):
                return

            event_title = (ev.get("event_name") or ev.get("name") or "AdsBooth") if ev else "AdsBooth"
            main_file = "softcopy_color.jpg" if os.path.exists(os.path.join(session_dir, "softcopy_color.jpg")) else (
                "hasil_cetak.jpg" if os.path.exists(os.path.join(session_dir, "hasil_cetak.jpg")) else "struk.png"
            )
            raw_files = sorted(f for f in os.listdir(session_dir) if f.startswith("foto_"))

            # Upload main file
            main_path = os.path.join(session_dir, main_file)
            if os.path.exists(main_path):
                s3.upload_file(main_path, f"d/{sid}/{main_file}")

            # Upload raw files
            for rf in raw_files:
                rf_path = os.path.join(session_dir, rf)
                s3.upload_file(rf_path, f"d/{sid}/{rf}")

            # Upload info metadata (info dan info.json)
            auto_del_min = int((ev or {}).get("download_auto_delete", 3) or 3)
            info_data = json.dumps({
                "ok": True,
                "id": sid,
                "title": event_title,
                "main_file": main_file,
                "raw_files": raw_files,
                "rem_sec": auto_del_min * 60,
                "cloud": True
            }).encode("utf-8")

            s3.upload_bytes(info_data, f"d/{sid}/info", content_type="application/json")
            s3.upload_bytes(info_data, f"d/{sid}/info.json", content_type="application/json")
            log.info("Session %s successfully synced to cloud storage.", sid)
        except Exception as e:
            log.error("Failed to sync session %s to cloud: %s", sid, e)

    _upload_pool.submit(_worker)
