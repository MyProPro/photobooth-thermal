// Cetak ke printer thermal USB yang dicolok ke tablet Android (kabel OTG) lewat WebUSB.
// Dipakai saat printer.type = "webusb". Server mengirim data ESC/POS (base64), file ini meneruskannya ke printer.
// Butuh Chrome di Android dan halaman dibuka lewat localhost atau HTTPS.
(function () {
  const supported = () => !!(navigator.usb && navigator.usb.requestDevice);
  let device = null;
  let out = null; // { iface, alt, ep }

  function pickEndpoint(dev) {
    let best = null;
    for (const iface of dev.configuration.interfaces) {
      for (const alt of iface.alternates) {
        const ep = alt.endpoints.find((e) => e.direction === 'out' && e.type === 'bulk');
        if (!ep) continue;
        const score = alt.interfaceClass === 7 ? 2 : (alt.interfaceClass === 255 ? 1 : 0); // 7 = printer
        if (!best || score > best.score) best = { iface: iface.interfaceNumber, alt: alt.alternateSetting, ep: ep.endpointNumber, score };
      }
    }
    return best;
  }

  async function prepare(dev) {
    if (!dev.opened) await dev.open();
    if (dev.configuration === null) await dev.selectConfiguration(1);
    const o = pickEndpoint(dev);
    if (!o) throw new Error('Printer endpoint (bulk OUT) not found');
    const iface = dev.configuration.interfaces.find((i) => i.interfaceNumber === o.iface);
    if (!iface.claimed) await dev.claimInterface(o.iface);
    if (o.alt) await dev.selectAlternateInterface(o.iface, o.alt);
    out = o;
    device = dev;
    return dev;
  }

  async function getDevice() {
    if (device && device.opened && out) return device;
    if (!supported()) throw new Error('This browser does not support WebUSB (use Chrome on Android)');
    const list = await navigator.usb.getDevices();
    if (!list.length) throw new Error('USB printer not connected. Tap "Connect USB printer".');
    return prepare(list[0]);
  }

  // Harus dipanggil dari klik (gesture) pengguna.
  async function connect() {
    if (!supported()) throw new Error('This browser does not support WebUSB (use Chrome on Android)');
    const dev = await navigator.usb.requestDevice({ filters: [] });
    await prepare(dev);
    return info();
  }

  function info() {
    if (!device) return null;
    return { name: [device.manufacturerName, device.productName].filter(Boolean).join(' ') || 'Printer USB',
             vendorId: device.vendorId, productId: device.productId };
  }

  async function paired() {
    if (!supported()) return null;
    if (device) return info();
    const list = await navigator.usb.getDevices();
    if (!list.length) return null;
    const d = list[0];
    return { name: [d.manufacturerName, d.productName].filter(Boolean).join(' ') || 'Printer USB',
             vendorId: d.vendorId, productId: d.productId };
  }

  function b64ToBytes(b64) {
    const bin = atob(b64);
    const u = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    return u;
  }

  async function writeBytes(bytes) {
    const dev = await getDevice();
    const CHUNK = 16384;
    for (let i = 0; i < bytes.length; i += CHUNK) {
      const r = await dev.transferOut(out.ep, bytes.subarray(i, i + CHUNK));
      if (r.status !== 'ok') throw new Error('Failed to send to printer: ' + r.status);
    }
  }

  // jobs: array base64 dari server
  async function printJobs(jobs) {
    for (const j of jobs || []) await writeBytes(b64ToBytes(j));
  }

  if (supported()) {
    navigator.usb.addEventListener('disconnect', (e) => { if (e.device === device) { device = null; out = null; } });
  }

  window.PBUSB = { supported, connect, paired, printJobs };
})();
