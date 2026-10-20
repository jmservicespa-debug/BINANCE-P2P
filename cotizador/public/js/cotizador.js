import { ADVISORS, ORIGINS, ROUTES, USDT_ROUTE, amountNum, belowMin, convert, fmt, invert, usdtNum } from './rutas.js';
import { BRL_BRAKE, USDT_URL, brlPerClp, parseCriptoYa } from './criptoya.js';
import { esc, flag, flags } from './ui.js';

const $ = (id) => document.getElementById(id);
const MAIN_LINE = 'jamer';
const dot = (t) => (t.endsWith('.') ? t : `${t}.`);  // "EE. UU." ya termina en punto  // a quién escribe quien llega sin enlace de asesor

// Asesor: viene en el enlace (?a=jamer) y se recuerda en este celular para la próxima visita.
let adv = new URLSearchParams(location.search).get('a');
try {
  if (adv && ADVISORS[adv]) localStorage.setItem('jmc_asesor', adv);
  else adv = localStorage.getItem('jmc_asesor');
} catch { /* sin almacenamiento: se muestran los dos asesores */ }
if (!ADVISORS[adv]) adv = null;

let data = null, origin = 'CL', route = null, mode = 'send';
const OTHER = 'OTHER';  // origen u otro destino fuera de las rutas principales: tasa por WhatsApp
// Orígenes que se muestran con su bandera y el aviso "Próximamente", con los destinos que vendrán.
const SOON = { BR: { name: 'Brasil', to: [['BR', 'Brasil'], ['CO', 'Colombia'], ['VE', 'Venezuela'], ['USDT', 'USDT']] } };
const GLOBE = '<svg class="flag" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="var(--box)" stroke="var(--box-line)"/><path d="M1 12h22M12 1c3 3.2 4.5 7 4.5 11S15 19.8 12 23c-3-3.2-4.5-7-4.5-11S9 4.2 12 1z" fill="none" stroke="var(--accent)" stroke-width="1.4"/></svg>';
const rateOf = (id) => data?.routes.find((r) => r.id === id);
const statusOf = (id) => rateOf(id)?.status ?? (rateOf(id)?.active ? 'on' : 'off');
// Se muestran las rutas activas y las de mercado inestable (estas sin tasa: se pide por WhatsApp).
const ALL = [...ROUTES, USDT_ROUTE];
const activeRoutes = (o) => ALL.filter((r) => r.from === o && ['on', 'ask'].includes(statusOf(r.id)));

function renderOrigins() {
  $('origins').innerHTML = Object.entries(ORIGINS).map(([k, o]) =>
    `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} ${esc(o.name)}</button>`).join('')
    + Object.entries(SOON).map(([k, s]) => `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} ${esc(s.name)}</button>`).join('')
    + `<button data-o="${OTHER}" aria-pressed="${origin === OTHER}">${GLOBE} Otro país</button>`;
  $('origins').querySelectorAll('button').forEach((b) => b.onclick = () => {
    origin = b.dataset.o; route = origin === OTHER || SOON[origin] ? null : activeRoutes(origin)[0]?.id ?? OTHER;
    ['o-to', 'o-amount', ...(origin === OTHER ? ['o-from'] : [])].forEach((id) => { $(id).value = ''; });
    $('amount').value = '';
    render();
  });
}

function renderDests() {
  $('dests').hidden = origin === OTHER || Boolean(SOON[origin]);
  if ($('dests').hidden) return;
  const list = activeRoutes(origin);
  $('dests').innerHTML = list.map((r) => `<button data-r="${r.id}" aria-pressed="${r.id === route}">${flags(r.to)}<span>${esc(r.name)}<small>${esc(r.unit)} (${r.cur})${statusOf(r.id) === 'ask' ? '<br>Mercado inestable' : ''}</small></span></button>`).join('')
    + `<button data-r="${OTHER}" aria-pressed="${route === OTHER}">${GLOBE}<span>Otro destino<small>Tasa por WhatsApp</small></span></button>`;
  $('dests').querySelectorAll('button').forEach((b) => b.onclick = () => {
    if (mode !== 'send' && b.dataset.r !== route) $('amount').value = '';  // la casilla está en la moneda del destino
    route = b.dataset.r; render();
  });
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
  const soon = Boolean(SOON[origin]);
  $('soon').hidden = !soon;
  $('wa').hidden = soon;
  if (soon) {
    $('soon-list').innerHTML = SOON[origin].to.map(([c, n]) => `<span>${flag(c)}${esc(n)}</span>`).join('');
    $('other').hidden = true; $('quote').hidden = true; $('dest-note').textContent = ''; return; }
  const isOther = origin === OTHER || route === OTHER;
  $('other').hidden = !isOther;
  $('quote').hidden = isOther;
  if (isOther) { otherQuote(); return; }
  const r = ALL.find((x) => x.id === route);
  const o = ORIGINS[origin];
  if (!r) { $('r-get').hidden = true; $('r-free').hidden = true; $('r-break').hidden = true; $('r-min').textContent = ''; $('r-big').textContent = '—'; $('r-send').textContent = ''; $('r-rate').textContent = ''; $('r-bcv').hidden = true; $('wa').innerHTML = waButtons(''); return; }
  const bcv = data.bcv?.value;
  // "Equivalente en dólares BCV" (llegan bolívares): solo hacia Venezuela y con el dólar BCV disponible.
  const bcvOk = r.to.includes('VE') && bcv > 0;
  $('mode-bcv').hidden = !bcvOk;
  if (mode === 'bcv' && !bcvOk) setMode('send');
  modeButtons(r);
  if (mode === 'sell') { sellUsdt(r, o); return; }
  if (statusOf(r.id) === 'ask') { unstable(r, o); return; }
  $('r-big').classList.remove('ask');
  const rate = rateOf(r.id).rate;
  amountLabels(r, o);
  if (!$('amount').value.trim()) { rateOnly(r, o, rate); return; }
  const isUsdt = r.cur === 'USDT';
  const x = (isUsdt && mode === 'get' ? usdtNum : amountNum)($('amount').value);
  const usd = mode === 'bcv' ? x : null;
  // Montos completos, sin decimales: desde ,50 se redondea hacia arriba; por debajo, hacia abajo.
  const target = mode === 'bcv' ? Math.round(x * bcv) : x;  // bolívares que deben llegar
  const send = Math.round(mode === 'send' ? x : invert(r, rate, target));
  // USDT con 2 decimales, hacia abajo (nunca se entrega de más); el resto, entero.
  const get = isUsdt ? Math.floor((mode === 'send' ? convert(r, rate, send) : target) * 100) / 100
    : Math.round(mode === 'send' ? convert(r, rate, send) : target);
  if (belowMin(r, send)) { minimum(r, o, send); return; }
  $('r-big').classList.remove('ask');
  $('r-free').hidden = false;
  $('r-break').hidden = false;
  $('r-break').innerHTML = [
    [isUsdt ? 'Monto a pagar' : 'Monto a enviar', `${fmt(send, 0)} ${o.cur}`],
    ['Comisión', `0 ${o.cur}`],
    ['Cargos extras', `0 ${o.cur}`],
    ['Tasa del día', isUsdt ? `${fmt(Number(rate), 2)} CLP por USDT` : rate],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')
    + `<dt class="total">Total a pagar</dt><dd class="total">${fmt(send, 0)} ${o.cur}</dd>`;
  $('r-label').textContent = isUsdt ? (mode === 'send' ? 'Recibes' : 'Debes pagar') : mode === 'send' ? `Recibe en ${r.name}` : 'Debes enviar';
  $('r-big').textContent = mode === 'send' ? `${fmt(get, r.dec)} ${r.cur}` : `${fmt(send, 0)} ${o.cur}`;
  // Lo que recibe la persona, bien visible cuando el cliente parte del monto a recibir.
  $('r-send').textContent = '';
  $('r-get').hidden = mode === 'send';
  if (mode !== 'send') {
    const ves = r.cur === 'VES';
    $('g-label').textContent = isUsdt ? 'Recibes' : `Recibe en ${r.name}`;
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
    : isUsdt ? `Hola, quiero comprar ${fmt(get, 2)} USDT pagando ${fmt(send, 0)} CLP (precio ${fmt(Number(rate), 2)} CLP por USDT, sin comisión). ¿Me confirmas?`
    : `Hola, quiero enviar ${fmt(send, 0)} ${o.cur} desde ${o.name} a ${dot(r.name)} Según el cotizador recibe ${fmt(get, r.dec)} ${r.cur} (tasa ${rate}, sin comisión). ¿Me confirmas?`;
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
  $('r-label').textContent = r.cur === 'USDT' ? 'USDT' : `Envíos a ${r.name}`;
  $('r-big').textContent = 'Mercado inestable';
  $('r-big').classList.add('ask');
  $('r-send').textContent = r.cur === 'USDT' ? 'El precio se confirma por WhatsApp.' : 'La tasa de este envío se confirma por WhatsApp.';
  $('r-rate').textContent = '';
  $('r-bcv').hidden = true;
  $('dest-note').textContent = r.note || '';
  $('r-min').textContent = r.min ? `Envío mínimo: ${fmt(r.min, 0)} ${o.cur}` : '';
  if (mode === 'send' && belowMin(r, x)) { minimum(r, o, x); return; }
  const amount = r.cur === 'USDT' ? (mode === 'sell' ? 'vender USDT' : 'comprar USDT')
    : !(Number.isFinite(x) && x > 0) ? 'hacer un envío'
    : mode === 'send' ? `enviar ${fmt(x, 0)} ${o.cur}` : mode === 'bcv' ? `que lleguen bolívares equivalentes a ${fmt(x, 0)} USD al dólar BCV` : `que reciban ${fmt(x, r.dec)} ${r.cur}`;
  $('wa').innerHTML = waButtons(r.cur === 'USDT' ? `Hola, quiero ${amount}. ¿Me das el precio de este momento?`
    : `Hola, quiero ${amount} desde ${o.name} a ${dot(r.name)} ¿Me das la tasa de este momento?`, 'Pedir tasa');
}

function amountLabels(r, o) {
  placeholder(r, o);
  $('amount-label').textContent = r.cur === 'USDT'
    ? { send: 'Pesos que pagas', get: 'USDT que quieres', sell: 'USDT que vendes' }[mode]
    : { send: 'Monto que envías', get: 'Monto que debe recibir', bcv: 'Los bolívares deben equivaler a' }[mode];
  $('amount-cur').textContent = mode === 'send' ? o.cur : mode === 'bcv' ? 'USD BCV' : r.cur;
}

// USDT: "Yo envío" / "Quiero que reciba" pasan a ser compra en pesos o en USDT, más la opción de vender.
function modeButtons(r) {
  const isUsdt = r.cur === 'USDT';
  const btn = (m) => document.querySelector(`#modes button[data-mode="${m}"]`);
  btn('send').textContent = isUsdt ? 'Compro (en pesos)' : 'Yo envío';
  btn('get').textContent = isUsdt ? 'Compro (en USDT)' : 'Quiero que reciba';
  $('mode-sell').hidden = !isUsdt;
  if (mode === 'sell' && !isUsdt) setMode('send');
}

// Vender USDT: el cliente entrega USDT y recibe pesos al precio de compra (bid de Vita − ganancia al comprar).
function sellUsdt(r, o) {
  const buy = rateOf(r.id)?.buyRate;
  amountLabels(r, o);
  if (!buy) { unstable(r, o); return; }
  $('r-big').classList.remove('ask');
  const x = usdtNum($('amount').value);
  ['r-get', 'r-bcv'].forEach((id) => { $(id).hidden = true; });
  $('r-rate').textContent = '';
  $('r-min').textContent = '';
  $('dest-note').textContent = 'Envías los USDT a la wallet o cuenta de Binance que te indiquemos (la red se confirma por WhatsApp)';
  if (!$('amount').value.trim()) {
    $('r-free').hidden = true; $('r-break').hidden = true;
    $('r-big').classList.add('ask');
    $('r-label').textContent = 'Te compramos tus USDT';
    $('r-big').textContent = `${fmt(Number(buy), 2)} CLP por USDT`;
    $('r-send').textContent = 'Escribe cuántos USDT vendes para ver cuántos pesos recibes.';
    $('wa').innerHTML = waButtons('Hola, quiero vender USDT.');
    return;
  }
  const clp = Math.floor(Math.round(x * Number(buy) * 100) / 100);  // pesos enteros, hacia abajo
  const ok = Number.isFinite(clp) && clp > 0;
  $('r-free').hidden = false;
  $('r-break').hidden = false;
  $('r-break').innerHTML = [
    ['USDT que entregas', `${fmt(x, 2)} USDT`],
    ['Comisión', '0 CLP'],
    ['Precio de compra', `${fmt(Number(buy), 2)} CLP por USDT`],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')
    + `<dt class="total">Total a recibir</dt><dd class="total">${fmt(clp, 0)} ${o.cur}</dd>`;
  $('r-label').textContent = 'Recibes en pesos';
  $('r-big').textContent = `${fmt(clp, 0)} ${o.cur}`;
  $('r-send').textContent = '';
  $('wa').innerHTML = waButtons(ok ? `Hola, quiero vender ${fmt(x, 2)} USDT. Según el cotizador recibo ${fmt(clp, 0)} CLP (precio ${fmt(Number(buy), 2)} CLP por USDT, sin comisión). ¿Me confirmas?` : 'Hola, quiero vender USDT.');
}

function setMode(m) {
  mode = m;
  document.querySelectorAll('#modes button').forEach((o) => o.setAttribute('aria-pressed', String(o.dataset.mode === m)));
  $('amount').value = '';  // cambia la moneda de la casilla: el cliente escribe su monto
}

// Casilla vacía al inicio: se muestra la tasa del día y un ejemplo en gris según la moneda.
const EXAMPLES = { CLP: '100.000', COP: '200.000', VES: '100.000', PEN: '300', USD: '100', USDT: '100', BRL: '500' };
function placeholder(r, o) {
  const cur = mode === 'send' ? o.cur : mode === 'bcv' ? 'BCV' : r.cur;
  $('amount').placeholder = `Ej. ${cur === 'BCV' ? '20' : EXAMPLES[cur] || '100'}`;
}

function rateOnly(r, o, rate) {
  const isUsdt = r.cur === 'USDT';
  ['r-get', 'r-free', 'r-break', 'r-bcv'].forEach((id) => { $(id).hidden = true; });
  $('r-big').classList.add('ask');
  $('r-label').textContent = `Tasa del día · ${r.name}`;
  $('r-big').textContent = isUsdt ? `${fmt(Number(rate), 2)} CLP por USDT` : rate;
  $('r-send').textContent = !isUsdt ? 'Escribe el monto para ver cuánto recibe.'
    : mode === 'get' ? 'Escribe cuántos USDT quieres para ver cuánto pagas.' : 'Escribe los pesos para ver cuántos USDT recibes.';
  $('r-rate').textContent = '';
  $('r-min').textContent = r.min ? `Envío mínimo: ${fmt(r.min, 0)} ${o.cur}` : '';
  $('dest-note').textContent = r.note || '';
  $('wa').innerHTML = waButtons(isUsdt ? 'Hola, quiero comprar USDT.' : `Hola, quiero cotizar un envío desde ${o.name} a ${dot(r.name)}`);
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

// USDT: el precio de Vita (CriptoYa) se lee desde el navegador del cliente y se le suma la ganancia.
async function loadUsdt() {
  if (!data?.usdt) { data.routes = data.routes.filter((x) => x.id !== USDT_ROUTE.id); return; }
  let ref = null;
  try {
    const res = await fetch(USDT_URL, { cache: 'no-store' });
    ref = res.ok ? parseCriptoYa(await res.text()) : null;
  } catch { ref = null; }
  const price = ref ? ref.value * (1 + Number(data.usdt.margin_pct) / 100) : NaN;
  // Precio al que se le compran USDT al cliente: bid de Vita menos la ganancia al comprar.
  const buy = ref?.bid ? ref.bid * (1 - Number(data.usdt.buy_margin_pct ?? 8) / 100) : NaN;
  data.routes = data.routes.filter((x) => x.id !== USDT_ROUTE.id);
  // Sin precio de referencia: la opción queda como "Mercado inestable" (tasa por WhatsApp).
  data.routes.push({ id: USDT_ROUTE.id, status: Number.isFinite(price) ? 'on' : 'ask', rate: Number.isFinite(price) ? price.toFixed(2) : '',
    buyRate: Number.isFinite(buy) && buy > 0 ? buy.toFixed(2) : '' });
}

// Brasil automático: la tasa sigue al mercado (CriptoYa, leído desde este navegador).
// Si no hay dato o el mercado se movió más de 2 % desde la calibración: "Mercado inestable".
async function loadBrl() {
  const r = data?.routes.find((x) => x.id === 'cl-br' && x.auto);
  if (!r) return;
  const cross = await brlPerClp();
  if (!cross || Math.abs(cross / r.auto.cal - 1) > BRL_BRAKE) { r.status = 'ask'; r.rate = ''; r.active = false; return; }
  r.rate = (cross * r.auto.k).toFixed(6);
}

async function load() {
  try {
    const res = await fetch('/api/tasas', { cache: 'no-store' });
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
    $('error').hidden = true;
  } catch {
    if (!data) { $('error').hidden = false; $('error').textContent = 'No pudimos cargar las tasas. Revisa tu conexión o escríbenos por WhatsApp.'; data = { routes: [], bcv: null }; }
  }
  await Promise.all([loadUsdt(), loadBrl()]);
  $('updated').textContent = data.updated
    ? 'Tasas del ' + new Date(data.updated).toLocaleString('es-CL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
    : 'Tasas aún no publicadas';
  if (origin !== OTHER && !SOON[origin] && route !== OTHER && (!route || !activeRoutes(origin).some((r) => r.id === route))) route = activeRoutes(origin)[0]?.id ?? null;
  render();
}
load();
setInterval(load, 5 * 60 * 1000);  // si el cliente deja la página abierta, ve la tasa nueva
