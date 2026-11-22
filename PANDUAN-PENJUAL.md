# Panduan Penjual AdsBooth

Langkah-langkah untuk menjual AdsBooth: menyiapkan kunci lisensi, menerbitkan lisensi pelanggan,
membuat installer, dan merilis versi baru. Ringkasan teknis ada di [README.md](README.md).

> **Jangan pernah commit / kirim** folder kunci `%USERPROFILE%\.adsbooth-license\` (berisi `private.key`).
> Yang boleh masuk Git hanya `licensing.py` (berisi kunci **publik**).

---

## 1. Persiapan sekali saja

```bat
cd E:\Projects\Python\yt\thermal-photobooth
.venv\Scripts\activate
python license_admin.py init
```

- Membuat `private.key` + `public.key` di `%USERPROFILE%\.adsbooth-license\`.
- Kunci publik otomatis ditulis ke `licensing.py` → **commit & push** perubahan ini.
- **Backup** folder `.adsbooth-license` (flashdisk + password manager / Google Drive pribadi).
  Kalau `private.key` hilang, lisensi baru tidak bisa diterbitkan dan semua perangkat harus diinstal ulang
  dengan kunci baru.
- Jangan jalankan `init --force` kecuali memang mau ganti kunci (semua lisensi lama jadi tidak berlaku).

Pasang juga [Inno Setup 6](https://jrsoftware.org/isdl.php) untuk membuat installer Windows.

### Lisensi untuk PC sendiri (development)
Tanpa lisensi, PC sendiri juga masuk masa coba 7 hari (hasil cetak ada tanda DEMO). Terbitkan lisensi seumur hidup:

```bat
python license_admin.py issue --device <ID dari Studio> --plan complete --name "Dev" --days 0
```
Tempel kodenya di **AdsBooth Studio → ⚙ Printer & tablet → Lisensi**.

---

## 2. Paket & harga

| Paket (`--plan`) | Isi |
|---|---|
| `thermal` | Receipt Photobooth 80mm |
| `photo` | foto 4R berwarna |
| `complete` | Receipt Photobooth + foto 4R + Living Photo |

Add-on: `--add living` (Living Photo untuk paket Receipt Photobooth / photo).

---

## 3. Alur melayani pelanggan baru

1. Pelanggan instal `AdsBooth-Setup-x.y.z.exe` (atau `adsbooth_x.y.z_amd64.deb` untuk Ubuntu).
   Langsung dapat **masa coba 7 hari**, semua fitur, hasil cetak bertanda DEMO.
2. Pelanggan buka **AdsBooth Studio → ⚙ Printer & tablet → Lisensi**, klik **Salin** di ID perangkat,
   kirim ke kamu (WA/email). Contoh: `AB-7KQ2-M9XD-4HTA-PZ3C`.
   ID juga tampil di layar kunci kiosk.
3. Setelah pembayaran, terbitkan kode:
   ```bat
   python license_admin.py issue --device AB-7KQ2-M9XD-4HTA-PZ3C --plan complete --name "Studio Ceria" --days 30 --out ceria.lic
   ```
4. Kirim kodenya (teks `AB1.xxxx.xxxx`) atau file `ceria.lic`.
   Pelanggan tempel/buka di Studio → **Aktifkan**. Kiosk langsung normal tanpa restart.

Semua kode yang pernah diterbitkan tercatat di `%USERPROFILE%\.adsbooth-license\issued.csv`.

---

## 3b. Alur Otomatis (Langganan Online via Midtrans)

Kini AdsBooth mendukung sistem pembayaran & aktivasi mandiri tanpa Anda perlu melayani manual:

1. Jalankan `license_server/server.py` di VPS (atau lokal dengan ngrok).
2. Isi kunci Midtrans di `license_server/config.json` dan pasang Webhook Midtrans ke `https://lisensi.domainanda.com/api/midtrans-webhook`.
3. Di `config.json` aplikasi AdsBooth, atur `"license_server_url": "https://lisensi.domainanda.com"`.
4. **Pengalaman Pelanggan**:
   - Pelanggan buka **AdsBooth Studio → Lisensi & Aktivasi**.
   - Muncul pilihan paket (Thermal, Foto 4R, Complete) & durasi (1 Bulan / 1 Tahun).
   - Klik **Bayar & Aktifkan Otomatis** → Jendela pembayaran Midtrans (QRIS / VA) terbuka.
   - Pelanggan bayar di HP.
   - Server lisensi menerima notifikasi lunas → otomatis membuat token lisensi Ed25519.
   - Studio di PC pelanggan langsung mendeteksi pembayaran dan **mengaktifkan lisensi seketika**.
   - Kode lisensi juga tetap tampil di halaman sukses Midtrans untuk salin-tempel manual jika diperlukan.
   - Panduan lengkap deploy ada di [`license_server/README.md`](license_server/README.md).

---

### Perpanjangan (langganan bulanan)
Terbitkan kode baru dengan `--days 30` (atau `--until 2027-02-28`), kirim, pelanggan tempel di Studio.
Kode baru menggantikan kode lama.

| Status | Arti | Yang terjadi |
|---|---|---|
| Aktif | lisensi berlaku | normal |
| Masa tenggang | 1-3 hari setelah habis | normal + peringatan di Studio |
| Habis | > 3 hari setelah habis | kiosk terkunci, tidak bisa cetak |
| Masa coba habis | 7 hari tanpa lisensi | kiosk terkunci |

Studio menampilkan peringatan mulai 5 hari sebelum habis.

### Upgrade paket
Terbitkan kode baru dengan `--plan` yang baru untuk ID perangkat yang sama.

### Pelanggan ganti PC
ID perangkat ikut berubah → terbitkan kode baru untuk ID baru (kebijakan sendiri: gratis 1x, dll.).
Instal ulang Windows di PC yang sama biasanya juga mengubah ID.

---

## 4. Masalah yang sering ditanyakan

| Pesan di Studio / kiosk | Penyebab | Solusi |
|---|---|---|
| "Lisensi ini untuk perangkat lain" | kode diterbitkan untuk ID lain / salah ketik ID | cek ID di Studio, terbitkan ulang |
| "Kode lisensi tidak sah" | kode terpotong saat copy-paste | kirim sebagai file `.lic` |
| "Kode lisensi ini sudah kedaluwarsa" | kode lama dipakai lagi | terbitkan kode baru |
| "Jam perangkat mundur" / "System clock is incorrect" | tanggal PC salah atau pernah dimundurkan | betulkan jam; kalau tetap terkunci, terbitkan kode baru (otomatis memulihkan) |
| "Mode not included" | event memakai mode di luar paket (mis. foto 4R di paket Receipt Photobooth) | ganti jenis cetak di Studio, atau upgrade paket |

Cek isi sebuah kode: `python license_admin.py verify <kode>`.

---

## 5. Membuat installer & rilis versi baru

1. Naikkan `VERSION` di `version.py` (mis. `1.0.0` → `1.0.1`).
2. Windows: dobel klik `installer\build-windows.bat` → `dist\AdsBooth-Setup-1.0.1.exe`.
   Ubuntu (di PC Ubuntu 22.04): `bash installer/build-linux.sh` → `dist/adsbooth_1.0.1_amd64.deb`.
3. Tes di PC lain / Windows Sandbox: instal, buka Studio, cetak tes, cek kamera & printer.
4. Commit & push, beri tag: `git tag v1.0.1 && git push --tags`.
5. Kirim installer ke pelanggan (Google Drive / link download). Pelanggan cukup menjalankan
   installer baru; data & lisensi tetap.

Folder `build/` dan `dist/` tidak ikut Git (ada di `.gitignore`).

Installer belum ditandatangani (code signing) → Windows SmartScreen menampilkan
"Windows protected your PC". Beri tahu pelanggan: klik **More info → Run anyway**.

---

## 6. Catatan keamanan

- Pengecekan lisensi ada di program yang sudah dikompilasi (Nuitka), bukan file `.py`.
  Pelanggan tidak menerima kode sumber.
- **Repo GitHub sebaiknya PRIVATE.** Kalau repo publik, siapa pun bisa mengunduh kode sumber dan
  menjalankannya tanpa lisensi. Halaman pemutar Living Photo (`docs/v/`) yang butuh hosting publik
  bisa dipindah ke repo publik terpisah atau ke VPS, lalu alamatnya diisi di `LIVING_BASE_URL` (`version.py`).
- Tahap berikutnya (server lisensi di VPS) menambah aktivasi online supaya lebih sulit diakali.
