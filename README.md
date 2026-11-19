# Thermal Photobooth 80mm

Photobooth dengan cetak instan ke printer thermal 80mm (ESC/POS).
Python (Flask) + halaman kiosk di browser + Pillow (dithering) + python-escpos.

```
app.py          server Flask + API
imaging.py      susun struk 576 dot, gaya Dither / Halftone / Kontras / Sketsa
printer.py      koneksi printer: win32 | usb | network | serial | file
config.json     semua pengaturan
static/         UI kiosk (index.html, style.css, app.js)
output/         dibuat otomatis: sessions/<id>/foto_n.jpg + struk.png, prints/*.png
```

## Cara jalan (Windows)

1. Instal Python 3.10+ dan Google Chrome.
2. Dobel-klik `run.bat`: membuat `.venv`, memasang dependensi, menjalankan server, lalu membuka Chrome mode kiosk.
   Keluar dari kiosk: `Alt+F4`.

Manual:
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Lalu buka http://localhost:5000

Default `printer.type` = `"file"` → tidak mencetak, hanya menyimpan PNG di `output/prints/`. Pakai ini untuk tes alur dulu.

## Setting printer (`config.json` → `printer`)

| type | isi yang dipakai | catatan |
|---|---|---|
| `win32` | `name` | Paling gampang di Windows. Instal driver printer, lalu isi nama persis seperti di *Printers & scanners* (mis. `POS-80`, `EPSON TM-T82`). |
| `usb` | `vendor_id`, `product_id` | Akses USB langsung. Di Windows perlu driver WinUSB (pakai Zadig) + libusb. |
| `network` | `host`, `port` (9100) | Printer LAN/Wi-Fi. |
| `serial` | `port` (`COM3`), `baudrate` | Printer serial / Bluetooth SPP. |

Lainnya:
- `paper_px`: 576 untuk 80mm @203dpi. Kalau hasil cetak kepotong di kanan, coba 512.
- `impl`: `bitImageRaster` (default). Kalau printer cetak sampah/karakter aneh, coba `graphics` atau `bitImageColumn`.
- `fragment_height`: kecilkan (mis. 128) kalau printer macet di tengah gambar panjang.
- `brightness`: >1.0 = lebih terang (thermal cenderung gelap), mis. `1.15`.
- `cut`: `false` kalau printer tidak punya auto-cutter.

## QR unduh versi digital

Struk & layar Selesai menampilkan QR ke `http://<IP-PC>:5000/d/<id>`.
HP tamu harus satu Wi-Fi dengan PC, dan port 5000 dibuka di Windows Firewall.
Kalau pakai domain/tunnel, isi `public_base_url`. Matikan dengan `"qr_download": false`.

## Pengaturan event

- `event_name`: judul di struk & layar.
- `logo_path`: mis. `"assets/logo.png"` (PNG hitam di atas putih/transparan paling bagus).
- `footer`, `max_copies`, `countdown_seconds`, `reset_seconds` (layar Selesai), `idle_seconds` (balik ke awal kalau ditinggal), `mirror` (foto dicerminkan seperti preview).

Font: otomatis pakai Arial/Consolas di Windows. Mau font lain? Taruh `fonts/regular.ttf`, `fonts/bold.ttf`, `fonts/mono.ttf`.

## Catatan kamera

Kamera dibuka lewat browser (`getUserMedia`). Ini hanya diizinkan di `localhost` atau HTTPS, jadi buka UI dari PC yang sama dengan kamera.
`run.bat` memakai `--use-fake-ui-for-media-stream` supaya izin kamera tidak muncul di kiosk.

## Template struk

Setelah sesi foto, tamu memilih template di layar **Pilih Template** (preview sudah pakai foto mereka).
Semua template hitam-putih dan mendukung Solo (1) / Duo (2) / Strip (3) / Grid (4 foto):

| id | nama | konsep |
|---|---|---|
| `klasik` | Klasik | judul event, garis putus-putus, foto, QR |
| `strip_rounded` | Strip Rounded | photostrip latar hitam, foto sudut membulat |
| `strip_kotak` | Strip Kotak | photostrip latar hitam, foto kotak tegas |
| `strip_kapsul` | Strip Kapsul | foto-foto menyatu membentuk kapsul |
| `strip_perangko` | Strip Perangko | tepi foto bergerigi seperti perangko |
| `strip_vintage` | Strip Vintage | bingkai ornamen (lengkung, cartouche, cushion) |
| `polaroid` | Polaroid | foto dalam bingkai polaroid miring, tulisan tangan |
| `film` | Film Strip | pita film hitam dengan lubang sprocket & nomor frame |
| `tiket` | Tiket Masuk | ADMIT ONE, kotak tanggal/jam/no, sobekan + stub barcode |
| `pass` | Guest Pass | kartu ID/lanyard, kolom NAMA untuk ditulis tangan, ACCESS: ALL AREA |
| `koran` | Koran | masthead "Kabar Booth", headline = pesan tamu, artikel 2 kolom |
| `majalah` | Cover Majalah | foto pertama jadi cover "BOOTH", foto lain "juga di edisi ini" |
| `belanja` | Struk Belanja | parodi struk: 3 x POSE ANDALAN — TOTAL: BAHAGIA |
| `elegan` | Elegan | bingkai ganda + ornamen, cocok untuk pernikahan |
| `kalender` | Kalender | kalender meja: foto di atas, kalender bulan berjalan di bawah, tanggal cetak dilingkari |
| `ramalan` | Ramalan | ramalan lucu acak, bar Rezeki/Jodoh/Karier/Mood, angka keberuntungan |
| `boarding` | Boarding Pass | rute bisa diisi per event (Studio → Info event, mis. DPS → BHG), gate & seat acak, stub barcode |
| `sertifikat` | Sertifikat | tamu memilih gelar di layar Review (atau Acak), mis. AURA +1000, CANTIK 95%; daftar gelar diatur per event di Studio |
| `resep` | Resep Dokter | dr. Booth Sp.S, 3 "obat" acak tulisan tangan |
| `cocok` | Tes Kecocokan | persentase cocok besar + hasil lab lucu |
| `kartupos` | Kartu Pos | prangko berisi foto, cap pos, garis untuk menulis pesan |
| `komik` | Komik | panel komik dengan balon kata acak, pesan tamu di panel terakhir |

Atur di `config.json`:
- `default_template`: template yang terpilih otomatis.
- `templates`: daftar id yang ditampilkan & urutannya, mis. `["elegan","polaroid","klasik"]`. Kosong = semua.

Tambah template sendiri: buat fungsi `t_namaku(c)` di `templates.py` (contoh paling sederhana: `t_klasik`), lalu daftarkan di `TEMPLATES`.

Template `strip_*` berlatar hitam penuh: cetaknya sedikit lebih lambat & panas. Kalau hasil terlalu pekat/kertas melengkung, turunkan density di printer atau naikkan `brightness`.

Font di folder `fonts/` (Josefin Sans, Bebas Neue, Archivo Black, Space Mono, Caveat, Playfair Display, Inter) berlisensi SIL Open Font License — boleh dipakai & disertakan.

## Gaya cetak

Dither, Halftone, Kontras, Sketsa, **ASCII** (foto tersusun dari huruf & simbol), **Mewarnai** (garis luar untuk diwarnai, cocok untuk anak).

## Fitur tambahan per event (Studio → Info event → Fitur tambahan)

- **Buku tamu + tanda tangan**: setelah review, tamu menulis nama, ucapan, dan tanda tangan di tablet. Ikut tercetak di struk.
  Semua ucapan bisa dilihat di Studio → *Buku tamu & undian* → *Buka halaman buku tamu* → Cetak / Simpan PDF.
- **Nomor undian**: setiap struk dapat nomor (= nomor struk). Undi di Studio → *Buku tamu & undian* → *Undi sekarang* (nomor yang sudah keluar tidak keluar lagi).
- **Tantangan pose**: pose acak muncul di layar sebelum tiap jepretan dan ikut tercetak.
- **Cetak arsip tuan rumah**: otomatis mencetak 1 salinan tambahan berlabel *ARSIP TUAN RUMAH*.

## Slideshow TV

Buka **http://localhost:5000/slideshow** (atau `http://<IP-PC>:5000/slideshow` dari PC/TV lain) di layar besar, lalu klik sekali untuk layar penuh.
Foto event aktif tampil bergantian; foto baru langsung muncul dengan label *FOTO BARU!*.

## Penghitung kertas

Studio → *Printer & tablet* → *Kertas*: isi panjang roll (default 50 m). Setiap cetak dihitung otomatis.
Kiosk menampilkan *KERTAS HAMPIR HABIS* saat sisa ≤ 3 m (`paper_warn_m`). Setelah ganti roll klik *Ganti roll baru (reset)*.

## Template Studio (banyak event)

Buka **http://localhost:5000/studio** (dari PC yang sama, atau `http://<IP-PC>:5000/studio` dari laptop lain di jaringan yang sama).

- **Event**: buat event baru, isi nama yang dicetak, logo, footer, dan layout apa saja yang boleh dipilih tamu.
- **Aktifkan di kiosk**: kiosk otomatis memuat ulang ke event itu saat kembali ke layar awal.
- **Template**: centang template yang tampil, ★ untuk yang terpilih otomatis, panah untuk urutan.
- **+ Template builder**: mulai dari preset (Putih minimal / Photostrip hitam + logo / Wedding elegan / Logo besar), lalu atur latar, logo, teks atas/bawah, font, bentuk foto, pemisah, bingkai, QR. Preview langsung di kanan.
  Kode teks: `{event} {date} {date_long} {day} {time} {caption} {no}`.
- **+ Upload frame PNG**: desain di Canva/Photoshop, lebar 576 px (atau 1152), area foto **transparan**. Lubang terdeteksi otomatis; jumlah lubang = jumlah foto.
- Jangan lupa **Simpan** (atau Ctrl+S).

Data tersimpan di folder `events/<id>/` (event.json + logo/frame). Hapus event = dipindah ke `events/_trash/`.
Tanpa event aktif, kiosk memakai pengaturan di `config.json`.

Kunci Studio dengan PIN: isi `"studio_pin": "1234"` di `config.json`.

## Template Sosial Media

Lima template meniru tata letak halaman profil (ikon digambar generik, tanpa logo resmi), semua mendukung 1–4 foto:

| id | nama | isi |
|---|---|---|
| `sosmed` | Instagram Profil | avatar + Posts/Followers/Following, tombol Follow/Message, grid foto |
| `threads` | Threads Profil | nama besar, avatar kanan, followers, satu thread berisi foto |
| `xprofil` | X Profil | banner, avatar, Following/Followers, tab Posts, satu post berisi foto |
| `facebook` | Facebook Profil | foto sampul, Add friend, satu postingan dengan Like/Comment/Share |
| `youtube` | YouTube Channel | banner, Subscribe, daftar thumbnail video + durasi |

Username, nama tampilan, website, dan bio diatur per event di **Studio → Info event → Template Sosial Media**
(tanpa event: blok `"social"` di config.json). Avatar = logo event, atau foto pertama kalau tidak ada logo.
Angka followers/like/views/subscriber diacak setiap cetak. Judul video/post = pesan tamu.

## Setup kiosk (tablet + printer)

Semua diatur dari **Studio → ⚙ Printer & tablet**.

### Perangkat
| Tablet | Cara pakai |
|---|---|
| **Windows tablet / PC** | Jalankan `run.bat` di perangkat itu. Kamera & printer langsung jalan (localhost). |
| **Android** | PC/mini PC/laptop jadi server (jalankan `run.bat`). Di Studio aktifkan **HTTPS**, restart server, lalu di tablet scan QR "Buka kiosk di tablet" (`https://<IP-PC>:5443/?kiosk=1`). Chrome → *Lanjutan → Lanjutkan* (sekali), izinkan kamera, menu ⋮ → *Tambahkan ke layar utama* agar layar penuh. |
| **iPad** | Sama seperti Android, buka di Safari → *Tampilkan detail → kunjungi situs* → izinkan kamera → Bagikan → *Tambah ke Layar Utama*. Pakai *Guided Access* agar tamu tidak keluar. |

Kenapa HTTPS? Browser di tablet hanya mengizinkan kamera di halaman HTTPS (atau localhost). Sertifikat dibuat otomatis di folder `certs/` — wajar kalau browser memberi peringatan "tidak aman", cukup lanjutkan sekali.
Tablet & server harus di Wi-Fi yang sama. Pastikan Windows Firewall mengizinkan port 5000 dan 5443.

### Printer
| Koneksi | Pilih di Studio |
|---|---|
| USB dengan driver Windows | **Windows** → pilih nama printer (tombol *Cari perangkat*) |
| Bluetooth | Pair di Windows dulu. Muncul sebagai printer → **Windows**. Muncul sebagai COM port (Bluetooth SPP) → **Bluetooth / Serial** |
| LAN / Wi-Fi | **LAN / Wi-Fi** → IP printer, port 9100 |
| USB tanpa driver | **USB langsung** → vendor/product ID (perlu WinUSB via Zadig) |

Klik **Cek koneksi** lalu **Cetak tes**. Struk tes punya penggaris tepi: kalau garis kiri/kanan tidak tercetak, pilih lebar *80 mm aman (512 dot)*. Printer 58 mm → pilih *384 dot*.

### Satu kiosk, banyak tamu
- Kiosk otomatis kembali ke awal setelah selesai / ditinggal (`reset_seconds`, `idle_seconds`).
- QR unduh foto bisa dimatikan per event (Studio → Info event). Untuk kiosk umum yang tamunya tidak memakai Wi-Fi yang sama, sebaiknya dimatikan.
- `camera_facing` di config.json: `"user"` (kamera depan) atau `"environment"` (kamera belakang).

## Android saja (tablet + printer USB lewat kabel OTG)

Server jalan di tablet (Termux), Chrome di tablet mengirim struk ke printer USB lewat **WebUSB**.

1. Pasang **Termux** dari F-Droid (bukan Play Store).
2. Salin folder `thermal-photobooth` ke tablet (mis. ke Download), lalu di Termux:
   ```
   termux-setup-storage
   cp -r ~/storage/downloads/thermal-photobooth ~/
   cd ~/thermal-photobooth && bash setup-android.sh
   ```
3. Jalankan server: `bash ~/thermal-photobooth/start-android.sh` (biarkan Termux terbuka).
4. Colok printer ke tablet dengan **kabel/adaptor USB OTG**.
5. Chrome → `http://localhost:5000/studio` → *Printer & tablet* → jenis **USB di tablet Android (kabel OTG)** →
   **Sambungkan printer USB** → pilih printer → **Simpan pengaturan printer** → **Cetak tes**.
6. Kiosk: Chrome → `http://localhost:5000/?kiosk=1` → menu ⋮ → *Tambahkan ke layar utama*.
   Aktifkan *Pin aplikasi* di Android supaya tamu tidak keluar.

Catatan:
- Izin printer disimpan per browser. Kalau muncul "PRINTER USB BELUM DISAMBUNGKAN", tekan tombol *Sambungkan printer USB* di layar awal kiosk.
- Matikan *optimasi baterai* untuk Termux & Chrome supaya tidak dimatikan Android.
- Mode ini hanya untuk Chrome di Android. Di Windows pakai mode **Windows**.

## Raspberry Pi 4 / 5 (Linux)

Satu alat: Pi + monitor sentuh + webcam USB + printer USB (mis. Epson TM-T82 USB).

1. Pasang **Raspberry Pi OS (64-bit, Desktop)**. Salin folder `thermal-photobooth` ke Pi (mis. `/home/pi/thermal-photobooth`).
2. Terminal di Pi:
   ```
   cd ~/thermal-photobooth
   bash install-autostart.sh
   sudo reboot
   ```
   Skrip ini: memasang Python & Chromium, izin printer USB (`/dev/usb/lp0`), server otomatis saat boot
   (`photobooth.service`), Chromium kiosk otomatis saat desktop menyala, dan mematikan screen blanking.
3. Colok printer USB. Studio (`http://localhost:5000/studio`, atau `http://<IP-Pi>:5000/studio` dari laptop) →
   *Printer & tablet* → **Raspberry Pi / Linux (USB, /dev/usb/lp0)** → *Cari perangkat* → **Simpan** → **Cetak tes**.

Perintah berguna:
- Jalankan manual tanpa autostart: `bash run-linux.sh`
- Lihat log server: `journalctl -u photobooth -f` · restart: `sudo systemctl restart photobooth`
- Keluar dari kiosk: `Alt+F4` (keyboard).

Tips Pi 4: centang 6–10 template per event di Studio supaya layar Pilih Template cepat; gunakan microSD A1/A2 atau SSD USB 3.
Layar Pilih Template menampilkan template satu per satu begitu siap (`render_workers` di config.json, default 3).
