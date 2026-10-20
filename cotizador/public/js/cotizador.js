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
const rateOf = (id) => data?.routes.find((r) => r.id === id);
const statusOf = (id) => rateOf(id)?.status ?? (rateOf(id)?.active ? 'on' : 'off');
// Se muestran las rutas activas y las de mercado inestable (estas sin tasa: se pide por WhatsApp).
const activeRoutes = (o) => ROUTES.filter((r) => r.from === o && ['on', 'ask'].includes(statusOf(r.id)));

function renderOrigins() {
  $('origins').innerHTML = Object.entries(ORIGINS).map(([k, o]) =>
    `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} Desde ${esc(o.name)}</button>`).join('');
  $('origins').querySelectorAll('button').forEach((b) => b.onclick = () => {
    origin = b.dataset.o; route = activeRoutes(origin)[0]?.id ?? null; render();
  });
}

function renderDests() {
  const list = activeRoutes(origin);
  $('dests').innerHTML = list.map((r) => `<button data-r="${r.id}" aria-pressed="${r.id === route}">${flags(r.to)}<span>${esc(r.name)}<small>${statusOf(r.id) === 'ask' ? 'Mercado inestable' : `${esc(r.unit)} (${r.cur})`}</small></span></button>`).join('')
    || '<span class="muted">Por ahora no hay envíos disponibles desde este país.</span>';
  $('dests').querySelectorAll('button').forEach((b) => b.onclick = () => { route = b.dataset.r; render(); });
}

function calc() {
  const r = ROUTES.find((x) => x.id === route);
  const o = ORIGINS[origin];
  if (!r) { $('r-free').hidden = true; $('r-break').hidden = true; $('r-min').textContent = ''; $('r-big').textContent = '—'; $('r-send').textContent = ''; $('r-rate').textContent = ''; $('r-bcv').hidden = true; $('wa').innerHTML = waButtons(''); return; }
  if (statusOf(r.id) === 'ask') { unstable(r, o); return; }
  $('r-big').classList.remove('ask');
  const rate = rateOf(r.id).rate;
  $('amount-label').textContent = mode === 'send' ? 'Monto que envías' : 'Monto que debe recibir';
  $('amount-cur').textContent = mode === 'send' ? o.cur : r.cur;
  const x = amountNum($('amount').value);
  const send = mode === 'send' ? x : Math.round(invert(r, rate, x));
  const get = mode === 'send' ? convert(r, rate, x) : x;
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
  $('r-send').textContent = mode === 'send' ? '' : `Recibe ${fmt(get, r.dec)} ${r.cur}`;
  $('r-rate').textContent = '';
  $('r-min').textContent = r.min ? `Envío mínimo: ${fmt(r.min, 0)} ${o.cur}` : '';
  const bcv = data.bcv?.value;
  $('r-bcv').hidden = !(r.to.includes('VE') && bcv > 0);
  if (!$('r-bcv').hidden) {
    $('b-rate').textContent = `${fmt(bcv, 2)} Bs/USD`;
    $('b-usd').textContent = `${fmt(get / bcv, 2)} USD`;
    $('b-date').textContent = data.bcv.date ? `(${data.bcv.date.split('-').reverse().join('/')})` : '';
  }
  $('dest-note').textContent = r.note || '';
  const ok = Number.isFinite(send) && Number.isFinite(get) && send > 0;
  const text = ok ? `Hola, quiero enviar ${fmt(send, 0)} ${o.cur} desde ${o.name} a ${r.name}. Según el cotizador recibe ${fmt(get, r.dec)} ${r.cur} (tasa ${rate}, sin comisión). ¿Me confirmas?` : '';
  $('wa').innerHTML = waButtons(text);
}

// Monto por debajo del mínimo de la ruta: no se cotiza, se indica el mínimo.
function minimum(r, o, send) {
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
  $('r-free').hidden = true;
  $('r-break').hidden = true;
  $('amount-label').textContent = mode === 'send' ? 'Monto que envías' : 'Monto que debe recibir';
  $('amount-cur').textContent = mode === 'send' ? o.cur : r.cur;
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
  const amount = Number.isFinite(x) && x > 0 ? (mode === 'send' ? `enviar ${fmt(x, 0)} ${o.cur}` : `que reciban ${fmt(x, r.dec)} ${r.cur}`) : 'hacer un envío';
  $('wa').innerHTML = waButtons(`Hola, quiero ${amount} desde ${o.name} a ${r.name}. ¿Me das la tasa de este momento?`, 'Pedir tasa por WhatsApp');
}

function waButtons(text, action) {
  // Enlace de un asesor: su nombre y número. Enlace general: un solo botón sin nombre a la línea principal.
  const p = ADVISORS[adv] || ADVISORS[MAIN_LINE];
  const msg = text || 'Hola, quiero cotizar un envío.';
  const label = action ? (adv ? `${action} a ${esc(p.name.split(' ')[0])}` : action)
    : adv ? `Escribir a ${esc(p.name.split(' ')[0])} por WhatsApp` : 'Escribir por WhatsApp';
  return `<a href="https://wa.me/${p.phone}?text=${encodeURIComponent(msg)}" target="_blank" rel="noopener">${label}</a>`
    + `<span class="fine">${adv ? esc(p.name) + ' · ' : ''}${p.show}</span>`
    + preferential(p);
}

// Montos altos: tasa preferencial conversada directamente con el asesor.
function preferential(p) {
  const r = ROUTES.find((x) => x.id === route);
  const where = r ? ` desde ${ORIGINS[origin].name} a ${r.name}` : '';
  const msg = `Hola, quiero enviar un monto alto${where}. ¿Qué tasa preferencial me puedes dar?`;
  const who = adv ? `Escríbele a ${esc(p.name.split(' ')[0])}` : 'Escríbenos';
  return `<div class="pref"><div><b>¿Montos altos?</b> Tenemos tasas preferenciales.</div>`
    + `<a href="https://wa.me/${p.phone}?text=${encodeURIComponent(msg)}" target="_blank" rel="noopener">${who} y pide tu tasa →</a></div>`;
}

function render() { renderOrigins(); renderDests(); calc(); }

document.querySelectorAll('#modes button').forEach((b) => b.onclick = () => {
  mode = b.dataset.mode;
  document.querySelectorAll('#modes button').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
  const r = ROUTES.find((x) => x.id === route);
  $('amount').value = mode === 'send' || r?.cur !== 'USD' ? '100.000' : '100';
  calc();
});
$('amount').oninput = calc;

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
  if (!route || !activeRoutes(origin).some((r) => r.id === route)) route = activeRoutes(origin)[0]?.id ?? null;
  render();
}
load();
setInterval(load, 5 * 60 * 1000);  // si el cliente deja la página abierta, ve la tasa nueva
