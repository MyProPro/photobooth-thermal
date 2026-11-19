// Thermal Photobooth — alur kiosk
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
  S = { layout: CFG.defaultLayout || 'strip', copies: 1, style: 'dither', caption: '', showLogo: true,
        photos: [], lastPrint: null, printed: 0, template: CFG.defaultTemplate, photoVer: 0, tplKey: '',
        poses: [], guestbook: null, certTitle: '', pendingJobs: null };
  if ($('#gbName')) { $('#gbName').value = ''; $('#gbMsg').value = ''; clearSign(); }
  $('#caption').value = '';
  $('#showLogo').checked = true;
  renderOptions();
}

// ---------- navigasi ----------
function go(name) {
  $$('.screen').forEach((el) => el.classList.remove('active'));
  $('#s-' + name).classList.add('active');
  document.body.classList.toggle('dark', name === 'camera');
  current = name;
  clearInterval(styleTimer); styleTimer = null;
  clearInterval(resetTimer); resetTimer = null;
  if (name === 'style') startStylePreview();
  if (name === 'review') { S.pendingJobs = null; renderReview(); }
  if (name === 'template') renderTemplates();
  if (name === 'guestbook') setTimeout(sizePad, 50);
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
  freshState(); go('welcome');
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

async function startCamera() {
  if (stream || DUMMY) return true;
  if (CFG.dummyCamera || !(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)) {
    enableDummy('dummy_camera / browser tanpa kamera');
    return true;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: CFG.cameraFacing || 'user', width: { ideal: 1920 }, height: { ideal: 1080 } },
      audio: false });
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

$('#btnStart').addEventListener('click', async () => {
  kioskMode();
  freshState();
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
$$('#layoutOptions .opt').forEach((b) => b.addEventListener('click', () => { S.layout = b.dataset.layout; renderOptions(); }));
$('#copyInc').addEventListener('click', () => { S.copies = Math.min(CFG.maxCopies, S.copies + 1); renderOptions(); });
$('#copyDec').addEventListener('click', () => { S.copies = Math.max(1, S.copies - 1); renderOptions(); });

// ---------- 3. gaya ----------
let styleBusy = false;
async function refreshStylePreview() {
  if (styleBusy || current !== 'style') return;
  const photo = capture(800);
  if (!photo) return;
  styleBusy = true;
  try {
    const j = await api('/api/stylize', { photo, style: S.style });
    if (current === 'style') $('#stylePreview').src = j.image;
  } catch (e) { console.warn(e); }
  styleBusy = false;
}
function startStylePreview() {
  startCamera().then(() => setTimeout(refreshStylePreview, 400));
  styleTimer = setInterval(refreshStylePreview, 2500);
}
$$('#styleOptions .opt').forEach((b) => b.addEventListener('click', () => {
  S.style = b.dataset.style; renderOptions(); refreshStylePreview();
}));
$('#caption').addEventListener('input', (e) => { S.caption = e.target.value; });
$('#showLogo').addEventListener('change', (e) => { S.showLogo = e.target.checked; });

$('#btnShoot').addEventListener('click', () => {
  const n = SHOTS[S.layout];
  S.photos = new Array(n).fill(null);
  shoot([...Array(n).keys()]);
});

// ---------- 4. kamera ----------
function renderThumbs(activeIdx) {
  const n = SHOTS[S.layout];
  $('#thumbs').innerHTML = '';
  for (let i = 0; i < n; i++) {
    const d = document.createElement('div');
    if (S.photos[i] && i !== activeIdx) { d.className = 'done'; d.style.backgroundImage = `url(${S.photos[i]})`; }
    else if (i === activeIdx) { d.className = 'now'; d.textContent = 'SEKARANG'; }
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
    for (const idx of indices) {
      if (current !== 'camera') return;
      $('#shotLabel').textContent = `FOTO ${idx + 1} DARI ${n}`;
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
      S.photos[idx] = capture();
      S.photoVer += 1;
      const f = $('#flash'); f.classList.add('on'); await sleep(60); f.classList.remove('on');
      renderThumbs(-1);
      await sleep(900);
    }
    if (current === 'camera') go(next);
  } finally {
    shooting = false;
    $('#count').textContent = '';
  }
}
$('#btnShutter').addEventListener('click', () => { skipCountdown = true; });
$('#btnCancel').addEventListener('click', () => resetAll());

// ---------- 4b. pilih template ----------
function markTemplate() {
  $$('#tplList .tpl').forEach((b) => {
    const on = b.dataset.id === S.template;
    b.classList.toggle('on', on); b.setAttribute('aria-pressed', on);
  });
}
let tplSeq = 0;
async function renderTemplates() {
  const key = [S.photoVer, S.layout, S.style, S.caption, S.showLogo].join('|');
  if (key === S.tplKey && $('#tplList .tpl')) { markTemplate(); return; }
  const seq = ++tplSeq;
  const list = $('#tplList');
  list.innerHTML = '<div class="loading mono">MENYIAPKAN TEMPLATE…</div>';
  $('#btnTplNext').disabled = true;
  let prep;
  try {
    prep = await api('/api/templates/prepare', payload());
  } catch (e) {
    list.innerHTML = '<div class="loading mono">GAGAL MEMUAT TEMPLATE: ' + e.message + '</div>';
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
    b.innerHTML = '<div class="tpl-img wait"><img alt="" class="hidden"><span class="mono">MENYIAPKAN…</span></div><b></b>';
    b.querySelector('img').alt = 'Template ' + t.name;
    b.querySelector('b').textContent = t.name;
    b.addEventListener('click', () => { S.template = t.id; markTemplate(); });
    list.appendChild(b);
  });
  if (!prep.templates.some((t) => t.id === S.template) && prep.templates.length) S.template = prep.templates[0].id;
  S.tplKey = key;
  markTemplate();
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
          img.src = j.image; img.classList.remove('hidden');
          box.classList.remove('wait'); box.querySelector('span').remove();
        } else {
          box.querySelector('span').textContent = 'GAGAL';
        }
      } catch (e) { /* lanjut template berikutnya */ }
    }
  };
  const workers = Math.max(1, Math.min(CFG.renderWorkers || 3, queue.length));
  await Promise.all(Array.from({ length: workers }, worker));
}
$('#btnTplNext').addEventListener('click', () => go('review'));
$('#btnTplRetake').addEventListener('click', () => {
  S.photos = new Array(SHOTS[S.layout]).fill(null);
  shoot([...Array(SHOTS[S.layout]).keys()], 'template');
});

// ---------- 5. review ----------
function payload() {
  return { layout: S.layout, style: S.style, caption: S.caption, showLogo: S.showLogo,
           copies: S.copies, template: S.template, photos: S.photos.filter(Boolean),
           poses: S.poses.slice(0, SHOTS[S.layout]), guestbook: S.guestbook, certTitle: S.certTitle };
}
function renderCertPick() {
  const on = S.template === 'sertifikat' && CFG.certTitles.length;
  $('#certPick').classList.toggle('hidden', !on);
  if (!on) return;
  if (!S.certTitle) S.certTitle = CFG.certTitles[Math.floor(Math.random() * CFG.certTitles.length)];
  const box = $('#certChips');
  box.innerHTML = '';
  const dice = document.createElement('button');
  dice.type = 'button'; dice.className = 'chip dice'; dice.textContent = 'Acak';
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
    $('#receiptPreview').src = j.image;
  } catch (e) {
    $('#previewLoading').textContent = 'PREVIEW GAGAL: ' + e.message;
    return;
  }
  $('#previewLoading').classList.add('hidden');
  $('#btnPrint').disabled = false;
}

async function renderReview() {
  const list = $('#shotList');
  list.innerHTML = '';
  S.photos.forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'shot';
    row.innerHTML = `<img alt=""><b>Foto ${i + 1}</b><button type="button">Ulangi</button>`;
    row.querySelector('img').src = p || '';
    row.querySelector('button').addEventListener('click', () => shoot([i], 'review'));
    list.appendChild(row);
  });
  renderCertPick();
  await renderPreview();
}
$('#btnRetakeAll').addEventListener('click', () => {
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
  $('#printStatus').textContent = 'Mohon tunggu sebentar';
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
      $('#printStatus').textContent = 'Mengirim ke printer…';
      await PBUSB.printJobs(j.jobs);
      S.pendingJobs = null;
    }
    clearInterval(anim);
    setPct(100);
    S.printed = S.copies;
    $('#printStatus').textContent = 'Selesai! Kertas sedang dipotong.';
    await sleep(900);
    go('done');
  } catch (e) {
    clearInterval(anim);
    $('#printErrorMsg').textContent = e.message;
    $('#btnUsbErr').classList.toggle('hidden', CFG.printerMode !== 'webusb');
    $('#printError').classList.remove('hidden');
    $('#printStatus').textContent = 'Ada masalah dengan printer.';
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
    if (e.name !== 'NotFoundError') alert('Gagal menyambungkan printer: ' + e.message);
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
  $('#btnReprint').textContent = left > 0 ? `Cetak lagi (${left}×)` : 'Cetak lagi';
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
  } catch (e) { alert('Gagal cetak ulang: ' + e.message); }
  clearInterval(resetTimer);
  startResetCountdown();
});

// ---------- status printer ----------
async function pollStatus() {
  try {
    const s = await api('/api/status');
    // Event diganti dari Studio -> muat ulang kiosk (langsung kalau sedang di layar awal)
    if (s.eventVersion && CFG.eventVersion && s.eventVersion !== CFG.eventVersion) {
      if (current === 'welcome') { location.reload(); return; }
      pendingReload = true;
    }
    const low = s.paper && s.paper.low;
    if (s.mode === 'webusb') {
      const d = await PBUSB.paired().catch(() => null);
      $('#btnUsb').classList.toggle('hidden', !!d);
      if (!d) {
        $('#statusDot').className = 'dot warn';
        $('#statusText').textContent = PBUSB.supported() ? 'PRINTER USB BELUM DISAMBUNGKAN' : 'BROWSER TIDAK MENDUKUNG USB';
        return;
      }
    } else {
      $('#btnUsb').classList.add('hidden');
    }
    $('#statusDot').className = 'dot ' + (!s.ok ? 'bad' : (low ? 'warn' : 'ok'));
    $('#statusText').textContent = !s.ok ? 'PRINTER BERMASALAH'
      : (low ? `KERTAS HAMPIR HABIS (${s.paper.left_m} m)` : (s.mode === 'file' ? 'MODE TES (TANPA PRINTER)' : 'PRINTER SIAP'));
    $('#statusText').title = s.message || '';
  } catch (e) {
    $('#statusDot').className = 'dot bad';
    $('#statusText').textContent = 'SERVER TIDAK TERHUBUNG';
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

// ---------- init ----------
(async function init() {
  try {
    const c = await api('/api/config');
    CFG = Object.assign(CFG, c);
    S.template = CFG.defaultTemplate;
    $('#eventName').textContent = c.eventName;
  } catch (e) { console.warn(e); }
  freshState();
  pollStatus();
  setInterval(pollStatus, 15000);
  // Mode kiosk hanya kalau dibuka dengan ?kiosk=1 (run.bat). Di browser biasa klik kanan tetap bisa.
  if (new URLSearchParams(location.search).has('kiosk')) {
    document.body.classList.add('kiosk');
    document.addEventListener('contextmenu', (e) => e.preventDefault());
  }
})();
