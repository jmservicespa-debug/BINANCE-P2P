import { ADVISORS, FLYERS, ORIGINS, ROUTES, amountNum, convert, fmt, rateNum, usdtNum } from './rutas.js';
import { esc, flag, flags } from './ui.js';
import { BRL_BRAKE, USDT_URL, brlPerClp, parseCriptoYa } from './criptoya.js';

const $ = (id) => document.getElementById(id);
const SOURCES = { bcv: 'leído del BCV', dolarapi: 'copia del BCV vía DolarApi, fuente no oficial', 'bcv-anterior': 'último valor leído', manual: 'valor manual' };
let saved = null;
const flyerBlobs = {};
const STATUS = [['on', 'Activa'], ['ask', 'Inestable · tasa por WhatsApp'], ['off', 'Apagada']];
const statusOf = (id) => saved.status?.[id] ?? (saved.active?.[id] === false ? 'off' : 'on');

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { 'content-type': 'application/json' }, credentials: 'same-origin', cache: 'no-store' });
  let body = {};
  try { body = await res.json(); } catch { /* respuesta vacía */ }
  return { status: res.status, body };
}

function showEditor(on) {
  $('login').hidden = on;
  ['power', 'editor', 'usdt', 'flyers', 'links', 'logout'].forEach((id) => { $(id).hidden = !on; });
}

async function start() {
  const { status, body } = await api('/api/sesion');
  if (status !== 200) { showEditor(false); $('password').focus(); return; }
  saved = body.saved;
  showEditor(true);
  renderPower(body.paused);
  renderRoutes();
  renderBcv(body.view.bcv, body.view.bcv_eur);
  renderLinks();
  drawFlyers();
  loadUsdt(true);
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

// Un botón para apagar todas las tasas en la noche y encenderlas al publicar (las tasas guardadas no se borran).
let paused = false;
function renderPower(p) {
  paused = p;
  $('power-txt').textContent = paused
    ? 'Tasas APAGADAS: los clientes ven "Actualizando tasas".'
    : 'Tasas encendidas: los clientes cotizan con las tasas publicadas.';
  $('power-btn').textContent = paused ? 'Encender todas las tasas' : 'Apagar todas las tasas';
  $('power-btn').className = paused ? 'btn' : 'btn ghost';
}
$('power-btn').onclick = async () => {
  $('power-btn').disabled = true;
  const { status, body } = await api('/api/pausa', { method: 'PUT', body: JSON.stringify({ paused: !paused }) });
  $('power-btn').disabled = false;
  if (status === 200) renderPower(body.paused);
  else $('power-txt').textContent = body.error || 'No se pudo cambiar. Intenta de nuevo.';
};

function renderRoutes() {
  $('last').textContent = saved.updated ? `Última publicación: ${new Date(saved.updated).toLocaleString('es-CL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}` : '';
  $('routes').innerHTML = Object.entries(ORIGINS).map(([k, o]) => `<h3 style="margin-top:8px">Desde ${esc(o.name)}</h3>`
    + ROUTES.filter((r) => r.from === k).map((r) => {
      const st = statusOf(r.id);
      return `<div class="route${st === 'on' ? '' : ' off'}" id="row-${r.id}">
        ${flags(r.to)}
        <div><h3>${esc(o.name)} → ${esc(r.name)}</h3><span class="op">${esc(r.unit)} · ${o.cur} ${r.op === 'mul' ? '× tasa' : '÷ tasa'}</span></div>
        <input type="text" id="in-${r.id}" value="${esc(saved.rates[r.id] || '')}" inputmode="decimal" aria-label="Tasa ${esc(o.name)} a ${esc(r.name)}">
        <span class="ex"><span id="ex-${r.id}"></span><select id="st-${r.id}" aria-label="Estado ${esc(o.name)} a ${esc(r.name)}">${STATUS.map(([v, t]) => `<option value="${v}"${v === st ? ' selected' : ''}>${t}</option>`).join('')}</select></span>
      </div>${r.id === 'cl-br' ? provBox() : ''}`;
    }).join('')).join('');
  for (const r of ROUTES) {
    const upd = () => {
      const v = convert(r, $('in-' + r.id).value, 100000);
      $('ex-' + r.id).textContent = Number.isFinite(v) ? `100.000 ${ORIGINS[r.from].cur} → ${fmt(v, r.dec)} ${r.cur}` : 'escribe una tasa válida';
      $('in-' + r.id).classList.remove('bad');
    };
    $('in-' + r.id).oninput = upd;
    upd();
    $('st-' + r.id).onchange = (e) => $('row-' + r.id).classList.toggle('off', e.target.value !== 'on');
  }
  $('bcv').value = saved.bcv_manual || '';
  $('bcv-flag').innerHTML = flag('VE');
  $('bcv-eur').value = saved.bcv_manual_eur || '';
  $('bcv-eur-flag').innerHTML = flag('VE');
  ['prov-brl', 'prov-m'].forEach((id) => { $(id).oninput = () => provCalc(true); });
  $('prov-auto').onchange = () => brlLive();
  provCalc(false);
  brlLive();
}

// Brasil: la tasa sale de lo que da el proveedor por 100.000 CLP más tu ganancia (el cliente solo ve la tasa final).
function provBox() {
  const b = saved.brl || {};
  return `<div class="prov">
    <span class="muted">Calcular desde tu proveedor (solo lo ves tú)</span>
    <div class="row2">
      <label class="f" for="prov-brl">BRL por 100 mil
        <span class="amount"><input id="prov-brl" inputmode="decimal" autocomplete="off" placeholder="Ej. 495,62" value="${esc(b.ref ?? '')}"></span></label>
      <label class="f" for="prov-m">Tu ganancia (%)
        <span class="amount"><input id="prov-m" inputmode="decimal" autocomplete="off" value="${esc(b.margin_pct || '8')}"></span></label>
    </div>
    <span class="muted" id="prov-out"></span>
    <label class="switch"><input type="checkbox" id="prov-auto" ${b.auto ? 'checked' : ''}> <b>Reales (BRL) automático</b></label>
    <span class="muted" id="prov-live">La tasa sigue sola al mercado. Al guardar, se calibra con el número de tu proveedor.</span>
  </div>`;
}

// Precio del real en CLP = precio del proveedor + tu ganancia; la tasa del flyer (reales por peso) es su inverso.
function provCalc(fill) {
  const brl = usdtNum($('prov-brl').value);
  const m = Number(String($('prov-m').value).replace(',', '.'));
  if (!(brl > 0) || !(m >= 0 && m <= 50)) {
    $('prov-out').textContent = 'Escribe cuántos reales da tu proveedor por 100.000 CLP y tu ganancia para calcular la tasa de Brasil.';
    return;
  }
  const provPrice = 100000 / brl, myPrice = provPrice * (1 + m / 100), rate = (1 / myPrice).toFixed(6);
  $('prov-out').textContent = `Proveedor: ${fmt(provPrice, 2)} CLP por real · con tu ${fmt(m, m % 1 ? 1 : 0)} %: ${fmt(myPrice, 2)} CLP por real → tasa ${rate}`;
  if (fill) { $('in-cl-br').value = rate; $('in-cl-br').dispatchEvent(new Event('input')); }
}

function renderBcv(b, e) {
  for (const [id, v, unit, name] of [['bcv-now', b, 'Bs/USD', 'dólares'], ['bcv-eur-now', e, 'Bs/EUR', 'euros']]) {
    $(id).textContent = v?.value
      ? `Hoy en el cotizador: ${fmt(v.value, 2)} ${unit} (${SOURCES[v.source] || v.source}${v.date ? ', ' + v.date.split('-').reverse().join('/') : ''}).`
      : `No se pudo leer el BCV y no hay valor manual: el cotizador no muestra el equivalente en ${name}.`;
    if (v?.errors?.length) $(id).textContent += ` Lectura automática fallida (${v.errors.join(' · ')}).`;
  }
}

function renderLinks() {
  const base = location.origin;
  $('advisors').innerHTML = [['General (botón sin nombre, a tu número)', base + '/'], ...Object.entries(ADVISORS).map(([k, a]) => [`${a.name} · ${a.show}`, `${base}/?a=${k}`])]
    .map(([who, url]) => `<div class="adv"><span>${esc(who)}</span><code>${esc(url)}</code></div>`).join('');
}

$('save').onclick = async () => {
  const body = { rates: {}, status: {}, bcv_manual: $('bcv').value.trim() || null, bcv_manual_eur: $('bcv-eur').value.trim() || null };
  for (const r of ROUTES) { body.rates[r.id] = $('in-' + r.id).value.trim(); body.status[r.id] = $('st-' + r.id).value; }
  body.brl = { ref: $('prov-brl').value.trim(), margin_pct: $('prov-m').value.trim(), auto: $('prov-auto').checked,
    cal_cross: brlCross };  // calibración: el mercado en el momento en que anotaste a tu proveedor
  if (body.brl.auto && !brlCross) {
    $('save-msg').hidden = false; $('save-msg').className = 'msg bad';
    $('save-msg').textContent = 'Reales automático necesita el precio del mercado y no se pudo leer. Desmarca la casilla o inténtalo de nuevo.';
    return;
  }
  const bad = ROUTES.filter((r) => body.status[r.id] === 'on' && !rateNum(body.rates[r.id]));
  bad.forEach((r) => $('in-' + r.id).classList.add('bad'));
  const msg = $('save-msg');
  msg.hidden = false;
  const badBcv = [[body.bcv_manual, 'Dólar BCV manual'], [body.bcv_manual_eur, 'Euro BCV manual']].filter(([v]) => v && !rateNum(v)).map(([, n]) => n);
  if (bad.length || badBcv.length) {
    msg.className = 'msg bad';
    msg.textContent = 'Revisa: ' + [...bad.map((r) => `${ORIGINS[r.from].name} → ${r.name}`), ...badBcv].join(', ') + '.';
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
  renderBcv(res.bcv, res.bcv_eur);
  drawFlyers();
};

// ------------------------------------------------------------------ flyers

const loadImg = (src) => new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = src; });

// Texto para el estado de WhatsApp: banderas (emoji) del país de origen y de los destinos activos, para copiar y pegar.
const emojiFlag = (c) => String.fromCodePoint(...[...c].map((ch) => 0x1F1E6 + ch.charCodeAt(0) - 65));
function autoStatusText(k) {
  const dests = [...new Set(ROUTES.filter((r) => r.from === k && statusOf(r.id) !== 'off').flatMap((r) => r.to))];
  return `${emojiFlag(k)} ➜ ${dests.map(emojiFlag).join(' ')}\n`
    + `💱 Tasas del día · JM Cambios\n`
    + `Cotiza tu envío aquí 👉 ${location.origin}/`;
}
const statusKey = (k) => `jmc_estado_${k}`;
function renderStatusText() {
  for (const k of ['CL', 'CO']) {
    let mine = null;
    try { mine = localStorage.getItem(statusKey(k)); } catch { /* sin almacenamiento: texto automático */ }
    $('estado-' + k).value = mine || autoStatusText(k);
  }
}
document.querySelectorAll('textarea.estado').forEach((t) => t.oninput = () => {
  try { localStorage.setItem(statusKey(t.id.slice(-2)), t.value); } catch { /* no se pudo recordar */ }
});
document.querySelectorAll('[data-reset]').forEach((b) => b.onclick = () => {
  try { localStorage.removeItem(statusKey(b.dataset.reset)); } catch { /* nada guardado */ }
  renderStatusText();
});
document.querySelectorAll('[data-copy]').forEach((b) => b.onclick = async () => {
  const t = $('estado-' + b.dataset.copy);
  try { await navigator.clipboard.writeText(t.value); } catch { t.select(); document.execCommand('copy'); }
  b.textContent = '¡Copiado!';
  setTimeout(() => { b.textContent = 'Copiar texto'; }, 2000);
});

async function drawFlyers() {
  renderStatusText();
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
      const st = statusOf(id);
      const text = st === 'ask' ? 'CONSULTAR' : st === 'on' && rateNum(saved.rates[id]) ? saved.rates[id] : '—';
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

// ------------------------------------------------------------------ calculadora USDT

let usdt = null;
const USDT_SOURCES = { vita: 'Vita Wallet vía CriptoYa', binancep2p: 'Binance P2P vía CriptoYa', mediana: 'mediana de exchanges vía CriptoYa', manual: 'valor manual' };
const pctOf = (id) => Number(String($(id).value).replace(',', '.')) || 0;
const usdtPrice = () => usdt?.ref?.value ? usdt.ref.value * (1 + pctOf('u-margin') / 100) : NaN;
// Precio de compra: lo que paga el mercado por USDT (bid de Vita) menos la ganancia al comprar.
const usdtBuyPrice = () => usdt?.ref?.bid ? Number((usdt.ref.bid * (1 - pctOf('u-buy') / 100)).toFixed(2)) : NaN;  // como lo ve el cliente

async function loadUsdt(fillInputs) {
  const { status, body } = await api('/api/usdt');
  if (status !== 200) return;
  usdt = body;
  if (fillInputs) { $('u-margin').value = body.margin_pct; $('u-buy').value = body.buy_margin_pct ?? '8'; $('u-manual').value = body.manual || ''; $('u-pub').checked = !!body.published; }
  // Si el servidor no pudo leer CriptoYa, este navegador la consulta directamente (como al abrir su página).
  if (!usdt.ref?.value || !usdt.ref.bid || usdt.ref.source === 'manual') {
    try {
      const res = await fetch(USDT_URL, { cache: 'no-store' });
      const got = res.ok ? parseCriptoYa(await res.text()) : null;
      if (got) usdt.ref = { ...got, age_s: 0, via: 'navegador' };
      else usdt.ref = { ...usdt.ref, error: `${usdt.ref.error || ''} · navegador: respondió ${res.status}` };
    } catch (e) {
      usdt.ref = { ...usdt.ref, error: `${usdt.ref.error || ''} · navegador: ${e.message || 'sin conexión'}` };
    }
  }
  renderUsdt();
}

function renderUsdt() {
  const r = usdt?.ref || {};
  $('u-ref').textContent = r.value ? `${fmt(r.value, 2)} CLP` : 'sin dato';
  const age = r.age_s == null ? '' : r.age_s < 90 ? ' · recién actualizado' : ` · hace ${Math.round(r.age_s / 60)} min`;
  $('u-src').textContent = r.value ? `${USDT_SOURCES[r.source] || r.source}${r.via ? ' (leído desde este equipo)' : ''}${age}${r.error && !r.via ? ` · la fuente falló (${r.error})` : ''}`
    : `No se pudo leer la referencia${r.error ? ` (${r.error})` : ''}. Escribe un valor manual.`;
  const price = usdtPrice();
  $('u-price').textContent = Number.isFinite(price) ? fmt(price, 2) : '—';
  const qty = usdtNum($('u-qty').value);
  const clp = amountNum($('u-clp').value);
  // Mismo precio en los dos sentidos: cobrar = USDT × precio (redondeado) · entregar = CLP ÷ precio (2 decimales, hacia abajo).
  const okQ = Number.isFinite(price) && qty > 0, okC = Number.isFinite(price) && clp > 0;
  $('u-pay').textContent = okQ ? `${fmt(Math.round(qty * price), 0)} CLP` : '—';
  $('u-pay-d').textContent = okQ ? `por ${fmt(qty, 2)} USDT` : '';
  $('u-get').textContent = okC ? `${fmt(Math.floor((clp / price) * 100) / 100, 2)} USDT` : '—';
  $('u-get-d').textContent = okC ? `por ${fmt(clp, 0)} CLP` : '';
  const buy = usdtBuyPrice(), sell = usdtNum($('u-sell').value);
  $('u-bprice').textContent = buy > 0 ? fmt(buy, 2) : '—';
  $('u-bref').textContent = r.bid ? `(compra de referencia ${fmt(r.bid, 2)})` : '(sin dato de compra)';
  const okS = buy > 0 && sell > 0;  // pagarle = USDT × precio de compra (entero, hacia abajo)
  $('u-bpay').textContent = okS ? `${fmt(Math.floor(Math.round(sell * buy * 100) / 100), 0)} CLP` : '—';
  $('u-bpay-d').textContent = okS ? `por ${fmt(sell, 2)} USDT` : '';
}
['u-margin', 'u-buy', 'u-qty', 'u-clp', 'u-sell'].forEach((id) => { $(id).oninput = renderUsdt; });

async function saveUsdtCfg() {
  const { status, body } = await api('/api/usdt', { method: 'PUT', body: JSON.stringify({ margin_pct: $('u-margin').value, buy_margin_pct: $('u-buy').value, manual: $('u-manual').value, published: $('u-pub').checked }) });
  const msg = $('u-msg');
  msg.hidden = false;
  if (status !== 200) { msg.className = 'msg bad'; msg.textContent = body.error || 'No se pudo guardar.'; return; }
  // Si la referencia se leyó desde este equipo, se conserva (el servidor no puede leer CriptoYa).
  usdt = { ...body, ref: usdt?.ref?.via && !body.ref?.bid ? usdt.ref : body.ref };
  msg.className = 'msg';
  msg.textContent = body.published ? 'Guardado. USDT activo: los clientes lo ven en el cotizador.' : 'Guardado. USDT desactivado: no aparece en el cotizador.';
  renderUsdt();
}
$('u-save').onclick = saveUsdtCfg;
$('u-pub').onchange = saveUsdtCfg;  // activar o desactivar se guarda al instante
setInterval(() => { if (!$('usdt').hidden) loadUsdt(false); }, 60 * 1000);

// ------------------------------------------------------------------ Brasil automático

let brlCross = null;  // reales por peso según el mercado, leído ahora desde este navegador

async function brlLive() {
  brlCross = await brlPerClp();
  const box = $('prov-live');
  if (!box) return;
  if (!brlCross) { box.textContent = 'No se pudo leer el precio del mercado ahora (CriptoYa). Reales automático no está disponible en este momento.'; return; }
  const b = saved.brl || {};
  let txt = `Mercado ahora: ${brlCross.toFixed(6)} reales por peso.`;
  if (b.auto && b.cal_cross) {
    const move = (brlCross / b.cal_cross - 1) * 100;
    txt += ` Cambio desde la última calibración: ${move >= 0 ? '+' : ''}${fmt(move, 2)} %` + (Math.abs(move) > BRL_BRAKE * 100 ? ' → en el cotizador sale "Mercado inestable" hasta que vuelvas a calibrar.' : '.');
  }
  box.textContent = txt + ' Al guardar, se calibra con el número de tu proveedor.';
}
setInterval(() => { if (!$('editor').hidden && $('prov-auto')?.checked) brlLive(); }, 60 * 1000);

