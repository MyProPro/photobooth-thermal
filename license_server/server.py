"""AdsBooth License & Midtrans Payment Server.

Server mandiri untuk menerima pembayaran langganan AdsBooth via Midtrans (QRIS, VA, E-Wallet)
dan menerbitkan token lisensi Ed25519 secara otomatis.
Dapat dijalankan di VPS atau lokal (dengan tunneling ngrok/cloudflared untuk webhook).
"""
import base64
import csv
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import Flask, jsonify, redirect, render_template_string, request
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("license-server")

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
DB_PATH = os.path.join(HERE, "orders.db")

# ---------------------------------------------------------------- Konfigurasi
DEFAULT_CONFIG = {
    "midtrans": {
        "is_production": False,
        "server_key": "YOUR_MIDTRANS_SERVER_KEY",
        "client_key": "YOUR_MIDTRANS_CLIENT_KEY",
    },
    "license": {
        "private_key_path": "",
        "public_key_path": "",
    },
    "pricing": {
        "thermal": {
            "name": "Paket Thermal (80mm)",
            "desc": "Struk receipt photobooth 80mm",
            "prices": {"30": 150000, "365": 1200000},
        },
        "photo": {
            "name": "Paket Foto 4R",
            "desc": "Cetak foto berwarna 4R (10x15 cm)",
            "prices": {"30": 250000, "365": 2000000},
        },
        "complete": {
            "name": "Paket Lengkap (All-in)",
            "desc": "Struk thermal + Foto 4R + Living Photo",
            "prices": {"30": 350000, "365": 2800000},
        },
    },
    "port": 8080,
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
        except Exception as e:
            logger.warning("Gagal membaca config.json, menggunakan default: %s", e)
    return DEFAULT_CONFIG


CONFIG = load_config()

# Helper Kriptografi
PLANS = ("thermal", "photo", "complete")
PLAN_FEAT = {"thermal": ["thermal"], "photo": ["photo"], "complete": ["thermal", "photo", "living"]}


def _b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s):
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def get_private_key():
    """Cari private key dari config, path lokal, atau default %USERPROFILE%\\.adsbooth-license\\private.key"""
    custom = CONFIG.get("license", {}).get("private_key_path")
    candidates = []
    if custom:
        candidates.append(os.path.abspath(os.path.join(HERE, custom)) if not os.path.isabs(custom) else custom)
    candidates.extend([
        os.path.join(HERE, "private.key"),
        os.path.join(os.path.expanduser("~"), ".adsbooth-license", "private.key"),
        os.path.join(os.path.expanduser("~"), ".photobooth-license", "private.key"),
        os.path.join(os.path.dirname(HERE), ".adsbooth-license", "private.key"),
    ])
    for p in candidates:
        if os.path.exists(p):
            try:
                raw_b64 = open(p, "r", encoding="utf-8").read().strip()
                return Ed25519PrivateKey.from_private_bytes(_b64d(raw_b64))
            except Exception as e:
                logger.error("Gagal membaca private key di %s: %s", p, e)
    raise RuntimeError("Private key Ed25519 tidak ditemukan! Pastikan path private.key sudah benar.")


def issue_token(device, plan, name="", days=30, lic_id=None):
    """Buat token lisensi resmi AB1 bertanda tangan Ed25519."""
    dev = device.strip().upper()
    dev = dev[:3] + dev[3:].replace("0", "O").replace("1", "I").replace("8", "B")
    if not re.fullmatch(r"AB-[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}", dev):
        raise ValueError("Format ID perangkat salah.")
    if plan not in PLANS:
        raise ValueError(f"Paket {plan} tidak valid.")

    now = int(time.time())
    exp = 0 if days == 0 else (now + days * 86400)
    feat = list(PLAN_FEAT.get(plan, []))
    lic_id = lic_id or ("L-" + uuid.uuid4().hex[:8].upper())

    payload = {
        "v": 1,
        "lic": lic_id,
        "dev": dev,
        "plan": plan,
        "feat": feat,
        "name": name,
        "iat": now,
        "exp": exp,
    }
    body = "AB1." + _b64e(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    sig = get_private_key().sign(body.encode())
    token = body + "." + _b64e(sig)
    return token, payload


# ---------------------------------------------------------------- Database SQLite
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                plan TEXT NOT NULL,
                days INTEGER NOT NULL,
                customer_name TEXT,
                customer_email TEXT,
                customer_phone TEXT,
                amount INTEGER NOT NULL,
                snap_token TEXT,
                snap_redirect_url TEXT,
                status TEXT NOT NULL,
                license_token TEXT,
                created_at INTEGER NOT NULL,
                paid_at INTEGER
            )
        """)
        conn.commit()


init_db()


def save_order(order):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO orders (
                order_id, device_id, plan, days, customer_name, customer_email,
                customer_phone, amount, snap_token, snap_redirect_url, status,
                license_token, created_at, paid_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order["order_id"], order["device_id"], order["plan"], order["days"],
            order.get("customer_name", ""), order.get("customer_email", ""),
            order.get("customer_phone", ""), order["amount"], order.get("snap_token", ""),
            order.get("snap_redirect_url", ""), order["status"],
            order.get("license_token", ""), order["created_at"], order.get("paid_at")
        ))
        conn.commit()


def get_order(order_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_latest_order_by_device(device_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE device_id = ? ORDER BY created_at DESC LIMIT 1", (device_id,))
        row = cur.fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------- Midtrans Helper
def midtrans_snap_url():
    is_prod = CONFIG.get("midtrans", {}).get("is_production", False)
    return "https://app.midtrans.com/snap/v1/transactions" if is_prod else "https://app.sandbox.midtrans.com/snap/v1/transactions"


def midtrans_js_url():
    is_prod = CONFIG.get("midtrans", {}).get("is_production", False)
    return "https://app.midtrans.com/snap/snap.js" if is_prod else "https://app.sandbox.midtrans.com/snap/snap.js"


def create_midtrans_transaction(order_id, gross_amount, device_id, plan, days, name, email, phone):
    server_key = CONFIG.get("midtrans", {}).get("server_key", "")
    if not server_key or "YOUR_MIDTRANS" in server_key:
        raise ValueError("Midtrans Server Key belum diisi di config.json")

    auth_str = base64.b64encode(f"{server_key}:".encode()).decode()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth_str}",
    }

    plan_info = CONFIG.get("pricing", {}).get(plan, {})
    plan_title = plan_info.get("name", plan.upper())
    duration_label = "1 Tahun" if days >= 365 else f"{days} Hari"

    payload = {
        "transaction_details": {
            "order_id": order_id,
            "gross_amount": int(gross_amount),
        },
        "item_details": [
            {
                "id": f"{plan}-{days}d",
                "price": int(gross_amount),
                "quantity": 1,
                "name": f"AdsBooth {plan_title} ({duration_label})",
            }
        ],
        "customer_details": {
            "first_name": name or "Pelanggan AdsBooth",
            "email": email or "support@adsbooth.id",
            "phone": phone or "08120000000",
        },
        "custom_field1": device_id,
        "custom_field2": plan,
        "custom_field3": str(days),
    }

    resp = requests.post(midtrans_snap_url(), headers=headers, json=payload, timeout=15)
    if resp.status_code not in (200, 201):
        logger.error("Midtrans Snap Error %d: %s", resp.status_code, resp.text)
        raise RuntimeError(f"Gagal membuat transaksi Midtrans: {resp.text}")

    data = resp.json()
    return data.get("token"), data.get("redirect_url")


# ---------------------------------------------------------------- Flask Web App
app = Flask(__name__)


@app.get("/")
def index():
    return jsonify({
        "service": "AdsBooth License Server",
        "status": "online",
        "time": int(time.time()),
        "production": CONFIG.get("midtrans", {}).get("is_production", False),
    })


@app.get("/api/pricing")
def get_pricing():
    """Kembalikan daftar paket & harga langganan."""
    return jsonify({
        "ok": True,
        "pricing": CONFIG.get("pricing", {}),
        "midtrans_client_key": CONFIG.get("midtrans", {}).get("client_key", ""),
        "is_production": CONFIG.get("midtrans", {}).get("is_production", False),
    })


@app.post("/api/create-transaction")
def api_create_transaction():
    """Membuat transaksi langganan baru & mendapatkan token Snap Midtrans."""
    data = request.get_json(force=True) or {}
    device_id = str(data.get("device_id", "")).strip().upper()
    plan = str(data.get("plan", "complete")).strip().lower()
    days = int(data.get("days", 30))
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()

    # Validasi input
    if not re.fullmatch(r"AB-[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}", device_id):
        return jsonify({"ok": False, "error": "ID Perangkat tidak valid (format: AB-XXXX-XXXX-XXXX-XXXX)"}), 400

    pricing = CONFIG.get("pricing", {}).get(plan)
    if not pricing:
        return jsonify({"ok": False, "error": f"Paket '{plan}' tidak ditemukan"}), 400

    prices = pricing.get("prices", {})
    amount = prices.get(str(days))
    if not amount:
        return jsonify({"ok": False, "error": f"Durasi {days} hari tidak tersedia untuk paket {plan}"}), 400

    order_id = f"AB-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"

    try:
        snap_token, snap_redirect_url = create_midtrans_transaction(
            order_id, amount, device_id, plan, days, name, email, phone
        )
    except Exception as e:
        logger.exception("Gagal generate Snap transaction")
        return jsonify({"ok": False, "error": str(e)}), 500

    order_record = {
        "order_id": order_id,
        "device_id": device_id,
        "plan": plan,
        "days": days,
        "customer_name": name,
        "customer_email": email,
        "customer_phone": phone,
        "amount": amount,
        "snap_token": snap_token,
        "snap_redirect_url": snap_redirect_url,
        "status": "pending",
        "created_at": int(time.time()),
        "paid_at": None,
        "license_token": None,
    }
    save_order(order_record)

    checkout_url = f"{request.host_url.rstrip('/')}/checkout/{order_id}"

    return jsonify({
        "ok": True,
        "order_id": order_id,
        "snap_token": snap_token,
        "snap_redirect_url": snap_redirect_url,
        "checkout_url": checkout_url,
    })


@app.post("/api/midtrans-webhook")
def api_midtrans_webhook():
    """Webhook notifikasi dari Midtrans saat status pembayaran berubah."""
    data = request.get_json(force=True) or {}
    order_id = data.get("order_id", "")
    status_code = data.get("status_code", "")
    gross_amount = data.get("gross_amount", "")
    signature_key = data.get("signature_key", "")
    transaction_status = data.get("transaction_status", "")
    fraud_status = data.get("fraud_status", "")

    server_key = CONFIG.get("midtrans", {}).get("server_key", "")
    expected_sig = hashlib.sha512(f"{order_id}{status_code}{gross_amount}{server_key}".encode()).hexdigest()

    if not hmac.compare_digest(signature_key, expected_sig):
        logger.warning("Webhook ditolak: Signature Key tidak sah untuk order %s", order_id)
        return jsonify({"status": "error", "message": "Invalid signature"}), 403

    order = get_order(order_id)
    if not order:
        logger.warning("Webhook order_id tidak ditemukan di database: %s", order_id)
        return jsonify({"status": "not_found"}), 404

    logger.info("Midtrans Webhook: order=%s, status=%s, fraud=%s", order_id, transaction_status, fraud_status)

    is_success = False
    if transaction_status in ("capture", "settlement"):
        if transaction_status == "capture":
            is_success = (fraud_status == "accept")
        else:
            is_success = True

    if is_success:
        if order["status"] != "paid" or not order.get("license_token"):
            try:
                token, payload = issue_token(
                    order["device_id"],
                    order["plan"],
                    name=order.get("customer_name") or "",
                    days=order["days"],
                )
                order["status"] = "paid"
                order["paid_at"] = int(time.time())
                order["license_token"] = token
                save_order(order)
                logger.info("LISENSI BERHASIL DITERBITKAN: order=%s, device=%s, token=%s...",
                            order_id, order["device_id"], token[:20])
            except Exception as e:
                logger.exception("Gagal generate lisensi untuk order %s: %s", order_id, e)
                return jsonify({"status": "error", "message": str(e)}), 500
    elif transaction_status in ("deny", "cancel", "expire"):
        order["status"] = transaction_status
        save_order(order)

    return jsonify({"status": "ok"})


@app.get("/api/check-order/<order_id>")
def api_check_order(order_id):
    """Digunakan oleh frontend / AdsBooth Studio untuk auto-polling status pembayaran."""
    order = get_order(order_id)
    if not order:
        return jsonify({"ok": False, "error": "Order tidak ditemukan"}), 404

    return jsonify({
        "ok": True,
        "order_id": order["order_id"],
        "device_id": order["device_id"],
        "plan": order["plan"],
        "days": order["days"],
        "amount": order["amount"],
        "status": order["status"],
        "license_token": order.get("license_token"),
        "paid_at": order.get("paid_at"),
    })


@app.get("/api/check-device/<device_id>")
def api_check_device(device_id):
    """Cek order terakhir untuk device_id tertentu."""
    order = get_latest_order_by_device(device_id.strip().upper())
    if not order:
        return jsonify({"ok": False, "found": False})
    return jsonify({
        "ok": True,
        "found": True,
        "order_id": order["order_id"],
        "status": order["status"],
        "license_token": order.get("license_token"),
        "paid_at": order.get("paid_at"),
        "plan": order["plan"],
    })


# ---------------------------------------------------------------- Halaman Web Checkout
CHECKOUT_PAGE_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pembayaran Lisensi AdsBooth</title>
  <script src="{{ snap_js_url }}" data-client-key="{{ client_key }}"></script>
  <style>
    :root {
      --bg: #F8F9FA;
      --card: #FFFFFF;
      --ink: #111827;
      --muted: #6B7280;
      --line: #E5E7EB;
      --brand: #2563EB;
      --brand-dark: #1D4ED8;
      --success: #059669;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--ink); display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
    .box { background: var(--card); max-width: 500px; width: 100%; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.06); border: 1px solid var(--line); overflow: hidden; }
    .header { background: #1E293B; color: #fff; padding: 24px 28px; }
    .header h1 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
    .header p { font-size: 13px; color: #94A3B8; }
    .body { padding: 28px; }
    .item-row { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px dashed var(--line); font-size: 14px; }
    .item-row .val { font-weight: 600; text-align: right; }
    .total-row { display: flex; justify-content: space-between; padding: 16px 0; font-size: 18px; font-weight: 700; color: var(--brand); }
    .btn { display: block; width: 100%; padding: 14px; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; text-align: center; text-decoration: none; margin-top: 20px; transition: 0.15s ease; }
    .btn-pay { background: var(--brand); color: #fff; }
    .btn-pay:hover { background: var(--brand-dark); }
    .btn-copy { background: #EEF2FF; color: var(--brand); border: 1.5px solid #C7D2FE; margin-top: 10px; }
    .btn-copy:hover { background: #E0E7FF; }
    .token-box { margin-top: 16px; background: #F1F5F9; border: 1.5px solid #CBD5E1; border-radius: 10px; padding: 12px; font-family: monospace; font-size: 12px; word-break: break-all; max-height: 120px; overflow-y: auto; color: #0F172A; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 99px; font-size: 12px; font-weight: 600; }
    .badge-paid { background: #D1FAE5; color: #065F46; }
    .badge-pending { background: #FEF3C7; color: #92400E; }
    .mono { font-family: monospace; }
  </style>
</head>
<body>
  <div class="box">
    <div class="header">
      <h1>Pembayaran Lisensi AdsBooth</h1>
      <p>ID Transaksi: <span class="mono">{{ order.order_id }}</span></p>
    </div>
    <div class="body">
      <div id="paymentView" {% if order.status == 'paid' %}style="display:none"{% endif %}>
        <div class="item-row">
          <span style="color:var(--muted)">Device ID</span>
          <span class="val mono">{{ order.device_id }}</span>
        </div>
        <div class="item-row">
          <span style="color:var(--muted)">Paket</span>
          <span class="val">{{ plan_name }} ({{ order.days }} Hari)</span>
        </div>
        <div class="item-row">
          <span style="color:var(--muted)">Atas Nama</span>
          <span class="val">{{ order.customer_name or '-' }}</span>
        </div>
        <div class="total-row">
          <span>Total Pembayaran</span>
          <span>Rp {{ "{:,}".format(order.amount).replace(',', '.') }}</span>
        </div>

        <button type="button" class="btn btn-pay" id="btnPay" onclick="openSnap()">Bayar Sekarang (QRIS / VA)</button>
        <p style="text-align:center;font-size:12px;color:var(--muted);margin-top:14px">
          Mendukung QRIS (GoPay, ShopeePay, BCA Mobile), Virtual Account &amp; E-Wallet.
        </p>
      </div>

      <div id="successView" {% if order.status != 'paid' %}style="display:none"{% endif %}>
        <div style="text-align:center;margin-bottom:18px">
          <span class="badge badge-paid">✓ Pembayaran Berhasil</span>
          <h2 style="font-size:20px;margin-top:10px">Lisensi Telah Aktif!</h2>
          <p style="font-size:13px;color:var(--muted);margin-top:4px">
            Jika AdsBooth Studio terbuka di perangkat Anda, lisensi otomatis aktif. Jika belum, Anda bisa menyalin kode lisensi di bawah ini.
          </p>
        </div>

        <div style="font-size:12px;font-weight:600;color:var(--muted);margin-bottom:4px">KODE LISENSI ANDA:</div>
        <div class="token-box" id="tokenBox">{{ order.license_token or '' }}</div>

        <button type="button" class="btn btn-copy" onclick="copyToken()">📋 Salin Kode Lisensi</button>
        <div id="copyNotice" style="display:none;text-align:center;font-size:13px;color:var(--success);margin-top:8px;font-weight:600">✓ Kode berhasil disalin ke clipboard!</div>

        <div style="background:#FAF8F3;border:1px solid #E2E8F0;border-radius:10px;padding:12px;font-size:12px;color:#475569;margin-top:16px">
          <b>Langkah aktivasi manual:</b> Buka AdsBooth Studio di PC photobooth Anda → buka menu <b>Lisensi &amp; Aktivasi</b> → tempel kode di atas dan klik <b>Aktifkan</b>.
        </div>
      </div>
    </div>
  </div>

  <script>
    const snapToken = "{{ order.snap_token }}";
    const orderId = "{{ order.order_id }}";

    function openSnap() {
      if (!snapToken) {
        alert("Token pembayaran tidak valid.");
        return;
      }
      snap.pay(snapToken, {
        onSuccess: function(result) {
          checkOrderStatus();
        },
        onPending: function(result) {
          alert("Pembayaran sedang diproses, silakan selesaikan pembayaran Anda.");
          pollStatus();
        },
        onError: function(result) {
          alert("Pembayaran gagal atau dibatalkan.");
        },
        onClose: function() {
          pollStatus();
        }
      });
    }

    let pollInterval = null;
    function pollStatus() {
      if (pollInterval) return;
      pollInterval = setInterval(checkOrderStatus, 3000);
    }

    function checkOrderStatus() {
      fetch('/api/check-order/' + orderId)
        .then(r => r.json())
        .then(res => {
          if (res.ok && res.status === 'paid' && res.license_token) {
            clearInterval(pollInterval);
            document.getElementById('paymentView').style.display = 'none';
            document.getElementById('successView').style.display = 'block';
            document.getElementById('tokenBox').innerText = res.license_token;
          }
        })
        .catch(err => console.error(err));
    }

    function copyToken() {
      const text = document.getElementById('tokenBox').innerText.trim();
      navigator.clipboard.writeText(text).then(() => {
        document.getElementById('copyNotice').style.display = 'block';
        setTimeout(() => {
          document.getElementById('copyNotice').style.display = 'none';
        }, 3000);
      });
    }

    // Mulai auto-polling saat halaman dibuka jika belum bayar
    {% if order.status != 'paid' %}
    pollStatus();
    {% endif %}
  </script>
</body>
</html>
"""


@app.get("/checkout/<order_id>")
def checkout_page(order_id):
    order = get_order(order_id)
    if not order:
        return "Order tidak ditemukan", 404

    client_key = CONFIG.get("midtrans", {}).get("client_key", "")
    plan_info = CONFIG.get("pricing", {}).get(order["plan"], {})
    plan_name = plan_info.get("name", order["plan"].upper())

    return render_template_string(
        CHECKOUT_PAGE_HTML,
        order=order,
        plan_name=plan_name,
        client_key=client_key,
        snap_js_url=midtrans_js_url(),
    )


if __name__ == "__main__":
    port = int(CONFIG.get("port", 8080))
    print(f"=== AdsBooth License & Midtrans Server berjalan di port {port} ===")
    print(f"URL: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
