# AdsBooth - versi Android (APK)

Membungkus server AdsBooth (Python/Flask) ke dalam aplikasi Android memakai
Chaquopy, dengan WebView sebagai layar kiosk. Di-build otomatis oleh GitHub
Actions (lihat .github/workflows/android.yml) - tidak perlu Android Studio.

## Tahapan
- Tahap 1: APK bukti-konsep (Flask + WebView + kamera di tablet).
- Tahap 1b: menjalankan app.py AdsBooth penuh.
- Tahap 2 (SUDAH): Jembatan Kotlin UsbPrinterBridge (USB OTG) & cetak socket LAN/Wi-Fi (port 9100) untuk printer thermal ESC/POS (Epson TM-T82/X dan printer sejenis).
- Tahap 3: foreground service, kunci layar penuh, ikon, cegah keluar aplikasi.

## Cara ambil APK
1. Push perubahan di folder android/ ke GitHub.
2. Buka tab Actions di GitHub, tunggu build "Build Android APK" selesai.
3. Unduh artifact "adsbooth-debug-apk", ekstrak, dapat file .apk.
4. Pindahkan ke tablet, izinkan "Install from unknown sources", pasang.

## Versi yang dipakai (sesuaikan jika build gagal)
- Android Gradle Plugin 8.6.0, Gradle 8.9, Kotlin 2.0.21
- Chaquopy 16.0.0, Python 3.12, compileSdk 34, minSdk 26
