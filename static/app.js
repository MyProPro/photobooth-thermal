// AdsBooth — alur kiosk
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const SHOTS = { solo: 1, duo: 2, strip: 3, grid: 4 };

let CFG = { certTitles: [], features: {}, poses: [], cameraFacing: 'user', layouts: ['solo', 'duo', 'strip', 'grid'], defaultLayout: 'strip', eventVersion: '', templates: [], defaultTemplate: 'klasik', maxCopies: 2, countdown: 3, resetSeconds: 15, idleSeconds: 90, mirror: true, qr: true };
let S = {};
let stream = null;
let DUMMY = false, dummyIdx = 0;
const dummyImgs = [];
let current = 'welcome';
let idleTimer = null, resetTimer = null, styleTimer = null;
let skipCountdown = false, shooting = false;

function freshState() {
  S = { layout: CFG.defaultLayout || 'strip', copies: 1, style: (CFG.styles && CFG.styles[0].id) || 'dither', caption: '', showLogo: true,
        photos: [], lastPrint: null, printed: 0, template: CFG.defaultTemplate, photoVer: 0, tplKey: '',
        poses: [], guestbook: null, certTitle: '', pendingJobs: null,
        eventName: CFG.eventName || '', footer: CFG.footer || '',
        username: (CFG.social && CFG.social.username) || '', website: (CFG.social && CFG.social.website) || '',
        koranTitle: 'Kabar Booth',
        brightness: CFG.brightness !== undefined ? CFG.brightness : 1.0,
        retakeCount: 0 };
  if ($('#gbName')) { $('#gbName').value = ''; $('#gbMsg').value = ''; clearSign(); }
  $('#caption').value = '';
  $('#showLogo').checked = true;
  syncEditFields();
  renderOptions();
}

// ---------- navigasi ----------
function go(name) {
  $$('.screen').forEach((el) => el.classList.remove('active'));
  $('#s-' + name).classList.add('active');
  document.body.classList.toggle('dark', name === 'camera');
  document.body.classList.toggle('intro-on', name === 'welcome');
  if (name === 'welcome') startIntro(); else stopIntro();
  current = name;
  clearInterval(styleTimer); styleTimer = null;
  clearInterval(resetTimer); resetTimer = null;
  if (name === 'style') startStylePreview();
  if (name === 'review') { S.pendingJobs = null; renderReview(); }
  if (name === 'template') renderTemplates();
  if (name === 'guestbook') setTimeout(sizePad, 50);
  if (name === 'camera') { sizeViewfinder(); setTimeout(sizeViewfinder, 60); }
  if (name === 'done') startResetCountdown();
  bumpIdle();
}
$$('[data-go]').forEach((b) => b.addEventListener('click', () => go(b.dataset.go)));

function bumpIdle() {
  clearTimeout(idleTimer);
  if (['welcome', 'printing', 'camera', 'done'].includes(current)) return;
  idleTimer = setTimeout(() => resetAll(), CFG.idleSeconds * 1000);
}
['pointerdown', 'keydown'].forEach((ev) => document.addEventListener(ev, bumpIdle));

let pendingReload = false;
function resetAll() {
  if (pendingReload) { location.reload(); return; }
  freshState();
  initEditControls(); go('welcome');
}

// ---------- kamera ----------
function enableDummy(reason) {
  if (DUMMY) return;
  DUMMY = true;
  console.warn('Mode dummy aktif:', reason);
  for (let i = 0; i < 4; i++) { const im = new Image(); im.src = `/api/dummy/${i}.jpg`; dummyImgs.push(im); }
  $('#video').classList.add('hidden');
  $('#dummyView').classList.remove('hidden');
  $('#dummyBadge').classList.remove('hidden');
  showDummy(0);
}
function showDummy(i) {
  dummyIdx = i;
  if (DUMMY) $('#dummyView').src = `/api/dummy/${i % 4}.jpg`;
}

// Viewfinder mengikuti rasio asli kamera (potret / lanskap), jadi tidak gepeng
// dan yang terlihat = yang difoto. Dihitung ulang saat layar diputar.
function camRatio() {
  const v = $('#video'), d = $('#dummyView');
  if (DUMMY && d.naturalWidth) return d.naturalWidth / d.naturalHeight;
  if (v.videoWidth) return v.videoWidth / v.videoHeight;
  return 4 / 3;
}
function sizeViewfinder() {
  const wrap = $('#vfWrap');
  if (!wrap || !wrap.clientWidth) return;
  const ar = camRatio();
  const W = wrap.clientWidth, Hh = wrap.clientHeight;
  let w = W, h = W / ar;
  if (h > Hh) { h = Hh; w = Hh * ar; }
  const vf = wrap.querySelector('.viewfinder');
  vf.style.width = Math.floor(w) + 'px';
  vf.style.height = Math.floor(h) + 'px';
  $('#s-camera').style.setProperty('--ar', ar.toFixed(4));
}
['loadedmetadata', 'resize'].forEach((ev) => $('#video').addEventListener(ev, sizeViewfinder));
$('#dummyView').addEventListener('load', sizeViewfinder);
window.addEventListener('resize', () => setTimeout(sizeViewfinder, 120));
window.addEventListener('orientationchange', () => setTimeout(sizeViewfinder, 400));

async function startCamera() {
  if (stream || DUMMY) return true;
  if (CFG.dummyCamera || !(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)) {
    enableDummy('dummy_camera / browser tanpa kamera');
    return true;
  }
  // resolusi dari Studio (720 / 1080 / 4k) + kamera tertentu berdasarkan nama (mis. "EMEET")
  // '1080+4k' = preview 1080p, saat jepret pindah sebentar ke 4K
  const RES = { '720': [1280, 720], '1080': [1920, 1080], '4k': [3840, 2160], '1080+4k': [1920, 1080] }[CFG.cameraRes] || [1920, 1080];
  const video = { width: { ideal: RES[0] }, height: { ideal: RES[1] }, frameRate: { ideal: 30, min: 15 } };
  try {
    const want = (CFG.cameraLabel || '').trim().toLowerCase();
    if (want) {
      let cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
      if (cams.length && !cams[0].label) {            // nama kamera baru muncul setelah izin kamera diberikan
        const tmp = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        tmp.getTracks().forEach((t) => t.stop());
        cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
      }
      const cam = cams.find((d) => d.label.toLowerCase().includes(want));
      if (cam) video.deviceId = { exact: cam.deviceId };
      else console.warn('Kamera "' + CFG.cameraLabel + '" tidak ditemukan, pakai kamera bawaan');
    }
    if (!video.deviceId) video.facingMode = CFG.cameraFacing || 'user';
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video, audio: false });
    } catch (e1) {                                       // resolusi/kamera tidak didukung -> coba yang standar
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: CFG.cameraFacing || 'user' }, audio: false });
    }
    const st = stream.getVideoTracks()[0];
    console.info('Kamera:', st.label, st.getSettings && st.getSettings());
    $('#video').srcObject = stream;
    $('#video2').srcObject = stream;
    return true;
  } catch (e) {
    enableDummy(e.message);   // tidak ada kamera -> pakai foto contoh
    return true;
  }
}

function capture(maxW = 1280) {
  if (DUMMY) {
    const im = dummyImgs[dummyIdx % 4];
    if (!im || !im.complete || !im.naturalWidth) return null;
    const c = $('#cap');
    const scale = Math.min(1, maxW / im.naturalWidth);
    c.width = Math.round(im.naturalWidth * scale);
    c.height = Math.round(im.naturalHeight * scale);
    c.getContext('2d').drawImage(im, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', 0.9);
  }
  const v = $('#video2').videoWidth ? $('#video2') : $('#video');
  if (!v.videoWidth) return null;
  const scale = Math.min(1, maxW / v.videoWidth);
  const c = $('#cap');
  c.width = Math.round(v.videoWidth * scale);
  c.height = Math.round(v.videoHeight * scale);
  const ctx = c.getContext('2d');
  ctx.save();
  if (CFG.mirror) { ctx.translate(c.width, 0); ctx.scale(-1, 1); }
  ctx.drawImage(v, 0, 0, c.width, c.height);
  ctx.restore();
  return c.toDataURL('image/jpeg', 0.9);
}

async function api(path, body) {
  const r = await fetch(path, { method: body ? 'POST' : 'GET',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.ok === false) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}

// ---------- 1. sambutan ----------
// layar penuh + jangan biarkan layar tablet mati (mode kiosk)
let wakeLock = null;
async function kioskMode() {
  try {
    if (new URLSearchParams(location.search).has('kiosk') && document.fullscreenEnabled && !document.fullscreenElement) {
      await document.documentElement.requestFullscreen();
    }
  } catch (e) { /* abaikan */ }
  try { if ('wakeLock' in navigator && !wakeLock) wakeLock = await navigator.wakeLock.request('screen'); } catch (e) { /* abaikan */ }
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') wakeLock = null; });

// ---------- tema warna & font (dari Studio) ----------
const THEME_FONTS = {
  modern: "'Space Grotesk','Inter',sans-serif", elegan: "'PB Playfair',Georgia,serif",
  geometris: "'PB Josefin',sans-serif", tegas: "'PB Archivo',sans-serif", poster: "'PB Bebas',sans-serif",
};
function applyTheme(t) {
  const r = document.documentElement.style;
  if (!t || !t.paper) return;
  const set = (k, v) => { if (v) r.setProperty(k, v); };
  set('--paper', t.paper); set('--ink', t.text); set('--card', t.card); set('--btn', t.btn);
  set('--btn-text', t.btn_text); set('--accent', t.accent); set('--printer', t.printer);
  r.setProperty('--muted', `color-mix(in srgb, ${t.text} 72%, ${t.paper})`);
  r.setProperty('--line', `color-mix(in srgb, ${t.text} 35%, ${t.paper})`);
  set('--head-font', THEME_FONTS[t.font]);
}
// Motif latar: berlaku walau tema warna masih bawaan.
function applyBackground(t) {
  t = t || {};
  const b = document.body, pat = t.pattern || 'titik';
  b.className = b.className.replace(/\bpat-\S+/g, '').trim();
  b.classList.add(pat === 'polos' ? 'pat-off' : 'pat-on', 'pat-' + pat);
  b.classList.toggle('no-fl', t.floaters === false);
  document.documentElement.style.setProperty('--pat-alpha', (t.pattern_strength || 12) + '%');
  const ph = $('#bgPhoto');
  if (t.bg_image) {
    ph.style.backgroundImage = `url('/api/theme-bg/${encodeURIComponent(t.bg_image)}')`;
    document.documentElement.style.setProperty('--bg-dim', (t.bg_dim ?? 55) / 100);
  }
  b.classList.toggle('has-photo', !!t.bg_image);
}

// ---------- layar intro: foto -> dither -> printer -> struk ----------
let INTRO = null, introTimers = [], introIdx = 0, introOn = false;
async function loadIntro() {
  try {
    INTRO = await api('/api/intro');
    $('#introName').textContent = INTRO.eventName || '';
    $('#ipName').textContent = (INTRO.eventName || '').toUpperCase();
    $('#ipDate').textContent = INTRO.date;
    const hasLogo = !!INTRO.logo;
    $('#introLogo').classList.toggle('hidden', !hasLogo);
    if (hasLogo) {
      $('#introLogo').onload = () => fitIntro();
      $('#introLogo').src = INTRO.logo;
    }
    INTRO.photos.forEach((p) => { new Image().src = p.color; new Image().src = p.dither; });
  } catch (e) { INTRO = null; }
  fitIntro();
}
function stopIntro() {
  introOn = false;
  introTimers.forEach(clearTimeout); introTimers = [];
}
function introStyle() {
  const s = CFG.introStyle || 'auto';
  return s === 'auto' ? (CFG.output === 'photo' ? 'instan' : 'thermal') : s;
}
function introCycle() {
  if (!introOn) return;
  const sty = introStyle();
  $('#introStage').classList.toggle('hidden', sty !== 'thermal');
  $('#icStage').classList.toggle('hidden', sty !== 'instan');
  $('#isStage').classList.toggle('hidden', sty !== 'strip');
  if (sty === 'instan') return introInstant();
  if (sty === 'strip') return introStrip();
  const st = $('#introStage');
  const at = (ms, fn) => introTimers.push(setTimeout(() => { if (introOn) fn(); }, ms));
  const ph = INTRO && INTRO.photos.length ? INTRO.photos[introIdx++ % INTRO.photos.length] : null;
  st.className = 'intro-stage';
  fitIntro();
  const out = CFG.output === 'photo' && ph ? ph.color : ph && ph.dither;   // mode foto: hasilnya berwarna
  if (ph) { $('#ipColor').src = ph.color; $('#ipDither').src = out; $('#ipPrint').src = out; }
  // 1) foto asli + flash, ditahan  2) scan jadi dither  3) masuk printer  4) struk keluar
  at(250, () => { st.className = 'intro-stage p-in'; });
  at(3400, () => { st.className = 'intro-stage p-scan'; });
  at(5400, () => { st.className = 'intro-stage p-feed'; });
  at(6300, () => { st.className = 'intro-stage p-print'; });
  at(9200, () => { st.className = 'intro-stage p-hold'; });
  at(11900, () => { st.className = 'intro-stage p-out'; });
  at(12700, introCycle);
}
const introAt = (ms, fn) => introTimers.push(setTimeout(() => { if (introOn) fn(); }, ms));
function introPhoto(k = 0) {
  const ps = INTRO && INTRO.photos.length ? INTRO.photos : null;
  return ps ? ps[(introIdx + k) % ps.length].color : '';
}
// kamera instan: jepret -> flash -> foto keluar dari slot -> warna muncul perlahan
function introInstant() {
  const st = $('#icStage');
  st.className = 'intro-stage ic-stage';
  fitIntro();
  $('#icImg').src = introPhoto(); introIdx++;
  $('#icName').textContent = (INTRO && INTRO.eventName) || '';
  $('#icDate').textContent = (INTRO && INTRO.date) || '';
  introAt(300, () => { st.className = 'intro-stage ic-stage p-in'; });
  introAt(1500, () => { st.className = 'intro-stage ic-stage p-shot'; });
  introAt(2300, () => { st.className = 'intro-stage ic-stage p-eject'; });
  introAt(4300, () => { st.className = 'intro-stage ic-stage p-dev'; });
  introAt(9200, () => { st.className = 'intro-stage ic-stage p-hold'; });
  introAt(11000, () => { st.className = 'intro-stage ic-stage p-out'; });
  introAt(11800, introCycle);
}
// photo strip: hitung mundur 3-2-1, flash 3x, strip keluar dari slot
function introStrip() {
  const st = $('#isStage');
  st.className = 'intro-stage is-stage p-reset';
  fitIntro();
  const ph = [introPhoto(0), introPhoto(1), introPhoto(2)]; introIdx += 3;
  ['#isS1', '#isS2', '#isS3'].forEach((s, i) => { $(s).src = ph[i]; });
  $('#isName').textContent = (INTRO && INTRO.eventName) || '';
  $('#isDate').textContent = (INTRO && INTRO.date) || '';
  const flash = () => $('#isStage .is-flash').animate([{ opacity: 1 }, { opacity: 0 }], { duration: 550, easing: 'ease-out' });
  const shot = (i) => { flash(); $('#isView').src = ph[i]; $('#isShot').textContent = i + 1; $('#isCount').textContent = ''; };
  $('#isView').src = ph[0]; $('#isShot').textContent = 1; $('#isCount').textContent = '';
  introAt(300, () => { st.className = 'intro-stage is-stage'; });
  introAt(900, () => { $('#isCount').textContent = '3'; });
  introAt(1600, () => { $('#isCount').textContent = '2'; });
  introAt(2300, () => { $('#isCount').textContent = '1'; });
  introAt(3000, () => shot(0));
  introAt(3900, () => { $('#isCount').textContent = '1'; $('#isShot').textContent = 2; });
  introAt(4400, () => shot(1));
  introAt(5300, () => { $('#isCount').textContent = '1'; $('#isShot').textContent = 3; });
  introAt(5800, () => shot(2));
  introAt(6500, () => { st.className = 'intro-stage is-stage p-print'; });
  introAt(10000, () => { st.className = 'intro-stage is-stage p-hold'; });
  introAt(11600, () => { st.className = 'intro-stage is-stage p-out'; });
  introAt(12400, introCycle);
}

// latar intro: struk mini & polaroid melayang naik
function buildIntroBg() {
  const bg = $('#introBg');
  if (!bg || bg.dataset.ready) return;
  bg.dataset.ready = '1';
  const photoIntro = introStyle() !== 'thermal';
  const kinds = ['receipt', 'polaroid', 'dot', 'receipt', 'polaroid', 'receipt', 'dot', 'polaroid', 'receipt', 'polaroid', 'dot', 'receipt', 'polaroid', 'receipt', 'dot', 'polaroid'];
  kinds.forEach((k0, i) => {
    let k = k0;
    if (photoIntro && k === 'receipt') k = 'strip';
    const el = document.createElement('div');
    el.className = 'fl fl-' + k;
    if (k === 'strip') el.innerHTML = '<i></i><i></i><i></i>';
    if (k === 'receipt') el.innerHTML = '<i></i><i class="s"></i><b></b><i></i><i class="s"></i>';
    if (k === 'polaroid') el.innerHTML = '<b></b>';
    const lane = (i + 0.5) / kinds.length;                    // sebar merata kiri-kanan
    const scale = k === 'dot' ? 1 + Math.random() * 0.8 : 1 + Math.random() * 0.8;
    const dur = 22 + Math.random() * 16;
    el.style.left = `calc(${(lane * 100).toFixed(1)}% - 35px)`;
    el.style.setProperty('--d', dur.toFixed(1) + 's');
    el.style.setProperty('--delay', (-Math.random() * dur).toFixed(1) + 's');   // langsung tersebar saat mulai
    el.style.setProperty('--r0', (Math.random() * 40 - 20).toFixed(0) + 'deg');
    el.style.setProperty('--r1', (Math.random() * 80 - 40).toFixed(0) + 'deg');
    el.style.setProperty('--o', (k === 'dot' ? 0.55 : 0.55 + Math.random() * 0.3).toFixed(2));
    el.style.zoom = scale;
    bg.appendChild(el);
  });
}
function sizeIntroBg() {
  const bg = $('#introBg');
  if (bg) bg.style.setProperty('--travel', (bg.clientHeight + 460) + 'px');
}

function fitIntro() {
  buildIntroBg();
  sizeIntroBg();
  const box = $('#introFit');
  if (!box || !box.clientHeight || !box.clientWidth) return;
  // Berikan margin aman agar foto dan animasi intro tidak pernah menabrak logo/nama event di atas
  const availH = Math.max(60, box.clientHeight - 24);
  const availW = Math.max(60, box.clientWidth - 24);
  const k = Math.max(0.35, Math.min(availH / 690, availW / 440, 1.4));
  ['#introStage', '#icStage', '#isStage'].forEach((s) => {
    const el = $(s);
    if (el) el.style.transform = `scale(${k})`;
  });
}
window.addEventListener('resize', () => setTimeout(fitIntro, 60));
async function startIntro() {
  if (introOn) return;
  introOn = true;
  await loadIntro();
  fitIntro();
  introTimers.forEach(clearTimeout); introTimers = [];
  introCycle();
}
// seluruh layar awal bisa disentuh untuk mulai (kecuali tombol operator)
$('#s-welcome').addEventListener('click', (e) => {
  if (e.target.closest('#btnUsb') || e.target.closest('#btnStart')) return;
  $('#btnStart').click();
});

$('#btnStart').addEventListener('click', async () => {
  kioskMode();
  freshState();
  initEditControls();
  go('layout');
  startCamera();
});

// ---------- 2. layout ----------
function renderOptions() {
  const shown = [...$$('#layoutOptions .opt')].filter((b) => CFG.layouts.includes(b.dataset.layout));
  $('#layoutOptions').style.gridTemplateColumns = `repeat(${Math.max(1, shown.length)}, minmax(0, 1fr))`;
  $$('#layoutOptions .opt').forEach((b) => {
    b.classList.toggle('hidden', !CFG.layouts.includes(b.dataset.layout));
    const on = b.dataset.layout === S.layout;
    b.classList.toggle('on', on); b.setAttribute('aria-pressed', on);
  });
  $$('#styleOptions .opt').forEach((b) => {
    const on = b.dataset.style === S.style;
    b.classList.toggle('on', on); b.setAttribute('aria-pressed', on);
  });
  $('#copies').textContent = S.copies;
  $('#maxCopies').textContent = CFG.maxCopies;
  $('#styleTag').textContent = 'PREVIEW · ' + S.style.toUpperCase();
}
$$('#layoutOptions .opt').forEach((b) => b.addEventListener('click', () => {
  S.layout = b.dataset.layout; renderOptions();
  setTimeout(() => go('style'), 180);   // tap langsung lanjut
}));
$('#copyInc').addEventListener('click', () => { S.copies = Math.min(CFG.maxCopies, S.copies + 1); renderOptions(); });
$('#copyDec').addEventListener('click', () => { S.copies = Math.max(1, S.copies - 1); renderOptions(); });

// ---------- 3. gaya ----------
let styleBusy = false;
let currentSampleType = null;
// Tiap kartu gaya memakai contoh foto model statis (cewe/cowo acak) agar tajam dan kamera tidak lag
async function refreshStylePreview() {
  if (styleBusy || current !== 'style') return;
  styleBusy = true;
  try {
    const sample = Math.random() < 0.5 ? 'cewe' : 'cowo';
    const data = await api('/api/sample-styles?sample=' + sample);
    if (data && data.styles && current === 'style') {
      currentSampleType = data.sample;
      $$('#styleOptions .opt').forEach((b) => {
        let box = b.querySelector('.sthumb');
        if (!box) {
          box = document.createElement('div');
          box.className = 'sthumb';
          box.innerHTML = '<img alt="">';
          b.prepend(box);
        }
        const s = b.dataset.style;
        if (data.styles[s]) {
          box.querySelector('img').src = data.styles[s];
        }
      });
    }
  } catch (e) {
    console.warn('Gagal memuat sample style:', e);
  }
  styleBusy = false;
}
function startStylePreview() {
  $$('#styleOptions .opt').forEach((b) => {
    if (!b.querySelector('.sthumb')) {
      const d = document.createElement('div');
      d.className = 'sthumb';
      d.innerHTML = '<img alt="">';
      b.prepend(d);
    }
  });
  // Siapkan kamera di latar belakang untuk tahap foto berikutnya,
  // tanpa membebani kamera/jaringan dengan loop capture berkala
  startCamera();
  refreshStylePreview();
}
$('#styleOptions').addEventListener('click', (e) => {
  const b = e.target.closest('.opt');
  if (!b) return;
  S.style = b.dataset.style; renderOptions();
  setTimeout(startShooting, 180);   // tap langsung ke kamera
});

// Mode cetak foto 4R: ganti pilihan gaya & teks yang menyebut "struk".
function applyOutputMode() {
  const photo = CFG.output === 'photo';
  document.body.classList.toggle('mode-photo', photo);
  $$('[data-photo]').forEach((el) => {
    if (el.dataset.thermal === undefined) el.dataset.thermal = el.textContent;
    el.textContent = photo ? el.dataset.photo : el.dataset.thermal;
  });
  if (!window.__thermalStyles) window.__thermalStyles = $('#styleOptions').innerHTML;
  $('#styleOptions').innerHTML = photo && CFG.styles
    ? CFG.styles.map((s) => `<button class="opt sm" data-style="${s.id}"><b>${s.name}</b><span>${s.desc}</span></button>`).join('')
    : window.__thermalStyles;
}
$('#caption').addEventListener('input', (e) => { S.caption = e.target.value; });
$('#showLogo').addEventListener('change', (e) => { S.showLogo = e.target.checked; });

function startShooting() {
  const n = SHOTS[S.layout];
  S.photos = new Array(n).fill(null);
  shoot([...Array(n).keys()]);
}
$('#btnShoot').addEventListener('click', startShooting);

// ---------- 4. kamera ----------
function renderThumbs(activeIdx) {
  const n = SHOTS[S.layout];
  $('#thumbs').innerHTML = '';
  for (let i = 0; i < n; i++) {
    const d = document.createElement('div');
    if (S.photos[i] && i !== activeIdx) { d.className = 'done'; d.style.backgroundImage = `url(${S.photos[i]})`; }
    else if (i === activeIdx) { d.className = 'now'; d.textContent = 'NOW'; }
    else d.textContent = String(i + 1);
    $('#thumbs').appendChild(d);
  }
}

async function shoot(indices, next = 'template') {
  if (shooting) return;
  if (!(await startCamera())) return;
  shooting = true;
  go('camera');
  $('.viewfinder').classList.toggle('mirror', CFG.mirror);
  const n = SHOTS[S.layout];
  try {
    // tombol "Siap foto!" di tengah layar; setelah ditekan semua foto jalan otomatis
    showDummy(indices[0]);
    renderThumbs(-1);
    $('#shotLabel').textContent = indices.length > 1 ? `${indices.length} PHOTOS` : `PHOTO ${indices[0] + 1} OF ${n}`;
    $('#readySub').textContent = indices.length > 1
      ? `${indices.length} photos, automatic · ${CFG.countdown}s countdown each`
      : `${CFG.countdown} second countdown`;
    $('#readyDots').innerHTML = indices.length > 1 ? indices.map(() => '<i></i>').join('') : '';
    $('#btnReady').classList.remove('hidden');
    $('#btnShutter').classList.add('hidden');
    await new Promise((res) => {
      const h = () => { $('#btnReady').removeEventListener('click', h); res(); };
      $('#btnReady').addEventListener('click', h);
      const watch = setInterval(() => { if (current !== 'camera') { clearInterval(watch); h(); } }, 300);
      $('#btnReady').addEventListener('click', () => clearInterval(watch), { once: true });
    });
    $('#btnReady').classList.add('hidden');
    $('#btnShutter').classList.remove('hidden');
    if (current !== 'camera') return;
    for (const idx of indices) {
      if (current !== 'camera') return;
      $('#shotLabel').textContent = `PHOTO ${idx + 1} OF ${n}`;
      showDummy(idx);
      if (CFG.features.pose_challenge && CFG.poses.length) {
        const used = S.poses.filter(Boolean);
        const pool = CFG.poses.filter((x) => !used.includes(x));
        S.poses[idx] = (pool.length ? pool : CFG.poses)[Math.floor(Math.random() * (pool.length || CFG.poses.length))];
        $('#poseText').textContent = S.poses[idx];
        $('#poseBox').classList.remove('hidden');
      }
      renderThumbs(idx);
      skipCountdown = false;
      for (let t = CFG.countdown; t > 0 && !skipCountdown; t--) {
        $('#count').textContent = t;
        for (let k = 0; k < 10 && !skipCountdown; k++) await sleep(100);
        if (current !== 'camera') return;
      }
      $('#count').textContent = '';
      $('#poseBox').classList.add('hidden');
      S.photos[idx] = await snapPhoto();
      S.photoVer += 1;
      renderThumbs(-1);
      await sleep(Math.max(250, 900 - (CFG.shotReviewMs || 0)));
    }
    if (current === 'camera') go(next);
  } finally {
    shooting = false;
    $('#count').textContent = '';
  }
}
$('#btnShutter').addEventListener('click', () => { skipCountdown = true; });

// Jepret: flash putih -> (opsional) pindah ke 4K & ambil foto -> tampilkan hasil sebentar -> kembali ke preview.
const nextFrame = (v) => new Promise((res) => {
  if (v.requestVideoFrameCallback) v.requestVideoFrameCallback(() => res()); else setTimeout(res, 60);
});
async function waitFrames(v, n, maxMs) {
  const t0 = performance.now();
  for (let i = 0; i < n && performance.now() - t0 < maxMs; i++) {
    await Promise.race([nextFrame(v), sleep(120)]);
  }
}
async function snapPhoto() {
  const f = $('#flash'), rv = $('#shotReview');
  const maxW = CFG.output === 'photo' ? 3840 : 1600;
  f.classList.add('on');                                   // layar putih penuh (menutupi pergantian resolusi)
  let photo = null;
  const track = stream && !DUMMY && stream.getVideoTracks()[0];
  const hires = CFG.cameraRes === '1080+4k' && track && track.applyConstraints;
  if (hires) {
    const v = $('#video'), limit = CFG.hiresTimeoutMs || 1500, t0 = performance.now();
    try {
      await Promise.race([track.applyConstraints({ width: { ideal: 3840 }, height: { ideal: 2160 } }), sleep(limit)]);
      while (v.videoWidth < 2500 && performance.now() - t0 < limit) await sleep(40);
      if (v.videoWidth >= 2500) {
        await waitFrames(v, 4, Math.max(150, limit - (performance.now() - t0)));   // tunggu exposure stabil
        photo = capture(3840);
      }
    } catch (e) { console.warn('Gagal pindah ke 4K:', e); }
    console.info('Jepret', photo ? '4K' : '1080p (fallback)', Math.round(performance.now() - t0) + 'ms');
  }
  if (!photo) { await sleep(60); photo = capture(maxW); }
  // hasil jepretan tampil diam sebentar; di belakangnya kamera kembali ke 1080p
  const reviewMs = CFG.shotReviewMs || 0;
  if (reviewMs > 0 && photo) { rv.src = photo; rv.classList.remove('hidden'); }
  f.classList.remove('on');                                // flash memudar
  const back = hires
    ? Promise.race([track.applyConstraints({ width: { ideal: 1920 }, height: { ideal: 1080 } }).catch(() => {}), sleep(2500)])
    : Promise.resolve();
  await Promise.all([back, sleep(reviewMs)]);
  rv.classList.add('hidden');
  return photo;
}
$('#btnCancel').addEventListener('click', () => {
  skipCountdown = true;
  $('#btnReady').classList.add('hidden');
  $('#poseBox').classList.add('hidden');
  $('#count').textContent = '';
  go('style');
});

// ---------- 4b. pilih template ----------
function markTemplate() {
  $$('#tplList .tpl').forEach((b) => {
    const on = b.dataset.id === S.template;
    b.classList.toggle('on', on); b.setAttribute('aria-pressed', on);
  });
}
let tplSeq = 0;
async function renderTemplates() {
  const left = Math.max(0, 2 - (S.retakeCount || 0));
  const canRetake = left > 0;
  $('#btnTplRetake').disabled = !canRetake;
  $('#btnTplRetake').textContent = canRetake ? (left === 2 ? 'Retake' : `Retake (${left} left)`) : 'Retake (max 2x)';
  const key = [S.photoVer, S.layout, S.style, S.caption, S.showLogo].join('|');
  if (key === S.tplKey && $('#tplList .tpl')) { markTemplate(); setupCarousel(); return; }
  const seq = ++tplSeq;
  const list = $('#tplList');
  list.innerHTML = '<div class="loading mono">PREPARING TEMPLATES…</div>';
  $('#btnTplNext').disabled = true;
  let prep;
  try {
    prep = await api('/api/templates/prepare', payload());
  } catch (e) {
    list.innerHTML = '<div class="loading mono">FAILED TO LOAD TEMPLATES: ' + e.message + '</div>';
    return;
  }
  if (seq !== tplSeq) return;
  // kartu kosong dulu, gambar diisi begitu siap
  list.innerHTML = '';
  prep.templates.forEach((t) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'tpl';
    b.dataset.id = t.id;
    b.innerHTML = '<div class="tpl-img wait"><img alt="" class="hidden"><span class="mono">PREPARING…</span></div><b></b>';
    b.querySelector('img').alt = 'Template ' + t.name;
    b.querySelector('b').textContent = t.name;
    b.addEventListener('click', () => {
      if (carDrag.moved) return;           // geser, bukan tap
      S.template = t.id; markTemplate(); setTimeout(() => go('review'), 180);
    });
    list.appendChild(b);
  });
  if (!prep.templates.some((t) => t.id === S.template) && prep.templates.length) S.template = prep.templates[0].id;
  S.tplKey = key;
  markTemplate();
  setupCarousel();
  $('#btnTplNext').disabled = !prep.templates.length;
  // urutan render: yang terpilih dulu, lalu sesuai urutan tampil
  const queue = prep.templates.map((t) => t.id).sort((a, b) => (a === S.template ? -1 : b === S.template ? 1 : 0));
  const worker = async () => {
    while (queue.length && seq === tplSeq) {
      const id = queue.shift();
      try {
        const r = await fetch(`/api/templates/render?token=${prep.token}&id=${encodeURIComponent(id)}`);
        const j = await r.json();
        if (seq !== tplSeq) return;
        const card = $(`#tplList .tpl[data-id="${CSS.escape(id)}"]`);
        if (!card) continue;
        const box = card.querySelector('.tpl-img');
        if (r.ok) {
          const img = card.querySelector('img');
          img.src = j.image; img.classList.remove('hidden'); carQueue();
          box.classList.remove('wait'); box.querySelector('span').remove();
        } else {
          box.querySelector('span').textContent = 'FAILED';
        }
      } catch (e) { /* lanjut template berikutnya */ }
    }
  };
  const workers = Math.max(1, Math.min(CFG.renderWorkers || 3, queue.length));
  await Promise.all(Array.from({ length: workers }, worker));
}
$('#btnTplNext').addEventListener('click', () => go('review'));

// ---------- keyboard layar: popup + teks tampil saat diketik ----------
const VK_FIELDS = '#editKoranTitle,#editEventName,#editCaption,#editFooter,#editUsername,#editWebsite,#gbName,#gbMsg';
const VK_LAYOUTS = {
  abc: [['1','2','3','4','5','6','7','8','9','0'], ['q','w','e','r','t','y','u','i','o','p'],
        ['a','s','d','f','g','h','j','k','l','\''], ['{shift}','z','x','c','v','b','n','m','{bk}'],
        ['{cancel}','{sym}','@','{space}','.','!','{done}']],
  sym: [['1','2','3','4','5','6','7','8','9','0'], ['-','/',':',';','(',')','&','"','#','_'],
        ['?',',','+','=','*','%','~','<','>','♥'], ['★','☺','✿','✓','♪','$','€','{bk}'],
        ['{cancel}','{abc}','@','{space}','.','!','{done}']],
};
const VK = { el: null, val: '', orig: '', mode: 'abc', shift: false, caps: false, lastShift: 0 };
function vkLabelOf(el) {
  const lab = el.closest('label') || $(`label[for="${el.id}"]`);
  const t = lab && (lab.querySelector('span:not(.muted),b') || lab);
  return (t ? t.textContent : el.placeholder || 'Text').replace(/\(.*\)/, '').trim();
}
function vkRender() {
  const k = $('#vkKeys'), up = VK.shift || VK.caps;
  k.innerHTML = VK_LAYOUTS[VK.mode].map((row) => '<div class="vk-row">' + row.map((key) => {
    const sp = { '{shift}': ['⇧', 'wide fn' + (VK.caps ? ' on caps' : VK.shift ? ' on' : '')], '{bk}': ['⌫', 'wide fn'],
      '{space}': ['space', 'space'], '{done}': ['Done', 'wide done'], '{cancel}': ['Cancel', 'wide fn'],
      '{sym}': ['123', 'fn'], '{abc}': ['ABC', 'fn'] }[key];
    const label = sp ? sp[0] : (up ? key.toUpperCase() : key);
    return `<button type="button" class="vk-key ${sp ? sp[1] : ''}" data-k="${key.replace(/"/g, '&quot;')}">${label}</button>`;
  }).join('') + '</div>').join('');
}
function vkPaint() {
  const max = VK.el.maxLength > 0 ? VK.el.maxLength : 200;
  $('#vkText').textContent = VK.val;
  $('#vkPh').textContent = VK.val ? '' : (VK.el.placeholder || '');
  $('#vkCount').textContent = `${VK.val.length}/${max}`;
  $('#vkCount').classList.toggle('full', VK.val.length >= max);
  const d = $('#vkDisplay'); d.scrollLeft = d.scrollWidth;
}
function vkOpen(el) {
  Object.assign(VK, { el, val: el.value, orig: el.value, mode: 'abc', caps: false });
  VK.shift = !el.value;                       // huruf pertama otomatis kapital
  $('#vkLabel').textContent = vkLabelOf(el).toUpperCase();
  $('#vkDisplay').classList.toggle('multi', el.tagName === 'TEXTAREA');
  vkRender(); vkPaint();
  $('#vk').style.zoom = $('#app').style.zoom || 1;     // skala sama dengan tampilan kiosk
  $('#vk').classList.remove('hidden'); $('#vk').setAttribute('aria-hidden', 'false');
  requestAnimationFrame(() => $('#vk').classList.add('open'));
}
function vkClose(save) {
  if (!VK.el) return;
  VK.el.value = save ? VK.val : VK.orig;
  VK.el.dispatchEvent(new Event('input', { bubbles: true }));   // preview & state ikut diperbarui
  $('#vk').classList.remove('open');
  setTimeout(() => { $('#vk').classList.add('hidden'); $('#vk').setAttribute('aria-hidden', 'true'); }, 200);
  VK.el = null;
}
function vkPress(key) {
  const max = VK.el.maxLength > 0 ? VK.el.maxLength : 200;
  if (key === '{done}') return vkClose(true);
  if (key === '{cancel}') return vkClose(false);
  if (key === '{bk}') VK.val = VK.val.slice(0, -1);
  else if (key === '{shift}') {
    const now = Date.now();
    if (VK.caps) { VK.caps = false; VK.shift = false; }
    else if (VK.shift && now - VK.lastShift < 400) { VK.caps = true; }   // ketuk 2x = CAPS
    else VK.shift = !VK.shift;
    VK.lastShift = now; vkRender(); return;
  } else if (key === '{sym}' || key === '{abc}') { VK.mode = key === '{sym}' ? 'sym' : 'abc'; vkRender(); return; }
  else {
    const ch = key === '{space}' ? ' ' : ((VK.shift || VK.caps) ? key.toUpperCase() : key);
    if (VK.val.length >= max) return;
    VK.val += ch;
    if (VK.shift && !VK.caps) { VK.shift = false; vkRender(); }
  }
  VK.el.value = VK.val;          // kolom asli ikut terisi
  vkPaint();
}
(function initVK() {
  $$(VK_FIELDS).forEach((el) => {
    el.setAttribute('readonly', '');          // keyboard bawaan perangkat tidak muncul
    el.setAttribute('inputmode', 'none');
    el.classList.add('vk-field');
    el.addEventListener('pointerdown', (e) => { e.preventDefault(); vkOpen(el); });
    el.addEventListener('focus', () => { el.blur(); });
  });
  $('#vkKeys').addEventListener('pointerdown', (e) => {
    const b = e.target.closest('.vk-key');
    if (!b) return;
    e.preventDefault();
    b.classList.add('down'); setTimeout(() => b.classList.remove('down'), 120);
    vkPress(b.dataset.k);
    bumpIdle();
  });
  $('#vk').addEventListener('pointerdown', (e) => { if (e.target.id === 'vk') vkClose(true); });   // tap di luar = simpan
  document.addEventListener('keydown', (e) => {          // keyboard fisik tetap bisa dipakai
    if (!VK.el) return;
    if (e.key === 'Enter') vkClose(true);
    else if (e.key === 'Escape') vkClose(false);
    else if (e.key === 'Backspace') vkPress('{bk}');
    else if (e.key.length === 1) {
      const max = VK.el.maxLength > 0 ? VK.el.maxLength : 200;
      if (VK.val.length < max) { VK.val += e.key; VK.el.value = VK.val; vkPaint(); }
    }
    else return;
    e.preventDefault();
  });
})();

// ---------- carousel template: geser / panah, kartu tengah membesar ----------
const carDrag = { on: false, x: 0, sl: 0, moved: false };
let carRaf = 0;
function carCards() { return [...$$('#tplList .tpl')]; }
function carSize() {
  const list = $('#tplList');
  if (!list || !list.clientHeight) return;
  const h = list.clientHeight - 24;
  const ratio = CFG.output === 'photo' ? 0.68 : 0.52;
  const w = Math.min(h * ratio, list.clientWidth * 0.62);
  list.style.setProperty('--cw', Math.round(w) + 'px');
  list.style.setProperty('--ch', Math.round(h) + 'px');
}
function carCenterIdx() {
  const list = $('#tplList'), mid = list.scrollLeft + list.clientWidth / 2;
  let best = 0, bd = Infinity;
  carCards().forEach((c, i) => { const d = Math.abs(c.offsetLeft + c.offsetWidth / 2 - mid); if (d < bd) { bd = d; best = i; } });
  return best;
}
function carPaint() {
  carRaf = 0;
  const list = $('#tplList'), cards = carCards();
  if (!cards.length) return;
  const mid = list.scrollLeft + list.clientWidth / 2;
  cards.forEach((c) => {
    const d = Math.min(1, Math.abs(c.offsetLeft + c.offsetWidth / 2 - mid) / (c.offsetWidth * 1.1));
    c.style.transform = `scale(${(1 - 0.16 * d).toFixed(3)})`;
    c.style.opacity = (1 - 0.45 * d).toFixed(2);
    c.classList.toggle('center', d < 0.25);
  });
  const i = carCenterIdx();
  $('#tplName').textContent = cards[i].querySelector('b').textContent;
  $('#tplCount').textContent = `${i + 1} / ${cards.length}`;
  $('#tplPrev').classList.toggle('off', i === 0);
  $('#tplNext').classList.toggle('off', i === cards.length - 1);
}
function carQueue() { if (!carRaf) carRaf = requestAnimationFrame(carPaint); }
function carGo(i, smooth = true) {
  const list = $('#tplList'), cards = carCards();
  if (!cards.length) return;
  i = Math.max(0, Math.min(cards.length - 1, i));
  const c = cards[i];
  list.scrollTo({ left: c.offsetLeft + c.offsetWidth / 2 - list.clientWidth / 2, behavior: smooth ? 'smooth' : 'auto' });
}
function setupCarousel() {
  carSize();
  const idx = Math.max(0, carCards().findIndex((c) => c.dataset.id === S.template));
  requestAnimationFrame(() => { carGo(idx, false); carPaint(); });
}
(function initCarousel() {
  const list = $('#tplList');
  list.addEventListener('scroll', carQueue, { passive: true });
  $('#tplPrev').addEventListener('click', () => carGo(carCenterIdx() - 1));
  $('#tplNext').addEventListener('click', () => carGo(carCenterIdx() + 1));
  // geser pakai mouse (layar sentuh sudah otomatis)
  list.addEventListener('pointerdown', (e) => {
    if (e.pointerType !== 'mouse') { carDrag.moved = false; return; }
    Object.assign(carDrag, { on: true, x: e.clientX, sl: list.scrollLeft, moved: false });
    list.classList.add('dragging');
  });
  window.addEventListener('pointermove', (e) => {
    if (!carDrag.on) return;
    const dx = e.clientX - carDrag.x;
    if (Math.abs(dx) > 8) carDrag.moved = true;
    list.scrollLeft = carDrag.sl - dx / (parseFloat($('#app').style.zoom) || 1);
  });
  window.addEventListener('pointerup', () => {
    if (!carDrag.on) return;
    carDrag.on = false; list.classList.remove('dragging');
    if (carDrag.moved) { carGo(carCenterIdx()); setTimeout(() => { carDrag.moved = false; }, 50); }
  });
  window.addEventListener('resize', () => { if (current === 'template') setTimeout(setupCarousel, 150); });
  document.addEventListener('keydown', (e) => {
    if (current !== 'template') return;
    if (e.key === 'ArrowLeft') carGo(carCenterIdx() - 1);
    if (e.key === 'ArrowRight') carGo(carCenterIdx() + 1);
  });
})();
$('#btnTplRetake').addEventListener('click', () => {
  if ((S.retakeCount || 0) >= 2) return;
  S.retakeCount = (S.retakeCount || 0) + 1;
  S.photos = new Array(SHOTS[S.layout]).fill(null);
  shoot([...Array(SHOTS[S.layout]).keys()], 'template');
});

// ---------- 5. review ----------
function payload() {
  return { layout: S.layout, style: S.style, caption: S.caption, showLogo: S.showLogo,
           copies: S.copies, template: S.template, photos: S.photos.filter(Boolean),
           poses: S.poses.slice(0, SHOTS[S.layout]), guestbook: S.guestbook, certTitle: S.certTitle,
           event_name: S.eventName, footer: S.footer, username: S.username, website: S.website,
           newspaper_name: S.koranTitle, koran_title: S.koranTitle,
           brightness: S.brightness, lucky: S.lucky };
}
function renderCertPick() {
  const on = S.template === 'sertifikat' && CFG.certTitles.length;
  $('#certPick').classList.toggle('hidden', !on);
  if (!on) return;
  if (!S.certTitle) S.certTitle = CFG.certTitles[Math.floor(Math.random() * CFG.certTitles.length)];
  const box = $('#certChips');
  box.innerHTML = '';
  const dice = document.createElement('button');
  dice.type = 'button'; dice.className = 'chip dice'; dice.textContent = 'Random';
  dice.addEventListener('click', () => {
    const others = CFG.certTitles.filter((t) => t !== S.certTitle);
    S.certTitle = others[Math.floor(Math.random() * others.length)] || S.certTitle;
    renderCertPick(); renderPreview();
  });
  box.appendChild(dice);
  CFG.certTitles.forEach((t) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip' + (t === S.certTitle ? ' on' : '');
    b.textContent = t.split('|')[0].trim();
    b.addEventListener('click', () => { S.certTitle = t; renderCertPick(); renderPreview(); });
    box.appendChild(b);
  });
}

let pvSeq = 0;
async function renderPreview() {
  const seq = ++pvSeq;
  $('#previewLoading').classList.remove('hidden');
  $('#btnPrint').disabled = true;
  try {
    const j = await api('/api/preview', payload());
    if (seq !== pvSeq) return;
    if (j.lucky) S.lucky = j.lucky;   // nomor undian acak: sama antara preview & cetak
    $('#receiptPreview').src = j.image;
  } catch (e) {
    $('#previewLoading').textContent = 'PREVIEW FAILED: ' + e.message;
    return;
  }
  $('#previewLoading').classList.add('hidden');
  $('#btnPrint').disabled = false;
}

let editDebounce = null;
function schedulePreview() {
  clearTimeout(editDebounce);
  editDebounce = setTimeout(() => {
    renderPreview();
  }, 350);
}

function updateEditFieldsForTemplate() {
  const tpl = S.template || 'klasik';
  const isKoran = tpl === 'koran';
  const isSocial = ['sosmed', 'threads', 'xprofil', 'facebook', 'youtube'].includes(tpl);
  const isCustom = tpl.startsWith('c:');
  const isPhoto = CFG.output === 'photo';

  // 1. Teks penutup (footer): hanya ada jika template benar-benar mencetak footer
  const showFooter = isPhoto || isCustom || tpl === 'klasik';
  $('#fieldFooter')?.classList.toggle('hidden', !showFooter);

  // 2. Sosmed: username & website
  $('#fieldSocial')?.classList.toggle('hidden', !isSocial);

  // 3. Khusus Koran: Nama Koran ("Kabar Booth")
  $('#fieldKoranTitle')?.classList.toggle('hidden', !isKoran);

  // 4. Nama Event: hampir semua template menampilkannya kecuali komik & sertifikat
  const hideEvent = ['komik', 'sertifikat'].includes(tpl);
  $('#fieldEventName')?.classList.toggle('hidden', hideEvent);

  // 5. Pesan / Headline:
  const noCaption = ['pass', 'kalender', 'cocok'].includes(tpl);
  $('#fieldCaption')?.classList.toggle('hidden', noCaption);
  if ($('#labelCaption')) {
    $('#labelCaption').textContent = isKoran ? 'Newspaper headline' : 'Caption under photo';
  }
  if ($('#editCaption')) {
    $('#editCaption').placeholder = isKoran ? 'GUEST CAUGHT ON CAMERA BEING HAPPY' : 'Write a short message…';
  }
}

function syncEditFields() {
  updateEditFieldsForTemplate();
  if ($('#editKoranTitle')) $('#editKoranTitle').value = S.koranTitle || 'Kabar Booth';
  if ($('#editEventName')) $('#editEventName').value = S.eventName || '';
  if ($('#editCaption')) $('#editCaption').value = S.caption || '';
  if ($('#editFooter')) $('#editFooter').value = S.footer || '';
  if ($('#editUsername')) $('#editUsername').value = S.username || '';
  if ($('#editWebsite')) $('#editWebsite').value = S.website || '';
  if ($('#editBrightness')) {
    const b = S.brightness !== undefined ? S.brightness : 1.0;
    $('#editBrightness').value = b;
    if ($('#valBright')) $('#valBright').textContent = Math.round(b * 100) + '%';
  }
}

let editControlsInit = false;
function initEditControls() {
  if (editControlsInit) return;
  editControlsInit = true;
  $('#editKoranTitle')?.addEventListener('input', (e) => {
    S.koranTitle = e.target.value;
    schedulePreview();
  });
  $('#editCaption')?.addEventListener('input', (e) => {
    S.caption = e.target.value;
    if ($('#caption')) $('#caption').value = e.target.value;
    schedulePreview();
  });
  $('#editEventName')?.addEventListener('input', (e) => {
    S.eventName = e.target.value;
    schedulePreview();
  });
  $('#editFooter')?.addEventListener('input', (e) => {
    S.footer = e.target.value;
    schedulePreview();
  });
  $('#editUsername')?.addEventListener('input', (e) => {
    S.username = e.target.value;
    schedulePreview();
  });
  $('#editWebsite')?.addEventListener('input', (e) => {
    S.website = e.target.value;
    schedulePreview();
  });
  $('#editBrightness')?.addEventListener('input', (e) => {
    S.brightness = parseFloat(e.target.value);
    if ($('#valBright')) $('#valBright').textContent = Math.round(S.brightness * 100) + '%';
    schedulePreview();
  });
  $('#btnResetEdit')?.addEventListener('click', () => {
    S.eventName = CFG.eventName || '';
    S.footer = CFG.footer || '';
    S.username = (CFG.social && CFG.social.username) || '';
    S.website = (CFG.social && CFG.social.website) || '';
    S.koranTitle = 'Kabar Booth';
    S.caption = $('#caption') ? $('#caption').value : '';
    S.brightness = CFG.brightness !== undefined ? CFG.brightness : 1.0;
    syncEditFields();
    renderPreview();
  });
}

async function renderReview() {
  const left = Math.max(0, 2 - (S.retakeCount || 0));
  const canRetake = left > 0;
  const quotaEl = $('#retakeQuota');
  if (quotaEl) {
    quotaEl.textContent = canRetake ? `Retake: ${left} of 2 left` : 'Retake: limit 2x reached';
    quotaEl.classList.toggle('quota-exhausted', !canRetake);
  }
  const list = $('#shotList');
  list.innerHTML = '';
  S.photos.forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'shot';
    row.innerHTML = `<img alt=""><b>Photo ${i + 1}</b><button type="button"${canRetake ? '' : ' disabled'}>Retake</button>`;
    row.querySelector('img').src = p || '';
    if (canRetake) {
      row.querySelector('button').addEventListener('click', () => {
        if ((S.retakeCount || 0) >= 2) return;
        S.retakeCount = (S.retakeCount || 0) + 1;
        shoot([i], 'review');
      });
    }
    list.appendChild(row);
  });
  $('#btnRetakeAll').disabled = !canRetake;
  $('#btnRetakeAll').textContent = canRetake
    ? (left === 2 ? 'Retake all photos (max 2x)' : `Retake all photos (${left} left)`)
    : 'Retake all photos (max 2x reached)';
  renderCertPick();
  syncEditFields();
  await renderPreview();
}
$('#btnRetakeAll').addEventListener('click', () => {
  if ((S.retakeCount || 0) >= 2) return;
  S.retakeCount = (S.retakeCount || 0) + 1;
  S.photos = new Array(SHOTS[S.layout]).fill(null);
  shoot([...Array(SHOTS[S.layout]).keys()]);
});

// ---------- 6. mencetak ----------
async function doPrint() {
  go('printing');
  $('#printError').classList.add('hidden');
  let pct = 0;
  const setPct = (v) => { pct = v; $('#pct').textContent = v + '%'; $('#bar').style.width = v + '%';
    $('#paperOut').style.height = (30 + v * 3) + 'px'; };
  setPct(0);
  $('#printStatus').textContent = 'Please wait a moment';
  const anim = setInterval(() => { if (pct < 90) setPct(pct + 3); }, 200);
  try {
    let j;
    if (S.pendingJobs) {
      j = S.lastPrint;               // data sudah dibuat, tinggal kirim ulang ke printer USB
    } else {
      j = await api('/api/print', payload());
      S.lastPrint = j;
    }
    if (j.jobs && j.jobs.length) {   // mode printer USB di tablet (WebUSB)
      S.pendingJobs = j.jobs;
      $('#printStatus').textContent = 'Sending to printer…';
      await PBUSB.printJobs(j.jobs);
      S.pendingJobs = null;
    }
    clearInterval(anim);
    setPct(100);
    S.printed = S.copies;
    $('#printStatus').textContent = 'Done! Cutting the paper.';
    await sleep(900);
    go('done');
  } catch (e) {
    clearInterval(anim);
    $('#printErrorMsg').textContent = e.message;
    $('#btnUsbErr').classList.toggle('hidden', CFG.printerMode !== 'webusb');
    $('#printError').classList.remove('hidden');
    $('#printStatus').textContent = 'There’s a problem with the printer.';
  }
}
$('#btnPrint').addEventListener('click', () => {
  if (CFG.features.guestbook) go('guestbook'); else doPrint();
});
$('#btnRetryPrint').addEventListener('click', doPrint);

// ---------- printer USB di tablet (WebUSB) ----------
async function usbConnect() {
  try {
    const d = await PBUSB.connect();
    pollStatus();
    return d;
  } catch (e) {
    if (e.name !== 'NotFoundError') alert('Could not connect the printer: ' + e.message);
    return null;
  }
}
$('#btnUsb').addEventListener('click', usbConnect);
$('#btnUsbErr').addEventListener('click', async () => { if (await usbConnect()) doPrint(); });

// ---------- 5b. buku tamu ----------
const pad = $('#gbSign');
let padCtx = null, drawing = false, signed = false;
function sizePad() {
  const r = pad.getBoundingClientRect();
  if (!r.width) return;
  pad.width = Math.round(r.width * 2); pad.height = Math.round(r.height * 2);
  padCtx = pad.getContext('2d');
  padCtx.lineWidth = 7; padCtx.lineCap = 'round'; padCtx.lineJoin = 'round'; padCtx.strokeStyle = '#121212';
  signed = false;
}
function clearSign() { if (padCtx) padCtx.clearRect(0, 0, pad.width, pad.height); signed = false; }
function padPos(e) {
  const r = pad.getBoundingClientRect();
  return [(e.clientX - r.left) * pad.width / r.width, (e.clientY - r.top) * pad.height / r.height];
}
pad.addEventListener('pointerdown', (e) => {
  if (!padCtx) sizePad();
  drawing = true; pad.setPointerCapture(e.pointerId);
  const [x, y] = padPos(e); padCtx.beginPath(); padCtx.moveTo(x, y); padCtx.lineTo(x + 0.1, y + 0.1); padCtx.stroke();
  signed = true;
});
pad.addEventListener('pointermove', (e) => {
  if (!drawing) return;
  const [x, y] = padPos(e); padCtx.lineTo(x, y); padCtx.stroke();
});
['pointerup', 'pointercancel'].forEach((t) => pad.addEventListener(t, () => { drawing = false; }));
$('#gbClear').addEventListener('click', clearSign);
$('#gbSkip').addEventListener('click', () => { S.guestbook = null; doPrint(); });
$('#gbPrint').addEventListener('click', () => {
  const name = $('#gbName').value.trim(), message = $('#gbMsg').value.trim();
  S.guestbook = (name || message || signed) ? { name, message, signature: signed ? pad.toDataURL('image/png') : null } : null;
  doPrint();
});

// ---------- 7. selesai ----------
function startResetCountdown() {
  const j = S.lastPrint || {};
  $('#luckyBox').classList.toggle('hidden', !j.lucky);
  if (j.lucky) $('#luckyNum').textContent = j.lucky;
  $('#qrCard').classList.toggle('hidden', !j.qr);
  if (j.qr) $('#qrImg').src = j.qr;
  const left = CFG.maxCopies - S.printed;
  $('#btnReprint').disabled = left <= 0;
  $('#btnReprint').textContent = left > 0 ? `Print again (${left}×)` : 'Print again';
  let secs = CFG.resetSeconds;
  $('#resetSecs').textContent = secs;
  resetTimer = setInterval(() => {
    secs -= 1;
    $('#resetSecs').textContent = secs;
    if (secs <= 0) resetAll();
  }, 1000);
}
$('#btnFinish').addEventListener('click', resetAll);
$('#btnReprint').addEventListener('click', async () => {
  if (!S.lastPrint || S.printed >= CFG.maxCopies) return;
  $('#btnReprint').disabled = true;
  try {
    const r = await api('/api/reprint/' + S.lastPrint.id, {});
    if (r.jobs && r.jobs.length) await PBUSB.printJobs(r.jobs);
    S.printed += 1;
  } catch (e) { alert('Reprint failed: ' + e.message); }
  clearInterval(resetTimer);
  startResetCountdown();
});

// ---------- status printer ----------
async function pollStatus() {
  try {
    const r = await fetch('/api/status');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const s = await r.json();
    // Event diganti dari Studio -> muat ulang kiosk (langsung kalau sedang di layar awal)
    if (s.eventVersion && CFG.eventVersion && s.eventVersion !== CFG.eventVersion) {
      if (current === 'welcome') { location.reload(); return; }
      pendingReload = true;
    }
    const low = CFG.output !== 'photo' && s.paper && s.paper.low;
    const pill = $('#introStatus');
    const problem = !s.ok ? 'PRINTER NOT CONNECTED' : (low ? 'PAPER LOW' : '');
    pill.textContent = problem; pill.classList.toggle('hidden', !problem);
    if (s.mode === 'webusb') {
      const d = await PBUSB.paired().catch(() => null);
      $('#btnUsb').classList.toggle('hidden', !!d);
      if (!d) {
        $('#introStatus').textContent = 'USB PRINTER NOT CONNECTED'; $('#introStatus').classList.remove('hidden');
        $('#statusDot').className = 'dot warn';
        $('#statusText').textContent = PBUSB.supported() ? 'USB PRINTER NOT CONNECTED' : 'BROWSER DOES NOT SUPPORT USB';
        return;
      }
    } else {
      $('#btnUsb').classList.add('hidden');
    }
    $('#statusDot').className = 'dot ' + (!s.ok ? 'bad' : (low ? 'warn' : 'ok'));
    $('#statusText').textContent = !s.ok ? 'PRINTER NOT CONNECTED'
      : (low ? `PAPER LOW (${s.paper.left_m} m)` : (s.mode === 'file' ? 'TEST MODE (NO PRINTER)' : 'PRINTER READY'));
    $('#statusText').title = s.message || '';
  } catch (e) {
    $('#statusDot').className = 'dot bad';
    $('#statusText').textContent = 'SERVER NOT CONNECTED';
  }
}

// ---------- skala layar (tablet / TV vertikal 24") ----------
// Desain dasar 768 px lebar (portrait). Di 1080x1920 semua diperbesar ~1.4x,
// tinggi sisa dipakai elemen yang fleksibel. Landscape: dibatasi tinggi min 900.
function fitScreen() {
  const W = window.innerWidth, H = window.innerHeight;
  const app = $('#app');
  const apply = (z) => {
    app.style.zoom = z;
    app.style.width = (W / z) + 'px';
    app.style.height = (H / z) + 'px';
  };
  const base = W < H ? 768 : 1024;
  let s = Math.max(0.5, W / base);
  apply(s);
  // Ukur layar yang paling tinggi; kalau ada yang tidak muat, perkecil skala.
  const screens = [...document.querySelectorAll('.screen')];
  const active = document.querySelector('.screen.active');
  const topbar = document.querySelector('.topbar').offsetHeight;
  let need = 0;
  screens.forEach((el) => {
    screens.forEach((x) => x.classList.remove('active'));
    el.classList.add('active');
    need = Math.max(need, el.scrollHeight + topbar);
  });
  screens.forEach((x) => x.classList.remove('active'));
  if (active) active.classList.add('active');
  if (need > H / s) apply(Math.max(0.5, H / (need + 8)));
}
window.addEventListener('resize', fitScreen);
window.addEventListener('orientationchange', fitScreen);
fitScreen();

// ---------- lisensi ----------
const LIC_TEXT = {
  trial_over: ['Trial period has ended', 'Enter a license code in Studio to keep printing.'],
  expired: ['License has expired', 'Please renew your subscription to keep printing.'],
  clock: ['System clock is incorrect', 'Fix the date & time on this device, then restart the photobooth.'],
};
function applyLicense(L) {
  if (!L) return;
  $('#demoBadge').classList.toggle('hidden', !L.demo);
  const locked = !L.ok || !!L.blocked;
  $('#licLock').classList.toggle('hidden', !locked);
  if (!locked) return;
  let [title, text] = LIC_TEXT[L.state] || ['Device not activated', 'Please contact your provider to activate this photobooth.'];
  if (L.ok && L.blocked) {
    title = 'Mode not included';
    text = CFG.output === 'photo' ? 'This license does not include 4R photo printing.' : 'This license does not include thermal receipt printing.';
  }
  $('#licTitle').textContent = title;
  $('#licText').textContent = text;
  $('#licId').textContent = L.deviceId || '-';
}

// ---------- init ----------
(async function init() {
  try {
    const c = await api('/api/config');
    CFG = Object.assign(CFG, c);
    S.template = CFG.defaultTemplate;
    applyOutputMode();
    applyTheme(CFG.theme);
    applyBackground(CFG.theme);
    $('#eventName').textContent = c.eventName;
    applyLicense(c.license);
  } catch (e) { console.warn(e); }
  freshState();
  initEditControls();
  document.body.classList.add('intro-on');
  startIntro();
  pollStatus();
  setInterval(pollStatus, 15000);
  // Mode kiosk hanya kalau dibuka dengan ?kiosk=1 (run.bat). Di browser biasa klik kanan tetap bisa.
  if (new URLSearchParams(location.search).has('kiosk')) {
    document.body.classList.add('kiosk');
    document.addEventListener('contextmenu', (e) => e.preventDefault());
  }
})();
