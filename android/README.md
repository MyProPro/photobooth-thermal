# AdsBooth - versi Android (APK)

Membungkus server AdsBooth (Python/Flask) ke dalam aplikasi Android memakai
Chaquopy, dengan WebView sebagai layar kiosk. Di-build otomatis oleh GitHub
Actions (lihat .github/workflows/android.yml) - tidak perlu Android Studio.

## Tahapan
- Tahap 1 (SEKARANG): APK bukti-konsep. Menjalankan Flask + halaman tes kamera.
  Membuktikan Chaquopy + Flask + WebView + kamera jalan di tablet.
- Tahap 1b: menjalankan app.py AdsBooth penuh (kiosk asli, belum cetak).
- Tahap 2: jembatan Kotlin USB OTG untuk cetak ke printer thermal USB.
- Tahap 3: foreground service, kunci layar penuh, ikon, cegah keluar aplikasi.

## Cara ambil APK
1. Push perubahan di folder android/ ke GitHub.
2. Buka tab Actions di GitHub, tunggu build "Build Android APK" selesai.
3. Unduh artifact "adsbooth-debug-apk", ekstrak, dapat file .apk.
4. Pindahkan ke tablet, izinkan "Install from unknown sources", pasang.

## Versi yang dipakai (sesuaikan jika build gagal)
- Android Gradle Plugin 8.6.0, Gradle 8.9, Kotlin 2.0.21
- Chaquopy 16.0.0, Python 3.12, compileSdk 34, minSdk 26
