// Template Studio — kelola event & template custom
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
  if (r.status === 401) {
    const p = prompt('PIN Studio:');
    if (p === null) throw new Error('PIN dibutuhkan');
    sessionStorage.setItem('studioPin', p);
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
  $('#activeText').textContent = act ? 'Aktif: ' + act.name : 'Aktif: config.json (tanpa event)';
  $('#activeBadge').classList.toggle('on', !!act);
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
  if (dirty && !confirm('Perubahan belum disimpan. Tetap pindah event?')) return;
  const j = await api('/api/studio/events/' + encodeURIComponent(id));
  ev = j.event;
  ev.custom_templates = ev.custom_templates || [];
  setDirty(false);
  editId = null;
  selTpl = ev.default_template || 'klasik';
  $('#emptyState').classList.add('hidden');
  $('#settings').classList.add('hidden');
  $('#editor').classList.remove('hidden');
  renderInfo();
  renderTemplateList();
  showListView();
  loadEvents();
  schedulePreview();
}

$('#btnNewEvent').addEventListener('click', async () => {
  const name = prompt('Nama event baru:', 'Wedding ...');
  if (!name) return;
  const j = await api('/api/studio/events', { json: { name } });
  await loadEvents();
  dirty = false;
  openEvent(j.event.id);
});
$('#btnDuplicate').addEventListener('click', async () => {
  const name = prompt('Nama event hasil duplikat:', ev.name + ' (salinan)');
  if (!name) return;
  if (dirty) await save();
  const j = await api('/api/studio/events', { json: { name, from: ev.id } });
  openEvent(j.event.id);
});
$('#btnDelete').addEventListener('click', async () => {
  if (!confirm(`Hapus event "${ev.name}"? (dipindah ke folder events/_trash)`)) return;
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
  $$('#tab-info [data-k]').forEach((el) => { el.value = ev[el.dataset.k] ?? ''; });
  ev.social = Object.assign({ username: '', display: '{event}', website: '', bio: '{date_long}' }, ev.social || {});
  $$('#tab-info [data-s]').forEach((el) => { el.value = ev.social[el.dataset.s] ?? ''; });
  $('#qrToggle').checked = ev.qr_download !== false;
  ev.features = Object.assign({ guestbook: false, lucky_draw: false, pose_challenge: false, host_copy: false }, ev.features || {});
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
}
function renderDefaultLayout() {
  const s = $('#defaultLayout');
  s.innerHTML = ev.layouts.map((l) => `<option value="${l}">${LAYOUT_NAMES[l]}</option>`).join('');
  if (!ev.layouts.includes(ev.default_layout)) ev.default_layout = ev.layouts[0];
  s.value = ev.default_layout;
}
$$('#tab-info [data-k]').forEach((el) => el.addEventListener('input', () => {
  ev[el.dataset.k] = el.value;
  if (el.dataset.k === 'name') $('#evTitle').textContent = el.value;
  setDirty(); schedulePreview();
}));
$$('#tab-info [data-s]').forEach((el) => el.addEventListener('input', () => {
  ev.social[el.dataset.s] = el.value;
  setDirty(); schedulePreview();
}));
$('#qrToggle').addEventListener('change', (e) => { ev.qr_download = e.target.checked; setDirty(); schedulePreview(); });
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
  ev.features[el.dataset.f] = el.checked; setDirty();
}));
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
  } catch (err) { alert('Upload logo gagal: ' + err.message); }
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
function allTemplates() {
  return [
    ...META.builtins.map((t) => ({ id: t.id, name: t.name, kind: 'bawaan' })),
    ...ev.custom_templates.map((t) => ({ id: 'c:' + t.id, name: t.name, kind: t.kind === 'overlay' ? 'frame' : 'builder', spec: t })),
  ];
}
function enabledIds() {
  const all = allTemplates().map((t) => t.id);
  return (ev.templates && ev.templates.length) ? ev.templates.filter((i) => all.includes(i)) : all;
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
        <button class="ghost" data-act="default" title="Jadikan terpilih otomatis">${ev.default_template === t.id ? '★' : '☆'}</button>
        ${t.spec ? '<button class="ghost" data-act="edit">Edit</button>' : ''}
      </div>
      <div class="arrows row">${on ? '<button data-act="up" aria-label="Naik">↑</button><button data-act="down" aria-label="Turun">↓</button>' : ''}</div>`;
    row.querySelector('input').addEventListener('change', (e) => {
      let list = enabledIds();
      list = e.target.checked ? [...list, t.id] : list.filter((x) => x !== t.id);
      if (!list.length) { e.target.checked = true; return; }
      ev.templates = list;
      if (!list.includes(ev.default_template)) ev.default_template = list[0];
      setDirty(); renderTemplateList();
    });
    row.querySelector('.name').addEventListener('click', () => { selTpl = t.id; renderTemplateList(); schedulePreview(); });
    row.querySelectorAll('[data-act]').forEach((b) => b.addEventListener('click', () => {
      const act = b.dataset.act;
      if (act === 'default') { ev.default_template = t.id; if (!en.includes(t.id)) ev.templates = [...en, t.id]; }
      if (act === 'edit') { openSpec(t.spec.id); return; }
      if (act === 'up' || act === 'down') {
        const list = enabledIds(); const i = list.indexOf(t.id); const j = act === 'up' ? i - 1 : i + 1;
        if (j < 0 || j >= list.length) return;
        [list[i], list[j]] = [list[j], list[i]]; ev.templates = list;
      }
      setDirty(); renderTemplateList();
    }));
    box.appendChild(row);
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

$('#btnNewBuilder').addEventListener('click', () => {
  const keys = Object.keys(PRESETS);
  const pick = prompt('Mulai dari preset:\n' + keys.map((k, i) => `${i + 1}. ${PRESETS[k].label}`).join('\n') + '\n\nKetik nomor:', '1');
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
$('#btnDelSpec').addEventListener('click', () => {
  const s = curSpec();
  if (!confirm(`Hapus template "${s.name}"?`)) return;
  ev.custom_templates = ev.custom_templates.filter((t) => t.id !== s.id);
  ev.templates = (ev.templates || []).filter((i) => i !== 'c:' + s.id);
  if (ev.default_template === 'c:' + s.id) ev.default_template = 'klasik';
  selTpl = ev.default_template;
  setDirty(); showListView(); renderTemplateList(); schedulePreview();
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
      } catch (err) { alert('Upload frame gagal: ' + err.message); }
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
  $('#pvName').textContent = 'Preview: ' + t.name;
  $('#pvImg').style.opacity = 0.5;
  try {
    const j = await api('/api/studio/preview', { json: {
      eventId: ev.id, event: ev, template: t.id, spec: t.spec || null,
      layout: pvLayout, caption: $('#pvCaption').value } });
    if (seq !== pvSeq) return;
    $('#pvImg').src = j.image;
    $('#pvInfo').textContent = `Tinggi struk ± ${(j.height / 8 / 10).toFixed(1)} cm (203 dpi). Foto contoh: sesi terakhir atau ilustrasi.`;
  } catch (e) {
    $('#pvInfo').textContent = 'Preview gagal: ' + e.message;
  }
  $('#pvImg').style.opacity = 1;
}
function setLayout(l) {
  pvLayout = l;
  $$('#pvLayouts button').forEach((b) => b.classList.toggle('on', b.dataset.l === l));
  schedulePreview();
}
$('#pvCaption').addEventListener('input', schedulePreview);

// ---------------------------------------------------------------- buku tamu & undian
const pinQ = () => (sessionStorage.getItem('studioPin') ? '?pin=' + encodeURIComponent(sessionStorage.getItem('studioPin')) : '');
async function loadGuest() {
  if (!ev) return;
  const id = encodeURIComponent(ev.id);
  const [g, d, st] = await Promise.all([api(`/api/studio/events/${id}/guestbook`), api(`/api/studio/events/${id}/draw`),
    api(`/api/studio/events/${id}/stats`).catch(() => null)]);
  if (st) renderStats(st);
  $('#csvOpen').href = `/studio/export/${id}.csv${pinQ()}`;
  $('#gbCount').textContent = g.count + ' ucapan';
  $('#gbOpen').href = `/studio/guestbook/${id}${pinQ()}`;
  $('#gbList').innerHTML = g.items.slice(0, 30).map((m) => `<div class="row" style="align-items:flex-start;flex-wrap:nowrap;gap:10px;border-bottom:1px solid var(--line);padding-bottom:8px">
      ${m.photos[0] ? `<img src="/d/${m.id}/${m.photos[0]}" alt="" style="width:72px;height:54px;object-fit:cover;border-radius:6px">` : ''}
      <div><div style="font-style:italic">${esc(m.guestbook.message)}</div>
      ${m.guestbook.signature ? `<img src="/d/${m.id}/ttd.png" alt="Tanda tangan" style="height:36px">` : ''}
      <div class="small"><b>${esc(m.guestbook.name)}</b> <span class="muted">· No. ${m.number}</span></div></div></div>`).join('') || '<p class="hint">Belum ada ucapan.</p>';
  renderDraw(d);
}
function renderStats(s) {
  const box = (label, val) => `<div class="card" style="padding:12px;text-align:center"><div style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:30px">${val}</div><div class="small muted">${label}</div></div>`;
  $('#statNums').innerHTML = box('sesi foto', s.sessions) + box('lembar dicetak', s.prints) + box('ucapan buku tamu', s.guestbook) + box('nomor undian', s.lucky);
  const max = Math.max(1, ...s.templates.map((t) => t.n));
  $('#statTpl').innerHTML = s.templates.slice(0, 6).map((t) => `<div class="row" style="flex-wrap:nowrap;gap:8px;margin:3px 0"><span style="width:130px">${esc(t.name)}</span>
      <span style="flex:1;height:10px;background:var(--ink);border-radius:4px;max-width:${Math.round(100 * t.n / max)}%"></span><b>${t.n}</b></div>`).join('') || '<span class="hint">Belum ada data.</span>';
  const hmax = Math.max(1, ...s.hours.map((h) => h.n));
  $('#statHours').innerHTML = s.hours.map((h) => `<div class="row" style="flex-wrap:nowrap;gap:8px;margin:3px 0"><span class="mono" style="width:44px">${h.h}:00</span>
      <span style="flex:1;height:10px;background:var(--accent);border-radius:4px;max-width:${Math.round(100 * h.n / hmax)}%"></span><b>${h.n}</b></div>`).join('') || '<span class="hint">Belum ada data.</span>';
}
function renderDraw(d) {
  $('#drawCount').textContent = `${d.issued} nomor · ${d.drawn.length} keluar`;
  $('#drawList').textContent = d.drawn.length ? d.drawn.map((x) => x.lucky).join(', ') : '-';
}
$('#btnDraw').addEventListener('click', async () => {
  const id = encodeURIComponent(ev.id);
  try {
    // efek acak angka sebelum hasil
    const t = setInterval(() => { $('#drawNum').textContent = String(Math.floor(Math.random() * 9999)).padStart(4, '0'); }, 60);
    const j = await api(`/api/studio/events/${id}/draw`, { method: 'POST' });
    await new Promise((r) => setTimeout(r, 1500));
    clearInterval(t);
    $('#drawNum').textContent = j.winner.lucky;
    $('#drawPhoto').classList.toggle('hidden', !j.winner.photo);
    if (j.winner.photo) $('#drawPhoto').src = j.winner.photo;
    renderDraw(await api(`/api/studio/events/${id}/draw`));
  } catch (e) { $('#drawNum').textContent = '----'; alert(e.message); }
});
$('#btnDrawReset').addEventListener('click', async () => {
  if (!confirm('Reset undian? Semua nomor bisa keluar lagi.')) return;
  await api(`/api/studio/events/${encodeURIComponent(ev.id)}/draw`, { method: 'DELETE' });
  $('#drawNum').textContent = '----'; $('#drawPhoto').classList.add('hidden');
  loadGuest();
});

function renderPaper(pp) {
  $('#paperBar').style.width = pp.pct_left + '%';
  $('#paperBadge').textContent = pp.low ? 'HAMPIR HABIS' : `${pp.left_m} m sisa`;
  $('#paperBadge').classList.toggle('on', !pp.low);
  $('#paperInfo').textContent = `Terpakai ${pp.used_m} m dari ${pp.roll_m} m · ${pp.prints} kali cetak sejak ${pp.since || '-'}`;
  $('#paperRoll').value = pp.roll_m;
}
$('#btnPaperSave').addEventListener('click', async () => renderPaper(await api('/api/studio/paper', { json: { roll_m: Number($('#paperRoll').value) } })));
$('#btnPaperReset').addEventListener('click', async () => {
  if (!confirm('Sudah pasang roll kertas baru? Penghitung akan direset.')) return;
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
  $$('.pr-group').forEach((g) => g.classList.toggle('hidden', g.dataset.type !== t));
  if (t === 'webusb') usbInfo();
}
async function usbInfo() {
  if (!PBUSB.supported()) { $('#usbInfo').textContent = 'Browser ini tidak mendukung WebUSB (buka di Chrome di tablet Android).'; return; }
  const d = await PBUSB.paired().catch(() => null);
  $('#usbInfo').textContent = d ? `Tersambung: ${d.name} (${d.vendorId.toString(16)}:${d.productId.toString(16)})` : 'Belum ada printer USB yang disambungkan di browser ini.';
}
$('#btnUsbPair').addEventListener('click', async () => {
  try { await PBUSB.connect(); } catch (e) { if (e.name !== 'NotFoundError') alert('Gagal: ' + e.message); }
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
  if (dirty && !confirm('Perubahan event belum disimpan. Tetap pindah?')) return;
  setDirty(false); ev = null;
  $('#editor').classList.add('hidden'); $('#emptyState').classList.add('hidden');
  $('#settings').classList.remove('hidden');
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
  const k = await api('/api/studio/connect');
  $('#kioskQr').src = k.kiosk_qr; $('#kioskUrl').textContent = k.kiosk;
  $('#httpsToggle').checked = k.https_enabled;
  $('#httpsHint').textContent = k.https_enabled
    ? 'HTTPS aktif. Tablet: buka alamat di atas. Matikan lalu restart server kalau tidak perlu.'
    : 'Tanpa HTTPS, kamera hanya jalan kalau kiosk dibuka di PC server sendiri. Setelah diubah, restart server.';
}
$('#btnSettings').addEventListener('click', openSettings);
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
  $('#httpsHint').textContent = 'Tersimpan. Restart server (tutup lalu jalankan run.bat) supaya berlaku.';
  $('#httpsHint').className = 'hint warn';
});

// ---------------------------------------------------------------- init
(async function init() {
  try {
    META = await api('/api/studio/meta');
  } catch (e) {
    document.body.innerHTML = '<p style="padding:40px">Studio tidak bisa dibuka: ' + esc(e.message) + '</p>';
    return;
  }
  $('#pvLayouts').innerHTML = META.layouts.map((l) => `<button data-l="${l}">${LAYOUT_NAMES[l].split(' ')[0]}</button>`).join('');
  $$('#pvLayouts button').forEach((b) => b.addEventListener('click', () => setLayout(b.dataset.l)));
  setLayout('strip');
  await loadEvents();
  const first = ACTIVE || (EVENTS[0] && EVENTS[0].id);
  if (first) openEvent(first);
})();
