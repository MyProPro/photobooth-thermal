# AdsBooth — photobooth struk thermal 80mm & foto 4R

AdsBooth: photobooth dengan cetak instan ke printer thermal 80mm (ESC/POS).
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
- **Bahasa teks cetak** (Studio → Info event): `Bahasa Indonesia` atau `English`. Mengubah teks bawaan yang tercetak (judul template, tanggal/bulan, nomor undian, buku tamu, tantangan pose, label arsip). Nama event, footer, caption, dan template custom tetap seperti yang diketik.
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

## Mode foto 4R berwarna (photobooth biasa)
Satu sistem bisa untuk dua jenis cetak. Pilih per event di **Studio → Info event → paling atas**:
- **Struk thermal 80mm** (hitam-putih, printer ESC/POS)
- **Foto 4R berwarna** (kertas 10×15 cm, 300 dpi, printer foto)

Di mode foto:
- **Layout**: Solo (1), Duo (2), Grid (4), dan Strip (3 foto, dicetak **2 strip 5×15 cm kembar** dalam satu lembar 4R, tinggal dipotong di tengah).
- **Gaya foto**: Warna, Cerah, Hitam putih, Sepia, Vintage, Sejuk.
- **Template**: Klasik putih, Hitam elegan, Polaroid, Roll film, Warna tema event (ikut warna tema kiosk), Sampul majalah, Pernikahan, dan **Bingkai sendiri (PNG)**.
- **Bingkai sendiri**: Studio → tab Template → upload PNG per layout. Area **transparan** = tempat foto (terdeteksi otomatis). Ukuran: Solo/Duo/Grid 1200×1800 px, Strip 600×1800 px.
- QR unduh, nomor undian, buku tamu, slideshow tetap jalan. Halaman unduh juga berisi hasil cetak 4R-nya.

**Printer foto** (Studio → Printer & tablet → *Printer foto*):
- **Windows**: pilih printer foto yang sudah terpasang drivernya (Canon Selphy, DNP, Citizen, Epson, dll). Di *Printing Preferences* driver, set kertas **4x6 / 10x15 cm**, dan **borderless** kalau ada.
- **Raspberry Pi / Linux**: lewat CUPS (`sudo apt install cups`, tambahkan printer di http://localhost:631).
- **Tes**: "simpan file saja" (hasil JPG di `output/prints`).
- Tekan **Cetak halaman tes** untuk cek warna dan tepi kertas.
- Catatan: mode foto tidak bisa mencetak langsung dari tablet Android (driver printer foto tidak ada di Android). Jalankan server di Windows/Pi; tablet tetap bisa jadi layar kiosk.

## QR video (Living Photo)
Setiap cetakan mendapat **QR unik** di bagian bawah struk (mode foto 4R: pojok kanan bawah).
1. Tamu scan QR pakai **kamera bawaan HP**, lalu halaman terbuka di Safari/Chrome.
2. Scan pertama: tamu **memilih video dari galeri HP-nya**, lalu video terkunci ke cetakan itu (tidak bisa diganti).
3. Scan berikutnya: **video langsung diputar** dari HP itu sendiri. Video tidak pernah di-upload ke mana pun.

Aktifkan per event: **Studio → Info event → Fitur tambahan → QR video (Living Photo)**.

**Hosting halaman (sekali saja):** halaman pemutarnya ada di folder `docs/v/` dan di-host gratis lewat GitHub Pages.
1. Push repo ke GitHub (lihat bagian Git di bawah).
2. Di GitHub: repo → **Settings → Pages** → Source: *Deploy from a branch* → Branch `main`, folder `/docs` → Save.
3. Tunggu ±1 menit. Halaman aktif di `https://mypropro.github.io/photobooth-thermal/v/` (repo harus *public* untuk GitHub Pages gratis).
4. Pakai domain/hosting sendiri? Upload isi folder `docs/v/` ke hosting **HTTPS**, lalu isi alamatnya:
   - bawaan produk (semua instalasi): `LIVING_BASE_URL` di `version.py`;
   - per mesin: `"living_base_url"` di `config.json`;
   - per event: Studio → kolom "Alamat halaman Living Photo".
   Urutan prioritas: event → config.json → version.py.

Catatan:
- Tamu harus scan dengan **kamera bawaan**, bukan scanner di dalam WhatsApp/Instagram/LINE (penyimpanannya terpisah, halaman akan memberi peringatan).
- Video diputar tanpa suara dulu (aturan browser HP), tap **"Tap for sound"** untuk suara.
- iPhone/Safari bisa menghapus data situs yang 7 hari tidak dibuka. Kalau terhapus, tamu cukup memilih video lagi.
- Video pendek (10–60 detik) paling aman. Video sangat besar bisa gagal disimpan, terutama di iPhone.

## Tema kiosk: warna, font & motif latar (Studio → Info event)
- **Preset warna**: Krem klasik, Gelap, Navy & emas, Pink pastel, Hijau sage. Setiap warna (latar, teks, kartu, tombol, teks tombol, aksen, printer) bisa diubah dengan color picker.
- **Font judul**: Modern, Elegan, Geometris, Tegas, Poster. Diambil dari folder `fonts/`, jadi tetap jalan offline.
- **Motif latar**: Polos, Titik, Garis, Kotak, Diagonal, Gelombang, Zigzag, Konfeti, Hati, Bintang, Bunga, Kamera. Warna motif ikut warna teks, dan kekuatannya bisa diatur.
- **Gambar latar sendiri** (PNG/JPG) dengan slider pudar, supaya tulisan tetap terbaca.
- Animasi foto/struk melayang di layar awal bisa dimatikan.
- Struk cetak tetap hitam-putih. Tema hanya mengubah tampilan layar kiosk.

## Slideshow TV

Buka **http://localhost:5000/slideshow** (atau `http://<IP-PC>:5000/slideshow` dari PC/TV lain) di layar besar, lalu klik sekali untuk layar penuh.
Foto event aktif tampil bergantian; foto baru langsung muncul dengan label *FOTO BARU!*.

## Penghitung kertas

Studio → *Printer & tablet* → *Kertas*: isi panjang roll (default 50 m). Setiap cetak dihitung otomatis.
Kiosk menampilkan *KERTAS HAMPIR HABIS* saat sisa ≤ 3 m (`paper_warn_m`). Setelah ganti roll klik *Ganti roll baru (reset)*.

## AdsBooth Studio (banyak event)

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

**PIN Studio wajib.** Saat Studio dibuka pertama kali dari perangkat yang menjalankan photobooth (`http://localhost:5000/studio`),
akan muncul layar **Buat PIN** (4-12 angka). PIN disimpan dalam bentuk hash, bukan teks biasa.
- Ganti PIN / keluar / "Studio hanya bisa dibuka dari perangkat ini": Studio → Printer & tablet → **Keamanan Studio**.
- 5x PIN salah = dikunci 5 menit.
- Lupa PIN / perangkat tanpa layar: jalankan `python app.py --set-pin 1234` di perangkat itu.

## Template Profil Sosial

Lima template bergaya halaman profil sosial generik (ikon digambar sendiri, tanpa nama atau logo merek apa pun), semua mendukung 1–4 foto:

| id | nama | isi |
|---|---|---|
| `sosmed` | Social Profile | avatar + Posts/Followers/Following, tombol Follow/Message, grid foto |
| `threads` | Text Feed | nama besar, avatar kanan, followers, satu postingan berisi foto |
| `xprofil` | Micro Profile | banner, avatar, Following/Followers, tab Posts, satu post berisi foto |
| `facebook` | Social Page | foto sampul, Add friend, satu postingan dengan Like/Comment/Share |
| `youtube` | Video Channel | banner, Subscribe, daftar thumbnail video + durasi |

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

## PC Ubuntu (mini PC / PC lama, mis. Intel i3)
Cocok untuk PC yang tidak kuat Windows 11. Pakai **Ubuntu Desktop 22.04 / 24.04 LTS**.
1. Install Ubuntu, sambungkan internet, salin folder `thermal-photobooth` ke home (mis. `~/thermal-photobooth`).
2. Buka Terminal di folder itu, lalu jalankan sekali:
   ```bash
   bash install-autostart.sh
   ```
   Skrip memasang Python, **Google Chrome** (bukan Chromium snap), CUPS untuk printer foto, izin printer thermal USB,
   server otomatis saat boot, kiosk layar penuh saat login, dan mematikan layar-mati/kunci layar.
3. **Settings → Users → Automatic Login** = ON, lalu `sudo reboot`.
4. Studio: `http://localhost:5000/studio` (atau dari laptop lain: `http://IP-PC:5000/studio`).
   - Printer thermal USB: Printer & tablet → "Raspberry Pi / Linux (USB, /dev/usb/lp0)" → Cetak tes.
   - Printer foto 4R: tambahkan dulu di CUPS (`http://localhost:631`), lalu pilih "Linux / Raspberry Pi: CUPS".
   - Kamera EMEET: Printer & tablet → Kamera → Deteksi kamera → pilih → Simpan. PC lama: pakai **1080p**.

Log server: `journalctl -u photobooth -f` · Restart: `sudo systemctl restart photobooth`.

## Lisensi (offline, per perangkat)

> Panduan lengkap untuk penjual (alur pelanggan, perpanjangan, masalah umum, rilis versi): **[PANDUAN-PENJUAL.md](PANDUAN-PENJUAL.md)**.

Setiap perangkat punya **ID perangkat** (mis. `AB-7KQ2-M9XD-4HTA-PZ3C`), terlihat di **Studio → ⚙ Printer & tablet → Lisensi**
dan di layar kunci kiosk. Kode lisensi hanya berlaku untuk ID itu.

| Status | Kiosk | Hasil cetak |
|---|---|---|
| Versi coba (7 hari pertama) | jalan, badge DEMO | ada tanda DEMO |
| Aktif | normal | normal |
| Masa tenggang (3 hari setelah habis) | normal, peringatan di Studio | normal |
| Habis / masa coba habis | terkunci (layar "Device not activated") | tidak bisa cetak |

Paket: `thermal` (struk), `photo` (foto 4R), `complete` (struk + foto 4R + Living Photo).
Living Photo bisa juga ditambahkan sebagai add-on (`--add living`).

**Khusus penjual (di PC sendiri, bukan di perangkat pelanggan):**

```bash
python license_admin.py init          # sekali saja: buat kunci, kunci publik otomatis masuk licensing.py
python license_admin.py issue --device AB-XXXX-XXXX-XXXX-XXXX --plan complete --name "Studio Ceria" --days 30
python license_admin.py issue --device AB-... --plan thermal --until 2027-01-31 --add living --out ceria.lic
python license_admin.py verify <kode>
```

- Kunci privat ada di `%USERPROFILE%\.adsbooth-license\` (Linux: `~/.adsbooth-license/`). **Backup folder itu.**
  Jangan di-commit, jangan dikirim. Kalau hilang, semua perangkat harus diupdate dengan kunci publik baru.
- Setelah `init`, commit perubahan `licensing.py` (isinya kunci publik, aman dibagikan).
- Semua kode yang diterbitkan tercatat di `issued.csv` di folder kunci.
- Langganan bulanan: terbitkan kode baru tiap periode (`--days 30`). Pelanggan tempel di Studio, langsung aktif.
- Jam PC mundur dideteksi (perangkat terkunci). Kode lisensi yang baru diterbitkan otomatis memulihkannya.
- `license_admin.py` tidak perlu ikut dikirim ke pelanggan (dibuang saat membuat installer).

## Membuat installer (untuk dijual)

> Langkah rilis lengkap: [PANDUAN-PENJUAL.md](PANDUAN-PENJUAL.md#5-membuat-installer--rilis-versi-baru).

Installer berisi program yang sudah **dikompilasi** (Nuitka): pelanggan tidak menerima file `.py`,
tidak perlu memasang Python, dan `license_admin.py` tidak ikut.

**Sebelum build pertama:** `python license_admin.py init` (kunci publik harus sudah terisi di `licensing.py`).
Naikkan `VERSION` di `version.py` setiap rilis.

### Windows → `dist\AdsBooth-Setup-<versi>.exe`
1. Pasang [Inno Setup 6](https://jrsoftware.org/isdl.php) (gratis).
2. Dobel klik `installer\build-windows.bat`. Kompilasi pertama 10-20 menit (Nuitka mengunduh compiler C sekali).

Hasil instalasi di PC pelanggan:
- Program di `C:\Program Files\AdsBooth`, data (config, event, foto tamu, lisensi) di `C:\ProgramData\AdsBooth`.
  Update = jalankan installer versi baru; data tidak tersentuh. Uninstall juga tidak menghapus data.
- Menu Start: **AdsBooth Kiosk**, **AdsBooth Studio**, **Hentikan AdsBooth**, **Folder data**.
- Pilihan saat instal: ikon desktop, kiosk otomatis saat Windows menyala, izin firewall untuk tablet.
- Browser kiosk: Chrome kalau ada, kalau tidak Microsoft Edge (selalu ada di Windows 10/11).
- Installer belum ditandatangani (code signing), jadi Windows SmartScreen akan menampilkan
  "Windows protected your PC" → klik **More info → Run anyway**.

### Ubuntu → `dist/adsbooth_<versi>_amd64.deb`
Build di Ubuntu 22.04 (hasilnya jalan di 22.04 & 24.04): `bash installer/build-linux.sh`

Di PC pelanggan:
```bash
sudo apt install ./adsbooth_1.0.0_amd64.deb
adsbooth-setup        # sebagai user desktop: server otomatis, kiosk otomatis, izin printer
```
Program di `/opt/adsbooth`, data di `~/.local/share/adsbooth`, server: `systemctl status adsbooth@<user>`.

### Perintah program terinstal
`adsbooth` (server + kiosk) · `adsbooth --studio` · `adsbooth --server` · `adsbooth --browser` ·
`adsbooth --set-pin 1234` · `adsbooth --version`

## Folder data & versi
Program dan data dipisah supaya update tidak menimpa data:
- **Folder program**: kode, `static/`, `fonts/` (boleh ditimpa saat update).
- **Folder data**: `config.json`, `events/`, `output/` (foto tamu, database), `certs/`, `logs/`.
  - Instalasi baru: Windows `C:\ProgramData\AdsBooth`, Linux `~/.local/share/adsbooth`.
  - **Mode portabel** (seperti sebelumnya): kalau di folder program sudah ada `config.json`/`events`/`output`, data tetap di folder program.
  - Bisa dipaksa ke folder lain dengan variabel `PHOTOBOOTH_DATA`.
- Lokasi folder data, versi aplikasi, dan tombol **Unduh log** ada di Studio → Printer & tablet → **Tentang**.
- Log: `logs/photobooth.log` (otomatis berputar, maks 5 file × 1 MB).
- Server memakai **Waitress** (stabil untuk jalan seharian); otomatis terpasang dari `requirements.txt`.

## Data & database

Semua data disimpan sebagai file (mudah dicadangkan/dipindah):

| Data | Lokasi |
|---|---|
| Pengaturan umum | `config.json` |
| Event, logo, frame | `events/<id>/` (`event.json`, `*.png`), event aktif: `events/active.txt` |
| Sesi tamu (foto, struk, info, tanda tangan) | `output/sessions/<kode>/` |
| Salinan semua struk | `output/prints/` |
| Nomor struk, undian, kertas | `output/counter.txt`, `output/draws/`, `output/paper.json` |

Tambahan **SQLite** (`output/photobooth.db`, bawaan Python, tanpa install) mencatat setiap sesi & undian untuk
**statistik** dan **ekspor CSV** (Studio → *Buku tamu, undian & statistik*). File tetap sumber utama:
kalau database dihapus, otomatis dibangun ulang dari `output/sessions/*/meta.json` saat server menyala.
Tabel: `sessions` (event, nomor, waktu, template, layout, gaya, pesan, undian, buku tamu, …) dan `draws`.

## Git: push & pull

Repo: `https://github.com/MyProPro/photobooth-thermal.git`

Yang **tidak** ikut Git (lihat `.gitignore`): `config.json`, `events/`, `output/` (foto tamu, struk, database), `.venv/`, `certs/`.
Jadi setelan printer & event di tiap perangkat aman saat `git pull`. Perangkat baru otomatis membuat `config.json` dari `config.example.json`.

### Pertama kali (dari PC Windows yang sudah berisi kode)
```bat
cd E:\Projects\Python\yt\thermal-photobooth
git init
git add .
git commit -m "Thermal photobooth 80mm"
git branch -M main
git remote add origin https://github.com/MyProPro/photobooth-thermal.git
git push -u origin main
```
Repo GitHub sudah berisi README/LICENSE dan push ditolak? Gabungkan dulu:
```bat
git pull origin main --allow-unrelated-histories --no-rebase
git push -u origin main
```
Kalau `config.json`/`events/` terlanjur ikut ter-commit sebelumnya, keluarkan dari Git (file di PC tidak dihapus):
```bat
git rm -r --cached config.json events
git commit -m "Lepas config & events dari Git"
git push
```

### Kirim perubahan berikutnya (push)
```bat
git add .
git commit -m "Tulis apa yang berubah"
git push
```

### Pasang di perangkat baru (clone)
```bash
git clone https://github.com/MyProPro/photobooth-thermal.git
cd photobooth-thermal
# Windows : run.bat
# Raspberry Pi : bash install-autostart.sh   (sekali), lalu sudo reboot
# Android (Termux): pkg install git -y lalu clone seperti di atas, bash setup-android.sh
```

### Ambil update terbaru (pull)
```bash
cd photobooth-thermal
git pull
```
Lalu restart server:
- Windows: tutup jendela server, jalankan `run.bat` (modul baru otomatis terpasang).
- Raspberry Pi: `bash run-linux.sh --setup && sudo systemctl restart photobooth`
- Android: hentikan server (Ctrl+C di Termux), jalankan lagi `bash start-android.sh`
  (kalau `requirements` berubah: `pip install flask qrcode python-escpos`).

`git pull` gagal karena ada file yang diubah di perangkat itu? Lihat dulu `git status`.
Untuk membuang perubahan lokal pada kode (bukan config/event): `git checkout -- <nama-file>` lalu `git pull` lagi.

### Memindahkan event ke perangkat lain
Event tidak ikut Git. Salin folder `events/<nama-event>/` ke folder `events/` di perangkat tujuan,
lalu aktifkan dari Studio.
