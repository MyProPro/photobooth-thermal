"""Versi aplikasi. Naikkan setiap rilis: MAJOR.MINOR.PATCH"""
VERSION = "1.0.0"
APP_NAME = "AdsBooth"

# Alamat bawaan halaman pemutar Living Photo (folder docs/v/ yang di-host statis).
# Ganti ke domain produk sendiri sebelum dijual, mis. "https://play.domainanda.com/v/".
# Bisa ditimpa tanpa ubah kode: config.json "living_base_url", atau per event di Studio.
# LIVING_BASE_URL = "https://mypropro.github.io/adsbooth/v/"
LIVING_BASE_URL = "https://adsbooth.my.id/v/"

# Alamat bawaan halaman unduh Softcopy foto (folder docs/d/ yang di-host statis / domain sendiri).
# Bisa ditimpa tanpa ubah kode: config.json "softcopy_base_url" atau "public_base_url".
SOFTCOPY_BASE_URL = "https://adsbooth.my.id/d/"
