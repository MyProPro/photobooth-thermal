"""Alat penjual AdsBooth: membuat kunci & menerbitkan kode lisensi. JANGAN ikut dikirim ke pelanggan.

  python license_admin.py init
      Buat pasangan kunci (sekali saja). Kunci privat disimpan di luar folder proyek,
      kunci publik ditulis otomatis ke licensing.py.

  python license_admin.py issue --device AB-XXXX-XXXX-XXXX-XXXX --plan complete --name "Studio Foto Ceria" --days 30
  python license_admin.py issue --device AB-... --plan thermal --until 2027-01-31 --add living
      Terbitkan kode lisensi. Kode dicetak di layar & dicatat di issued.csv.
      --days 0 = tanpa batas waktu (lisensi seumur hidup).

  python license_admin.py verify <kode>
      Lihat isi kode lisensi (cek tanda tangan).

Lokasi kunci: %USERPROFILE%\\.adsbooth-license (Windows) / ~/.adsbooth-license (Linux),
atau set env PB_LICENSE_KEYS. BACKUP folder itu: kalau kunci privat hilang, semua pelanggan harus
diberi aplikasi dengan kunci publik baru.
"""
import argparse
import base64
import csv
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_DIR = os.environ.get("PB_LICENSE_KEYS") or os.path.join(os.path.expanduser("~"), ".adsbooth-license")
_OLD_DIR = os.path.join(os.path.expanduser("~"), ".photobooth-license")      # nama lama (sebelum AdsBooth)
if not os.environ.get("PB_LICENSE_KEYS") and not os.path.exists(KEY_DIR) and os.path.exists(_OLD_DIR):
    KEY_DIR = _OLD_DIR
PRIV = os.path.join(KEY_DIR, "private.key")
PUB = os.path.join(KEY_DIR, "public.key")
LOG = os.path.join(KEY_DIR, "issued.csv")
PLANS = ("thermal", "photo", "complete")
PLAN_FEAT = {"thermal": ["thermal"], "photo": ["photo"], "complete": ["thermal", "photo", "living"]}


def b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def load_private():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if not os.path.exists(PRIV):
        sys.exit(f"Kunci privat tidak ada di {PRIV}. Jalankan dulu: python license_admin.py init")
    return Ed25519PrivateKey.from_private_bytes(b64d(open(PRIV).read().strip()))


def write_public_to_app(pub_b64):
    path = os.path.join(HERE, "licensing.py")
    s = open(path, encoding="utf-8").read()
    s2 = re.sub(r'^PUBLIC_KEY = ".*"$', f'PUBLIC_KEY = "{pub_b64}"', s, count=1, flags=re.M)
    if s2 == s and f'PUBLIC_KEY = "{pub_b64}"' not in s:
        sys.exit("Baris PUBLIC_KEY di licensing.py tidak ditemukan.")
    with open(path, "w", encoding="utf-8") as f:
        f.write(s2)


def cmd_init(a):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if os.path.exists(PRIV) and not a.force:
        pub = open(PUB).read().strip()
        write_public_to_app(pub)
        print(f"Kunci sudah ada di {KEY_DIR} (tidak dibuat ulang). Kunci publik ditulis ke licensing.py.")
        return
    os.makedirs(KEY_DIR, exist_ok=True)
    k = Ed25519PrivateKey.generate()
    raw = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    with open(PRIV, "w") as f:
        f.write(b64e(raw))
    with open(PUB, "w") as f:
        f.write(b64e(pub))
    try:
        os.chmod(PRIV, 0o600)
    except OSError:
        pass
    write_public_to_app(b64e(pub))
    print(f"Kunci dibuat di: {KEY_DIR}")
    print("  private.key  -> RAHASIA. Backup ke flashdisk/password manager. Jangan di-commit / dikirim.")
    print(f"  public.key   -> sudah ditulis ke licensing.py ({b64e(pub)})")


def cmd_issue(a):
    dev = a.device.strip().upper()
    dev = dev[:3] + dev[3:].replace("0", "O").replace("1", "I").replace("8", "B")   # salah ketik umum
    if not re.fullmatch(r"AB-[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}-[A-Z2-7]{4}", dev):
        sys.exit("Format ID perangkat salah. Contoh: AB-7KQ2-M9XD-4HTA-PZ3C (lihat di AdsBooth Studio -> Lisensi).")
    now = int(time.time())
    if a.until:
        d = datetime.strptime(a.until, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        exp = int(d.timestamp())
    elif a.days == 0:
        exp = 0
    else:
        exp = now + a.days * 86400
    feat = list(PLAN_FEAT[a.plan])
    for x in a.add or []:
        if x not in feat:
            feat.append(x)
    payload = {"v": 1, "lic": a.id or "L-" + uuid.uuid4().hex[:8].upper(), "dev": dev, "plan": a.plan,
               "feat": feat, "name": a.name, "iat": now, "exp": exp}
    body = "AB1." + b64e(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    sig = load_private().sign(body.encode())
    token = body + "." + b64e(sig)
    os.makedirs(KEY_DIR, exist_ok=True)
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["waktu", "lic", "device", "plan", "fitur", "nama", "berlaku_sampai", "kode"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), payload["lic"], dev, a.plan, " ".join(feat),
                    a.name, datetime.fromtimestamp(exp).strftime("%Y-%m-%d") if exp else "selamanya", token])
    print(f"Lisensi {payload['lic']} | {a.plan} ({', '.join(feat)}) | {a.name or '-'}")
    print("Berlaku sampai:", datetime.fromtimestamp(exp).strftime("%d %b %Y %H:%M") if exp else "selamanya")
    print("\nKode lisensi (kirim ke pelanggan, tempel di Studio -> Lisensi):\n")
    print(token)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(token)
        print(f"\nDisimpan juga ke {a.out}")


def cmd_verify(a):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    tok = "".join(a.token.split())
    parts = tok.split(".")
    if len(parts) != 3 or parts[0] != "AB1":
        sys.exit("Format kode salah.")
    payload = json.loads(b64d(parts[1]))
    try:
        Ed25519PublicKey.from_public_bytes(b64d(open(PUB).read().strip())).verify(b64d(parts[2]), f"AB1.{parts[1]}".encode())
        print("Tanda tangan: SAH")
    except Exception:  # noqa: BLE001
        print("Tanda tangan: TIDAK SAH (atau dibuat dengan kunci lain)")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if payload.get("exp"):
        print("Berlaku sampai:", datetime.fromtimestamp(payload["exp"]).strftime("%d %b %Y %H:%M"))


def main():
    ap = argparse.ArgumentParser(description="Alat lisensi AdsBooth (khusus penjual)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="buat kunci (sekali)")
    p.add_argument("--force", action="store_true", help="buat kunci BARU (lisensi lama jadi tidak berlaku!)")
    p = sub.add_parser("issue", help="terbitkan kode lisensi")
    p.add_argument("--device", required=True, help="ID perangkat dari Studio -> Lisensi")
    p.add_argument("--plan", required=True, choices=PLANS)
    p.add_argument("--name", default="", help="nama pelanggan / usaha")
    p.add_argument("--days", type=int, default=30, help="masa berlaku (hari). 0 = selamanya")
    p.add_argument("--until", help="berlaku sampai tanggal YYYY-MM-DD (mengganti --days)")
    p.add_argument("--add", action="append", choices=["thermal", "photo", "living"], help="fitur tambahan (add-on)")
    p.add_argument("--id", help="ID lisensi (opsional, default acak)")
    p.add_argument("--out", help="simpan kode ke file .lic")
    p = sub.add_parser("verify", help="periksa kode lisensi")
    p.add_argument("token")
    a = ap.parse_args()
    {"init": cmd_init, "issue": cmd_issue, "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    main()
