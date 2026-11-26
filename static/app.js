// AdsBooth — alur kiosk
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const SHOTS = { solo: 1, duo: 2, strip: 3, grid: 4 };

let CFG = { certTitles: [], features: {}, poses: [], cameraFacing: 'user', layouts: ['solo', 'duo', 'strip', 'grid'], defaultLayout: 'strip', eventVersion: '', templates: [], defaultTemplate: 'klasik', maxCopies: 2, countdown: 3, resetSeconds: 60, idleSeconds: 90, mirror: true, qr: true };
let S = {};
let stream = null;
let DUMMY = false, dummyIdx = 0;
const dummyImgs = [];
let current = 'welcome';
let idleTimer = null, resetTimer = null, styleTimer = null;
let skipCountdown = false, shooting = false;

function freshState() {
  if (S.paymentTimer) { clearInterval(S.paymentTimer); S.paymentTimer = null; }
  if (S.paymentPollTimer) { clearInterval(S.paymentPollTimer); S.paymentPollTimer = null; }
  S = { layout: CFG.defaultLayout || 'strip', copies: 1, style: (CFG.styles && CFG.styles[0].id) || 'bw', caption: '', showLogo: true,
        photos: [], lastPrint: null, printed: 0, template: CFG.defaultTemplate, photoVer: 0, tplKey: '',
        poses: [], guestbook: null, certTitle: '', pendingJobs: null,
        eventName: CFG.eventName || '', footer: CFG.footer || '',
        username: (CFG.social && CFG.social.username) || '', website: (CFG.social && CFG.social.website) || '',
        koranTitle: 'Kabar Booth',
        brightness: CFG.brightness !== undefined ? CFG.brightness : 1.0,
        retakeCount: 0,
        outputMode: (CFG.output === 'both' ? null : CFG.output),
        paid: false,
        paymentTx: null,
        paymentTimer: null,
        paymentPollTimer: null };
  if ($('#gbName')) { $('#gbName').value = ''; $('#gbMsg').value = ''; clearSign(); }
  if ($('#caption')) $('#caption').value = '';
  if ($('#showLogo')) $('#showLogo').checked = true;
  if ($('#paymentCard')) $('#paymentCard').classList.add('hidden');
  if ($('#paySuccessCard')) $('#paySuccessCard').classList.add('hidden');
  if ($('#printingQrCard')) $('#printingQrCard').classList.add('hidden');
  if ($('#modePickerModal')) $('#modePickerModal').classList.add('hidden');
  if ($('#btnPrint')) { $('#btnPrint').classList.remove('hidden'); $('#btnPrint').disabled = false; }
  const tplBtn = $('.tpl-change');
  if (tplBtn) tplBtn.classList.remove('hidden');
  const editPanel = $('#editPanel');
  if (editPanel) editPanel.classList.remove('hidden');
  if ($('#btnRetakeAll')) $('#btnRetakeAll').classList.remove('hidden');
  if ($('#copyDec')) $('#copyDec').disabled = false;
  if ($('#copyInc')) $('#copyInc').disabled = false;
  syncEditFields();
  renderOptions();
}

// ---------- topbar clock ----------
function updateTopbarClock() {
  const el = $('#topbarClock');
  if (!el) return;
  const now = new Date();
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const d = String(now.getDate()).padStart(2, '0');
  const m = MONTHS[now.getMonth()];
  const y = now.getFullYear();
  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  el.textContent = `${d} ${m} ${y} | ${hh}:${mm}`;
}
setInterval(updateTopbarClock, 1000);
updateTopbarClock();

// ---------- navigasi ----------
function go(name) {
  window.go = go;
  const fromScreen = current;
  let flyToTopbar = false, rFromIntro = null;
  let flyToIntro = false, rFromTopbar = null;

  if (fromScreen === 'welcome' && name === 'layout') {
    const il = $('#introLogo');
    if (il && !il.classList.contains('hidden') && (il.naturalWidth || il.offsetWidth > 0)) {
      rFromIntro = il.getBoundingClientRect();
      flyToTopbar = true;
    }
  } else if (fromScreen && fromScreen !== 'welcome' && name === 'welcome') {
    const tl = $('#topbarLogo');
    if (tl && !tl.classList.contains('hidden') && (tl.naturalWidth || tl.offsetWidth > 0)) {
      rFromTopbar = tl.getBoundingClientRect();
      flyToIntro = true;
    }
  }

  $$('.screen').forEach((el) => el.classList.remove('active'));
  $('#s-' + name).classList.add('active');
  // background disamakan pada semua scene (termasuk kamera)
  document.body.classList.remove('dark');
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

  if (flyToTopbar && rFromIntro) {
    requestAnimationFrame(() => {
      const tl = $('#topbarLogo');
      if (tl && !tl.classList.contains('hidden')) {
        const r2 = tl.getBoundingClientRect();
        if (r2.width > 0 && r2.height > 0) {
          const appZoom = parseFloat($('#app').style.zoom) || 1;
          const dx = ((rFromIntro.left + rFromIntro.width / 2) - (r2.left + r2.width / 2)) / appZoom;
          const dy = ((rFromIntro.top + rFromIntro.height / 2) - (r2.top + r2.height / 2)) / appZoom;
          const scale = (rFromIntro.height / r2.height) || 1;
          tl.animate([
            {
              transform: `translate(${dx}px, ${dy}px) scale(${scale})`,
              transformOrigin: 'center center',
              opacity: 0.95
            },
            {
              transform: 'translate(0, 0) scale(1)',
              transformOrigin: 'center center',
              opacity: 1
            }
          ], {
            duration: 600,
            easing: 'cubic-bezier(0.16, 1, 0.3, 1)'
          });
        }
      }
    });
  } else if (flyToIntro && rFromTopbar) {
    requestAnimationFrame(() => {
      const il = $('#introLogo');
      if (il && !il.classList.contains('hidden')) {
        const r2 = il.getBoundingClientRect();
        if (r2.width > 0 && r2.height > 0) {
          const appZoom = parseFloat($('#app').style.zoom) || 1;
          const dx = ((rFromTopbar.left + rFromTopbar.width / 2) - (r2.left + r2.width / 2)) / appZoom;
          const dy = ((rFromTopbar.top + rFromTopbar.height / 2) - (r2.top + r2.height / 2)) / appZoom;
          const scale = (rFromTopbar.height / r2.height) || 1;
          il.animate([
            {
              transform: `translate(${dx}px, ${dy}px) scale(${scale})`,
              transformOrigin: 'center center',
              opacity: 0.95
            },
            {
              transform: 'translate(0, 0) scale(1)',
              transformOrigin: 'center center',
              opacity: 1
            }
          ], {
            duration: 600,
            easing: 'cubic-bezier(0.16, 1, 0.3, 1)'
          });
        }
      }
    });
  }
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
// Rasio foto per template (h/w) — cermin dari templates.py. Panduan viewfinder ikut ini.
const TPL_RATIO = {
  musik:{solo:1.15,duo:0.95,strip:1.1,grid:1.0},
  teater:{solo:1.2,duo:0.9,strip:1.1,grid:1.0},
  nowplaying:{solo:1.0,duo:0.85,strip:0.9,grid:1.0},
  konser:{solo:1.15,duo:0.9,strip:1.05,grid:1.0},
  chat:{solo:1.0,duo:1.0,strip:1.0,grid:1.0},
  idcard:{solo:1.25,duo:0.8,strip:0.85,grid:1.0},
  poster:{solo:1.3,duo:1.0,strip:1.05,grid:1.0},
};
const DEFAULT_RATIO = { solo:0.75, duo:0.75, strip:2/3, grid:1.0, feed:1.0 };
function photoRatioHW() {
  const lay = S.layout || 'strip';
  const m = TPL_RATIO[S.template];
  return (m && m[lay]) || DEFAULT_RATIO[lay] || 0.75;   // tinggi / lebar
}
function ratioLabel(a) {
  const opts=[[1,'1:1'],[3/4,'3:4'],[4/5,'4:5'],[9/16,'9:16'],[4/3,'4:3'],[3/2,'3:2'],[16/9,'16:9']];
  let best=opts[0], bd=1e9;
  for (const [v,l] of opts){ const dd=Math.abs(v-a); if(dd<bd){bd=dd;best=[v,l];} }
  return best[1];
}

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
  const g = $("#vfGuide");
  if (g) g.classList.add("hidden");
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
    const v = $('#video');
    v.srcObject = stream;
    try { await v.play(); } catch (e) {}
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
  const v = $('#video');
  if (!v || !v.videoWidth || !v.videoHeight) return null;
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
    if ($('#introName')) $('#introName').textContent = INTRO.eventName || '';
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
let dualIntroStep = 0;
const DUAL_INTRO_STYLES = ['thermal', 'strip', 'thermal', 'instan'];
const PHOTO_INTRO_STYLES = ['strip', 'instan'];

function introStyle() {
  const cfgStyle = (CFG.introStyle || '').toLowerCase();
  if (cfgStyle === 'strip') return 'strip';
  if (cfgStyle === 'instan') return 'instan';
  if (cfgStyle === 'thermal') return 'thermal';

  const out = CFG.output || 'thermal';
  if (out === 'photo') {
    return 'strip'; // Mode Foto: Photo Strip Korea 3-Pose (Opsi A)
  }
  if (out === 'both') {
    return DUAL_INTRO_STYLES[dualIntroStep % DUAL_INTRO_STYLES.length];
  }
  // Mode Thermal (Receipt): Animasi printer struk thermal monokrom
  return 'thermal';
}

function nextDualIntro() {
  const cfgStyle = (CFG.introStyle || '').toLowerCase();
  if (cfgStyle === 'strip' || cfgStyle === 'instan' || cfgStyle === 'thermal') return;
  const out = CFG.output || 'thermal';
  if (out === 'photo') {
    dualIntroStep = (dualIntroStep + 1) % PHOTO_INTRO_STYLES.length;
  } else if (out === 'both') {
    dualIntroStep = (dualIntroStep + 1) % DUAL_INTRO_STYLES.length;
  }
}

function introCycle() {
  if (!introOn) return;
  const isBoth = CFG.output === 'both';
  const sty = introStyle();
  $('#introStage').classList.toggle('hidden', sty !== 'thermal');
  $('#icStage').classList.toggle('hidden', sty !== 'instan');
  $('#isStage').classList.toggle('hidden', sty !== 'strip');

  // Update badge pill highlight in dual mode (hanya aktif di dual mode)
  const badge = $('#introDualBadge');
  if (badge) {
    badge.classList.toggle('hidden', !isBoth);
    const pReceipt = $('#idPillReceipt');
    const pPhoto = $('#idPillPhoto');
    if (pReceipt && pPhoto) {
      pReceipt.classList.toggle('active', sty === 'thermal');
      pPhoto.classList.toggle('active', sty !== 'thermal');
    }
  }
  const prompt = $('#introPrompt');
  if (prompt) prompt.classList.add('hidden');

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
  at(12700, () => { nextDualIntro(); introCycle(); });
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
  introAt(11800, () => { nextDualIntro(); introCycle(); });
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
  introAt(12400, () => { nextDualIntro(); introCycle(); });
}

// latar intro: khusus receipt photobooth menampilkan mini souvenir template cetak thermal asli
function buildIntroBg() {
  const bg = $('#introBg');
  if (!bg) return;

  const isThermal = (CFG.output || 'thermal') === 'thermal';
  const isBoth = CFG.output === 'both';
  const isPhoto = CFG.output === 'photo';

  const evName = (INTRO && INTRO.eventName) || 'PHOTOBOOTH';
  const evDate = (INTRO && INTRO.date) || '23.11.2026';
  const getDither = (idx) => {
    if (INTRO && INTRO.photos && INTRO.photos.length) {
      return INTRO.photos[idx % INTRO.photos.length].dither;
    }
    return `/api/intro/${idx % 3}.png`;
  };

  if (!bg.dataset.ready) {
    bg.dataset.ready = '1';
    let kinds = [];
    if (isThermal) {
      // Khusus mode receipt: template cetak thermal mini (card solo & strip) dengan foto hasil dither thermal + sparkle dots
      kinds = ['th-card', 'th-strip', 'dot', 'th-card', 'th-strip', 'dot', 'th-card', 'th-strip', 'dot', 'th-card', 'th-strip', 'dot'];
    } else if (isPhoto) {
      kinds = ['strip', 'polaroid', 'dot', 'strip', 'polaroid', 'dot', 'strip', 'polaroid', 'dot', 'strip', 'polaroid', 'dot'];
    } else {
      kinds = ['th-card', 'strip', 'dot', 'th-strip', 'polaroid', 'dot', 'th-card', 'strip', 'dot', 'th-strip', 'polaroid', 'dot'];
    }

    kinds.forEach((k, i) => {
      const el = document.createElement('div');
      el.className = 'fl fl-' + k;
      const phIdx = i % 3;

      if (k === 'th-card') {
        el.innerHTML = `
          <div class="fl-th-header">${evName}</div>
          <img class="fl-th-img" src="${getDither(phIdx)}" alt="">
          <div class="fl-th-footer">${evDate} · ADSBOOTH</div>
        `;
      } else if (k === 'th-strip') {
        el.innerHTML = `
          <div class="fl-th-header">${evName}</div>
          <img class="fl-th-img" src="${getDither(phIdx)}" alt="">
          <img class="fl-th-img" src="${getDither((phIdx + 1) % 3)}" alt="">
          <div class="fl-th-footer">${evDate}</div>
        `;
      } else if (k === 'strip') {
        el.innerHTML = '<i></i><i></i><i></i>';
      } else if (k === 'polaroid') {
        el.innerHTML = '<b></b>';
      }

      const lane = (i + 0.5) / kinds.length;                    // sebar merata kiri-kanan
      const scale = k === 'dot' ? 1 + Math.random() * 0.4 : 0.92 + Math.random() * 0.22;
      const dur = 22 + Math.random() * 12;
      el.style.left = `calc(${(lane * 100).toFixed(1)}% - 38px)`;
      el.style.setProperty('--d', dur.toFixed(1) + 's');
      el.style.setProperty('--delay', (-Math.random() * dur).toFixed(1) + 's');   // langsung tersebar saat mulai
      el.style.setProperty('--r0', (Math.random() * 26 - 13).toFixed(0) + 'deg');
      el.style.setProperty('--r1', (Math.random() * 52 - 26).toFixed(0) + 'deg');
      el.style.setProperty('--o', (k === 'dot' ? 0.45 : 0.85 + Math.random() * 0.15).toFixed(2));
      el.style.setProperty('--s', scale.toFixed(2));
      bg.appendChild(el);
    });
  } else {
    // Perbarui foto & teks template jika data intro baru termuat
    const headers = bg.querySelectorAll('.fl-th-header');
    headers.forEach(h => { if (INTRO && INTRO.eventName) h.textContent = INTRO.eventName; });
    const footers = bg.querySelectorAll('.fl-th-footer');
    footers.forEach(f => { if (INTRO && INTRO.date) f.textContent = f.textContent.includes('ADSBOOTH') ? `${INTRO.date} · ADSBOOTH` : INTRO.date; });
    const imgs = bg.querySelectorAll('.fl-th-img');
    imgs.forEach((img, idx) => {
      if (INTRO && INTRO.photos && INTRO.photos.length) {
        img.src = INTRO.photos[idx % INTRO.photos.length].dither;
      }
    });
  }
  sizeIntroBg();
}
function sizeIntroBg() {
  const bg = $('#introBg');
  const h = Math.max(window.innerHeight || 1080, (bg && bg.clientHeight) || 1080, 1080);
  if (bg) bg.style.setProperty('--travel', (h + 500) + 'px');
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
  if (CFG.output === 'both') {
    const modal = $('#modePickerModal');
    if (modal) modal.classList.remove('hidden');
    return;
  }
  applyOutputMode();
  go('layout');
  startCamera();
});

$$('.mode-card').forEach((card) => {
  card.addEventListener('click', () => {
    const mode = card.dataset.mode;
    S.outputMode = mode;
    const modal = $('#modePickerModal');
    if (modal) modal.classList.add('hidden');
    applyOutputMode(mode);
    go('layout');
    startCamera();
  });
});
const btnCancelMode = $('#btnCancelMode');
if (btnCancelMode) {
  btnCancelMode.addEventListener('click', () => {
    const modal = $('#modePickerModal');
    if (modal) modal.classList.add('hidden');
  });
}

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
  setTimeout(() => go('style'), 180);   // pilih gaya cetak dulu (Dither/Halftone/Contrast)
}));
$('#copyInc').addEventListener('click', () => {
  if (S.paid) return;
  S.copies = Math.min(CFG.maxCopies, S.copies + 1);
  renderOptions();
  if (current === 'review' && CFG.payment && CFG.payment.enabled && !S.paid) {
    startPaymentFlow();
  }
});
$('#copyDec').addEventListener('click', () => {
  if (S.paid) return;
  S.copies = Math.max(1, S.copies - 1);
  renderOptions();
  if (current === 'review' && CFG.payment && CFG.payment.enabled && !S.paid) {
    startPaymentFlow();
  }
});

// ---------- 3. gaya ----------
const DEFAULT_PHOTO_STYLES = [
  { id: 'warna', name: 'Color', desc: 'True, natural color' },
  { id: 'cerah', name: 'Vivid', desc: 'Brighter, livelier colors' },
  { id: 'bw', name: 'Black & white', desc: 'Classic, soft contrast' },
  { id: 'sepia', name: 'Sepia', desc: 'Warm brown, old-photo look' },
  { id: 'vintage', name: 'Vintage', desc: 'Faded, warm, a little grain' },
  { id: 'dingin', name: 'Cool', desc: 'Blue tint, clean' }
];

let styleBusy = false;
let currentSampleType = null;
// Tiap kartu gaya memakai contoh foto model statis (cewe/cowo acak) agar tajam dan kamera tidak lag
async function refreshStylePreview() {
  if (styleBusy || current !== 'style') return;
  styleBusy = true;
  try {
    const sample = Math.random() < 0.5 ? 'cewe' : 'cowo';
    const mode = S.outputMode || (CFG.output === 'both' ? 'thermal' : CFG.output);
    const data = await api('/api/sample-styles?sample=' + sample + '&mode=' + mode);
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
        let fav = box.querySelector('.badge-fav');
        if (data.favorite_style && s === data.favorite_style) {
          if (!fav) {
            fav = document.createElement('span');
            fav.className = 'badge-fav';
            fav.textContent = 'FAVORIT';
            box.appendChild(fav);
          }
        } else {
          if (fav) fav.remove();
        }
      });
    }
  } catch (e) {
    console.warn('Gagal memuat sample style:', e);
  }
  styleBusy = false;
}
function updateStyleArrows() {
  const el = $('#styleOptions');
  const prev = $('#stylePrev');
  const next = $('#styleNext');
  if (!el || !prev || !next) return;
  const canScroll = el.scrollWidth > el.clientWidth + 12;
  if (!canScroll) {
    prev.classList.add('off');
    next.classList.add('off');
    return;
  }
  prev.classList.toggle('off', el.scrollLeft <= 10);
  next.classList.toggle('off', el.scrollLeft >= el.scrollWidth - el.clientWidth - 10);
}

const styleDrag = { on: false, x: 0, sl: 0, moved: false };
const styleOptEl = $('#styleOptions');
if (styleOptEl) {
  styleOptEl.addEventListener('scroll', updateStyleArrows, { passive: true });
  styleOptEl.addEventListener('pointerdown', (e) => {
    if (e.pointerType !== 'mouse') { styleDrag.moved = false; return; }
    Object.assign(styleDrag, { on: true, x: e.clientX, sl: styleOptEl.scrollLeft, moved: false });
    styleOptEl.classList.add('dragging');
  });
  window.addEventListener('pointermove', (e) => {
    if (!styleDrag.on) return;
    const dx = e.clientX - styleDrag.x;
    if (Math.abs(dx) > 6) styleDrag.moved = true;
    styleOptEl.scrollLeft = styleDrag.sl - dx;
  });
  window.addEventListener('pointerup', () => {
    if (!styleDrag.on) return;
    styleDrag.on = false;
    styleOptEl.classList.remove('dragging');
  });
}
$('#stylePrev')?.addEventListener('click', () => {
  const el = $('#styleOptions');
  if (el) el.scrollBy({ left: -el.clientWidth * 0.75, behavior: 'smooth' });
});
$('#styleNext')?.addEventListener('click', () => {
  const el = $('#styleOptions');
  if (el) el.scrollBy({ left: el.clientWidth * 0.75, behavior: 'smooth' });
});

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
  setTimeout(updateStyleArrows, 60);
}
$('#styleOptions').addEventListener('click', (e) => {
  if (styleDrag.moved) return;
  const b = e.target.closest('.opt');
  if (!b) return;
  S.style = b.dataset.style; renderOptions();
  setTimeout(startShooting, 180);   // tap langsung ke kamera
});

// Mode cetak foto 4R / Receipt: ganti pilihan gaya & teks yang menyebut "struk".
function applyOutputMode(mode) {
  const currentMode = mode || S.outputMode || (CFG.output === 'both' ? 'thermal' : CFG.output);
  const photo = currentMode === 'photo';
  document.body.classList.toggle('mode-photo', photo);
  $$('[data-photo]').forEach((el) => {
    if (el.dataset.thermal === undefined) el.dataset.thermal = el.textContent;
    el.textContent = photo ? el.dataset.photo : el.dataset.thermal;
  });
  if (!window.__thermalStyles) window.__thermalStyles = $('#styleOptions').innerHTML;
  const pStyles = (CFG.styles && CFG.styles.length) ? CFG.styles : DEFAULT_PHOTO_STYLES;
  $('#styleOptions').innerHTML = photo
    ? pStyles.map((s) => `<button class="opt sm" data-style="${s.id}"><b>${s.name}</b><span>${s.desc}</span></button>`).join('')
    : window.__thermalStyles;

  // Sesuaikan style aktif agar sesuai dengan mode yang dipilih
  if (photo) {
    if (!['warna', 'cerah', 'bw', 'sepia', 'vintage', 'dingin'].includes(S.style)) {
      S.style = 'warna';
    }
  } else {
    if (!['bw', 'dither', 'halftone', 'kontras', 'sketsa', 'ascii', 'mewarnai'].includes(S.style)) {
      S.style = 'bw';
    }
  }
  renderOptions();
  const el = $('#styleOptions');
  if (el) el.scrollLeft = 0;
  setTimeout(updateStyleArrows, 60);
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
  sizeViewfinder();
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
  if (!photo) { await sleep(120); photo = capture(maxW); }
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
    S.availableTemplates = (prep && prep.templates) ? prep.templates : [];
  } catch (e) {
    list.innerHTML = '<div class="loading mono">FAILED TO LOAD TEMPLATES: ' + e.message + '</div>';
    return;
  }
  if (seq !== tplSeq) return;
  // kartu kosong dulu, gambar diisi begitu siap
  list.innerHTML = '';
  // pastikan ada template terpilih, lalu urutkan: terpilih dulu, sisanya dari bentuk/rasio paling mirip
  if (!prep.templates.some((t) => t.id === S.template) && prep.templates.length) S.template = prep.templates[0].id;
  (function sortByShape() {
    const lay = S.layout || 'strip';
    const rof = (id) => { const m = TPL_RATIO[id]; return (m && m[lay]) || DEFAULT_RATIO[lay] || 0.75; };
    const selR = rof(S.template);
    prep.templates.sort((a, b) =>
      a.id === S.template ? -1 : b.id === S.template ? 1 : Math.abs(rof(a.id) - selR) - Math.abs(rof(b.id) - selR));
  })();
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
           brightness: S.brightness, lucky: S.lucky,
           payment_tx: S.paymentTx || null,
           output: S.outputMode || (CFG.output === 'both' ? 'thermal' : CFG.output) };
}
function renderCertPick() {
  const on = S.template === 'sertifikat' && CFG.certTitles.length;
  $('#certPick')?.classList.toggle('hidden', !on);
  if (!on) return;
  if (!S.certTitle) S.certTitle = CFG.certTitles[Math.floor(Math.random() * CFG.certTitles.length)];
  const box = $('#certChips');
  if (!box) return;
  box.innerHTML = '';

  const activeLabel = $('#certActiveName');
  if (activeLabel) activeLabel.textContent = S.certTitle.split('|')[0].trim();

  const dice = document.createElement('button');
  dice.type = 'button';
  dice.className = 'chip dice';
  dice.textContent = '🎲 Acak';
  dice.title = 'Pilih gelar secara acak';
  dice.addEventListener('click', () => {
    const others = CFG.certTitles.filter((t) => t !== S.certTitle);
    S.certTitle = others[Math.floor(Math.random() * others.length)] || S.certTitle;
    renderCertPick();
    renderPreview();
    setTimeout(() => {
      const activeEl = box.querySelector('.chip.on');
      if (activeEl) activeEl.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }, 60);
  });
  box.appendChild(dice);

  CFG.certTitles.forEach((t) => {
    const b = document.createElement('button');
    b.type = 'button';
    const isSelected = t === S.certTitle;
    b.className = 'chip' + (isSelected ? ' on' : '');
    b.textContent = t.split('|')[0].trim();
    b.title = t;
    b.addEventListener('click', () => {
      S.certTitle = t;
      renderCertPick();
      renderPreview();
      setTimeout(() => {
        b.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      }, 60);
    });
    box.appendChild(b);
  });

  // Pastikan chip aktif terlihat saat pertama kali render
  setTimeout(() => {
    const activeEl = box.querySelector('.chip.on');
    if (activeEl) activeEl.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }, 100);
}

// Navigasi scroll horizontal chip gelar sertifikat
$('#certNavPrev')?.addEventListener('click', () => {
  $('#certChips')?.scrollBy({ left: -140, behavior: 'smooth' });
});
$('#certNavNext')?.addEventListener('click', () => {
  $('#certChips')?.scrollBy({ left: 140, behavior: 'smooth' });
});

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
  if (CFG.payment && CFG.payment.enabled && !S.paid) {
    $('#btnPrint').disabled = true;
    $('#btnPrint').classList.add('hidden');
  } else {
    $('#btnPrint').disabled = false;
    $('#btnPrint').classList.remove('hidden');
  }
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

// Carousel Template di Layar Review
function getAvailableTemplates() {
  if (S.availableTemplates && S.availableTemplates.length) {
    return S.availableTemplates;
  }
  if (CFG.templates && CFG.templates.length) {
    return CFG.templates;
  }
  return [{ id: S.template || 'klasik', name: S.template || 'Default' }];
}

function updateReviewTplMeta() {
  const tpls = getAvailableTemplates();
  if (!tpls.length) return;
  const idx = tpls.findIndex((t) => t.id === S.template);
  const cur = idx >= 0 ? tpls[idx] : tpls[0];
  const nameEl = $('#revTplName');
  const countEl = $('#revTplCount');
  if (nameEl) nameEl.textContent = cur ? (cur.name || cur.id) : (S.template || '-');
  if (countEl) countEl.textContent = `${idx >= 0 ? idx + 1 : 1} / ${tpls.length}`;

  const showNav = !S.paid && tpls.length > 1;
  $('#revTplPrev')?.classList.toggle('hidden', !showNav);
  $('#revTplNext')?.classList.toggle('hidden', !showNav);
}

let revStepDebounce = false;
async function stepReviewTemplate(dir) {
  if (S.paid || revStepDebounce) return;
  const tpls = getAvailableTemplates();
  if (!tpls.length) return;
  let idx = tpls.findIndex((t) => t.id === S.template);
  if (idx < 0) idx = 0;
  idx = (idx + dir + tpls.length) % tpls.length;
  const nextTpl = tpls[idx];
  if (!nextTpl || nextTpl.id === S.template) return;

  revStepDebounce = true;
  S.template = nextTpl.id;
  updateReviewTplMeta();
  renderCertPick();
  updateEditFieldsForTemplate();
  try {
    await renderPreview();
  } finally {
    revStepDebounce = false;
  }
}

$('#revTplPrev')?.addEventListener('click', () => stepReviewTemplate(-1));
$('#revTplNext')?.addEventListener('click', () => stepReviewTemplate(1));

// Swipe touch gesture pada preview paper di halaman review
let revTouchX = 0;
let revTouchY = 0;
const paperRev = $('#paperReview');
if (paperRev) {
  paperRev.addEventListener('touchstart', (e) => {
    revTouchX = e.touches[0].clientX;
    revTouchY = e.touches[0].clientY;
  }, { passive: true });
  paperRev.addEventListener('touchend', (e) => {
    const dx = e.changedTouches[0].clientX - revTouchX;
    const dy = e.changedTouches[0].clientY - revTouchY;
    if (Math.abs(dx) > 35 && Math.abs(dx) > Math.abs(dy)) {
      if (dx < 0) stepReviewTemplate(1);
      else stepReviewTemplate(-1);
    }
  }, { passive: true });
}

window.addEventListener('keydown', (e) => {
  if (current === 'review' && !S.paid && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
    if (e.key === 'ArrowLeft') stepReviewTemplate(-1);
    if (e.key === 'ArrowRight') stepReviewTemplate(1);
  }
});

async function renderReview() {
  // Pastikan daftar template tersedia untuk carousel review
  if (!S.availableTemplates || !S.availableTemplates.length) {
    try {
      const prep = await api('/api/templates/prepare', payload());
      if (prep && prep.templates) S.availableTemplates = prep.templates;
    } catch (_) {}
  }

  updateReviewTplMeta();

  const editPanel = $('#editPanel');
  if (editPanel) editPanel.classList.toggle('hidden', !!S.paid);
  if ($('#copyDec')) $('#copyDec').disabled = !!S.paid;
  if ($('#copyInc')) $('#copyInc').disabled = !!S.paid;

  renderCertPick();
  syncEditFields();
  await renderPreview();

  // Kasir / Pembayaran QRIS Kiosk
  if (CFG.payment && CFG.payment.enabled) {
    if (!S.paid) {
      startPaymentFlow();
    } else {
      onPaymentSuccess();
    }
  } else {
    if ($('#paymentCard')) $('#paymentCard').classList.add('hidden');
    if ($('#paySuccessCard')) $('#paySuccessCard').classList.add('hidden');
    $('#btnPrint').classList.remove('hidden');
    $('#btnPrint').disabled = false;
  }
}

// ---------- Kasir / Pembayaran QRIS ----------
async function startPaymentFlow() {
  if (!CFG.payment || !CFG.payment.enabled || S.paid) return;

  const mode = S.outputMode || (CFG.output === 'both' ? 'thermal' : CFG.output);
  const copies = S.copies || 1;
  const priceUnit = mode === 'photo' ? (CFG.payment.price_photo || 30000) : (CFG.payment.price_receipt || 15000);
  const totalAmount = priceUnit * copies;
  const timeoutSecs = CFG.payment.timeout_seconds || 120;

  const card = $('#paymentCard');
  if (card) card.classList.remove('hidden');
  const succ = $('#paySuccessCard');
  if (succ) succ.classList.add('hidden');
  $('#btnPrint').classList.add('hidden');
  $('#btnPrint').disabled = true;

  const payTotalText = $('#payTotalText');
  if (payTotalText) payTotalText.textContent = 'Rp ' + Number(totalAmount).toLocaleString('id-ID');
  const payDetailText = $('#payDetailText');
  if (payDetailText) payDetailText.textContent = `${copies} Lembar ${mode === 'photo' ? '4R Photobooth' : 'Receipt Photobooth'}`;

  // Countdown timer
  let remaining = timeoutSecs;
  const timerBadge = $('#payTimerSecs');
  const updateTimer = () => {
    if (!timerBadge) return;
    const mm = String(Math.floor(remaining / 60)).padStart(2, '0');
    const ss = String(remaining % 60).padStart(2, '0');
    timerBadge.textContent = `${mm}:${ss}`;
  };
  updateTimer();

  if (S.paymentTimer) clearInterval(S.paymentTimer);
  S.paymentTimer = setInterval(async () => {
    remaining -= 1;
    updateTimer();
    if (remaining <= 0) {
      clearInterval(S.paymentTimer);
      S.paymentTimer = null;
      if (S.paymentPollTimer) clearInterval(S.paymentPollTimer);
      await showKioskAlert('Waktu Pembayaran Habis', 'Waktu batas pembayaran telah habis. Kiosk kembali ke awal.', '⏱️', 'Kembali ke Awal');
      resetAll();
    }
  }, 1000);

  // Request payment create
  try {
    const res = await api('/api/payment/create', {
      output: mode,
      copies: copies,
      amount: totalAmount,
      method: CFG.payment?.method || 'qr'
    });
    if (res.ok && res.required) {
      S.paymentTx = res.tx_id;
      const method = res.method || CFG.payment.method || 'qr';
      S.paymentMethod = method;

      // Setup tab & tampilan QR / Manual
      const qrBox = $('#payQrBox');
      const manualBox = $('#payManualBox');
      const tabs = $('#payTabs');
      const tagText = $('#payTagText');
      const simBox = $('#paySimBox');

      if ((res.qr || res.qr_image) && $('#payQrImg')) {
        $('#payQrImg').src = res.qr || res.qr_image;
      }

      if (method === 'manual') {
        if (tabs) tabs.classList.add('hidden');
        if (qrBox) qrBox.classList.add('hidden');
        if (manualBox) manualBox.classList.remove('hidden');
        if (tagText) tagText.textContent = 'PEMBAYARAN TUNAI / KASIR';
        if (simBox) simBox.classList.add('hidden');
      } else if (method === 'both') {
        if (tabs) tabs.classList.remove('hidden');
        if (qrBox) qrBox.classList.remove('hidden');
        if (manualBox) manualBox.classList.add('hidden');
        if (tagText) tagText.textContent = 'PILIHAN PEMBAYARAN';
        $('#btnPayTabQr')?.classList.add('on');
        $('#btnPayTabManual')?.classList.remove('on');
        if (simBox) simBox.classList.toggle('hidden', CFG.payment.gateway !== 'simulator');
      } else {
        // default: 'qr'
        if (tabs) tabs.classList.add('hidden');
        if (qrBox) qrBox.classList.remove('hidden');
        if (manualBox) manualBox.classList.add('hidden');
        if (tagText) tagText.textContent = 'PEMBAYARAN QRIS';
        if (simBox) simBox.classList.toggle('hidden', CFG.payment.gateway !== 'simulator');
      }

      // Start polling
      if (S.paymentPollTimer) clearInterval(S.paymentPollTimer);
      S.paymentPollTimer = setInterval(async () => {
        if (!S.paymentTx || S.paid) {
          clearInterval(S.paymentPollTimer);
          return;
        }
        try {
          const st = await api('/api/payment/status/' + S.paymentTx);
          if (st.status === 'paid') {
            onPaymentSuccess();
          } else if (st.status === 'expired') {
            clearInterval(S.paymentPollTimer);
            clearInterval(S.paymentTimer);
            await showKioskAlert('Waktu Pembayaran Habis', 'Waktu pembayaran telah habis. Kiosk kembali ke awal.', '⏱️', 'Kembali ke Awal');
            resetAll();
          }
        } catch (e) {
          // ignore transient poll error
        }
      }, 2000);
    }
  } catch (err) {
    console.warn('Gagal membuat pembayaran:', err);
  }
}

function onPaymentSuccess() {
  S.paid = true;
  if (S.paymentTimer) { clearInterval(S.paymentTimer); S.paymentTimer = null; }
  if (S.paymentPollTimer) { clearInterval(S.paymentPollTimer); S.paymentPollTimer = null; }

  if ($('#paymentCard')) $('#paymentCard').classList.add('hidden');
  if ($('#paySuccessCard')) $('#paySuccessCard').classList.remove('hidden');

  // Kunci tombol template & carousel panah
  $('#revTplPrev')?.classList.add('hidden');
  $('#revTplNext')?.classList.add('hidden');
  const editPanel = $('#editPanel');
  if (editPanel) editPanel.classList.add('hidden');
  if ($('#copyDec')) $('#copyDec').disabled = true;
  if ($('#copyInc')) $('#copyInc').disabled = true;

  // Tampilkan tombol Print now
  $('#btnPrint').classList.remove('hidden');
  $('#btnPrint').disabled = false;
}

// Tab switcher pembayaran (saat method === 'both')
$('#btnPayTabQr')?.addEventListener('click', () => {
  $('#btnPayTabQr')?.classList.add('on');
  $('#btnPayTabManual')?.classList.remove('on');
  $('#payQrBox')?.classList.remove('hidden');
  $('#payManualBox')?.classList.add('hidden');
  const simBox = $('#paySimBox');
  if (simBox) simBox.classList.toggle('hidden', CFG.payment.gateway !== 'simulator');
});
$('#btnPayTabManual')?.addEventListener('click', () => {
  $('#btnPayTabManual')?.classList.add('on');
  $('#btnPayTabQr')?.classList.remove('on');
  $('#payManualBox')?.classList.remove('hidden');
  $('#payQrBox')?.classList.add('hidden');
  $('#paySimBox')?.classList.add('hidden');
});

// Tombol Konfirmasi Bayar Tunai / Kasir Manual
$('#btnConfirmManualPay')?.addEventListener('click', async () => {
  if (!S.paymentTx) return;
  const btn = $('#btnConfirmManualPay');
  if (btn) { btn.disabled = true; btn.textContent = 'Memverifikasi...'; }
  try {
    const res = await api('/api/payment/confirm-manual/' + S.paymentTx, {});
    if (res.ok) {
      onPaymentSuccess();
    }
  } catch (e) {
    await showKioskAlert('Konfirmasi Gagal', e.message || 'Gagal konfirmasi pembayaran kasir.', '⚠️');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '✓ Sudah Bayar ke Kasir'; }
  }
});

const btnSimPay = $('#btnSimulatePay');
if (btnSimPay) {
  btnSimPay.addEventListener('click', async () => {
    if (!S.paymentTx) return;
    try {
      await api('/api/payment/simulate/' + S.paymentTx, {});
      onPaymentSuccess();
    } catch (e) {
      await showKioskAlert('Simulasi Gagal', 'Simulasi gagal: ' + e.message, '⚠️', 'OK');
    }
  });
}

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
    // Tampilkan QR Softcopy berwarna langsung di layar mencetak jika aktif
    const pQrCard = $('#printingQrCard');
    if (j.qr) {
      const pQrImg = $('#printingQrImg');
      if (pQrImg) pQrImg.src = j.qr;
      if (pQrCard) pQrCard.classList.remove('hidden');
      const qImg = $('#qrImg');
      if (qImg) qImg.src = j.qr;
    } else {
      if (pQrCard) pQrCard.classList.add('hidden');
    }
    if (j.jobs && j.jobs.length) {   // mode printer USB di tablet (WebUSB)
      S.pendingJobs = j.jobs;
      $('#printStatus').textContent = 'Sending to printer…';
      await PBUSB.printJobs(j.jobs);
      S.pendingJobs = null;
    }
    if (j.photo_url && PBPHOTO.supported()) {   // mode cetak foto LAN (Android Print Framework)
      $('#printStatus').textContent = 'Opening printer…';
      await PBPHOTO.printPhoto(j.photo_url, j.photo_copies, j.photo_media, j.photo_borderless);
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
    if (e.name !== 'NotFoundError') await showKioskAlert('Koneksi Printer Gagal', 'Gagal menghubungkan printer: ' + e.message, '⚠️', 'OK');
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
  } catch (e) { await showKioskAlert('Cetak Ulang Gagal', 'Gagal cetak ulang: ' + e.message, '⚠️', 'OK'); }
  clearInterval(resetTimer);
  startResetCountdown();
});

// ---------- status printer ----------
let lastPrinterOk = null;   // status printer terakhir yang diketahui (dipakai saat server tidak merespons)
let lastPrinterStatus = null; // objek status printer terakhir dari /api/status
let lastServerError = null; // pesan error saat fetch /api/status gagal
let printerReadyTimer = null; // timer untuk menyembunyikan status setelah PRINTER READY
let lastKnownReady = null;  // status apakah sebelumnya printer dalam kondisi ready

function hidePrinterIndicator() {
  const indicator = $('#stepLabel');
  if (!indicator) return;
  indicator.classList.add('fade-out');
  setTimeout(() => {
    if (indicator.classList.contains('fade-out')) {
      indicator.classList.add('hidden');
      indicator.classList.remove('fade-out');
    }
  }, 300);
}

function showPrinterIndicator() {
  const indicator = $('#stepLabel');
  if (!indicator) return;
  indicator.classList.remove('fade-out');
  indicator.classList.remove('hidden');
}

async function pollStatus() {
  try {
    const r = await fetch('/api/status', { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const s = await r.json();
    lastPrinterStatus = s;

    // Event diganti dari Studio -> muat ulang kiosk (langsung kalau sedang di layar awal)
    if (s.eventVersion && CFG.eventVersion && s.eventVersion !== CFG.eventVersion) {
      if (current === 'welcome') { location.reload(); return; }
      pendingReload = true;
    }
    const low = CFG.output !== 'photo' && s.paper && s.paper.low;
    const pill = $('#introStatus');
    const updatePill = (msg, show = true) => {
      if (pill) {
        pill.textContent = msg || '';
        pill.classList.toggle('hidden', !show || !msg);
      }
    };
    const btnUsb = $('#btnUsb');
    const statusDot = $('#statusDot');
    const statusText = $('#statusText');

    if (s.mode === 'webusb' || s.mode === 'android_usb') {
      const d = await PBUSB.paired().catch(() => null);
      if (!d) {
        lastPrinterOk = false;
        lastKnownReady = false;
        if (printerReadyTimer) { clearTimeout(printerReadyTimer); printerReadyTimer = null; }
        showPrinterIndicator();
        updatePill('USB PRINTER DISCONNECTED', true);
        if (btnUsb) {
          btnUsb.textContent = 'Connect USB Printer';
          btnUsb.classList.remove('hidden');
        }
        if (statusDot) statusDot.className = 'dot bad';
        if (statusText) {
          statusText.textContent = 'PRINTER DISCONNECTED';
          statusText.title = s.message || 'Check OTG cable or enable OTG in tablet settings';
        }
        return;
      }
      if (!d.hasPermission) {
        lastPrinterOk = false;
        lastKnownReady = false;
        if (printerReadyTimer) { clearTimeout(printerReadyTimer); printerReadyTimer = null; }
        showPrinterIndicator();
        updatePill('USB PERMISSION REQUIRED', true);
        if (btnUsb) {
          btnUsb.textContent = 'Grant USB Permission';
          btnUsb.classList.remove('hidden');
        }
        if (statusDot) statusDot.className = 'dot warn';
        if (statusText) {
          statusText.textContent = 'USB PERMISSION REQUIRED';
          statusText.title = s.message || 'Tap to grant USB printer permission';
        }
        return;
      }
      // d.hasPermission === true dan printer terhubung
      if (btnUsb) btnUsb.classList.add('hidden');
      lastPrinterOk = !!s.ok;
      const isReady = s.ok && !low;
      if (!isReady) {
        lastKnownReady = false;
        if (printerReadyTimer) { clearTimeout(printerReadyTimer); printerReadyTimer = null; }
        showPrinterIndicator();
        const problem = !s.ok ? 'PRINTER OFFLINE' : 'PAPER LOW';
        updatePill(problem, true);
        if (statusDot) statusDot.className = 'dot ' + (!s.ok ? 'bad' : 'warn');
        if (statusText) {
          statusText.textContent = !s.ok ? 'PRINTER OFFLINE' : `PAPER LOW (${s.paper.left_m} m)`;
          statusText.title = s.message || '';
        }
        return;
      }
      // Ready!
      updatePill('', false);
      if (lastKnownReady !== true) {
        lastKnownReady = true;
        showPrinterIndicator();
        if (statusDot) statusDot.className = 'dot ok';
        if (statusText) {
          statusText.textContent = 'PRINTER READY';
          statusText.title = s.message || '';
        }
        if (printerReadyTimer) clearTimeout(printerReadyTimer);
        printerReadyTimer = setTimeout(() => {
          hidePrinterIndicator();
          printerReadyTimer = null;
        }, 3500);
      } else if (!printerReadyTimer) {
        hidePrinterIndicator();
      }
      return;
    }

    // Mode printer lainnya (network, win32, file, photo)
    if (btnUsb) btnUsb.classList.add('hidden');
    lastPrinterOk = !!s.ok;
    const isReady = s.ok && !low;
    if (!isReady) {
      lastKnownReady = false;
      if (printerReadyTimer) { clearTimeout(printerReadyTimer); printerReadyTimer = null; }
      showPrinterIndicator();
      const problem = !s.ok ? (s.message || 'PRINTER OFFLINE') : 'PAPER LOW';
      updatePill(problem, true);
      if (statusDot) statusDot.className = 'dot ' + (!s.ok ? 'bad' : 'warn');
      if (statusText) {
        statusText.textContent = !s.ok ? 'PRINTER OFFLINE' : `PAPER LOW (${s.paper.left_m} m)`;
        statusText.title = s.message || '';
      }
      return;
    }
    // Ready!
    updatePill('', false);
    if (lastKnownReady !== true) {
      lastKnownReady = true;
      showPrinterIndicator();
      if (statusDot) statusDot.className = 'dot ok';
      if (statusText) {
        statusText.textContent = s.mode === 'file' ? 'TEST MODE (NO PRINTER)' : 'PRINTER READY';
        statusText.title = s.message || '';
      }
      if (printerReadyTimer) clearTimeout(printerReadyTimer);
      printerReadyTimer = setTimeout(() => {
        hidePrinterIndicator();
        printerReadyTimer = null;
      }, 3500);
    } else if (!printerReadyTimer) {
      hidePrinterIndicator();
    }
  } catch (e) {
    console.error('pollStatus error:', e);
    lastServerError = e.message || String(e);
    lastPrinterStatus = null;
    lastKnownReady = false;
    if (printerReadyTimer) { clearTimeout(printerReadyTimer); printerReadyTimer = null; }
    showPrinterIndicator();
    const statusDot = $('#statusDot');
    const statusText = $('#statusText');
    if (statusDot) statusDot.className = 'dot bad';
    if (statusText) {
      statusText.textContent = lastPrinterOk ? 'SERVER NOT CONNECTED' : 'SERVER & PRINTER NOT CONNECTED';
      statusText.title = 'Server error (/api/status failed): ' + e.message;
    }
  }
}

// ---------- skala layar (tablet / TV vertikal 24") ----------
// Desain dasar 768 px lebar (portrait). Di 1080x1920 semua diperbesar ~1.4x,
// tinggi sisa dipakai elemen yang fleksibel. Landscape: dibatasi tinggi min 900.
// Pada layar ponsel (mobile viewport), gunakan layout responsive native tanpa paksaan zoom tablet.
function fitScreen() {
  const W = window.innerWidth, H = window.innerHeight;
  const app = $('#app');
  if (!app) return;
  const isMobile = (W <= 600) || (W < H && W <= 768) || (W > H && H <= 500);
  if (isMobile) {
    app.style.zoom = '';
    app.style.width = '100%';
    app.style.height = '100%';
    return;
  }
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
  const topbar = document.querySelector('.topbar')?.offsetHeight || 60;
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
    text = CFG.output === 'photo' ? 'This license does not include 4R photo printing.' : 'This license does not include Receipt Photobooth printing.';
  }
  $('#licTitle').textContent = title;
  $('#licText').textContent = text;
  $('#licId').textContent = L.deviceId || '-';
}

// ---------- init ----------
function revealApp() {
  const sp = document.getElementById('splash');
  if (!sp) return;
  let fired = false;
  const SPLASH_MIN_MS = 1600;   // minimal tampil biar sempat terlihat (ubah di sini)
  const hide = () => requestAnimationFrame(() => requestAnimationFrame(() => {
    sp.classList.add('hide');
    setTimeout(() => { if (sp.parentNode) sp.remove(); }, 550);
  }));
  const done = () => {
    if (fired) return; fired = true;
    setTimeout(hide, Math.max(0, SPLASH_MIN_MS - performance.now()));
  };
  const fonts = (document.fonts && document.fonts.ready) ? document.fonts.ready : Promise.resolve();
  Promise.race([fonts, new Promise((r) => setTimeout(r, 4000))]).then(done);
  setTimeout(done, 6000);   // batas aman: jangan sampai splash nyangkut
}
(async function init() {
  try {
    const c = await api('/api/config');
    CFG = Object.assign(CFG, c);
    S.template = CFG.defaultTemplate;
    applyOutputMode();
    applyTheme(CFG.theme);
    applyBackground(CFG.theme);
    if ($('#eventName')) $('#eventName').textContent = c.eventName;
    if ($('#topbarLogo')) {
      if (c.logo) {
        $('#topbarLogo').src = c.logo;
        $('#topbarLogo').classList.remove('hidden');
      } else {
        $('#topbarLogo').classList.add('hidden');
      }
    }
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
  revealApp();
})();

// ---------- Akses Rahasia Studio (Hidden Gesture: Tap 4x pojok kanan atas) ----------
let adminTapCount = 0;
let adminTapTimer = null;
const secretTap = $('#secretAdminTap');
if (secretTap) {
  secretTap.addEventListener('click', (e) => {
    e.stopPropagation();
    adminTapCount += 1;
    clearTimeout(adminTapTimer);
    adminTapTimer = setTimeout(() => { adminTapCount = 0; }, 1800);
    if (adminTapCount >= 3) {   // ketuk 3x di kanan atas
      adminTapCount = 0;
      openAdminPinModal();
    }
  });
}

// Pintasan Keyboard: Tekan Escape atau Q 3x berturut-turut untuk buka menu admin
let adminKeyCount = 0;
let adminKeyTimer = null;
window.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
  if (e.key === 'Escape' || e.key.toLowerCase() === 'q') {
    adminKeyCount += 1;
    clearTimeout(adminKeyTimer);
    adminKeyTimer = setTimeout(() => { adminKeyCount = 0; }, 1500);
    if (adminKeyCount >= 3) {
      adminKeyCount = 0;
      openAdminPinModal();
    }
  }
});

async function openAdminPinModal() {
  try {
    const _st = await api('/api/studio/session');
    if (_st && _st.needSetup) { window.location.href = '/studio'; return; }
  } catch (_) {}
  const m = $('#adminPinModal');
  const inp = $('#adminPinInput');
  const err = $('#adminPinErr');
  const pinView = $('#adminPinView');
  const licView = $('#adminLicenseView');
  const confView = $('#adminShutdownConfirmView');
  const succView = $('#adminLicenseSuccessView');
  if (!m || !inp) return;
  if (pinView) pinView.classList.remove('hidden');
  if (licView) licView.classList.add('hidden');
  if (confView) confView.classList.add('hidden');
  if (succView) succView.classList.add('hidden');
  inp.value = '';
  if (err) err.classList.add('hidden');
  m.classList.remove('hidden');
  setTimeout(() => inp.focus(), 150);
}

function closeAdminPinModal() {
  const m = $('#adminPinModal');
  if (m) m.classList.add('hidden');
}

$('#btnAdminPinCancel')?.addEventListener('click', closeAdminPinModal);
$('#btnAdminModalClose')?.addEventListener('click', closeAdminPinModal);
$('#btnAdminPinSubmit')?.addEventListener('click', submitAdminPin);
$('#adminPinInput')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') submitAdminPin();
  if (e.key === 'Escape') closeAdminPinModal();
});

// Klik "🛑 Shut Down": Tampilkan modal konfirmasi custom versi aplikasi (bukan dialog native)
$('#btnAdminShutdown')?.addEventListener('click', () => {
  const inp = $('#adminPinInput');
  const err = $('#adminPinErr');
  const pin = (inp?.value || '').trim();
  if (!pin) {
    if (err) {
      err.textContent = 'Masukkan PIN admin untuk mematikan AdsBooth.';
      err.classList.remove('hidden');
    }
    inp?.focus();
    return;
  }
  // Beralih ke view konfirmasi custom di dalam modal aplikasi
  $('#adminPinView')?.classList.add('hidden');
  $('#adminLicenseView')?.classList.add('hidden');
  $('#adminShutdownConfirmView')?.classList.remove('hidden');
});

// Tombol Batal pada konfirmasi shut down -> kembali ke input PIN
$('#btnConfirmShutdownNo')?.addEventListener('click', () => {
  $('#adminShutdownConfirmView')?.classList.add('hidden');
  $('#adminPinView')?.classList.remove('hidden');
  $('#adminPinInput')?.focus();
});

// Tombol "Ya, Matikan Sekarang" pada konfirmasi shut down
$('#btnConfirmShutdownYes')?.addEventListener('click', async () => {
  const btn = $('#btnConfirmShutdownYes');
  const inp = $('#adminPinInput');
  const err = $('#adminPinErr');
  const pin = (inp?.value || '').trim();

  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Mematikan sistem...';
  }

  try {
    const res = await api('/api/admin/shutdown', { pin });
    if (res.ok) {
      document.body.innerHTML = '<div style="position:fixed;inset:0;background:#0f172a;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:sans-serif;text-align:center;padding:24px"><div style="font-size:56px;margin-bottom:16px">👋</div><b style="font-size:26px;margin-bottom:10px">AdsBooth Sedang Dimatikan...</b><p style="color:#94a3b8;font-size:16px;max-width:440px;line-height:1.5">Sistem dan server telah dinonaktifkan dengan aman. Layar ini akan tertutup otomatis.</p></div>';
      setTimeout(() => {
        try { window.close(); } catch (_) {}
      }, 1200);
    } else {
      throw new Error(res.error || 'PIN salah');
    }
  } catch (e) {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🛑 Ya, Matikan Sekarang';
    }
    // Kembali ke view PIN dan tampilkan error
    $('#adminShutdownConfirmView')?.classList.add('hidden');
    $('#adminPinView')?.classList.remove('hidden');
    if (err) {
      err.textContent = e.message || 'PIN salah, gagal mematikan AdsBooth.';
      err.classList.remove('hidden');
    }
    if (inp) {
      inp.value = '';
      inp.focus();
    }
  }
});

// Toggle view Lupa PIN di Modal Kiosk
$('#btnAdminForgotPin')?.addEventListener('click', () => {
  $('#adminPinView')?.classList.add('hidden');
  $('#adminShutdownConfirmView')?.classList.add('hidden');
  $('#adminLicenseView')?.classList.remove('hidden');
  const inpLic = $('#adminLicenseInput');
  if (inpLic) { inpLic.value = ''; inpLic.focus(); }
  $('#adminLicenseErr')?.classList.add('hidden');
});

$('#btnAdminLicenseBack')?.addEventListener('click', () => {
  $('#adminLicenseView')?.classList.add('hidden');
  $('#adminShutdownConfirmView')?.classList.add('hidden');
  $('#adminPinView')?.classList.remove('hidden');
  $('#adminPinInput')?.focus();
});

$('#btnAdminLicenseSubmit')?.addEventListener('click', submitAdminLicenseReset);
$('#adminLicenseInput')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitAdminLicenseReset(); }
});

async function submitAdminLicenseReset() {
  const inp = $('#adminLicenseInput');
  const err = $('#adminLicenseErr');
  const licenseKey = (inp?.value || '').trim();
  if (!licenseKey) return;
  if (err) err.classList.add('hidden');
  try {
    const res = await api('/api/studio/reset-pin-license', { licenseKey, newPin: '1234' });
    if (res.ok) {
      $('#adminLicenseView')?.classList.add('hidden');
      $('#adminPinView')?.classList.add('hidden');
      $('#adminShutdownConfirmView')?.classList.add('hidden');
      $('#adminLicenseSuccessView')?.classList.remove('hidden');
      $('#btnAdminLicenseSuccessOk')?.addEventListener('click', () => {
        window.location.href = '/studio';
      });
    } else {
      throw new Error(res.error || 'Kode lisensi tidak valid');
    }
  } catch (e) {
    if (err) {
      err.textContent = e.message || 'Kode lisensi tidak valid.';
      err.classList.remove('hidden');
    }
  }
}

async function submitAdminPin() {
  const inp = $('#adminPinInput');
  const err = $('#adminPinErr');
  const pin = (inp?.value || '').trim();
  if (!pin) return;
  try {
    const res = await api('/api/studio/login', { pin });
    if (res.ok) {
      window.location.href = '/studio';
    } else {
      throw new Error(res.error || 'PIN salah');
    }
  } catch (e) {
    if (err) {
      err.textContent = e.message || 'PIN salah, silakan coba lagi.';
      err.classList.remove('hidden');
    }
    if (inp) {
      inp.value = '';
      inp.focus();
    }
  }
}

// ---------- Modal Notifikasi Sistem In-App Kiosk ----------
function showKioskAlert(title, message, icon = 'ℹ️', btnText = 'OK', isHtml = false) {
  return new Promise((resolve) => {
    const modal = $('#kioskAppModal');
    const t = $('#kioskModalTitle');
    const msg = $('#kioskModalMessage');
    const ico = $('#kioskModalIcon');
    const btnOk = $('#btnKioskModalOk');
    const btnCancel = $('#btnKioskModalCancel');
    if (!modal) {
      resolve(true);
      return;
    }
    if (t) t.textContent = title;
    if (msg) {
      if (isHtml) msg.innerHTML = message;
      else msg.textContent = message;
    }
    if (ico) {
      ico.textContent = icon;
      if (icon === '⏱️' || icon === '❌' || icon === '🛑') {
        ico.style.background = '#fee2e2';
        ico.style.color = '#dc2626';
      } else if (icon === '⚠️') {
        ico.style.background = '#fef3c7';
        ico.style.color = '#d97706';
      } else if (icon === '✅') {
        ico.style.background = '#dcfce7';
        ico.style.color = '#15803d';
      } else {
        ico.style.background = '#dbeafe';
        ico.style.color = '#1d4ed8';
      }
    }
    if (btnOk) btnOk.textContent = btnText;
    if (btnCancel) btnCancel.classList.add('hidden');
    modal.classList.remove('hidden');

    const onOk = () => {
      btnOk?.removeEventListener('click', onOk);
      modal.classList.add('hidden');
      resolve(true);
    };
    btnOk?.addEventListener('click', onOk);
  });
}

function showKioskConfirm(title, message, okText = 'Ya', cancelText = 'Batal', icon = '❓', isHtml = false) {
  return new Promise((resolve) => {
    const modal = $('#kioskAppModal');
    const t = $('#kioskModalTitle');
    const msg = $('#kioskModalMessage');
    const ico = $('#kioskModalIcon');
    const btnOk = $('#btnKioskModalOk');
    const btnCancel = $('#btnKioskModalCancel');
    if (!modal) {
      resolve(false);
      return;
    }
    if (t) t.textContent = title;
    if (msg) {
      if (isHtml) msg.innerHTML = message;
      else msg.textContent = message;
    }
    if (ico) {
      ico.textContent = icon;
      if (icon === '❌' || icon === '🛑') {
        ico.style.background = '#fee2e2';
        ico.style.color = '#dc2626';
      } else if (icon === '⚠️') {
        ico.style.background = '#fef3c7';
        ico.style.color = '#d97706';
      } else {
        ico.style.background = '#dbeafe';
        ico.style.color = '#1d4ed8';
      }
    }
    if (btnOk) btnOk.textContent = okText;
    if (btnCancel) {
      btnCancel.textContent = cancelText;
      btnCancel.classList.remove('hidden');
    }
    modal.classList.remove('hidden');

    const cleanUp = () => {
      btnOk?.removeEventListener('click', onOk);
      btnCancel?.removeEventListener('click', onCancel);
      modal.classList.add('hidden');
    };
    const onOk = () => {
      cleanUp();
      resolve(true);
    };
    const onCancel = () => {
      cleanUp();
      resolve(false);
    };
    btnOk?.addEventListener('click', onOk);
    btnCancel?.addEventListener('click', onCancel);
  });
}

// Modal info status printer ketika indikator pojok kanan bawah diketuk
async function showPrinterStatusModal() {
  const s = lastPrinterStatus || {};
  let d = null;
  try {
    if (typeof PBUSB !== 'undefined') d = await PBUSB.paired();
  } catch (_) {}

  const isAndroid = typeof window.AndroidUsbPrinter !== 'undefined';
  let rawMsg = (s && s.message) || (lastServerError ? 'Koneksi ke backend server gagal: ' + lastServerError : '');
  let devCount = 0;
  if (isAndroid) {
    try {
      const raw = window.AndroidUsbPrinter.getStatus();
      const st = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (st) {
        if (st.message) rawMsg = st.message;
        if (st.device_count !== undefined) devCount = st.device_count;
      }
    } catch (_) {}
  }

  const isOk = !!(s && s.ok && (!d || d.hasPermission !== false));
  const hasPerm = d ? d.hasPermission : (s && s.has_permission);
  const devName = (d && d.name) || (s && s.device_name) || (isAndroid ? (devCount > 0 ? 'Perangkat USB lain' : 'Tidak ada perangkat USB terdeteksi') : (s.name || 'Printer'));
  const statusColor = isOk ? '#16a34a' : (hasPerm === false ? '#d97706' : '#dc2626');
  const statusLabel = isOk ? 'SIAP DIGUNAKAN' : (hasPerm === false ? 'BUTUH IZIN AKSES USB' : 'BELUM TERHUBUNG');
  const statusIcon = isOk ? '🖨️' : (hasPerm === false ? '🔑' : '⚠️');

  const html = `
    <div style="text-align:left;font-size:14px;line-height:1.55;color:#1f2937">
      <div style="display:flex;align-items:center;justify-content:space-between;background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:10px 14px;margin-bottom:12px">
        <div>
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;font-weight:700">Status Printer</div>
          <div style="font-weight:800;font-size:15px;color:${statusColor}">${statusLabel}</div>
        </div>
        <div style="font-size:24px">${statusIcon}</div>
      </div>
      <div style="margin-bottom:10px">
        <div style="font-size:11px;color:#6b7280;font-weight:700;text-transform:uppercase;margin-bottom:2px">Perangkat:</div>
        <div style="font-weight:600;font-size:14px;color:#111">${devName}</div>
      </div>
      <div style="background:#f3f4f6;border-radius:12px;padding:10px 14px;font-size:12.5px;color:#374151;margin-bottom:14px;border:1px solid #e5e7eb;word-break:break-word">
        <b style="color:#111">Diagnosa Sistem:</b><br>${rawMsg || 'Belum ada info status printer.'}
      </div>
      <div style="font-size:12px;color:#4b5563;background:#fffbeb;border:1px solid #fde68a;border-radius:12px;padding:10px 14px;line-height:1.5">
        <b style="color:#92400e">Petunjuk jika printer belum tersambung:</b>
        <ol style="margin:4px 0 0;padding-left:18px">
          <li>Pastikan kabel OTG tercolok kuat ke tablet dan printer ON.</li>
          <li>Di HP/Tablet Android: Buka <b>Pengaturan &rarr; Pengaturan Tambahan / Sistem &rarr; aktifkan 'Koneksi OTG'</b>.</li>
          <li>Ketuk tombol di bawah untuk meminta dialog izin USB.</li>
        </ol>
      </div>
    </div>
  `;

  const ok = await showKioskConfirm(
    'Status Printer USB',
    html,
    'Sambungkan / Minta Izin',
    'Tutup',
    statusIcon,
    true
  );

  if (ok) {
    await usbConnect();
    pollStatus();
  }
}

// Pasang klik pada indikator printer pojok kanan bawah
const printerIndicator = $('#stepLabel');
if (printerIndicator) {
  printerIndicator.addEventListener('click', showPrinterStatusModal);
}

// Override dialog native browser di Kiosk agar 100% menggunakan modal sistem
window.alert = function(msg) {
  return showKioskAlert('Pemberitahuan', String(msg || ''), 'ℹ️', 'OK');
};
window.confirm = function(msg) {
  return showKioskConfirm('Konfirmasi', String(msg || ''), 'Ya', 'Batal', '❓');
};
