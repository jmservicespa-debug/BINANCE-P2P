import { ADVISORS, ORIGINS, ROUTES, amountNum, belowMin, convert, fmt, invert } from './rutas.js';
import { esc, flag, flags } from './ui.js';

const $ = (id) => document.getElementById(id);
const MAIN_LINE = 'jamer';  // a quién escribe quien llega sin enlace de asesor

// Asesor: viene en el enlace (?a=jamer) y se recuerda en este celular para la próxima visita.
let adv = new URLSearchParams(location.search).get('a');
try {
  if (adv && ADVISORS[adv]) localStorage.setItem('jmc_asesor', adv);
  else adv = localStorage.getItem('jmc_asesor');
} catch { /* sin almacenamiento: se muestran los dos asesores */ }
if (!ADVISORS[adv]) adv = null;

let data = null, origin = 'CL', route = null, mode = 'send';
const OTHER = 'OTHER';  // origen u otro destino fuera de las rutas principales: tasa por WhatsApp
const GLOBE = '<svg class="flag" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="var(--box)" stroke="var(--box-line)"/><path d="M1 12h22M12 1c3 3.2 4.5 7 4.5 11S15 19.8 12 23c-3-3.2-4.5-7-4.5-11S9 4.2 12 1z" fill="none" stroke="var(--accent)" stroke-width="1.4"/></svg>';
const rateOf = (id) => data?.routes.find((r) => r.id === id);
const statusOf = (id) => rateOf(id)?.status ?? (rateOf(id)?.active ? 'on' : 'off');
// Se muestran las rutas activas y las de mercado inestable (estas sin tasa: se pide por WhatsApp).
const activeRoutes = (o) => ROUTES.filter((r) => r.from === o && ['on', 'ask'].includes(statusOf(r.id)));

function renderOrigins() {
  $('origins').innerHTML = Object.entries(ORIGINS).map(([k, o]) =>
    `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} ${esc(o.name)}</button>`).join('')
    + `<button data-o="${OTHER}" aria-pressed="${origin === OTHER}">${GLOBE} Otro país</button>`;
  $('origins').querySelectorAll('button').forEach((b) => b.onclick = () => {
    origin = b.dataset.o; route = origin === OTHER ? null : activeRoutes(origin)[0]?.id ?? OTHER;
    ['o-to', 'o-amount', ...(origin === OTHER ? ['o-from'] : [])].forEach((id) => { $(id).value = ''; });
    render();
  });
}

function renderDests() {
  $('dests').hidden = origin === OTHER;
  if (origin === OTHER) return;
  const list = activeRoutes(origin);
  $('dests').innerHTML = list.map((r) => `<button data-r="${r.id}" aria-pressed="${r.id === route}">${flags(r.to)}<span>${esc(r.name)}<small>${statusOf(r.id) === 'ask' ? 'Mercado inestable' : `${esc(r.unit)} (${r.cur})`}</small></span></button>`).join('')
    + `<button data-r="${OTHER}" aria-pressed="${route === OTHER}">${GLOBE}<span>Otro destino<small>Tasa por WhatsApp</small></span></button>`;
  $('dests').querySelectorAll('button').forEach((b) => b.onclick = () => { route = b.dataset.r; render(); });
}

// Otro país (origen) u otro destino: sin tasa publicada; el cliente la pide por WhatsApp.
function otherQuote() {
  const fixed = origin !== OTHER;
  if (fixed) $('o-from').value = ORIGINS[origin].name;
  $('o-from').disabled = fixed;
  const from = $('o-from').value.trim(), to = $('o-to').value.trim(), amount = $('o-amount').value.trim();
  const text = `Hola, quiero enviar dinero${from ? ` desde ${from}` : ''}${to ? ` a ${to}` : ''}${amount ? `. Monto aproximado: ${amount}` : ''}. ¿Qué tasa tienen?`;
  $('wa').innerHTML = waButtons(text, 'Pedir tasa');
}

function calc() {
  const isOther = origin === OTHER || route === OTHER;
  $('other').hidden = !isOther;
  $('quote').hidden = isOther;
  if (isOther) { otherQuote(); return; }
  const r = ROUTES.find((x) => x.id === route);
  const o = ORIGINS[origin];
  if (!r) { $('r-get').hidden = true; $('r-free').hidden = true; $('r-break').hidden = true; $('r-min').textContent = ''; $('r-big').textContent = '—'; $('r-send').textContent = ''; $('r-rate').textContent = ''; $('r-bcv').hidden = true; $('wa').innerHTML = waButtons(''); return; }
  const bcv = data.bcv?.value;
  // "Equivalente en dólares BCV" (llegan bolívares): solo hacia Venezuela y con el dólar BCV disponible.
  const bcvOk = r.to.includes('VE') && bcv > 0;
  $('mode-bcv').hidden = !bcvOk;
  if (mode === 'bcv' && !bcvOk) setMode('send');
  if (statusOf(r.id) === 'ask') { unstable(r, o); return; }
  $('r-big').classList.remove('ask');
  const rate = rateOf(r.id).rate;
  amountLabels(r, o);
  const x = amountNum($('amount').value);
  const usd = mode === 'bcv' ? x : null;
  // Montos completos, sin decimales: desde ,50 se redondea hacia arriba; por debajo, hacia abajo.
  const target = mode === 'bcv' ? Math.round(x * bcv) : x;  // bolívares que deben llegar
  const send = Math.round(mode === 'send' ? x : invert(r, rate, target));
  const get = Math.round(mode === 'send' ? convert(r, rate, send) : target);
  if (belowMin(r, send)) { minimum(r, o, send); return; }
  $('r-big').classList.remove('ask');
  $('r-free').hidden = false;
  $('r-break').hidden = false;
  $('r-break').innerHTML = [
    ['Monto a enviar', `${fmt(send, 0)} ${o.cur}`],
    ['Comisión', `0 ${o.cur}`],
    ['Cargos extras', `0 ${o.cur}`],
    ['Tasa del día', rate],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')
    + `<dt class="total">Total a pagar</dt><dd class="total">${fmt(send, 0)} ${o.cur}</dd>`;
  $('r-label').textContent = mode === 'send' ? `Recibe en ${r.name}` : 'Debes enviar';
  $('r-big').textContent = mode === 'send' ? `${fmt(get, r.dec)} ${r.cur}` : `${fmt(send, 0)} ${o.cur}`;
  // Lo que recibe la persona, bien visible cuando el cliente parte del monto a recibir.
  $('r-send').textContent = '';
  $('r-get').hidden = mode === 'send';
  if (mode !== 'send') {
    const ves = r.cur === 'VES';
    $('g-label').textContent = `Recibe en ${r.name}`;
    $('g-amount').textContent = `${fmt(get, r.dec)} ${ves ? 'Bs' : r.cur}`;
    $('g-sub').textContent = mode === 'bcv' ? `Equivalen a ${fmt(usd, 0)} USD al dólar BCV` : ves ? 'Bolívares (VES)' : r.unit;
  }
  $('r-rate').textContent = '';
  $('r-min').textContent = r.min ? `Envío mínimo: ${fmt(r.min, 0)} ${o.cur}` : '';
  $('r-bcv').hidden = !bcvOk;
  if (!$('r-bcv').hidden) {
    $('b-rate').textContent = `${fmt(bcv, 2)} Bs/USD`;
    $('b-usd').textContent = `${fmt(Math.round(get / bcv), 0)} USD`;
    $('b-date').textContent = data.bcv.date ? `(${data.bcv.date.split('-').reverse().join('/')})` : '';
  }
  $('dest-note').textContent = r.note || '';
  const ok = Number.isFinite(send) && Number.isFinite(get) && send > 0;
  const text = !ok ? '' : mode === 'bcv'
    ? `Hola, necesito que lleguen ${fmt(get, 0)} Bs a ${r.name} (equivalentes a ${fmt(usd, 0)} USD al dólar BCV), enviando desde ${o.name}. Según el cotizador debo pagar ${fmt(send, 0)} ${o.cur} (tasa ${rate}, sin comisión). ¿Me confirmas?`
    : `Hola, quiero enviar ${fmt(send, 0)} ${o.cur} desde ${o.name} a ${r.name}. Según el cotizador recibe ${fmt(get, r.dec)} ${r.cur} (tasa ${rate}, sin comisión). ¿Me confirmas?`;
  $('wa').innerHTML = waButtons(text);
}

// Monto por debajo del mínimo de la ruta: no se cotiza, se indica el mínimo.
function minimum(r, o, send) {
  $('r-get').hidden = true;
  $('r-free').hidden = true;
  $('r-break').hidden = true;
  $('r-label').textContent = `Envíos a ${r.name}`;
  $('r-big').textContent = `Mínimo ${fmt(r.min, 0)} ${o.cur}`;
  $('r-big').classList.add('ask');
  $('r-send').textContent = mode === 'send' ? `Escribiste ${fmt(send, 0)} ${o.cur}.` : `Para ese monto tendrías que enviar ${fmt(send, 0)} ${o.cur}.`;
  $('r-rate').textContent = '';
  $('r-min').textContent = '';
  $('r-bcv').hidden = true;
  $('dest-note').textContent = r.note || '';
  $('wa').innerHTML = waButtons('');
}

// Mercado inestable: no se calcula; el cliente pide la tasa del momento con su monto ya escrito.
function unstable(r, o) {
  $('r-get').hidden = true;
  $('r-free').hidden = true;
  $('r-break').hidden = true;
  amountLabels(r, o);
  const x = amountNum($('amount').value);
  $('r-label').textContent = `Envíos a ${r.name}`;
  $('r-big').textContent = 'Mercado inestable';
  $('r-big').classList.add('ask');
  $('r-send').textContent = 'La tasa de este envío se confirma por WhatsApp.';
  $('r-rate').textContent = '';
  $('r-bcv').hidden = true;
  $('dest-note').textContent = r.note || '';
  $('r-min').textContent = r.min ? `Envío mínimo: ${fmt(r.min, 0)} ${o.cur}` : '';
  if (mode === 'send' && belowMin(r, x)) { minimum(r, o, x); return; }
  const amount = !(Number.isFinite(x) && x > 0) ? 'hacer un envío'
    : mode === 'send' ? `enviar ${fmt(x, 0)} ${o.cur}` : mode === 'bcv' ? `que lleguen bolívares equivalentes a ${fmt(x, 0)} USD al dólar BCV` : `que reciban ${fmt(x, r.dec)} ${r.cur}`;
  $('wa').innerHTML = waButtons(`Hola, quiero ${amount} desde ${o.name} a ${r.name}. ¿Me das la tasa de este momento?`, 'Pedir tasa');
}

function amountLabels(r, o) {
  $('amount-label').textContent = { send: 'Monto que envías', get: 'Monto que debe recibir', bcv: 'Los bolívares deben equivaler a' }[mode];
  $('amount-cur').textContent = mode === 'send' ? o.cur : mode === 'bcv' ? 'USD BCV' : r.cur;
}

function setMode(m) {
  mode = m;
  document.querySelectorAll('#modes button').forEach((o) => o.setAttribute('aria-pressed', String(o.dataset.mode === m)));
  const r = ROUTES.find((x) => x.id === route);
  $('amount').value = m === 'bcv' ? '20' : m === 'send' || r?.cur !== 'USD' ? '100.000' : '100';
}

function waButtons(text, action) {
  // Enlace de un asesor: su nombre y número. Enlace general: un solo botón sin nombre a la línea principal.
  const p = ADVISORS[adv] || ADVISORS[MAIN_LINE];
  const msg = text || 'Hola, quiero cotizar un envío.';
  const label = action ? (adv ? `${action} a ${esc(p.name.split(' ')[0])} por WhatsApp` : `${action} por WhatsApp`)
    : adv ? `Escribir a ${esc(p.name.split(' ')[0])} por WhatsApp` : 'Escribir por WhatsApp';
  return `<a href="https://wa.me/${p.phone}?text=${encodeURIComponent(msg)}" target="_blank" rel="noopener">${label}</a>`
    + `<span class="fine">${adv ? esc(p.name) + ' · ' : ''}${p.show}</span>`;
}

function render() { renderOrigins(); renderDests(); calc(); }

document.querySelectorAll('#modes button').forEach((b) => b.onclick = () => { setMode(b.dataset.mode); calc(); });
$('amount').oninput = calc;
['o-from', 'o-to', 'o-amount'].forEach((id) => { $(id).oninput = otherQuote; });

async function load() {
  try {
    const res = await fetch('/api/tasas', { cache: 'no-store' });
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
    $('error').hidden = true;
  } catch {
    if (!data) { $('error').hidden = false; $('error').textContent = 'No pudimos cargar las tasas. Revisa tu conexión o escríbenos por WhatsApp.'; data = { routes: [], bcv: null }; }
  }
  $('updated').textContent = data.updated
    ? 'Tasas del ' + new Date(data.updated).toLocaleString('es-CL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
    : 'Tasas aún no publicadas';
  if (origin !== OTHER && route !== OTHER && (!route || !activeRoutes(origin).some((r) => r.id === route))) route = activeRoutes(origin)[0]?.id ?? null;
  render();
}
load();
setInterval(load, 5 * 60 * 1000);  // si el cliente deja la página abierta, ve la tasa nueva
