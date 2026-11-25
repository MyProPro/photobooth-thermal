// AdsBooth Studio — kelola event & template custom
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const uid = () => Math.random().toString(36).slice(2, 8);
const clone = (o) => JSON.parse(JSON.stringify(o));

let META = null, EVENTS = [], ACTIVE = '';
let ev = null;            // salinan event yang sedang diedit
let dirty = false;
let selTpl = 'klasik';    // template yang di-preview
let editId = null;        // id template custom yang sedang diedit
let pvLayout = 'strip';
const LAYOUT_NAMES = { solo: 'Solo (1)', duo: 'Duo (2)', strip: 'Strip (3)', grid: 'Grid (4)' };
const LAYOUT_N = { solo: 1, duo: 2, strip: 3, grid: 4 };

// ---------------------------------------------------------------- API
async function api(path, opts = {}) {
  const headers = Object.assign({}, opts.headers || {});
  const pin = sessionStorage.getItem('studioPin');
  if (pin) headers['X-Studio-Pin'] = pin;
  if (opts.json !== undefined) { headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(opts.json); }
  const r = await fetch(path, { method: opts.method || (opts.body ? 'POST' : 'GET'), headers, body: opts.body });
  if (r.status === 401) {            // sesi habis -> minta PIN lagi, lalu ulangi permintaan
    await showAuth(false);
    return api(path, opts);
  }
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.ok === false) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}
const assetUrl = (f) => f ? `/api/studio/events/${encodeURIComponent(ev.id)}/asset/${encodeURIComponent(f)}` : '';

function setDirty(v = true) {
  dirty = v;
  $('#saveBar').classList.toggle('hidden', !v);
}
window.addEventListener('beforeunload', (e) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

// ---------------------------------------------------------------- event list
async function loadEvents() {
  const j = await api('/api/studio/events');
  EVENTS = j.events; ACTIVE = j.active;
  const act = EVENTS.find((e) => e.id === ACTIVE);
  if (act) {
    $('#activeBadge').classList.remove('hidden');
    $('#activeBadge').classList.add('on');
    $('#activeText').textContent = 'Aktif: ' + act.name;
  } else {
    $('#activeBadge').classList.add('hidden');
    $('#activeBadge').classList.remove('on');
    $('#activeText').textContent = '';
  }
  $('#eventList').innerHTML = EVENTS.length ? '' : '<p class="hint">Belum ada event.</p>';
  EVENTS.forEach((e) => {
    const b = document.createElement('button');
    b.className = 'ev' + (ev && ev.id === e.id ? ' sel' : '');
    b.innerHTML = `<b>${esc(e.name)}</b><span class="small muted">${esc(e.event_name)}</span>
      <div class="row" style="margin-top:6px">${e.active ? '<span class="badge on"><span class="dot"></span>AKTIF</span>' : ''}
      ${e.custom_count ? `<span class="badge">${e.custom_count} template custom</span>` : ''}</div>`;
    b.addEventListener('click', () => openEvent(e.id));
    $('#eventList').appendChild(b);
  });
  if (ev) $('#btnActivate').textContent = ev.id === ACTIVE ? '✓ Aktif di kiosk' : 'Aktifkan di kiosk';
}

async function openEvent(id) {
  if (dirty && !(await showStudioConfirm('Pindah Event', 'Perubahan belum disimpan. Tetap pindah event?', 'Tetap Pindah', 'Batal', '⚠️'))) return;
  const j = await api('/api/studio/events/' + encodeURIComponent(id));
  ev = j.event;
  ev.custom_templates = ev.custom_templates || [];
  setDirty(false);
  editId = null;
  ev.photo_frames = ev.photo_frames || {};
  selTpl = (ev.output === 'photo' ? ev.photo_default_template : ev.default_template) || 'klasik';
  $('#emptyState').classList.add('hidden');
  $('#settings').classList.add('hidden');
  $('#licenseView').classList.add('hidden');
  $('#editor').classList.remove('hidden');
  $('#btnSettings').classList.remove('sel');
  $('#btnLicenseNav').classList.remove('sel');
  renderInfo();
  renderOutput();
  renderTemplateList();
  showListView();
  loadEvents();
  schedulePreview();
}

$('#btnNewEvent').addEventListener('click', async () => {
  const name = await showStudioPrompt('Nama Event Baru', 'Masukkan nama event baru:', 'Wedding ...', 'Contoh: Wedding Budi & Ani', '🎉');
  if (!name || !name.trim()) return;
  const j = await api('/api/studio/events', { json: { name: name.trim() } });
  await loadEvents();
  dirty = false;
  openEvent(j.event.id);
});
$('#btnDuplicate').addEventListener('click', async () => {
  const name = await showStudioPrompt('Duplikasi Event', 'Nama event hasil duplikat:', ev.name + ' (salinan)', 'Nama Event', '📋');
  if (!name || !name.trim()) return;
  if (dirty) await save();
  const j = await api('/api/studio/events', { json: { name: name.trim(), from: ev.id } });
  openEvent(j.event.id);
});
$('#btnDelete').addEventListener('click', async () => {
  if (!(await showStudioConfirm('Hapus Event', `Hapus event "${ev.name}"?\n(Dipindah ke folder events/_trash)`, 'Hapus', 'Batal', '🗑️'))) return;
  await api('/api/studio/events/' + encodeURIComponent(ev.id), { method: 'DELETE' });
  ev = null; setDirty(false);
  $('#editor').classList.add('hidden'); $('#emptyState').classList.remove('hidden');
  loadEvents();
});
$('#btnActivate').addEventListener('click', async () => {
  if (dirty) await save();
  await api(`/api/studio/events/${encodeURIComponent(ev.id)}/activate`, { method: 'POST' });
  loadEvents();
});

async function save() {
  $('#saveState').textContent = 'Menyimpan…';
  try {
    delete ev.download_url;
    const j = await api('/api/studio/events/' + encodeURIComponent(ev.id), { method: 'PUT', json: ev });
    ev = j.event;
    setDirty(false);
    $('#evTitle').textContent = ev.name;
    loadEvents();
  } catch (e) {
    $('#saveState').textContent = 'Gagal: ' + e.message;
  }
}
$('#btnSave').addEventListener('click', save);
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && ev) { e.preventDefault(); save(); }
});

// ---------------------------------------------------------------- tabs
$$('.tabs button').forEach((b) => b.addEventListener('click', () => {
  $$('.tabs button').forEach((x) => x.classList.toggle('on', x === b));
  $('#tab-info').classList.toggle('hidden', b.dataset.tab !== 'info');
  $('#tab-templates').classList.toggle('hidden', b.dataset.tab !== 'templates');
  $('#tab-guest').classList.toggle('hidden', b.dataset.tab !== 'guest');
  if (b.dataset.tab === 'templates') schedulePreview();
  if (b.dataset.tab === 'guest') loadGuest();
}));

// ---------------------------------------------------------------- info
function renderInfo() {
  $('#evTitle').textContent = ev.name;
  $('#evId').textContent = 'events/' + ev.id;
  $$('#tab-info [data-k]').forEach((el) => {
    if (el.dataset.k === 'reset_seconds') el.value = String(ev.reset_seconds || 60);
    else el.value = ev[el.dataset.k] ?? '';
  });
  ev.social = Object.assign({ username: '', display: '{event}', website: '', bio: '{date_long}' }, ev.social || {});
  $$('#tab-info [data-s]').forEach((el) => { el.value = ev.social[el.dataset.s] ?? ''; });
  $('#qrToggle').checked = ev.qr_download !== false;
  if ($('#printQrToggle')) $('#printQrToggle').checked = !!ev.print_qr;
  ev.features = Object.assign({ guestbook: false, lucky_draw: false, pose_challenge: false, host_copy: false, living_photo: false }, ev.features || {});
  $$('#featureChecks [data-f]').forEach((el) => { el.checked = !!ev.features[el.dataset.f]; });
  $('#certTitles').value = (ev.cert_titles && ev.cert_titles.length ? ev.cert_titles : META.certTitles).join('\n');
  ev.boarding = Object.assign({ from_code: 'SNI', from: 'Sini', to_code: 'BHG', to: 'Bahagia' }, ev.boarding || {});
  $$('#tab-info [data-b]').forEach((el) => { el.value = ev.boarding[el.dataset.b] ?? ''; });
  const lc = $('#layoutChecks');
  lc.innerHTML = '';
  META.layouts.forEach((l) => {
    const lab = document.createElement('label');
    lab.className = 'check card';
    lab.style.padding = '10px 14px';
    lab.innerHTML = `<input type="checkbox" ${ev.layouts.includes(l) ? 'checked' : ''}> ${LAYOUT_NAMES[l]}`;
    lab.querySelector('input').addEventListener('change', (e) => {
      ev.layouts = META.layouts.filter((x) => x === l ? e.target.checked : ev.layouts.includes(x));
      if (!ev.layouts.length) { ev.layouts = [l]; e.target.checked = true; }
      renderDefaultLayout(); setDirty();
    });
    lc.appendChild(lab);
  });
  renderDefaultLayout();
  renderLogo();
  renderIntro();
  renderTheme();

  // Kasir & Pembayaran QRIS Kiosk
  ev.payment = Object.assign({
    enabled: false,
    method: 'qr',
    price_receipt: 15000,
    price_photo: 30000,
    timeout_seconds: 120,
    gateway: 'simulator',
    qris_image: ''
  }, ev.payment || {});
  if ($('#payEnabled')) $('#payEnabled').checked = !!ev.payment.enabled;
  if ($('#payPriceReceipt')) $('#payPriceReceipt').value = ev.payment.price_receipt ?? 15000;
  if ($('#payPricePhoto')) $('#payPricePhoto').value = ev.payment.price_photo ?? 30000;
  if ($('#payTimeout')) $('#payTimeout').value = String(ev.payment.timeout_seconds ?? 120);
  if ($('#payMethod')) $('#payMethod').value = ev.payment.method || 'qr';
  if ($('#payGateway')) $('#payGateway').value = ev.payment.gateway || 'simulator';
  renderPayGateway();
  renderPayQrisPrev();

  // Softcopy Foto & Auto-Delete Privasi
  const isQrOn = ev.qr_download !== false;
  if ($('#qrToggle')) $('#qrToggle').checked = isQrOn;
  if ($('#autoDeleteWrap')) $('#autoDeleteWrap').style.opacity = isQrOn ? '1' : '0.5';
  if ($('#downloadAutoDelete')) {
    $('#downloadAutoDelete').value = String(ev.download_auto_delete ?? 3);
    $('#downloadAutoDelete').disabled = !isQrOn;
  }
}

function renderPayGateway() {
  const method = ev.payment?.method || 'qr';
  const showGateway = method === 'qr' || method === 'both';
  const isStatic = showGateway && ev.payment?.gateway === 'static';
  const gwField = $('#payGatewayField');
  if (gwField) gwField.classList.toggle('hidden', !showGateway);
  const row = $('#payQrisImgRow');
  if (row) row.classList.toggle('hidden', !isStatic);
}

function renderPayQrisPrev() {
  const prev = $('#payQrisPrev');
  const del = $('#btnPayQrisDel');
  if (!prev || !del) return;
  if (ev.payment && ev.payment.qris_image) {
    prev.src = assetUrl(ev.payment.qris_image);
    prev.classList.remove('hidden');
    del.classList.remove('hidden');
  } else {
    prev.classList.add('hidden');
    del.classList.add('hidden');
  }
}
function renderDefaultLayout() {
  const s = $('#defaultLayout');
  s.innerHTML = ev.layouts.map((l) => `<option value="${l}">${LAYOUT_NAMES[l]}</option>`).join('');
  if (!ev.layouts.includes(ev.default_layout)) ev.default_layout = ev.layouts[0];
  s.value = ev.default_layout;
}
$$('#tab-info [data-k]').forEach((el) => ['input', 'change'].forEach((evt) => el.addEventListener(evt, () => {
  ev[el.dataset.k] = el.dataset.k === 'reset_seconds' ? parseInt(el.value, 10) : el.value;
  if (el.dataset.k === 'name') $('#evTitle').textContent = el.value;
  if (el.dataset.k === 'event_name') paintThemePrev();
  setDirty(); schedulePreview();
})));
$$('#tab-info [data-s]').forEach((el) => el.addEventListener('input', () => {
  ev.social[el.dataset.s] = el.value;
  setDirty(); schedulePreview();
}));
if ($('#qrToggle')) {
  $('#qrToggle').addEventListener('change', (e) => {
    ev.qr_download = e.target.checked;
    if ($('#autoDeleteWrap')) $('#autoDeleteWrap').style.opacity = e.target.checked ? '1' : '0.5';
    if ($('#downloadAutoDelete')) $('#downloadAutoDelete').disabled = !e.target.checked;
    setDirty();
    schedulePreview();
  });
}
if ($('#printQrToggle')) {
  $('#printQrToggle').addEventListener('change', (e) => {
    ev.print_qr = e.target.checked;
    setDirty();
    schedulePreview();
  });
}
$('#certTitles').addEventListener('input', (e) => {
  ev.cert_titles = e.target.value.split('\n').map((x) => x.trim()).filter(Boolean);
  setDirty(); schedulePreview();
});
$('#btnCertDefault').addEventListener('click', () => {
  $('#certTitles').value = META.certTitles.join('\n'); ev.cert_titles = META.certTitles.slice(); setDirty(); schedulePreview();
});
$$('#tab-info [data-b]').forEach((el) => el.addEventListener('input', () => {
  ev.boarding[el.dataset.b] = el.value; setDirty(); schedulePreview();
}));
$$('#featureChecks [data-f]').forEach((el) => el.addEventListener('change', () => {
  ev.features[el.dataset.f] = el.checked; setDirty(); schedulePreview();
}));

// Payment & softcopy listeners
if ($('#payEnabled')) {
  $('#payEnabled').addEventListener('change', (e) => {
    ev.payment.enabled = e.target.checked;
    setDirty();
  });
}
if ($('#payPriceReceipt')) {
  $('#payPriceReceipt').addEventListener('input', (e) => {
    ev.payment.price_receipt = parseInt(e.target.value) || 0;
    setDirty();
  });
}
if ($('#payPricePhoto')) {
  $('#payPricePhoto').addEventListener('input', (e) => {
    ev.payment.price_photo = parseInt(e.target.value) || 0;
    setDirty();
  });
}
if ($('#payTimeout')) {
  $('#payTimeout').addEventListener('change', (e) => {
    ev.payment.timeout_seconds = parseInt(e.target.value) || 120;
    setDirty();
  });
}
if ($('#payMethod')) {
  $('#payMethod').addEventListener('change', (e) => {
    ev.payment.method = e.target.value;
    renderPayGateway();
    setDirty();
  });
}
if ($('#payGateway')) {
  $('#payGateway').addEventListener('change', (e) => {
    ev.payment.gateway = e.target.value;
    renderPayGateway();
    setDirty();
  });
}
if ($('#payQrisFile')) {
  $('#payQrisFile').addEventListener('change', async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const r = await upload(f, 'qris');
      ev.payment.qris_image = r.file;
      setDirty();
      renderPayQrisPrev();
    } catch (err) {
      await showStudioAlert('Upload Gagal', 'Upload QRIS gagal: ' + err.message, '❌');
    }
    e.target.value = '';
  });
}
if ($('#btnPayQrisDel')) {
  $('#btnPayQrisDel').addEventListener('click', () => {
    ev.payment.qris_image = '';
    setDirty();
    renderPayQrisPrev();
  });
}

if ($('#downloadAutoDelete')) {
  $('#downloadAutoDelete').addEventListener('change', (e) => {
    ev.download_auto_delete = parseInt(e.target.value) || 3;
    setDirty();
  });
}
// ---------------------------------------------------------------- tema kiosk
const THEME_PRESETS = {
  krem:  { label: 'Krem klasik', paper: '#F2EFE8', text: '#121212', card: '#FFFFFF', btn: '#121212', btn_text: '#F2EFE8', accent: '#C8410F', printer: '#121212', font: 'modern' },
  gelap: { label: 'Gelap', paper: '#141414', text: '#F2EFE8', card: '#232323', btn: '#F2EFE8', btn_text: '#141414', accent: '#FF8A5C', printer: '#2E2E2E', font: 'modern' },
  navy:  { label: 'Navy & emas', paper: '#F7F3EA', text: '#1B2A41', card: '#FFFFFF', btn: '#1B2A41', btn_text: '#F7F3EA', accent: '#B08D57', printer: '#1B2A41', font: 'elegan' },
  pink:  { label: 'Pink pastel', paper: '#FBEFF1', text: '#3A2A2E', card: '#FFFFFF', btn: '#C9566F', btn_text: '#FFFFFF', accent: '#C9566F', printer: '#3A2A2E', font: 'geometris' },
  sage:  { label: 'Hijau sage', paper: '#EEF2EA', text: '#1F2A22', card: '#FFFFFF', btn: '#4E6B55', btn_text: '#FFFFFF', accent: '#B8692E', printer: '#1F2A22', font: 'geometris' },
};
const THEME_KEYS = [['paper', 'Latar'], ['text', 'Teks'], ['card', 'Kartu'], ['btn', 'Tombol'], ['btn_text', 'Teks tombol'],
  ['accent', 'Aksen'], ['printer', 'Printer']];
const THEME_FONT_CSS = { modern: "'Space Grotesk',sans-serif", elegan: "'PB Playfair',Georgia,serif", geometris: "'PB Josefin',sans-serif",
  tegas: "'PB Archivo',sans-serif", poster: "'PB Bebas',sans-serif" };
const BG_PATTERNS = {
  polos: { label: 'Polos', url: '', size: '' },
  titik: { label: 'Titik', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18'%3E%3Ccircle cx='9' cy='9' r='1.6'/%3E%3C/svg%3E\")", size: '18px 18px' },
  garis: { label: 'Garis', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20'%3E%3Crect y='9' width='20' height='1.6'/%3E%3C/svg%3E\")", size: '20px 20px' },
  kotak: { label: 'Kotak', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='28'%3E%3Cpath d='M0 0h28v1.4H0zM0 0h1.4v28H0z'/%3E%3C/svg%3E\")", size: '28px 28px' },
  diagonal: { label: 'Diagonal', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16'%3E%3Cpath d='M-2 18L18 -2l1.2 1.2L-0.8 19.2zM14 18l4-4 1.2 1.2-4 4z'/%3E%3C/svg%3E\")", size: '16px 16px' },
  gelombang: { label: 'Gelombang', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='48' height='24'%3E%3Cpath d='M0 12q12-10 24 0t24 0' fill='none' stroke='black' stroke-width='1.8'/%3E%3C/svg%3E\")", size: '48px 24px' },
  zigzag: { label: 'Zigzag', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='20'%3E%3Cpath d='M0 14l8-8 8 8 8-8 8 8' fill='none' stroke='black' stroke-width='1.8'/%3E%3C/svg%3E\")", size: '32px 20px' },
  konfeti: { label: 'Konfeti', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Crect x='10' y='14' width='10' height='4' transform='rotate(30 15 16)'/%3E%3Ccircle cx='70' cy='20' r='3'/%3E%3Crect x='95' y='60' width='10' height='4' transform='rotate(-40 100 62)'/%3E%3Ccircle cx='30' cy='80' r='2.5'/%3E%3Crect x='55' y='95' width='9' height='4' transform='rotate(70 59 97)'/%3E%3Cpath d='M45 45l4 8 4-8z'/%3E%3Ccircle cx='105' cy='105' r='2'/%3E%3Cpath d='M85 25l3 6 3-6z'/%3E%3C/svg%3E\")", size: '120px 120px' },
  hati: { label: 'Hati', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='56'%3E%3Cpath d='M14 22c-4-4-10-1-8 4 1 3 8 8 8 8s7-5 8-8c2-5-4-8-8-4z'/%3E%3Cpath d='M42 34c-3-3-7-1-6 3 1 2 6 6 6 6s5-4 6-6c1-4-3-6-6-3z'/%3E%3C/svg%3E\")", size: '56px 56px' },
  bintang: { label: 'Bintang', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3Cpath d='M15 6l2.6 5.6 6 .7-4.5 4.1 1.2 6-5.3-3-5.3 3 1.2-6L6.4 12.3l6-.7z'/%3E%3Cpath d='M45 36l1.6 3.4 3.7.4-2.8 2.6.8 3.7-3.3-1.9-3.3 1.9.8-3.7-2.8-2.6 3.7-.4z'/%3E%3C/svg%3E\")", size: '60px 60px' },
  bunga: { label: 'Bunga', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='64' height='64'%3E%3Cg transform='translate(16 16)'%3E%3Ccircle r='3'/%3E%3Ccircle cy='-6' r='3.4'/%3E%3Ccircle cy='6' r='3.4'/%3E%3Ccircle cx='-6' r='3.4'/%3E%3Ccircle cx='6' r='3.4'/%3E%3C/g%3E%3Ccircle cx='48' cy='48' r='2.4'/%3E%3C/svg%3E\")", size: '64px 64px' },
  kamera: { label: 'Kamera', url: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='72' height='72'%3E%3Cpath d='M10 16h5l2-3h8l2 3h5v14H10z' fill='none' stroke='black' stroke-width='1.6'/%3E%3Ccircle cx='21' cy='23' r='4' fill='none' stroke='black' stroke-width='1.6'/%3E%3Ccircle cx='54' cy='54' r='2'/%3E%3C/svg%3E\")", size: '72px 72px' },
};
function curTheme() { return Object.assign({}, THEME_PRESETS.krem, ev.theme || {}); }
function renderTheme() {
  const t = curTheme();
  $('#themePresets').innerHTML = Object.entries(THEME_PRESETS).map(([k, p]) =>
    `<button type="button" class="ghost" data-preset="${k}" style="gap:8px"><span style="width:16px;height:16px;border-radius:50%;background:${p.paper};box-shadow:inset 0 0 0 5px ${p.btn},0 0 0 1px #0003"></span>${p.label}</button>`).join('');
  $$('#themePresets [data-preset]').forEach((b) => b.addEventListener('click', () => {
    const p = Object.assign({}, THEME_PRESETS[b.dataset.preset]); delete p.label;
    const keep = {}; ['pattern', 'pattern_strength', 'floaters', 'bg_image', 'bg_dim'].forEach((k) => { if (ev.theme && k in ev.theme) keep[k] = ev.theme[k]; });
    ev.theme = Object.assign(p, keep); setDirty(); renderTheme();
  }));
  $('#themeColors').innerHTML = THEME_KEYS.map(([k, l]) => `<label class="color-in">${l}<input type="color" data-t="${k}" value="${t[k]}"></label>`).join('');
  $$('#themeColors [data-t]').forEach((el) => el.addEventListener('input', () => {
    ev.theme = Object.assign(curTheme(), { [el.dataset.t]: el.value }); delete ev.theme.label; setDirty(); paintThemePrev();
  }));
  $('#themeFont').value = t.font || 'modern';
  const pat = t.pattern || 'titik';
  $('#patGrid').innerHTML = Object.entries(BG_PATTERNS).map(([k, p]) =>
    `<button type="button" class="pat-sw${k === pat ? ' on' : ''}" data-pat="${k}" style="--sw-size:${p.size};--sw-ink:${t.text};background:${t.paper};color:${t.text}"><i></i><span>${p.label}</span></button>`).join('');
  $$('#patGrid [data-pat]').forEach((b) => b.style.setProperty('--sw-pat', BG_PATTERNS[b.dataset.pat].url || 'none'));
  $$('#patGrid [data-pat]').forEach((b) => b.addEventListener('click', () => setTheme({ pattern: b.dataset.pat }, true)));
  $('#patStr').value = t.pattern_strength || 12; $('#patStrVal').textContent = ($('#patStr').value) + '%';
  $('#patFloat').checked = t.floaters !== false;
  $('#bgPrev').classList.toggle('hidden', !t.bg_image); $('#btnBgDel').classList.toggle('hidden', !t.bg_image);
  $('#bgDimWrap').classList.toggle('hidden', !t.bg_image);
  if (t.bg_image) $('#bgPrev').src = assetUrl(t.bg_image);
  $('#bgDim').value = t.bg_dim ?? 55; $('#bgDimVal').textContent = $('#bgDim').value + '%';
  paintThemePrev();
}
function setTheme(patch, rerender) {
  ev.theme = Object.assign(curTheme(), patch); delete ev.theme.label; setDirty();
  rerender ? renderTheme() : paintThemePrev();
}
$('#patStr').addEventListener('input', (e) => { $('#patStrVal').textContent = e.target.value + '%'; setTheme({ pattern_strength: +e.target.value }); });
$('#patFloat').addEventListener('change', (e) => setTheme({ floaters: e.target.checked }));
$('#bgDim').addEventListener('input', (e) => { $('#bgDimVal').textContent = e.target.value + '%'; setTheme({ bg_dim: +e.target.value }); });
$('#bgFile').addEventListener('change', async (e) => {
  const f = e.target.files[0]; if (!f) return;
  try { setTheme({ bg_image: (await upload(f, 'bg')).file }, true); }
  catch (err) { await showStudioAlert('Upload Gagal', 'Upload gambar gagal: ' + err.message, '❌'); }
  e.target.value = '';
});
$('#btnBgDel').addEventListener('click', () => setTheme({ bg_image: '' }, true));
function paintThemePrev() {
  const t = curTheme(), s = $('#themePrev').style;
  s.setProperty('--tp-paper', t.paper); s.setProperty('--tp-text', t.text); s.setProperty('--tp-card', t.card);
  s.setProperty('--tp-btn', t.btn); s.setProperty('--tp-btntext', t.btn_text); s.setProperty('--tp-accent', t.accent);
  s.setProperty('--tp-printer', t.printer); s.setProperty('--tp-font', THEME_FONT_CSS[t.font] || THEME_FONT_CSS.modern);
  $('#themePrev .tp-name').textContent = ev.event_name || 'Nama Event';
  const p = BG_PATTERNS[t.pattern || 'titik'] || BG_PATTERNS.titik;
  s.setProperty('--tp-pat', p.url || 'none'); s.setProperty('--tp-size', p.size);
  s.setProperty('--tp-alpha', (t.pattern_strength || 12) / 100 * 1.4);
  s.backgroundImage = t.bg_image ? `linear-gradient(color-mix(in srgb, ${t.paper} ${t.bg_dim ?? 55}%, transparent), color-mix(in srgb, ${t.paper} ${t.bg_dim ?? 55}%, transparent)), url('${assetUrl(t.bg_image)}')` : '';
}
$('#themeFont').addEventListener('change', (e) => {
  ev.theme = Object.assign(curTheme(), { font: e.target.value }); delete ev.theme.label; setDirty(); paintThemePrev();
});
$('#btnThemeReset').addEventListener('click', () => { ev.theme = {}; setDirty(); renderTheme(); });

function renderIntro() {
  ev.intro_style = 'auto';
  const out = ev.output || 'thermal';
  const icon = $('#introAutoIcon');
  const title = $('#introAutoTitle');
  const desc = $('#introAutoDesc');
  if (icon && title && desc) {
    if (out === 'photo') {
      icon.textContent = '📸';
      title.textContent = 'Animasi Intro: Otomatis Mode Foto 4R';
      desc.textContent = 'Layar kiosk otomatis memutar animasi bilik foto strip 3-2-1 blitz flash & kamera polaroid berwarna.';
    } else if (out === 'both') {
      icon.textContent = '✨';
      title.textContent = 'Animasi Intro: Otomatis Mode Dual (Receipt & 4R)';
      desc.textContent = 'Layar kiosk otomatis memutar showcase animasi Receipt dan Foto 4R secara bergantian.';
    } else {
      icon.textContent = '🧾';
      title.textContent = 'Animasi Intro: Otomatis Mode Receipt Photobooth';
      desc.textContent = 'Layar kiosk otomatis memutar animasi mesin printer struk thermal kasir monokrom.';
    }
  }

  if (!Array.isArray(ev.intro_photos)) {
    ev.intro_photos = ev.intro_photo ? [ev.intro_photo] : [];
  }
  ev.intro_photo = ev.intro_photos[0] || '';

  const grid = $('#introPhotosGrid');
  if (!grid) return;
  grid.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    const file = ev.intro_photos[i] || '';
    const slot = document.createElement('div');
    slot.className = 'intro-slot';
    slot.style.cssText = 'width:125px;display:flex;flex-direction:column;align-items:center;gap:6px;border:1px dashed var(--line,#ccc);border-radius:10px;padding:8px;background:var(--card,#fafafa)';
    slot.innerHTML = `
      <div style="width:108px;height:125px;display:flex;align-items:center;justify-content:center;background:#eee;border-radius:6px;overflow:hidden;position:relative">
        ${file ? `<img src="${assetUrl(file)}" style="width:100%;height:100%;object-fit:cover" alt="Foto ${i + 1}">` : `<span class="mono" style="font-size:12px;color:#888;text-align:center">Foto ${i + 1}<br><small>(Kosong)</small></span>`}
      </div>
      <div class="row" style="gap:4px;margin-top:2px;width:100%;justify-content:center">
        <label class="btn" style="height:30px;font-size:12px;padding:0 8px;display:inline-flex;align-items:center;cursor:pointer;flex:1;justify-content:center">
          ${file ? 'Ganti' : 'Upload'}
          <input type="file" class="hidden" accept="image/png,image/jpeg">
        </label>
        ${file ? `<button type="button" class="ghost" style="height:30px;font-size:12px;padding:0 8px;color:#c33" title="Hapus foto">Hapus</button>` : ''}
      </div>
    `;
    const input = slot.querySelector('input');
    input.addEventListener('change', async (e) => {
      const f = e.target.files && e.target.files[0];
      if (!f) return;
      try {
        const res = await upload(f, 'intro');
        ev.intro_photos[i] = res.file;
        ev.intro_photo = ev.intro_photos[0] || '';
        renderIntro();
        setDirty();
      } catch (err) {
        await showStudioAlert('Upload Gagal', 'Upload foto gagal: ' + err.message, '❌');
      }
      e.target.value = '';
    });
    const btnDel = slot.querySelector('button');
    if (btnDel) {
      btnDel.addEventListener('click', () => {
        ev.intro_photos.splice(i, 1);
        ev.intro_photo = ev.intro_photos[0] || '';
        renderIntro();
        setDirty();
      });
    }
    grid.appendChild(slot);
  }
}
function renderLogo() {
  $('#logoPrev').classList.toggle('hidden', !ev.logo);
  $('#btnLogoDel').classList.toggle('hidden', !ev.logo);
  if (ev.logo) $('#logoPrev').src = assetUrl(ev.logo);
}
$('#logoFile').addEventListener('change', async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  try {
    ev.logo = (await upload(f, 'logo')).file;
    renderLogo(); setDirty(); schedulePreview();
  } catch (err) { await showStudioAlert('Upload Gagal', 'Upload logo gagal: ' + err.message, '❌'); }
  e.target.value = '';
});
$('#btnLogoDel').addEventListener('click', () => { ev.logo = ''; renderLogo(); setDirty(); schedulePreview(); });

async function upload(file, kind) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('kind', kind);
  return api(`/api/studio/events/${encodeURIComponent(ev.id)}/upload`, { body: fd });
}

// ---------------------------------------------------------------- daftar template
let studioTplSub = 'thermal';
const isPhoto = () => !!ev && (ev.output === 'photo' || (ev.output === 'both' && studioTplSub === 'photo'));
const TK = () => (isPhoto() ? 'photo_templates' : 'templates');
const DK = () => (isPhoto() ? 'photo_default_template' : 'default_template');
function allTemplates() {
  if (isPhoto()) return META.photoTemplates.map((t) => ({ id: t.id, name: t.name, kind: 'foto' }));
  return [
    ...META.builtins.map((t) => ({ id: t.id, name: t.name, kind: 'bawaan' })),
    ...ev.custom_templates.map((t) => ({ id: 'c:' + t.id, name: t.name, kind: t.kind === 'overlay' ? 'frame' : 'builder', spec: t })),
  ];
}
function enabledIds() {
  const all = allTemplates().map((t) => t.id);
  const cur = ev[TK()];
  return (cur && cur.length) ? cur.filter((i) => all.includes(i)) : all;
}
const isMobileStudio = () => window.matchMedia('(max-width:600px)').matches;
async function renderInlinePreview(t, el) {
  try {
    const j = await api('/api/studio/preview', { json: {
      eventId: ev.id, event: ev, template: t.id, spec: t.spec || null,
      layout: pvLayout, caption: ($('#pvCaption') ? $('#pvCaption').value : '') } });
    el.innerHTML = `<img src="${j.image}" alt="Preview ${esc(t.name)}">`;
  } catch (e) {
    el.innerHTML = `<div class="small warn" style="padding:8px">Preview gagal: ${esc(e.message)}</div>`;
  }
}
function renderTemplateList() {
  const all = allTemplates();
  const en = enabledIds();
  const ordered = [...en.map((i) => all.find((t) => t.id === i)), ...all.filter((t) => !en.includes(t.id))];
  const box = $('#tplList');
  box.innerHTML = '';
  ordered.forEach((t) => {
    const on = en.includes(t.id);
    const row = document.createElement('div');
    row.className = 'tpl-row' + (t.id === selTpl ? ' sel' : '');
    row.innerHTML = `<input type="checkbox" ${on ? 'checked' : ''} aria-label="Tampilkan ${esc(t.name)}">
      <div class="name"><b>${esc(t.name)}</b><span class="tag">${t.kind.toUpperCase()}</span></div>
      <div class="row">
        <button class="ghost" data-act="default" title="Jadikan terpilih otomatis">${ev[DK()] === t.id ? '★' : '☆'}</button>
        ${t.spec ? `<button class="ghost" data-act="edit">Edit</button><button class="ghost" data-act="del" style="color:var(--accent,#e11d48)" title="Hapus template custom ini">Hapus</button>` : ''}
      </div>
      <div class="arrows row">${on ? '<button data-act="up" aria-label="Naik">↑</button><button data-act="down" aria-label="Turun">↓</button>' : ''}</div>`;
    row.querySelector('input').addEventListener('change', (e) => {
      let list = enabledIds();
      list = e.target.checked ? [...list, t.id] : list.filter((x) => x !== t.id);
      if (!list.length) { e.target.checked = true; return; }
      ev[TK()] = list;
      if (!list.includes(ev[DK()])) ev[DK()] = list[0];
      setDirty(); renderTemplateList();
    });
    row.querySelector('.name').addEventListener('click', () => { selTpl = t.id; renderTemplateList(); if (!isMobileStudio()) schedulePreview(); });
    row.querySelectorAll('[data-act]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation();
      const act = b.dataset.act;
      if (act === 'default') { ev[DK()] = t.id; if (!en.includes(t.id)) ev[TK()] = [...en, t.id]; }
      if (act === 'edit') { openSpec(t.spec.id); return; }
      if (act === 'del') { deleteCustomTemplate(t.spec.id, t.name); return; }
      if (act === 'up' || act === 'down') {
        const list = enabledIds(); const i = list.indexOf(t.id); const j = act === 'up' ? i - 1 : i + 1;
        if (j < 0 || j >= list.length) return;
        [list[i], list[j]] = [list[j], list[i]]; ev[TK()] = list;
      }
      setDirty(); renderTemplateList();
    }));
    box.appendChild(row);
    if (t.id === selTpl && isMobileStudio()) {
      const pv = document.createElement('div');
      pv.className = 'tpl-inline-pv';
      pv.innerHTML = '<div class="small muted" style="padding:8px">Memuat preview...</div>';
      box.appendChild(pv);
      renderInlinePreview(t, pv);
    }
  });
}

// ---------------------------------------------------------------- jenis cetak (thermal / foto 4R / both)
const FRAME_LAYOUTS = [['solo', 'Solo · 1200×1800'], ['duo', 'Duo · 1200×1800'], ['strip', 'Strip · 600×1800'], ['grid', 'Grid · 1200×1800']];
function renderOutput() {
  const photo = isPhoto();
  document.body.classList.toggle('ev-photo', photo);
  $$('#outPick [data-out]').forEach((b) => b.classList.toggle('on', b.dataset.out === (ev.output || 'thermal')));
  const bothPicker = $('#bothTplPicker');
  if (bothPicker) bothPicker.classList.toggle('hidden', ev.output !== 'both');
  if ($('#btnBothTplThermal')) $('#btnBothTplThermal').classList.toggle('on', studioTplSub === 'thermal');
  if ($('#btnBothTplPhoto')) $('#btnBothTplPhoto').classList.toggle('on', studioTplSub === 'photo');
  markOutputLicense();
  $('#photoFrames').innerHTML = FRAME_LAYOUTS.map(([l, label]) => {
    const f = ev.photo_frames[l];
    return `<div class="frame-slot"><b>${label}</b>${f ? `<img src="${assetUrl(f)}" alt="">` : '<div class="empty">belum ada</div>'}
      <div class="row"><label class="ghost" style="cursor:pointer">Upload<input type="file" accept="image/png" hidden data-frame="${l}"></label>
      ${f ? `<button class="ghost" type="button" data-unframe="${l}">Hapus</button>` : ''}</div></div>`;
  }).join('');
  $$('#photoFrames [data-frame]').forEach((inp) => inp.addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const r = await upload(f, 'photoframe');
      ev.photo_frames[inp.dataset.frame] = r.file; setDirty(); renderOutput(); schedulePreview();
      if (r.slots) await showStudioAlert('Bingkai Terpasang', `Bingkai terpasang: ${r.slots} area foto terdeteksi.`, '✅');
    } catch (err) { await showStudioAlert('Upload Gagal', 'Upload bingkai gagal: ' + err.message, '❌'); }
  }));
  $$('#photoFrames [data-unframe]').forEach((b) => b.addEventListener('click', () => {
    delete ev.photo_frames[b.dataset.unframe]; setDirty(); renderOutput(); schedulePreview();
  }));
}
$$('#outPick [data-out]').forEach((b) => b.addEventListener('click', () => {
  ev.output = b.dataset.out; setDirty();
  if (ev.output === 'both') {
    studioTplSub = 'thermal';
  }
  selTpl = (isPhoto() ? ev.photo_default_template : ev.default_template) || 'klasik';
  showListView(); renderOutput(); renderTemplateList(); renderIntro(); schedulePreview();
}));

const btnBothTplThermal = $('#btnBothTplThermal');
if (btnBothTplThermal) {
  btnBothTplThermal.addEventListener('click', () => {
    studioTplSub = 'thermal';
    selTpl = ev.default_template || 'klasik';
    renderOutput();
    renderTemplateList();
    schedulePreview();
  });
}
const btnBothTplPhoto = $('#btnBothTplPhoto');
if (btnBothTplPhoto) {
  btnBothTplPhoto.addEventListener('click', () => {
    studioTplSub = 'photo';
    selTpl = ev.photo_default_template || 'polaroid';
    renderOutput();
    renderTemplateList();
    schedulePreview();
  });
}

// ---------------------------------------------------------------- preset builder
const blk = (text, font, size, extra = {}) => Object.assign({ text, font, size, spacing: 0, upper: false }, extra);
const PRESETS = {
  putih: { label: 'Putih minimal', spec: {
    background: 'white', border: 'none', logo: false, logo_h: 80, logo_mode: 'dark',
    header1: blk('{date_long}', 'geo', 18, { spacing: 3, upper: true }), header2: blk('{event}', 'geob', 44, { upper: true }),
    divider_top: 'none', photo_shape: 'rounded', radius: 14, keyline: 0, photo_ratio: 'auto', gap: 14, side: 28, grid: 'stack',
    divider_bottom: 'dashed', footer1: blk('{caption}', 'hand', 42), footer2: blk('No. {no}', 'mono', 18),
    qr: true, qr_size: 120, qr_text: 'scan untuk versi digital', pad_top: 30, pad_bottom: 40, after_photos: 30 } },
  hitam: { label: 'Photostrip hitam + logo', spec: {
    background: 'black', border: 'none', logo: true, logo_h: 80, logo_mode: 'dark',
    header1: blk('', 'geo', 20), header2: blk('', 'geo', 20), divider_top: 'none',
    photo_shape: 'rounded', radius: 18, keyline: 4, photo_ratio: 'auto', gap: 16, side: 28, grid: 'stack',
    divider_bottom: 'none', footer1: blk('{date_long}', 'geo', 22, { spacing: 3, upper: true }), footer2: blk('{event}', 'geob', 54, { spacing: 2, upper: true }),
    qr: true, qr_size: 110, qr_text: '', pad_top: 30, pad_bottom: 40, after_photos: 36 } },
  wedding: { label: 'Wedding elegan', spec: {
    background: 'white', border: 'double', logo: true, logo_h: 80, logo_mode: 'dark',
    header1: blk('The Wedding of', 'serif', 20, { spacing: 4, upper: true }), header2: blk('{event}', 'serifb', 44),
    divider_top: 'ornament', photo_shape: 'arch', radius: 18, keyline: 0, photo_ratio: 'portrait', gap: 22, side: 56, grid: 'stack',
    divider_bottom: 'ornament', footer1: blk('{caption}', 'hand', 44), footer2: blk('{date_long}', 'serif', 22),
    qr: true, qr_size: 110, qr_text: '', pad_top: 50, pad_bottom: 50, after_photos: 30 } },
  logo: { label: 'Logo besar + garis', spec: {
    background: 'white', border: 'line', logo: true, logo_h: 130, logo_mode: 'dark',
    header1: blk('{event}', 'bebas', 50), header2: blk('{day}, {date_long}', 'mono', 16),
    divider_top: 'dashed', photo_shape: 'rect', radius: 0, keyline: 3, photo_ratio: 'auto', gap: 16, side: 36, grid: 'stack',
    divider_bottom: 'dashed', footer1: blk('{caption}', 'hand', 42), footer2: blk('TERIMA KASIH', 'bebas', 46),
    qr: true, qr_size: 120, qr_text: '', pad_top: 34, pad_bottom: 40, after_photos: 26 } },
};

$('#btnNewBuilder').addEventListener('click', async () => {
  const keys = Object.keys(PRESETS);
  const pick = await showStudioPrompt('Pilih Preset Template', 'Mulai dari preset:\n' + keys.map((k, i) => `${i + 1}. ${PRESETS[k].label}`).join('\n') + '\n\nKetik nomor:', '1', 'Nomor preset', '🎨');
  if (!pick) return;
  const key = keys[parseInt(pick, 10) - 1] || keys[0];
  const spec = Object.assign({ id: uid(), name: PRESETS[key].label, kind: 'builder' }, clone(PRESETS[key].spec));
  addSpec(spec);
});
$('#btnNewOverlay').addEventListener('click', () => {
  addSpec({ id: uid(), name: 'Frame custom', kind: 'overlay', frames: {}, slots: {}, dither: true, extra_text: '', extra_font: 'geo', extra_size: 26, qr: false });
});
function addSpec(spec) {
  ev.custom_templates.push(spec);
  if (ev.templates && ev.templates.length) ev.templates.push('c:' + spec.id);
  setDirty(); renderTemplateList(); openSpec(spec.id);
}

// ---------------------------------------------------------------- editor template
function showListView() {
  editId = null;
  $('#tplListView').classList.remove('hidden');
  $('#specView').classList.add('hidden');
}
$('#btnBackList').addEventListener('click', () => { showListView(); renderTemplateList(); });
async function deleteCustomTemplate(id, name) {
  if (!(await showStudioConfirm('Hapus Template', `Hapus template "${name || 'ini'}"?`, 'Hapus', 'Batal', '🗑️'))) return;
  ev.custom_templates = (ev.custom_templates || []).filter((t) => t.id !== id);
  ev.templates = (ev.templates || []).filter((i) => i !== 'c:' + id);
  if (ev.default_template === 'c:' + id) ev.default_template = 'klasik';
  if (selTpl === 'c:' + id) selTpl = ev.default_template || 'klasik';
  setDirty();
  showListView();
  renderTemplateList();
  schedulePreview();
}
$('#btnDelSpec').addEventListener('click', () => {
  const s = curSpec();
  if (s) deleteCustomTemplate(s.id, s.name);
});
$('#btnDupSpec').addEventListener('click', () => {
  const s = clone(curSpec()); s.id = uid(); s.name += ' (salinan)';
  addSpec(s);
});
const curSpec = () => ev.custom_templates.find((t) => t.id === editId);

function openSpec(id) {
  editId = id;
  selTpl = 'c:' + id;
  $('#tplListView').classList.add('hidden');
  $('#specView').classList.remove('hidden');
  const s = curSpec();
  $('#specForm').innerHTML = '';
  if (s.kind === 'overlay') buildOverlayForm(s); else buildBuilderForm(s);
  schedulePreview();
}

const getP = (o, path) => path.split('.').reduce((a, k) => (a == null ? a : a[k]), o);
function setP(o, path, v) {
  const ks = path.split('.'); let a = o;
  ks.slice(0, -1).forEach((k) => { a[k] = a[k] || {}; a = a[k]; });
  a[ks[ks.length - 1]] = v;
}
function changed() { setDirty(); schedulePreview(); }

function fld(s, path, label, type = 'text', opts = {}) {
  const wrap = document.createElement('label');
  wrap.className = type === 'check' ? 'check' : 'field';
  let input;
  if (type === 'select') {
    input = document.createElement('select');
    input.innerHTML = opts.options.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('');
  } else {
    input = document.createElement('input');
    input.type = type === 'check' ? 'checkbox' : type;
    if (opts.min !== undefined) input.min = opts.min;
    if (opts.max !== undefined) input.max = opts.max;
    if (opts.placeholder) input.placeholder = opts.placeholder;
  }
  const v = getP(s, path);
  if (type === 'check') input.checked = !!v; else input.value = v ?? '';
  input.addEventListener(type === 'select' || type === 'check' ? 'change' : 'input', () => {
    let val = type === 'check' ? input.checked : input.value;
    if (type === 'number') val = Number(val || 0);
    setP(s, path, val);
    if (path === 'name') renderTemplateList();
    changed();
  });
  if (type === 'check') { wrap.append(input, document.createTextNode(' ' + label)); }
  else { const sp = document.createElement('span'); sp.textContent = label; wrap.append(sp, input); }
  if (opts.hint) { const h = document.createElement('span'); h.className = 'hint'; h.textContent = opts.hint; wrap.append(h); }
  return wrap;
}
function sec(title, ...children) {
  const box = document.createElement('div');
  const h = document.createElement('div'); h.className = 'sec'; h.textContent = title;
  box.append(h, ...children);
  return box;
}
function grid(cols, ...children) {
  const g = document.createElement('div');
  g.style.display = 'grid'; g.style.gap = '10px';
  g.style.gridTemplateColumns = `repeat(${cols},minmax(0,1fr))`;
  g.append(...children);
  return g;
}
const FONT_OPTS = () => Object.entries(META.fonts);
function textBlock(s, key, label) {
  if (!s[key]) s[key] = blk('', 'geo', 24);
  const b = document.createElement('div');
  b.className = 'blk';
  b.append(
    fld(s, key + '.text', label, 'text', { placeholder: 'kosong = tidak tampil' }),
    fld(s, key + '.font', 'Font', 'select', { options: FONT_OPTS() }),
    fld(s, key + '.size', 'Ukuran', 'number', { min: 10, max: 160 }),
    fld(s, key + '.spacing', 'Jarak huruf', 'number', { min: 0, max: 20 }),
    fld(s, key + '.upper', 'KAPITAL', 'check'),
  );
  return b;
}
const DIVIDERS = [['none', 'Tidak ada'], ['line', 'Garis'], ['dashed', 'Putus-putus'], ['dots', 'Titik-titik'], ['ornament', 'Ornamen']];
const SHAPE_NAMES = { rect: 'Kotak', rounded: 'Sudut bulat', stamp: 'Perangko', arch: 'Lengkung (arch)', cartouche: 'Ornamen (cartouche)', cushion: 'Bantal (cushion)' };
const RATIO_NAMES = { auto: 'Otomatis', wide: 'Lebar 16:9', landscape: 'Landscape 3:2', classic: 'Klasik 4:3', square: 'Kotak 1:1', portrait: 'Portrait 4:5' };

function buildBuilderForm(s) {
  const tokens = document.createElement('p');
  tokens.className = 'hint';
  tokens.innerHTML = 'Kode teks: <span class="mono">{event} {date} {date_long} {day} {time} {caption} {no}</span> — ganti otomatis saat dicetak. Baris kosong = tidak ditampilkan.';
  $('#specForm').append(
    grid(3,
      fld(s, 'name', 'Nama template'),
      fld(s, 'background', 'Latar', 'select', { options: [['white', 'Putih'], ['black', 'Hitam']] }),
      fld(s, 'border', 'Bingkai luar', 'select', { options: [['none', 'Tidak ada'], ['line', 'Garis'], ['rounded', 'Garis bulat'], ['double', 'Ganda + ornamen']] })),
    tokens,
    sec('Logo event',
      grid(3, fld(s, 'logo', 'Tampilkan logo', 'check'),
        fld(s, 'logo_h', 'Tinggi logo (px)', 'number', { min: 30, max: 300 }),
        fld(s, 'logo_mode', 'Bagian logo yang dicetak', 'select', { options: [['dark', 'Bagian gelap'], ['light', 'Bagian terang']] })),
      hintEl('Logo diupload di tab Info event. Di latar hitam, logo otomatis dicetak putih.')),
    sec('Teks atas', textBlock(s, 'header1', 'Baris 1'), spacer(), textBlock(s, 'header2', 'Baris 2'), spacer(),
      grid(3, fld(s, 'divider_top', 'Pemisah sebelum foto', 'select', { options: DIVIDERS }),
        fld(s, 'pad_top', 'Jarak atas (px)', 'number', { min: 0, max: 300 }))),
    sec('Foto',
      grid(3,
        fld(s, 'photo_shape', 'Bentuk foto', 'select', { options: META.shapes.map((k) => [k, SHAPE_NAMES[k] || k]) }),
        fld(s, 'radius', 'Radius sudut (bulat)', 'number', { min: 0, max: 200 }),
        fld(s, 'keyline', 'Garis tepi foto (px)', 'number', { min: 0, max: 20 }),
        fld(s, 'photo_ratio', 'Rasio foto', 'select', { options: META.ratios.map((k) => [k, RATIO_NAMES[k] || k]) }),
        fld(s, 'gap', 'Jarak antar foto (px)', 'number', { min: 0, max: 120 }),
        fld(s, 'side', 'Margin samping (px)', 'number', { min: 0, max: 200 }),
        fld(s, 'grid', 'Susunan 4 foto', 'select', { options: [['stack', 'Menurun (strip)'], ['2x2', 'Kotak 2×2']] }),
        fld(s, 'after_photos', 'Jarak setelah foto (px)', 'number', { min: 0, max: 200 }))),
    sec('Teks bawah',
      grid(3, fld(s, 'divider_bottom', 'Pemisah setelah foto', 'select', { options: DIVIDERS })), spacer(),
      textBlock(s, 'footer1', 'Baris 1'), spacer(), textBlock(s, 'footer2', 'Baris 2')),
    sec('QR & penutup',
      grid(3, fld(s, 'qr', 'Tampilkan QR unduh', 'check'),
        fld(s, 'qr_size', 'Ukuran QR (px)', 'number', { min: 80, max: 260 }),
        fld(s, 'qr_text', 'Teks di bawah QR'),
        fld(s, 'pad_bottom', 'Jarak bawah (px)', 'number', { min: 0, max: 300 }))),
  );
}
function spacer() { const d = document.createElement('div'); d.style.height = '8px'; return d; }
function hintEl(t) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = t; return p; }

function buildOverlayForm(s) {
  s.frames = s.frames || {}; s.slots = s.slots || {};
  const guide = document.createElement('div');
  guide.className = 'card';
  guide.innerHTML = `<b>Cara membuat frame</b>
    <ol class="small" style="margin:6px 0 0;padding-left:18px">
      <li>Buat kanvas lebar <b>${META.paperPx} px</b> (atau ${META.paperPx * 2} px), tinggi bebas.</li>
      <li>Desain bingkai hitam-putih (logo, teks, ornamen). Hindari abu-abu tipis — printer hanya hitam.</li>
      <li>Bagian untuk foto dibuat <b>transparan</b> (bentuk bebas: kotak, bulat, hati…). Selain itu jangan transparan.</li>
      <li>Simpan sebagai <b>PNG</b>. Jumlah lubang = jumlah foto (Solo 1, Duo 2, Strip 3, Grid 4).</li>
    </ol>`;
  const slots = document.createElement('div');
  slots.className = 'grid4';
  META.layouts.forEach((l) => {
    const box = document.createElement('div');
    box.className = 'frame-slot';
    const f = s.frames[l];
    const n = s.slots[l];
    box.innerHTML = `<b>${LAYOUT_NAMES[l]}</b>
      ${f ? `<img src="${assetUrl(f)}" alt="Frame ${l}">` : '<div class="hint" style="padding:30px 0">Belum ada frame</div>'}
      ${f ? (n === LAYOUT_N[l] ? `<span class="okc small">✓ ${n} area foto</span>` : `<span class="warn small">${n} area foto (butuh ${LAYOUT_N[l]})</span>`) : ''}
      <label class="btn">${f ? 'Ganti PNG' : 'Upload PNG'}<input type="file" accept="image/png" class="hidden" aria-label="Upload frame ${l}"></label>
      ${f ? '<button class="ghost" data-del>Hapus</button>' : ''}`;
    box.querySelector('input').addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const r = await upload(file, 'frame');
        s.frames[l] = r.file; s.slots[l] = r.slots;
        setDirty(); openSpec(s.id);
        if (pvLayout !== l) setLayout(l);
      } catch (err) { await showStudioAlert('Upload Gagal', 'Upload frame gagal: ' + err.message, '❌'); }
    });
    const del = box.querySelector('[data-del]');
    if (del) del.addEventListener('click', () => { delete s.frames[l]; delete s.slots[l]; setDirty(); openSpec(s.id); });
    slots.appendChild(box);
  });
  $('#specForm').append(
    grid(2, fld(s, 'name', 'Nama template'), fld(s, 'dither', 'Haluskan gradasi frame (dither)', 'check')),
    spacer(), guide,
    sec('Frame per layout', slots, hintEl('Layout tanpa frame tidak menampilkan template ini di kiosk.')),
    sec('Tambahan di bawah frame (opsional)',
      grid(3, fld(s, 'extra_text', 'Teks', 'text', { placeholder: 'mis. {date_long}' }),
        fld(s, 'extra_font', 'Font', 'select', { options: FONT_OPTS() }),
        fld(s, 'extra_size', 'Ukuran', 'number', { min: 10, max: 120 })),
      spacer(), fld(s, 'qr', 'Tambahkan QR unduh di bawah frame', 'check')),
  );
}

// ---------------------------------------------------------------- preview
let pvTimer = null, pvSeq = 0;
function schedulePreview() {
  clearTimeout(pvTimer);
  pvTimer = setTimeout(runPreview, 350);
}
async function runPreview() {
  if (!ev || $('#tab-templates').classList.contains('hidden')) return;
  const seq = ++pvSeq;
  const t = allTemplates().find((x) => x.id === selTpl) || allTemplates()[0];
  if (t && t.spec && t.spec.kind === 'overlay') {
    const frames = t.spec.frames || {};
    if (!frames[pvLayout]) {
      const firstWithFrame = Object.keys(frames)[0];
      if (firstWithFrame && firstWithFrame !== pvLayout) {
        setLayout(firstWithFrame);
        return;
      }
    }
  }
  $('#pvName').textContent = 'Preview: ' + t.name;
  $('#pvImg').style.opacity = 0.5;
  try {
    const j = await api('/api/studio/preview', { json: {
      eventId: ev.id, event: ev, template: t.id, spec: t.spec || null,
      output: isPhoto() ? 'photo' : 'thermal',
      layout: pvLayout, caption: $('#pvCaption') ? $('#pvCaption').value : '' } });
    if (seq !== pvSeq) return;
    $('#pvImg').src = j.image;
    const pvInfo = $('#pvInfo');
    if (pvInfo) {
      pvInfo.textContent = isPhoto()
        ? 'Kertas foto 4R (10×15 cm, 300 dpi). Layout Strip = 2 strip 5×15 cm kembar, tinggal dipotong.'
        : `Tinggi struk ± ${(j.height / 8 / 10).toFixed(1)} cm (203 dpi). Foto contoh: sesi terakhir atau ilustrasi.`;
    }
  } catch (e) {
    const pvInfo = $('#pvInfo');
    if (pvInfo) pvInfo.textContent = 'Preview gagal: ' + e.message;
  }
  $('#pvImg').style.opacity = 1;
}
function setLayout(l) {
  pvLayout = l;
  $$('#pvLayouts button').forEach((b) => b.classList.toggle('on', b.dataset.l === l));
  schedulePreview();
}
$('#pvCaption')?.addEventListener('input', schedulePreview);

// ---------------------------------------------------------------- statistik event
const pinQ = () => (sessionStorage.getItem('studioPin') ? '?pin=' + encodeURIComponent(sessionStorage.getItem('studioPin')) : '');
async function loadGuest() {
  if (!ev) return;
  const id = encodeURIComponent(ev.id);
  const st = await api(`/api/studio/events/${id}/stats`).catch(() => null);
  if (st) renderStats(st);
  const csv = $('#csvOpen');
  if (csv) csv.href = `/studio/export/${id}.csv${pinQ()}`;
}
function renderStats(s) {
  const box = (label, val) => `<div class="card" style="padding:14px;text-align:center"><div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:32px">${val}</div><div class="small muted" style="margin-top:4px">${label}</div></div>`;
  const statNums = $('#statNums');
  if (statNums) statNums.innerHTML = box('Total Sesi Foto', s.sessions ?? 0) + box('Total Lembar Dicetak', s.prints ?? 0);
  const max = Math.max(1, ...(s.templates || []).map((t) => t.n));
  const statTpl = $('#statTpl');
  if (statTpl) statTpl.innerHTML = (s.templates || []).slice(0, 6).map((t) => `<div class="row" style="flex-wrap:nowrap;gap:8px;margin:3px 0"><span style="width:130px">${esc(t.name)}</span>
      <span style="flex:1;height:10px;background:var(--ink);border-radius:4px;max-width:${Math.round(100 * t.n / max)}%"></span><b>${t.n}</b></div>`).join('') || '<span class="hint">Belum ada data.</span>';
  const hmax = Math.max(1, ...(s.hours || []).map((h) => h.n));
  const statHours = $('#statHours');
  if (statHours) statHours.innerHTML = (s.hours || []).map((h) => `<div class="row" style="flex-wrap:nowrap;gap:8px;margin:3px 0"><span class="mono" style="width:44px">${h.h}:00</span>
      <span style="flex:1;height:10px;background:var(--accent);border-radius:4px;max-width:${Math.round(100 * h.n / hmax)}%"></span><b>${h.n}</b></div>`).join('') || '<span class="hint">Belum ada data.</span>';
}
const btnDraw = $('#btnDraw');
if (btnDraw) {
  btnDraw.addEventListener('click', async () => {});
}
const btnDrawReset = $('#btnDrawReset');
if (btnDrawReset) {
  btnDrawReset.addEventListener('click', async () => {});
}

function renderPaper(pp) {
  $('#paperBar').style.width = pp.pct_left + '%';
  $('#paperBadge').textContent = pp.low ? 'HAMPIR HABIS' : `${pp.left_m} m sisa`;
  $('#paperBadge').classList.toggle('on', !pp.low);
  $('#paperInfo').textContent = `Terpakai ${pp.used_m} m dari ${pp.roll_m} m · ${pp.prints} kali cetak sejak ${pp.since || '-'}`;
  $('#paperRoll').value = pp.roll_m;
}
$('#btnPaperSave').addEventListener('click', async () => renderPaper(await api('/api/studio/paper', { json: { roll_m: Number($('#paperRoll').value) } })));
$('#btnPaperReset').addEventListener('click', async () => {
  if (!(await showStudioConfirm('Reset Kertas', 'Sudah pasang roll kertas baru? Penghitung akan direset.', 'Ya, Reset', 'Batal', '📄'))) return;
  renderPaper(await api('/api/studio/paper', { json: { reset: true } }));
});

// ---------------------------------------------------------------- printer & tablet
let PR = null;
const prVal = () => ({
  printer: {
    type: $('#prType').value, name: $('#prName').value.trim(), host: $('#prHost').value.trim(),
    port: Number($('#prPort').value || 9100), serial_port: $('#prSerial').value.trim(),
    baudrate: Number($('#prBaud').value), vendor_id: $('#prVid').value.trim(), product_id: $('#prPid').value.trim(),
    device_path: $('#prDev').value.trim() || '/dev/usb/lp0',
    impl: $('#prImpl').value, feed_lines: Number($('#prFeed').value || 3), cut: $('#prCut').checked,
  },
  paper_px: Number($('#prPaper').value), brightness: Number($('#prBright').value || 1),
});
function prGroups() {
  const t = $('#prType').value;
  $$('.pr-group').forEach((g) => g.classList.toggle('hidden', g.dataset.type !== t && !(g.dataset.type === 'webusb' && t === 'android_usb')));
  if (t === 'webusb' || t === 'android_usb') usbInfo();
}
async function usbInfo() {
  if (!PBUSB.supported()) { $('#usbInfo').textContent = 'Browser ini tidak mendukung USB printer (buka di Chrome di tablet Android atau pasang APK AdsBooth).'; return; }
  const d = await PBUSB.paired().catch(() => null);
  if (d) {
    const permNote = d.hasPermission === false ? ' (Perlu izin USB: klik Sambungkan)' : '';
    const idStr = (d.vendorId && d.productId) ? ` [${d.vendorId}:${d.productId}]` : '';
    $('#usbInfo').textContent = `Tersambung: ${d.name}${idStr}${permNote}`;
  } else {
    $('#usbInfo').textContent = 'Belum ada printer USB yang disambungkan (pastikan kabel OTG tercolok).';
  }
}
$('#btnUsbPair').addEventListener('click', async () => {
  try { await PBUSB.connect(); } catch (e) { if (e.name !== 'NotFoundError') await showStudioAlert('Koneksi Gagal', 'Gagal: ' + e.message, '❌'); }
  usbInfo();
});
function prStatus(s) {
  const b = $('#prStatus');
  b.textContent = s.ok ? (s.mode === 'file' ? 'MODE TES' : 'SIAP') : 'BERMASALAH';
  b.classList.toggle('on', !!s.ok);
  $('#prMsg').textContent = s.message || '';
  $('#prMsg').className = 'small ' + (s.ok ? 'okc' : 'warn');
}
async function openSettings() {
  if (dirty && !(await showStudioConfirm('Perubahan Belum Disimpan', 'Perubahan event belum disimpan. Tetap pindah?', 'Pindah', 'Batal', '⚠️'))) return;
  setDirty(false); ev = null;
  $('#editor').classList.add('hidden'); $('#emptyState').classList.add('hidden');
  $('#licenseView').classList.add('hidden');
  $('#settings').classList.remove('hidden');
  $('#btnSettings').classList.add('sel');
  $('#btnLicenseNav').classList.remove('sel');
  loadEvents();
  PR = await api('/api/studio/printer');
  const c = PR.printer || {};
  $('#prType').value = c.type || 'file';
  $('#prName').value = c.name || ''; $('#prHost').value = c.host || ''; $('#prPort').value = c.port || 9100;
  $('#prSerial').value = c.serial_port || ''; $('#prBaud').value = String(c.baudrate || 9600);
  $('#prVid').value = c.vendor_id || ''; $('#prPid').value = c.product_id || '';
  $('#prDev').value = c.device_path || '/dev/usb/lp0';
  $('#prImpl').value = c.impl || 'bitImageRaster'; $('#prFeed').value = c.feed_lines ?? 3; $('#prCut').checked = c.cut !== false;
  $('#prPaper').value = String(PR.paper_px); $('#prBright').value = PR.brightness;
  prGroups(); prStatus(PR.status);
  renderPaper(await api('/api/studio/paper'));
  loadCamera().catch((e) => { $('#camMsg').textContent = 'Gagal memuat: ' + e.message; });
  loadLicense();
  loadSecurity().catch((e) => { $('#secMsg').textContent = 'Gagal memuat: ' + e.message; });
  loadPhotoPrinter().catch((e) => { $('#ppMsg').textContent = 'Gagal memuat: ' + e.message; });
  const k = await api('/api/studio/connect');
  $('#kioskQr').src = k.kiosk_qr; $('#kioskUrl').textContent = k.kiosk;
  $('#httpsToggle').checked = k.https_enabled;
  $('#httpsHint').textContent = k.https_enabled
    ? 'HTTPS aktif. Tablet: buka alamat di atas.'
    : 'Tanpa HTTPS, kamera hanya jalan kalau kiosk dibuka di PC server sendiri.';
  $('#httpsHint').className = 'hint';
  $('#lanToggle').checked = k.lan_enabled;
  $('#lanToggle').disabled = k.lan_enabled && !k.is_local;   // mematikan Wi-Fi hanya dari komputer server
  $('#lanHint').textContent = k.lan_enabled
    ? (k.is_local ? 'Aktif: HP / tablet di Wi-Fi yang sama bisa membuka kiosk lewat alamat di atas.'
                  : 'Aktif. Untuk mematikan, buka Studio langsung di komputer server.')
    : 'Nonaktif: kiosk & Studio hanya bisa dibuka dari komputer ini (localhost).';
  $('#lanHint').className = 'hint';
  if (k.lan_enabled !== k.lan_running) {
    $('#lanHint').textContent += ' Perubahan belum berlaku - tekan Restart server.';
    $('#lanHint').className = 'hint warn';
  }
}
$('#btnSettings').addEventListener('click', openSettings);

async function openLicense() {
  if (dirty && !(await showStudioConfirm('Perubahan Belum Disimpan', 'Perubahan event belum disimpan. Tetap pindah?', 'Pindah', 'Batal', '⚠️'))) return;
  setDirty(false); ev = null;
  $('#editor').classList.add('hidden'); $('#emptyState').classList.add('hidden');
  $('#settings').classList.add('hidden');
  $('#licenseView').classList.remove('hidden');
  $('#btnSettings').classList.remove('sel');
  $('#btnLicenseNav').classList.add('sel');
  loadEvents();
  loadLicense();
}
$('#btnLicenseNav').addEventListener('click', openLicense);

// ---------------------------------------------------------------- kamera
async function loadCamera() {
  const c = (await api('/api/studio/camera')).camera || {};
  $('#camLabel').value = c.label || ''; $('#camRes').value = c.resolution || '1080';
  $('#camFacing').value = c.facing || 'user'; $('#camMirror').checked = c.mirror !== false;
  $('#camReview').value = String(c.review_ms ?? 1000); $('#camHiresTimeout').value = String(c.hires_timeout_ms || 1500);
  camHiresToggle();
}
function camHiresToggle() { $('#camHiresWrap').classList.toggle('hidden', $('#camRes').value !== '1080+4k'); }
$('#camRes').addEventListener('change', camHiresToggle);
$('#btnCamSave').addEventListener('click', async () => {
  try {
    await api('/api/studio/camera', { method: 'PUT', json: { camera: {
      label: $('#camLabel').value, resolution: $('#camRes').value, facing: $('#camFacing').value, mirror: $('#camMirror').checked,
      review_ms: +$('#camReview').value, hires_timeout_ms: +$('#camHiresTimeout').value } } });
    $('#camMsg').textContent = 'Tersimpan. Muat ulang (Ctrl+F5) layar kiosk supaya kamera baru dipakai.';
  } catch (e) { $('#camMsg').textContent = 'Gagal simpan: ' + e.message; }
});
$('#btnCamDetect').addEventListener('click', async () => {
  $('#camMsg').textContent = 'Meminta izin kamera…';
  try {
    const tmp = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    tmp.getTracks().forEach((t) => t.stop());
    const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput');
    $('#camList').innerHTML = cams.length ? cams.map((d, i) => `<button type="button" class="ghost" data-cam="${esc(d.label || 'Kamera ' + (i + 1))}">${esc(d.label || 'Kamera ' + (i + 1))}</button>`).join('')
      : '<span class="hint">Tidak ada kamera terdeteksi.</span>';
    $$('#camList [data-cam]').forEach((b) => b.addEventListener('click', () => {
      $('#camLabel').value = b.dataset.cam.replace(/\s*\([0-9a-f]{4}:[0-9a-f]{4}\)\s*$/i, '');
      $('#camMsg').textContent = 'Dipilih: ' + $('#camLabel').value + '. Tekan "Simpan kamera".';
    }));
    $('#camMsg').textContent = cams.length + ' kamera ditemukan. Klik salah satu untuk memilih. (Deteksi ini hanya melihat kamera di perangkat tempat Studio dibuka.)';
  } catch (e) { $('#camMsg').textContent = 'Tidak bisa mengakses kamera: ' + e.message + ' (butuh localhost atau HTTPS)'; }
});

// ---------------------------------------------------------------- printer foto
let PP = null;
function ppNames() {
  const t = $('#ppType').value, cur = (PP.printer || {}).name || '';
  const list = (PP.found && PP.found[t]) || [];
  const opts = [...new Set([...list, ...(cur ? [cur] : [])])];
  $('#ppName').innerHTML = t === 'file' ? '<option value="">(tidak perlu)</option>'
    : (opts.length ? opts.map((n) => `<option ${n === cur ? 'selected' : ''}>${esc(n)}</option>`).join('')
      : '<option value="">(tidak ada printer terdeteksi)</option>');
  $('#ppName').disabled = t === 'file';
}
function ppStatus(s) {
  $('#ppBadge').textContent = s.ok ? 'SIAP' : 'MASALAH';
  $('#ppBadge').style.background = s.ok ? '#2F7D3A' : '#C8410F'; $('#ppBadge').style.color = '#fff';
  $('#ppMsg').textContent = s.message || '';
}
async function loadPhotoPrinter() {
  PP = await api('/api/studio/photo-printer');
  const c = PP.printer || {};
  $('#ppType').value = c.type || 'file';
  $('#ppBorderless').checked = c.borderless !== false;
  ppNames(); ppStatus(PP.status);
}
const ppBody = () => ({ printer: { type: $('#ppType').value, name: $('#ppName').value, borderless: $('#ppBorderless').checked } });
$('#ppType').addEventListener('change', ppNames);
$('#btnPpSave').addEventListener('click', async () => {
  try { const r = await api('/api/studio/photo-printer', { method: 'PUT', json: ppBody() }); ppStatus(r.status); }
  catch (e) { await showStudioAlert('Gagal Simpan', 'Gagal simpan: ' + e.message, '❌'); }
});
$('#btnPpTest').addEventListener('click', async () => {
  $('#ppMsg').textContent = 'Mencetak halaman tes…';
  try { const r = await api('/api/studio/photo-printer/test', { json: ppBody() }); $('#ppMsg').textContent = 'Terkirim. Salinan: ' + r.saved; }
  catch (e) { $('#ppMsg').textContent = 'Gagal: ' + e.message; }
});
$('#prType').addEventListener('change', prGroups);
$('#btnDiscover').addEventListener('click', async () => {
  $('#prMsg').textContent = 'Mencari…'; $('#prMsg').className = 'small';
  const d = await api('/api/studio/printer/discover', { method: 'POST' });
  $('#prWinList').innerHTML = d.windows.map((n) => `<option value="${esc(n)}">`).join('');
  $('#prComList').innerHTML = d.serial.map((s) => `<option value="${esc(s.port)}">${esc(s.desc)}</option>`).join('');
  $('#prDevList').innerHTML = (d.devices || []).map((x) => `<option value="${esc(x)}">`).join('');
  const parts = [];
  parts.push(`Windows: ${d.windows.length ? d.windows.join(', ') : '-'}`);
  parts.push(`COM: ${d.serial.length ? d.serial.map((s) => s.port + (s.desc ? ` (${s.desc})` : '')).join(', ') : '-'}`);
  if (d.usb.length) parts.push(`USB: ${d.usb.map((u) => u.vendor_id + ':' + u.product_id).join(', ')}`);
  if ((d.devices || []).length) parts.push(`Linux: ${d.devices.join(', ')}`);
  $('#prMsg').textContent = parts.join(' · ') + (d.notes.length ? ' — ' + d.notes.join(' ') : '');
});
$('#btnCheck').addEventListener('click', async () => {
  $('#prMsg').textContent = 'Mengecek…'; $('#prMsg').className = 'small';
  prStatus(await api('/api/studio/printer/check', { json: prVal() }));
});
$('#btnTestPrint').addEventListener('click', async () => {
  $('#prMsg').textContent = 'Mencetak tes…'; $('#prMsg').className = 'small';
  try {
    const j = await api('/api/studio/printer/test', { json: prVal() });
    if (j.jobs && j.jobs.length) await PBUSB.printJobs(j.jobs);
    $('#testImg').src = j.image; $('#testImg').classList.remove('hidden'); $('#testHint').classList.add('hidden');
    $('#prMsg').textContent = $('#prType').value === 'file' ? `Mode tes: disimpan di ${j.saved}`
      : ($('#prType').value === 'webusb' ? 'Terkirim ke printer USB lewat browser.' : 'Terkirim ke printer.');
    $('#prMsg').className = 'small okc';
  } catch (e) { $('#prMsg').textContent = 'Gagal cetak: ' + e.message; $('#prMsg').className = 'small warn'; }
});
$('#btnSavePrinter').addEventListener('click', async () => {
  const j = await api('/api/studio/printer', { method: 'PUT', json: prVal() });
  prStatus(j.status);
  $('#prMsg').textContent = 'Tersimpan. ' + (j.status.message || '');
});
$('#httpsToggle').addEventListener('change', async (e) => {
  await api('/api/studio/connect', { method: 'PUT', json: { https_enabled: e.target.checked } });
  $('#httpsHint').textContent = 'Tersimpan. Tekan Restart server supaya berlaku.';
  $('#httpsHint').className = 'hint warn';
});
$('#lanToggle').addEventListener('change', async (e) => {
  try {
    await api('/api/studio/connect', { method: 'PUT', json: { lan_enabled: e.target.checked } });
    $('#lanHint').textContent = 'Tersimpan. Tekan Restart server supaya berlaku.'
      + (e.target.checked ? '' : ' Tablet / HP lain yang sedang membuka kiosk akan terputus.');
    $('#lanHint').className = 'hint warn';
  } catch (err) {
    e.target.checked = !e.target.checked;
    $('#lanHint').textContent = err.message;
    $('#lanHint').className = 'hint warn';
  }
});
$('#btnRestartServer').addEventListener('click', async () => {
  const ok = await showStudioConfirm('Restart Server',
    'Server akan berhenti sebentar (sekitar 5-10 detik). Kiosk yang sedang dipakai tamu ikut terputus sebentar lalu tersambung lagi. Lanjutkan?',
    'Restart', 'Batal', '🔄');
  if (!ok) return;
  const btn = $('#btnRestartServer'), msg = $('#restartMsg');
  btn.disabled = true; msg.className = 'small'; msg.textContent = 'Merestart server…';
  try { await api('/api/studio/restart', { method: 'POST', json: {} }); }
  catch (err) { btn.disabled = false; msg.className = 'small warn'; msg.textContent = 'Gagal: ' + err.message; return; }
  await new Promise((r) => setTimeout(r, 3000));          // tunggu server lama benar-benar mati
  const end = Date.now() + 60000;
  while (Date.now() < end) {
    try {
      const r = await fetch('/api/status', { cache: 'no-store' });
      if (r.ok) { msg.textContent = 'Server sudah jalan lagi. Memuat ulang…'; setTimeout(() => location.reload(), 600); return; }
    } catch (_) { /* masih restart */ }
    await new Promise((r) => setTimeout(r, 1000));
  }
  btn.disabled = false; msg.className = 'small warn';
  msg.textContent = 'Server belum kembali setelah 60 detik. Cek jendela server / jalankan run.bat lagi.';
});

// ---------------------------------------------------------------- PIN Studio
function showAuth(setup, msg) {
  return new Promise((resolve) => {
    $('#auth').classList.remove('hidden');
    $('#authForm').classList.remove('hidden');
    $('#resetPinForm').classList.add('hidden');
    $('#resetPinSuccessCard')?.classList.add('hidden');

    $('#authTitle').textContent = setup ? 'Buat PIN AdsBooth Studio' : 'Masuk AdsBooth Studio';
    $('#authHint').textContent = msg || (setup
      ? 'Pertama kali: buat PIN 4-12 angka untuk mengunci Studio. Simpan baik-baik.'
      : 'Masukkan PIN Studio.');
    $('#authPin2').classList.toggle('hidden', !setup);
    $('#authBtn').textContent = setup ? 'Simpan PIN' : 'Masuk';
    $('#btnForgotPin').classList.toggle('hidden', setup);
    $('#authMsg').textContent = '';
    $('#authPin').value = ''; $('#authPin2').value = '';
    setTimeout(() => $('#authPin').focus(), 50);

    // Tombol Lupa PIN
    $('#btnForgotPin').onclick = () => {
      $('#authForm').classList.add('hidden');
      $('#resetPinForm').classList.remove('hidden');
      $('#resetPinSuccessCard')?.classList.add('hidden');
      $('#resetLicenseKey').value = '';
      $('#resetPinMsg').textContent = '';
      setTimeout(() => $('#resetLicenseKey').focus(), 50);
    };

    // Tombol Batal Reset
    $('#btnCancelResetPin').onclick = () => {
      $('#resetPinForm').classList.add('hidden');
      $('#resetPinSuccessCard')?.classList.add('hidden');
      $('#authForm').classList.remove('hidden');
      $('#authMsg').textContent = '';
      setTimeout(() => $('#authPin').focus(), 50);
    };

    // Form Submit Reset PIN dengan License Key
    $('#resetPinForm').onsubmit = async (e) => {
      e.preventDefault();
      const licenseKey = $('#resetLicenseKey').value.trim();

      if (!licenseKey) {
        $('#resetPinMsg').textContent = 'Kode lisensi harus diisi.';
        return;
      }

      $('#btnDoResetPin').disabled = true;
      $('#resetPinMsg').textContent = 'Memverifikasi lisensi & mereset PIN...';

      try {
        const r = await fetch('/api/studio/reset-pin-license', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ licenseKey, newPin: '1234' })
        });
        const j = await r.json().catch(() => ({}));
        if (!r.ok || !j.ok) {
          $('#resetPinMsg').textContent = j.error || 'Gagal memverifikasi lisensi.';
          $('#btnDoResetPin').disabled = false;
          return;
        }
        $('#btnDoResetPin').disabled = false;
        // Tampilkan kartu sukses versi aplikasi (BUKAN alert native!)
        $('#resetPinForm').classList.add('hidden');
        $('#authForm').classList.add('hidden');
        $('#resetPinSuccessCard')?.classList.remove('hidden');
        $('#btnResetPinSuccessOk').onclick = () => {
          $('#auth').classList.add('hidden');
          resolve();
        };
      } catch (err) {
        $('#resetPinMsg').textContent = 'Server tidak terhubung.';
        $('#btnDoResetPin').disabled = false;
      }
    };

    $('#authForm').onsubmit = async (e) => {
      e.preventDefault();
      const pin = $('#authPin').value.trim();
      if (setup && pin !== $('#authPin2').value.trim()) { $('#authMsg').textContent = 'PIN tidak sama.'; return; }
      try {
        const r = await fetch(setup ? '/api/studio/setup-pin' : '/api/studio/login', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin }) });
        const j = await r.json().catch(() => ({}));
        if (!r.ok || !j.ok) { $('#authMsg').textContent = j.error || 'Gagal'; return; }
        $('#auth').classList.add('hidden');
        resolve();
      } catch (err) { $('#authMsg').textContent = 'Server tidak terhubung.'; }
    };
  });
}
async function ensureLogin() {
  const s = await (await fetch('/api/studio/session')).json();
  if (s.loggedIn) return true;
  if (s.localOnly && !s.local) {
    document.body.innerHTML = '<p style="padding:40px;font:16px Inter,sans-serif">Studio hanya bisa dibuka dari perangkat photobooth ini.</p>';
    return false;
  }
  if (s.needSetup) {
    if (!s.local) {
      document.body.innerHTML = '<p style="padding:40px;font:16px Inter,sans-serif;max-width:560px">PIN Studio belum dibuat. Untuk keamanan, buka Studio pertama kali dari perangkat yang menjalankan photobooth: <b>http://localhost:5000/studio</b></p>';
      return false;
    }
    await showAuth(true);
  } else {
    await showAuth(false);
  }
  return true;
}

// ---------------------------------------------------------------- keamanan & tentang
async function loadSecurity() {
  const s = await api('/api/studio/security');
  $('#secLocal').checked = !!s.localOnly;
  const a = await api('/api/studio/about');
  if (a.livingDefault && $('#livingUrl')) $('#livingUrl').placeholder = a.livingDefault;
  if ($('#cfgLivingUrl')) {
    $('#cfgLivingUrl').value = a.livingBaseUrl || '';
    $('#cfgLivingUrl').placeholder = a.livingDefault || 'https://mypropro.github.io/adsbooth/v/';
  }
  $('#aboutInfo').innerHTML = `<b style="font-size:17px">${esc(a.app)}</b> <span class="badge">v${esc(a.version)}</span>`
    + (a.updateAvailable
        ? `<br><span class="badge warn" style="margin-top:6px">Update tersedia: v${esc(a.latest || '')}</span>`
        : `<br><span class="small muted" style="display:inline-block;margin-top:6px">Versi terpasang (terbaru)</span>`);
}
$('#btnSaveLivingUrl').addEventListener('click', async () => {
  const url = ($('#cfgLivingUrl').value || '').trim();
  try {
    const res = await api('/api/studio/living-url', { method: 'PUT', json: { url } });
    $('#livingMsg').textContent = url ? 'Alamat Living Photo berhasil disimpan.' : 'Menggunakan alamat default bawaan.';
    $('#livingMsg').style.color = '#2F7D3A';
    $('#cfgLivingUrl').value = res.livingBaseUrl || '';
  } catch (e) {
    $('#livingMsg').textContent = 'Gagal menyimpan: ' + e.message;
    $('#livingMsg').style.color = '#c33';
  }
});
$('#btnResetLivingUrl').addEventListener('click', async () => {
  try {
    const res = await api('/api/studio/living-url', { method: 'PUT', json: { url: '' } });
    $('#cfgLivingUrl').value = '';
    $('#livingMsg').textContent = 'Kembali ke alamat default: ' + (res.livingDefault || '');
    $('#livingMsg').style.color = '#2F7D3A';
  } catch (e) {
    $('#livingMsg').textContent = 'Gagal: ' + e.message;
    $('#livingMsg').style.color = '#c33';
  }
});
function showStudioAlert(title, message, icon = '✅', btnText = 'OK') {
  return new Promise((resolve) => {
    const modal = $('#studioAppModal');
    const t = $('#studioModalTitle');
    const msg = $('#studioModalMessage');
    const ico = $('#studioModalIcon');
    const inpWrap = $('#studioModalInputWrap');
    const btnOk = $('#btnStudioModalOk');
    const btnCancel = $('#btnStudioModalCancel');
    if (!modal) {
      resolve();
      return;
    }
    if (t) t.textContent = title;
    if (msg) msg.textContent = message;
    if (inpWrap) inpWrap.classList.add('hidden');
    if (btnCancel) btnCancel.classList.add('hidden');
    if (btnOk) {
      btnOk.textContent = btnText;
      btnOk.style.display = '';
    }
    if (ico) {
      ico.textContent = icon;
      if (icon === '❌' || icon === '🛑') {
        ico.style.background = '#fee2e2';
        ico.style.color = '#dc2626';
      } else if (icon === '⚠️') {
        ico.style.background = '#fef3c7';
        ico.style.color = '#d97706';
      } else if (icon === '🗑️') {
        ico.style.background = '#fee2e2';
        ico.style.color = '#b91c1c';
      } else {
        ico.style.background = '#dcfce7';
        ico.style.color = '#15803d';
      }
    }
    modal.classList.remove('hidden');
    const onOk = () => {
      btnOk?.removeEventListener('click', onOk);
      modal.classList.add('hidden');
      resolve();
    };
    btnOk?.addEventListener('click', onOk);
  });
}

function showStudioConfirm(title, message, okText = 'Ya', cancelText = 'Batal', icon = '❓') {
  return new Promise((resolve) => {
    const modal = $('#studioAppModal');
    const t = $('#studioModalTitle');
    const msg = $('#studioModalMessage');
    const ico = $('#studioModalIcon');
    const inpWrap = $('#studioModalInputWrap');
    const btnOk = $('#btnStudioModalOk');
    const btnCancel = $('#btnStudioModalCancel');
    if (!modal) {
      resolve(false);
      return;
    }
    if (t) t.textContent = title;
    if (msg) msg.textContent = message;
    if (inpWrap) inpWrap.classList.add('hidden');
    if (ico) {
      ico.textContent = icon;
      if (icon === '❌' || icon === '🛑' || icon === '🗑️') {
        ico.style.background = '#fee2e2';
        ico.style.color = '#dc2626';
      } else if (icon === '⚠️') {
        ico.style.background = '#fef3c7';
        ico.style.color = '#d97706';
      } else {
        ico.style.background = '#e0f2fe';
        ico.style.color = '#0369a1';
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

function showStudioPrompt(title, message, defaultValue = '', placeholder = '', icon = '✏️') {
  return new Promise((resolve) => {
    const modal = $('#studioAppModal');
    const t = $('#studioModalTitle');
    const msg = $('#studioModalMessage');
    const ico = $('#studioModalIcon');
    const inpWrap = $('#studioModalInputWrap');
    const inp = $('#studioModalInput');
    const btnOk = $('#btnStudioModalOk');
    const btnCancel = $('#btnStudioModalCancel');
    if (!modal || !inp) {
      resolve(null);
      return;
    }
    if (t) t.textContent = title;
    if (msg) msg.textContent = message;
    if (ico) {
      ico.textContent = icon;
      ico.style.background = '#e0e7ff';
      ico.style.color = '#4338ca';
    }
    if (inpWrap) inpWrap.classList.remove('hidden');
    inp.placeholder = placeholder || '';
    inp.value = defaultValue || '';
    if (btnOk) btnOk.textContent = 'Simpan';
    if (btnCancel) {
      btnCancel.textContent = 'Batal';
      btnCancel.classList.remove('hidden');
    }
    modal.classList.remove('hidden');
    setTimeout(() => {
      inp.focus();
      inp.select();
    }, 100);

    const onKey = (e) => {
      if (e.key === 'Enter') onOk();
      if (e.key === 'Escape') onCancel();
    };
    const cleanUp = () => {
      btnOk?.removeEventListener('click', onOk);
      btnCancel?.removeEventListener('click', onCancel);
      inp?.removeEventListener('keydown', onKey);
      modal.classList.add('hidden');
      if (inpWrap) inpWrap.classList.add('hidden');
    };
    const onOk = () => {
      const val = inp.value;
      cleanUp();
      resolve(val);
    };
    const onCancel = () => {
      cleanUp();
      resolve(null);
    };
    btnOk?.addEventListener('click', onOk);
    btnCancel?.addEventListener('click', onCancel);
    inp.addEventListener('keydown', onKey);
  });
}

// Override dialog bawaan browser di Studio
window.alert = function(msg) {
  return showStudioAlert('Pemberitahuan', String(msg || ''), 'ℹ️', 'OK');
};

$('#btnSecPin')?.addEventListener('click', async () => {
  const oldPin = ($('#secOld')?.value || '').trim();
  const newPin = ($('#secNew')?.value || '').trim();
  const msg = $('#secMsg');

  if (!oldPin) {
    if (msg) { msg.textContent = 'Masukkan PIN lama terlebih dahulu.'; msg.style.color = '#c33'; }
    $('#secOld')?.focus();
    return;
  }
  if (!newPin || newPin.length < 4) {
    if (msg) { msg.textContent = 'PIN baru minimal 4 angka.'; msg.style.color = '#c33'; }
    $('#secNew')?.focus();
    return;
  }

  try {
    await api('/api/studio/security', { method: 'PUT', json: { oldPin, newPin } });
    if ($('#secOld')) $('#secOld').value = '';
    if ($('#secNew')) $('#secNew').value = '';
    if (msg) { msg.textContent = 'PIN berhasil diganti.'; msg.style.color = '#2F7D3A'; }
    await showStudioAlert('PIN Berhasil Diganti!', 'PIN Studio Anda telah berhasil diperbarui ke nomor baru. Gunakan PIN baru ini saat masuk ke Studio berikutnya.', '✅');
  } catch (e) {
    if (msg) { msg.textContent = e.message || 'Gagal mengganti PIN.'; msg.style.color = '#c33'; }
    await showStudioAlert('Gagal Mengganti PIN', e.message || 'PIN lama salah atau tidak valid.', '❌');
  }
});
$('#secLocal').addEventListener('change', async (e) => {
  try {
    await api('/api/studio/security', { method: 'PUT', json: { localOnly: e.target.checked } });
    $('#secMsg').textContent = e.target.checked ? 'Studio sekarang hanya bisa dibuka dari perangkat ini.' : 'Studio bisa dibuka dari perangkat lain di jaringan (tetap pakai PIN).';
  } catch (err) { e.target.checked = !e.target.checked; $('#secMsg').textContent = err.message; }
});
$('#btnLogout').addEventListener('click', async () => {
  await fetch('/api/studio/logout', { method: 'POST' });
  location.reload();
});

// ---------------------------------------------------------------- lisensi
let LIC = null;
const LIC_LABEL = { active: 'Aktif', grace: 'Masa tenggang', trial: 'Versi coba', expired: 'Habis', trial_over: 'Masa coba habis', clock: 'Jam salah' };
const FEAT_NAME = { thermal: 'Receipt Photobooth', photo: 'Foto 4R', living: 'Living Photo' };
const fmtDate = (t) => new Date(t * 1000).toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' });
async function loadLicense() {
  try { LIC = await api('/api/studio/license'); } catch (e) { $('#licInfo').textContent = 'Gagal memuat: ' + e.message; return; }
  const s = LIC, good = s.state === 'active' || s.state === 'grace';
  $('#licDevice').textContent = s.deviceId;
  const bStatus = $('#licBadgeStatus');
  if (bStatus) {
    bStatus.textContent = LIC_LABEL[s.state] || s.state;
    bStatus.className = 'badge ' + (good ? 'on' : (s.state === 'trial' ? '' : 'warn'));
  }
  let h = `<span class="st ${s.state === 'active' ? 'ok' : ''}">${esc(LIC_LABEL[s.state] || s.state)}</span>`;
  if (good) {
    h += `Paket <b>${esc(s.planName || s.plan)}</b> · ${esc((s.feat || []).map((f) => FEAT_NAME[f] || f).join(', '))}<br>`;
    if (s.customer) h += `Atas nama: <b>${esc(s.customer)}</b><br>`;
    h += s.expires ? `Berlaku sampai <b>${fmtDate(s.expires)}</b>${s.state === 'active' ? ` (sisa ${s.daysLeft} hari)` : ''}` : 'Berlaku selamanya';
    if (s.licenseId) h += ` · <span class="mono">${esc(s.licenseId)}</span>`;
  } else if (s.state === 'trial') {
    h += `Semua fitur bisa dicoba, hasil cetak diberi tanda DEMO. Sisa <b>${s.trialDaysLeft} hari</b>.`;
  }
  if (s.message && s.state !== 'trial') h += `<br><span class="warn">${esc(s.message)}</span>`;
  if (s.blocked && s.ok) h += `<br><span class="warn">${esc(s.blocked)}</span>`;
  if (s.error) h += `<br><span class="warn">Kode tersimpan tidak bisa dipakai: ${esc(s.error)}</span>`;
  if (!s.keyReady) h += '<br><span class="warn">Kunci publik belum diisi (jalankan license_admin.py init di PC penjual).</span>';
  $('#licInfo').innerHTML = h;
  $('#btnLicRemove').classList.toggle('hidden', !s.licenseId && !s.error);
  const pill = $('#licPill');
  const warn = !good || s.state === 'grace' || (s.state === 'active' && s.daysLeft !== null && s.daysLeft <= 5);
  pill.classList.toggle('hidden', s.state === 'active' && !warn);
  pill.classList.toggle('ok', !warn);
  pill.textContent = s.state === 'trial' ? `VERSI COBA · ${s.trialDaysLeft} hari`
    : s.state === 'active' ? `Lisensi habis ${s.daysLeft} hari lagi` : (LIC_LABEL[s.state] || s.state).toUpperCase();
  markOutputLicense();
  loadPricingPlans();
}
function markOutputLicense() {
  if (!LIC) return;
  $$('#outPick [data-out]').forEach((b) => {
    const o = b.dataset.out;
    const feats = LIC.feat || [];
    let hasLic = true;
    if (LIC.ok) {
      if (o === 'both') {
        hasLic = feats.includes('both') || (feats.includes('thermal') && feats.includes('photo'));
      } else {
        hasLic = feats.includes(o);
      }
    }
    b.classList.toggle('nolic', LIC.ok && !hasLic);
  });
  const liv = document.querySelector('[data-f="living_photo"]');
  if (liv) liv.closest('label').classList.toggle('nolic-f', LIC.ok && !(LIC.feat || []).includes('living'));
}
$('#licPill').addEventListener('click', openLicense);
$('#btnLicCopy').addEventListener('click', () => {
  const t = $('#licDevice').textContent;
  (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(
    () => {
      $('#licMsg').textContent = '✓ ID perangkat disalin.';
      $('#licMsg').className = 'small okc';
      const b = $('#btnLicCopy');
      const old = b.textContent;
      b.textContent = '✓ Tersalin!';
      setTimeout(() => { b.textContent = old; }, 2000);
    },
    () => { showStudioPrompt('ID Perangkat', 'Salin ID perangkat di bawah ini:', t, '', '📋'); });
});
$('#licFile').addEventListener('change', async (e) => {
  const f = e.target.files[0]; if (!f) return;
  $('#licToken').value = (await f.text()).trim(); e.target.value = '';
});
$('#btnLicSave').addEventListener('click', async () => {
  const token = $('#licToken').value.trim();
  if (!token) { $('#licMsg').textContent = 'Tempel kode lisensi dulu.'; return; }
  try {
    await api('/api/studio/license', { json: { token } });
    $('#licToken').value = ''; $('#licMsg').textContent = 'Lisensi aktif. Kiosk menyesuaikan otomatis saat kembali ke layar awal.';
    loadLicense();
  } catch (e) { $('#licMsg').textContent = e.message; }
});
$('#btnLicRemove').addEventListener('click', async () => {
  if (!(await showStudioConfirm('Hapus Lisensi', 'Hapus lisensi dari perangkat ini?', 'Hapus', 'Batal', '⚠️'))) return;
  try { await api('/api/studio/license', { method: 'DELETE' }); $('#licMsg').textContent = 'Lisensi dihapus.'; loadLicense(); }
  catch (e) { $('#licMsg').textContent = e.message; }
});

// ---------------------------------------------------------------- Langganan Online (Midtrans)
let PRICING_DATA = null;
let SELECTED_PLAN = 'complete';
let SELECTED_DAYS = 30;
let ORDER_POLL_TIMER = null;

function renderPlanChoices() {
  const container = $('#licPlanChoices');
  if (!container || !PRICING_DATA) return;
  const pricing = PRICING_DATA.pricing || {};
  let html = '';
  for (const [key, p] of Object.entries(pricing)) {
    const isSel = key === SELECTED_PLAN;
    const priceVal = (p.prices && p.prices[SELECTED_DAYS]) || 0;
    const formatted = new Intl.NumberFormat('id-ID').format(priceVal);
    html += `
      <div class="lic-plan-card ${isSel ? 'on' : ''}" data-plan="${esc(key)}">
        <b style="font-size:14px;display:block;color:var(--ink)">${esc(p.name)}</b>
        <span style="font-size:11px;color:var(--muted);display:block;margin-top:2px">${esc(p.desc || '')}</span>
        <div style="font-size:16px;font-weight:700;color:var(--brand, #2563EB);margin-top:8px">Rp ${formatted}</div>
      </div>
    `;
  }
  container.innerHTML = html;
  $$('.lic-plan-card').forEach((el) => {
    el.addEventListener('click', () => {
      SELECTED_PLAN = el.dataset.plan;
      renderPlanChoices();
      updateTotalAmount();
    });
  });
}

function updateTotalAmount() {
  const totalEl = $('#licTotalAmount');
  if (!totalEl || !PRICING_DATA) return;
  const p = (PRICING_DATA.pricing || {})[SELECTED_PLAN];
  const priceVal = (p && p.prices && p.prices[SELECTED_DAYS]) || 0;
  totalEl.textContent = 'Rp ' + new Intl.NumberFormat('id-ID').format(priceVal);
}

async function loadPricingPlans() {
  try {
    PRICING_DATA = await api('/api/studio/license/plans');
    renderPlanChoices();
    updateTotalAmount();
  } catch (e) {
    console.warn('Gagal memuat paket langganan:', e);
  }
}

$$('#licDurChoices .lic-dur-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    $$('#licDurChoices .lic-dur-btn').forEach((b) => b.classList.remove('on'));
    btn.classList.add('on');
    SELECTED_DAYS = parseInt(btn.dataset.days, 10);
    renderPlanChoices();
    updateTotalAmount();
  });
});

if ($('#btnLicSubscribe')) {
  $('#btnLicSubscribe').addEventListener('click', async () => {
    const btn = $('#btnLicSubscribe');
    const oldText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '⏳ Menyiapkan pembayaran...';
    try {
      const res = await api('/api/studio/license/create-checkout', {
        json: {
          plan: SELECTED_PLAN,
          days: SELECTED_DAYS,
          name: ($('#licCustName').value || '').trim()
        }
      });
      if (!res.ok) throw new Error(res.error || 'Gagal membuat pembayaran.');

      // Buka popup / tab checkout Midtrans
      window.open(res.checkout_url || res.snap_redirect_url, '_blank');

      // Tampilkan notifikasi polling aktivasi
      const pollNotice = $('#licPollNotice');
      if (pollNotice) pollNotice.classList.remove('hidden');

      // Mulai polling otomatis ke server
      if (ORDER_POLL_TIMER) clearInterval(ORDER_POLL_TIMER);
      ORDER_POLL_TIMER = setInterval(async () => {
        try {
          const poll = await api('/api/studio/license/poll-order/' + res.order_id);
          if (poll.paid && poll.activated) {
            clearInterval(ORDER_POLL_TIMER);
            ORDER_POLL_TIMER = null;
            if (pollNotice) pollNotice.classList.add('hidden');
            await showStudioAlert('Pembayaran Berhasil!', 'Lisensi perangkat Anda telah aktif secara otomatis.', '🎉');
            loadLicense();
          }
        } catch (err) {
          console.warn('Polling error:', err);
        }
      }, 3000);

    } catch (e) {
      await showStudioAlert('Kendala Pembayaran', e.message, '⚠️');
    } finally {
      btn.disabled = false;
      btn.innerHTML = oldText;
    }
  });
}


// ---------------------------------------------------------------- init
(async function init() {
  if (!(await ensureLogin())) return;
  try {
    META = await api('/api/studio/meta');
  } catch (e) {
    document.body.innerHTML = '<p style="padding:40px">Studio tidak bisa dibuka: ' + esc(e.message) + '</p>';
    return;
  }
  $('#pvLayouts').innerHTML = META.layouts.map((l) => `<button data-l="${l}">${LAYOUT_NAMES[l].split(' ')[0]}</button>`).join('');
  $$('#pvLayouts button').forEach((b) => b.addEventListener('click', () => setLayout(b.dataset.l)));
  setLayout('strip');
  loadLicense();
  await loadEvents();
  const first = ACTIVE || (EVENTS[0] && EVENTS[0].id);
  if (first) openEvent(first);
})();
