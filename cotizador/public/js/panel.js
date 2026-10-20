import { ADVISORS, FLYERS, ORIGINS, ROUTES, convert, fmt, rateNum } from './rutas.js';
import { esc, flag, flags } from './ui.js';

const $ = (id) => document.getElementById(id);
const SOURCES = { bcv: 'leído del BCV', 'bcv-anterior': 'último valor leído del BCV', manual: 'valor manual' };
let saved = null;
const flyerBlobs = {};

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { 'content-type': 'application/json' }, credentials: 'same-origin', cache: 'no-store' });
  let body = {};
  try { body = await res.json(); } catch { /* respuesta vacía */ }
  return { status: res.status, body };
}

function showEditor(on) {
  $('login').hidden = on;
  ['editor', 'flyers', 'links', 'logout'].forEach((id) => { $(id).hidden = !on; });
}

async function start() {
  const { status, body } = await api('/api/sesion');
  if (status !== 200) { showEditor(false); $('password').focus(); return; }
  saved = body.saved;
  showEditor(true);
  renderRoutes();
  renderBcv(body.view.bcv);
  renderLinks();
  drawFlyers();
}

$('login').onsubmit = async (e) => {
  e.preventDefault();
  const { status, body } = await api('/api/login', { method: 'POST', body: JSON.stringify({ password: $('password').value }) });
  $('password').value = '';
  if (status === 200) { $('login-msg').hidden = true; start(); return; }
  $('login-msg').hidden = false;
  $('login-msg').textContent = body.error || 'No se pudo entrar. Intenta de nuevo.';
};
$('logout').onclick = async () => { await api('/api/logout', { method: 'POST' }); showEditor(false); };

function renderRoutes() {
  $('last').textContent = saved.updated ? `Última publicación: ${new Date(saved.updated).toLocaleString('es-CL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}` : '';
  $('routes').innerHTML = Object.entries(ORIGINS).map(([k, o]) => `<h3 style="margin-top:8px">Desde ${esc(o.name)}</h3>`
    + ROUTES.filter((r) => r.from === k).map((r) => {
      const on = saved.active[r.id] !== false;
      return `<div class="route${on ? '' : ' off'}" id="row-${r.id}">
        ${flags(r.to)}
        <div><h3>${esc(o.name)} → ${esc(r.name)}</h3><span class="op">${esc(r.unit)} · ${o.cur} ${r.op === 'mul' ? '× tasa' : '÷ tasa'}</span></div>
        <input type="text" id="in-${r.id}" value="${esc(saved.rates[r.id] || '')}" inputmode="decimal" aria-label="Tasa ${esc(o.name)} a ${esc(r.name)}">
        <span class="ex"><span id="ex-${r.id}"></span><label class="switch"><input type="checkbox" id="on-${r.id}" ${on ? 'checked' : ''}> activa</label></span>
      </div>`;
    }).join('')).join('');
  for (const r of ROUTES) {
    const upd = () => {
      const v = convert(r, $('in-' + r.id).value, 100000);
      $('ex-' + r.id).textContent = Number.isFinite(v) ? `100.000 ${ORIGINS[r.from].cur} → ${fmt(v, r.dec)} ${r.cur}` : 'escribe una tasa válida';
      $('in-' + r.id).classList.remove('bad');
    };
    $('in-' + r.id).oninput = upd;
    upd();
    $('on-' + r.id).onchange = (e) => $('row-' + r.id).classList.toggle('off', !e.target.checked);
  }
  $('bcv').value = saved.bcv_manual || '';
  $('bcv-flag').innerHTML = flag('VE');
}

function renderBcv(b) {
  $('bcv-now').textContent = b?.value
    ? `Hoy en el cotizador: ${fmt(b.value, 2)} Bs/USD (${SOURCES[b.source] || b.source}${b.date ? ', ' + b.date.split('-').reverse().join('/') : ''}).`
    : 'No se pudo leer el BCV y no hay valor manual: el cotizador no muestra el equivalente en dólares.';
}

function renderLinks() {
  const base = location.origin;
  $('advisors').innerHTML = [['General (los dos)', base + '/'], ...Object.entries(ADVISORS).map(([k, a]) => [`${a.name} · ${a.show}`, `${base}/?a=${k}`])]
    .map(([who, url]) => `<div class="adv"><span>${esc(who)}</span><code>${esc(url)}</code></div>`).join('');
}

$('save').onclick = async () => {
  const body = { rates: {}, active: {}, bcv_manual: $('bcv').value.trim() || null };
  for (const r of ROUTES) { body.rates[r.id] = $('in-' + r.id).value.trim(); body.active[r.id] = $('on-' + r.id).checked; }
  const bad = ROUTES.filter((r) => body.active[r.id] && !rateNum(body.rates[r.id]));
  bad.forEach((r) => $('in-' + r.id).classList.add('bad'));
  const msg = $('save-msg');
  msg.hidden = false;
  if (bad.length || (body.bcv_manual && !rateNum(body.bcv_manual))) {
    msg.className = 'msg bad';
    msg.textContent = 'Revisa: ' + [...bad.map((r) => `${ORIGINS[r.from].name} → ${r.name}`), ...(body.bcv_manual && !rateNum(body.bcv_manual) ? ['Dólar BCV manual'] : [])].join(', ') + '.';
    return;
  }
  $('save').disabled = true;
  const { status, body: res } = await api('/api/tasas', { method: 'PUT', body: JSON.stringify(body) });
  $('save').disabled = false;
  if (status === 401) { msg.className = 'msg bad'; msg.textContent = 'Tu sesión venció. Entra de nuevo; lo que escribiste no se guardó.'; showEditor(false); return; }
  if (status !== 200) { msg.className = 'msg bad'; msg.textContent = res.error || 'No se pudo guardar. Intenta de nuevo.'; return; }
  saved = { ...body, updated: res.updated };
  msg.className = 'msg';
  msg.textContent = `Publicado (${new Date(res.updated).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}): el cotizador ya muestra estas tasas y los flyers están listos abajo.`;
  renderRoutes();
  renderBcv(res.bcv);
  drawFlyers();
};

// ------------------------------------------------------------------ flyers

const loadImg = (src) => new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = src; });

async function drawFlyers() {
  try { await document.fonts.load('800 60px Montserrat'); } catch { /* usa la letra de respaldo */ }
  for (const [k, f] of Object.entries(FLYERS)) {
    let img;
    try { img = await loadImg(f.file); } catch { $('fly-' + k).alt = 'No se pudo cargar la plantilla'; continue; }
    const c = document.createElement('canvas');
    c.width = 1080; c.height = 1080;
    const g = c.getContext('2d');
    g.drawImage(img, 0, 0, 1080, 1080);
    g.fillStyle = '#3D1A5E'; g.textAlign = 'center'; g.textBaseline = 'middle';
    for (const [id, cx, cy] of f.slots) {
      const text = saved.active[id] !== false && rateNum(saved.rates[id]) ? saved.rates[id] : '—';
      let size = f.size;
      do { g.font = `800 ${size}px Montserrat, sans-serif`; size -= 2; } while (g.measureText(text).width > f.maxW && size > 20);
      g.fillText(text, cx, cy + 3);
    }
    const blob = await new Promise((ok) => c.toBlob(ok, 'image/png'));
    flyerBlobs[k] = blob;
    $('fly-' + k).src = URL.createObjectURL(blob);
  }
}

const flyerName = (k) => `tasas-${k === 'CL' ? 'chile' : 'colombia'}-${new Date().toISOString().slice(0, 10)}.png`;
document.querySelectorAll('[data-dl]').forEach((b) => b.onclick = () => {
  const k = b.dataset.dl;
  if (!flyerBlobs[k]) return;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(flyerBlobs[k]); a.download = flyerName(k);
  document.body.appendChild(a); a.click(); a.remove();
});
document.querySelectorAll('[data-share]').forEach((b) => b.onclick = async () => {
  const k = b.dataset.share;
  if (!flyerBlobs[k]) return;
  const file = new File([flyerBlobs[k]], flyerName(k), { type: 'image/png' });
  if (navigator.canShare?.({ files: [file] })) {
    try { await navigator.share({ files: [file] }); } catch { /* el usuario canceló */ }
  } else {
    b.textContent = 'Usa Descargar en este equipo';
  }
});

start();
