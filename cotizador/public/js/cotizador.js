import { ADVISORS, ORIGINS, ROUTES, amountNum, convert, fmt, invert } from './rutas.js';
import { esc, flag, flags } from './ui.js';

const $ = (id) => document.getElementById(id);

// Asesor: viene en el enlace (?a=jamer) y se recuerda en este celular para la próxima visita.
let adv = new URLSearchParams(location.search).get('a');
try {
  if (adv && ADVISORS[adv]) localStorage.setItem('jmc_asesor', adv);
  else adv = localStorage.getItem('jmc_asesor');
} catch { /* sin almacenamiento: se muestran los dos asesores */ }
if (!ADVISORS[adv]) adv = null;

let data = null, origin = 'CL', route = null, mode = 'send';
const rateOf = (id) => data?.routes.find((r) => r.id === id);
const activeRoutes = (o) => ROUTES.filter((r) => r.from === o && rateOf(r.id)?.active);

function renderOrigins() {
  $('origins').innerHTML = Object.entries(ORIGINS).map(([k, o]) =>
    `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} Desde ${esc(o.name)}</button>`).join('');
  $('origins').querySelectorAll('button').forEach((b) => b.onclick = () => {
    origin = b.dataset.o; route = activeRoutes(origin)[0]?.id ?? null; render();
  });
}

function renderDests() {
  const list = activeRoutes(origin);
  $('dests').innerHTML = list.map((r) => `<button data-r="${r.id}" aria-pressed="${r.id === route}">${flags(r.to)}<span>${esc(r.name)}<small>${esc(r.unit)} (${r.cur})</small></span></button>`).join('')
    || '<span class="muted">Por ahora no hay envíos disponibles desde este país.</span>';
  $('dests').querySelectorAll('button').forEach((b) => b.onclick = () => { route = b.dataset.r; render(); });
}

function calc() {
  const r = ROUTES.find((x) => x.id === route);
  const o = ORIGINS[origin];
  if (!r) { $('r-big').textContent = '—'; $('r-send').textContent = ''; $('r-rate').textContent = ''; $('r-bcv').hidden = true; $('wa').innerHTML = waButtons(''); return; }
  const rate = rateOf(r.id).rate;
  $('amount-label').textContent = mode === 'send' ? 'Monto que envías' : 'Monto que debe recibir';
  $('amount-cur').textContent = mode === 'send' ? o.cur : r.cur;
  const x = amountNum($('amount').value);
  const send = mode === 'send' ? x : Math.round(invert(r, rate, x));
  const get = mode === 'send' ? convert(r, rate, x) : x;
  $('r-label').textContent = mode === 'send' ? `Recibe en ${r.name}` : 'Debes enviar';
  $('r-big').textContent = mode === 'send' ? `${fmt(get, r.dec)} ${r.cur}` : `${fmt(send, 0)} ${o.cur}`;
  $('r-send').textContent = mode === 'send' ? `Envías ${fmt(send, 0)} ${o.cur}` : `Recibe ${fmt(get, r.dec)} ${r.cur}`;
  $('r-rate').textContent = `Tasa ${rate}`;
  const bcv = data.bcv?.value;
  $('r-bcv').hidden = !(r.to.includes('VE') && bcv > 0);
  if (!$('r-bcv').hidden) {
    $('b-rate').textContent = `${fmt(bcv, 2)} Bs/USD`;
    $('b-usd').textContent = `${fmt(get / bcv, 2)} USD`;
    $('b-date').textContent = data.bcv.date ? `(${data.bcv.date.split('-').reverse().join('/')})` : '';
  }
  $('dest-note').textContent = r.note || '';
  const ok = Number.isFinite(send) && Number.isFinite(get) && send > 0;
  const text = ok ? `Hola, quiero enviar ${fmt(send, 0)} ${o.cur} desde ${o.name} a ${r.name}. Según el cotizador recibe ${fmt(get, r.dec)} ${r.cur} (tasa ${rate}). ¿Me confirmas?` : '';
  $('wa').innerHTML = waButtons(text);
}

function waButtons(text) {
  const people = adv ? [ADVISORS[adv]] : Object.values(ADVISORS);
  const msg = text || 'Hola, quiero cotizar un envío.';
  return people.map((p) => `<a href="https://wa.me/${p.phone}?text=${encodeURIComponent(msg)}" target="_blank" rel="noopener">Escribir a ${esc(p.name.split(' ')[0])} por WhatsApp</a>`).join('')
    + `<span class="fine">${people.map((p) => `${esc(p.name)} · ${p.show}`).join(' · ')}</span>`;
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
  if (!route || !rateOf(route)?.active) route = activeRoutes(origin)[0]?.id ?? null;
  render();
}
load();
setInterval(load, 5 * 60 * 1000);  // si el cliente deja la página abierta, ve la tasa nueva
