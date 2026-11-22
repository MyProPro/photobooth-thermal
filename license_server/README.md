# AdsBooth License & Midtrans Server

Server backend otomatis untuk menerima pembayaran online (QRIS, GoPay, ShopeePay, BCA Virtual Account, Kartu Kredit) melalui **Midtrans** dan otomatis menerbitkan serta mengaktifkan token lisensi Ed25519 untuk aplikasi **AdsBooth Photobooth**.

---

## Fitur Utama

1. **Auto-Generate License Token**: Begitu pembayaran lunas (*settlement*), lisensi langsung dibuat dengan tanda tangan kriptografi Ed25519 dan tersimpan di database.
2. **Instant Copy-Paste & Auto-Activate**: 
   - Di halaman sukses, kode lisensi langsung muncul beserta tombol **Salin Kode Lisensi**.
   - Di aplikasi AdsBooth Studio (PC photobooth), sistem dapat melakukan auto-polling sehingga lisensi aktif seketika (*zero-touch activation*).
3. **Database SQLite Ringan**: Riwayat transaksi, status pembayaran, dan token lisensi tersimpan rapi di `orders.db`.
4. **Verifikasi Keamanan Webhook**: Setiap notifikasi dari Midtrans diverifikasi menggunakan SHA-512 Signature Key untuk mencegah pemalsuan status pembayaran.

---

## 1. Persiapan & Konfigurasi

Salin file `config.example.json` menjadi `config.json` (atau edit langsung `config.json`):

```json
{
  "midtrans": {
    "is_production": false,
    "server_key": "SB-Mid-server-xxxxxxxxxxxxxxxxx",
    "client_key": "SB-Mid-client-xxxxxxxxxxxxxxxxx"
  },
  "license": {
    "private_key_path": "../.adsbooth-license/private.key"
  },
  "pricing": {
    "thermal": {
      "name": "Paket Thermal (80mm)",
      "desc": "Struk receipt photobooth 80mm",
      "prices": {
        "30": 150000,
        "365": 1200000
      }
    },
    "photo": {
      "name": "Paket Foto 4R",
      "desc": "Cetak foto berwarna 4R (10x15 cm)",
      "prices": {
        "30": 250000,
        "365": 2000000
      }
    },
    "complete": {
      "name": "Paket Lengkap (All-in)",
      "desc": "Struk thermal + Foto 4R + Living Photo",
      "prices": {
        "30": 350000,
        "365": 2800000
      }
    }
  },
  "port": 8080
}
```

### Mendapatkan Kunci Midtrans:
1. Buka [dashboard.midtrans.com](https://dashboard.midtrans.com) (atau [dashboard.sandbox.midtrans.com](https://dashboard.sandbox.midtrans.com) untuk mode testing).
2. Masuk ke menu **Settings → Access Keys**.
3. Salin **Server Key** dan **Client Key** ke `config.json`.
4. Atur `"is_production": false` saat testing Sandbox, dan ubah ke `true` saat siap jualan live.

---

## 2. Pengaturan Webhook di Dashboard Midtrans

Agar Midtrans dapat memberi tahu server saat pelanggan selesai membayar:
1. Masuk ke Dashboard Midtrans → **Settings → Configuration**.
2. Pada kolom **Payment Notification URL**, isi alamat server Anda:
   ```
   https://lisensi.namadomainanda.com/api/midtrans-webhook
   ```
3. Klik **Save Changes**.

---

## 3. Uji Coba di Komputer Lokal (Menggunakan Ngrok)

Jika Anda ingin menguji coba pembayaran di laptop/PC lokal:
1. Jalankan server lisensi:
   ```bash
   cd license_server
   python server.py
   ```
2. Buka terminal baru dan jalankan ngrok:
   ```bash
   ngrok http 8080
   ```
3. Salin URL HTTPS dari ngrok (contoh: `https://abcd-1234.ngrok-free.app`), lalu masukkan ke Dashboard Midtrans Sandbox:
   ```
   https://abcd-1234.ngrok-free.app/api/midtrans-webhook
   ```
4. Buka halaman checkout atau coba simulasi pembayaran via [Simulator Midtrans](https://simulator.sandbox.midtrans.com).

---

## 4. Deploy ke Server Produksi (VPS Ubuntu)

Untuk menjalankan server ini 24/7 di VPS (DigitalOcean / IDCloudHost / DomaiNesia / dll):

1. Upload folder `license_server` dan file kunci privat `private.key` ke VPS.
2. Pasang dependensi di VPS:
   ```bash
   sudo apt update && sudo apt install -y python3-pip python3-venv
   python3 -m venv venv
   source venv/bin/activate
   pip install flask requests cryptography
   ```
3. Buat service systemd (`/etc/systemd/system/adsbooth-license.service`):
   ```ini
   [Unit]
   Description=AdsBooth License & Midtrans Server
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/license_server
   ExecStart=/home/ubuntu/license_server/venv/bin/python server.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
4. Aktifkan service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now adsbooth-license
   ```
5. Pasang Nginx + Certbot (SSL HTTPS gratis):
   ```nginx
   server {
       server_name lisensi.namadomainanda.com;
       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
