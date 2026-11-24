// Cetak foto 4R ke printer LAN (Mopria / AirPrint / Epson / Canon, dll) lewat
// Android Print Framework. Aktif saat berjalan di APK AdsBooth; jembatan Kotlin:
// window.AndroidPhotoPrinter.printPhoto(url, copies, media, borderless).
(function () {
  const bridge = () => (typeof window.AndroidPhotoPrinter !== 'undefined') ? window.AndroidPhotoPrinter : null;
  const supported = () => !!bridge();

  // url    : URL gambar 4R di server lokal (mis. /api/session/<id>/print.jpg)
  // copies : jumlah salinan
  // media  : ukuran kertas ('4x6', 'A4', dsb) — dipetakan ke PrintAttributes di Kotlin
  // borderless : true untuk tanpa margin
  async function printPhoto(url, copies, media, borderless) {
    const b = bridge();
    if (!b) throw new Error('Cetak foto LAN hanya tersedia di aplikasi AdsBooth (APK).');
    const abs = new URL(url, location.origin).href;
    const raw = b.printPhoto(abs, String(copies || 1), String(media || '4x6'), !!borderless);
    let r = raw;
    if (typeof raw === 'string') { try { r = JSON.parse(raw); } catch (e) { r = { ok: raw === 'true' }; } }
    if (r === false || (r && r.ok === false)) {
      throw new Error((r && r.message) || 'Gagal membuka dialog cetak Android.');
    }
    return r || { ok: true };
  }

  window.PBPHOTO = { supported, printPhoto };
})();
