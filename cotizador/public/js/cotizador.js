import { ADVISORS, ORIGINS, ROUTES, USDT_ROUTE, amountNum, belowMin, convert, fmt, invert, usdtNum } from './rutas.js';
import { BRL_BRAKE, USDT_URL, brlPerClp, copPerClp, parseCriptoYa } from './criptoya.js';
import { esc, flag, flags } from './ui.js';

const $ = (id) => document.getElementById(id);
const MAIN_LINE = 'jamer';
const dot = (t) => (t.endsWith('.') ? t : `${t}.`);  // "EE. UU." ya termina en punto  // a quién escribe quien llega sin enlace de asesor

// Asesor: solo cuando viene en el enlace (?a=jamer). El enlace general muestra siempre "Escribir por WhatsApp", sin nombre.
let adv = new URLSearchParams(location.search).get('a');
if (!ADVISORS[adv]) adv = null;
try { localStorage.removeItem('jmc_asesor'); } catch { /* lo recordado por la versión anterior ya no se usa */ }

let data = null, origin = 'CL', route = null, mode = 'send';
const OTHER = 'OTHER';  // origen u otro destino fuera de las rutas principales: tasa por WhatsApp
const CUR_NAME = { CLP: 'pesos', COP: 'pesos', EUR: 'euros', VES: 'bolívares', PEN: 'soles', USD: 'dólares', BRL: 'reales' };
const LONG_NAME = { CLP: 'pesos chilenos', COP: 'pesos colombianos' };
// Dólar y euro BCV con 2 decimales (el cálculo usa el valor completo que publica el BCV).
const bcvFmt = (v) => fmt(v, 2);
const fmt2 = (v) => fmt(v, Number.isInteger(v) ? 0 : 2);  // 100 → "100"; 100,5 → "100,50"
// Orígenes que se muestran con su bandera y el aviso "Próximamente", con los destinos que vendrán.
const SOON = { BR: { name: 'Brasil', to: [['PE', 'Perú'], ['CO', 'Colombia'], ['VE', 'Venezuela'], ['USDT', 'USDT (dólar Binance)']] } };
const GLOBE = '<svg class="flag" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="var(--box)" stroke="var(--box-line)"/><path d="M1 12h22M12 1c3 3.2 4.5 7 4.5 11S15 19.8 12 23c-3-3.2-4.5-7-4.5-11S9 4.2 12 1z" fill="none" stroke="var(--accent)" stroke-width="1.4"/></svg>';
const rateOf = (id) => data?.routes.find((r) => r.id === id);
const statusOf = (id) => rateOf(id)?.status ?? (rateOf(id)?.active ? 'on' : 'off');
// Se muestran las rutas activas y las de mercado inestable (estas sin tasa: se pide por WhatsApp).
const ALL = [...ROUTES, USDT_ROUTE];
// Marca de Binance junto a "dólar Binance" (la gente conoce el USDT así). JM Cambios es comerciante independiente.
const BNB = '<svg class="bnb" viewBox="0 0 126 126" aria-hidden="true"><g fill="#F0B90B"><path d="M63 46 80 63 63 80 46 63z"/>'
  + '<path d="M28 54 37 63 28 72 19 63zM98 54 107 63 98 72 89 63z"/><path d="M63 9 96 42 84 54 63 33 42 54 30 42z"/><path d="M63 117 30 84 42 72 63 93 84 72 96 84z"/></g></svg>';
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
  $('to-q').hidden = $('dests').hidden;
  if ($('dests').hidden) return;
  const list = activeRoutes(origin);
  $('dests').innerHTML = list.map((r) => `<button data-r="${r.id}" aria-pressed="${r.id === route}">${flags(r.to)}<span>${esc(r.name)}<small>${r.cur === 'USDT' ? BNB : ''}${esc(r.unit)} (${r.cur})${statusOf(r.id) === 'ask' ? '<br>Mercado inestable' : ''}</small></span></button>`).join('')
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

// Franja de indicadores que va pasando: los del destino elegido y los del país de origen (solo informativos).
let ind = null, lastTicker = '';
const TICK = {
  VE: () => [['Dólar BCV', data?.bcv?.value, 'Bs', bcvFmt], ['Euro BCV', data?.bcv_eur?.value, 'Bs', bcvFmt],
    ['USDT promedio', ind?.ve?.usdt?.value, 'Bs', (v) => fmt(v, 2)]],
  CO: () => [['TRM', ind?.co?.trm?.value, 'COP', (v) => fmt(v, 2)], ['Euro', ind?.co?.eur?.value, 'COP', (v) => fmt(v, 2)],
    ['Bitcoin', ind?.co?.btc?.value, 'COP', (v) => fmt(v, 0)]],
  BR: () => [['Dólar', ind?.br?.usd?.value, 'BRL', (v) => fmt(v, 4)], ['Euro', ind?.br?.eur?.value, 'BRL', (v) => fmt(v, 4)]],
};
function ticker() {
  const r = ALL.find((x) => x.id === route);
  const countries = [...new Set([...(SOON[origin] ? [] : r?.to || []), origin])].filter((c) => TICK[c]);
  const items = countries.flatMap((c) => TICK[c]().filter(([, v]) => v > 0)
    .map(([name, v, unit, f]) => `<span class="tick">${flag(c)}${esc(name)} <b>${f(v)} ${unit}</b></span>`));
  $('ticker').hidden = !items.length;
  const html = items.join('');
  if (!items.length || html === lastTicker) return;  // sin cambios: no se reinicia el movimiento
  lastTicker = html;
  $('ticker-track').style.setProperty('--dur', `${Math.max(14, items.length * 5)}s`);
  $('ticker-track').innerHTML = `<div class="ticker-group">${html}</div><div class="ticker-group" aria-hidden="true">${html}</div>`;
}

async function loadIndicators() {
  try {
    const res = await fetch('/api/indicadores', { cache: 'no-store' });
    if (res.ok) ind = await res.json();
  } catch { /* sin indicadores: la franja muestra solo lo que haya */ }
  ticker();
}

// Seguimiento (solo conteos, sin datos de la persona): una visita y una cotización por ruta en cada sesión, y cada clic en WhatsApp.
function track(e, r) {
  const k = `jmc_${e}_${r || ''}`;
  try { if (e !== 'whatsapp') { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, '1'); } } catch { /* sin almacenamiento: se cuenta igual */ }
  fetch('/api/evento', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ e, r }), keepalive: true }).catch(() => {});
}
const currentRoute = () => (SOON[origin] ? null : origin === OTHER || route === OTHER ? 'otro' : route);
let cotizaTimer = null;
function maybeCotiza() {  // cuenta cuando el cliente deja escrito un monto (no cada tecla)
  clearTimeout(cotizaTimer);
  const id = currentRoute();
  if (id && ['amount', 'u-top', 'u-bot', 'o-amount'].some((x) => $(x).value.trim())) cotizaTimer = setTimeout(() => track('cotiza', id), 1500);
}
$('wa').addEventListener('click', (ev) => { if (ev.target.closest('a')) track('whatsapp', currentRoute()); });

function calc() {
  ticker();
  maybeCotiza();
  $('h-cot').textContent = 'Cotiza tu envío';
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
  const isUsdt = r?.cur === 'USDT';
  $('usdt-ui').hidden = !isUsdt;
  $('std').hidden = isUsdt;
  if (isUsdt) $('h-cot').textContent = 'USDT · dólar Binance';
  if (isUsdt) { usdtQuote(r); return; }
  if (!r) { $('r-get').hidden = true; $('r-free').hidden = true; $('r-break').hidden = true; $('r-min').textContent = ''; $('r-big').textContent = '—'; $('r-send').textContent = ''; $('r-rate').textContent = ''; $('r-bcv').hidden = true; $('wa').innerHTML = waButtons(''); return; }
  // Opciones con la moneda, para que quede claro qué se escribe: "Pesos que envío" · "Bolívares que llegan".
  const [give, take] = curNames(r);
  $('modes').querySelector('[data-mode="send"] b').textContent = `${cap(give)} que envío`;
  $('modes').querySelector('[data-mode="get"] b').textContent = `${cap(take)} que llegan`;
  const bcv = data.bcv?.value, eur = data.bcv_eur?.value;
  // "Equivalente en dólares / euros BCV" (llegan bolívares): solo hacia Venezuela y con el valor BCV disponible.
  const bcvOk = r.to.includes('VE') && bcv > 0, eurOk = r.to.includes('VE') && eur > 0;
  $('mode-bcv').hidden = !bcvOk;
  $('mode-eur').hidden = !eurOk;
  if ((mode === 'bcv' && !bcvOk) || (mode === 'eur' && !eurOk)) setMode('send');
  if (statusOf(r.id) === 'ask') { unstable(r, o); return; }
  $('r-big').classList.remove('ask');
  const rate = rateOf(r.id).rate;
  amountLabels(r, o);
  if (!$('amount').value.trim()) { rateOnly(r, o, rate); return; }
  const x = amountNum($('amount').value);
  const ref = mode === 'bcv' ? bcv : mode === 'eur' ? eur : null;  // bolívares por dólar o por euro BCV
  const usd = ref ? x : null;
  const refName = mode === 'eur' ? 'EUR al euro BCV' : 'USD al dólar BCV';
  // Montos completos, sin decimales: desde ,50 se redondea hacia arriba; por debajo, hacia abajo.
  const target = ref ? Math.round(x * ref) : x;  // bolívares que deben llegar
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
    $('g-sub').textContent = ref ? `Equivalen a ${fmt2(usd)} ${refName}` : ves ? 'Bolívares (VES)' : r.unit;
  }
  $('r-rate').textContent = '';
  $('r-min').textContent = r.min ? `Envío mínimo: ${fmt(r.min, 0)} ${o.cur}` : '';
  // Debajo del resultado: cuánto equivalen los bolívares en dólares y en euros BCV.
  const day = (v) => (v?.date ? `(${v.date.split('-').reverse().join('/')})` : '');
  $('r-bcv').hidden = !(bcvOk || eurOk);
  $('b-usd-rows').hidden = !bcvOk;
  $('b-eur-rows').hidden = !eurOk;
  if (bcvOk) {
    $('b-rate').textContent = `${bcvFmt(bcv)} Bs/USD`;
    $('b-usd').textContent = `${fmt(get / bcv, 2)} USD`;
    $('b-date').textContent = day(data.bcv);
  }
  if (eurOk) {
    $('e-rate').textContent = `${bcvFmt(eur)} Bs/EUR`;
    $('e-eur').textContent = `${fmt(get / eur, 2)} EUR`;
    $('e-date').textContent = day(data.bcv_eur);
  }
  $('dest-note').textContent = r.note || '';
  const ok = Number.isFinite(send) && Number.isFinite(get) && send > 0;
  const text = !ok ? '' : ref
    ? `Hola, necesito que lleguen ${fmt(get, 0)} Bs a ${r.name} (equivalentes a ${fmt2(usd)} ${refName}), enviando desde ${o.name}. Según el cotizador debo pagar ${fmt(send, 0)} ${o.cur} (tasa ${rate}, sin comisión). ¿Me confirmas?`
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
    : mode === 'send' ? `enviar ${fmt(x, 0)} ${o.cur}` : mode === 'bcv' ? `que lleguen bolívares equivalentes a ${fmt2(x)} USD al dólar BCV` : mode === 'eur' ? `que lleguen bolívares equivalentes a ${fmt2(x)} EUR al euro BCV` : `que reciban ${fmt(x, r.dec)} ${r.cur}`;
  $('wa').innerHTML = waButtons(`Hola, quiero ${amount} desde ${o.name} a ${dot(r.name)} ¿Me das la tasa de este momento?`, 'Pedir tasa');
}

// Nombre de las monedas en palabras. Chile → Colombia: las dos serían "pesos", así que se dice cuál es cuál.
function curNames(r) {
  let [give, take] = [CUR_NAME[ORIGINS[r.from]?.cur] || 'monto', CUR_NAME[r.cur] || r.cur];
  if (give === take && LONG_NAME[ORIGINS[r.from]?.cur]) [give, take] = [LONG_NAME[ORIGINS[r.from].cur], LONG_NAME[r.cur]];
  return [give, take];
}
const cap = (t) => t.charAt(0).toUpperCase() + t.slice(1);

function amountLabels(r, o) {
  placeholder(r, o);
  const [give, take] = curNames(r);
  $('amount-label').textContent = { send: `Escribe los ${give} que envías`, get: `Escribe los ${take} que deben llegar`,
    bcv: 'Escribe los dólares BCV (te decimos los bolívares)', eur: 'Escribe los euros BCV (te decimos los bolívares)' }[mode];
  $('amount-cur').textContent = mode === 'send' ? o.cur : mode === 'bcv' ? 'USD BCV' : mode === 'eur' ? 'EUR BCV' : r.cur;
}

function setMode(m) {
  mode = m;
  document.querySelectorAll('#modes button').forEach((o) => o.setAttribute('aria-pressed', String(o.dataset.mode === m)));
  $('amount').value = '';  // cambia la moneda de la casilla: el cliente escribe su monto
}

// USDT: Comprar o Vender, con dos casillas enlazadas (se escribe en cualquiera y la otra se calcula).
// Comprar: pagas CLP, recibes USDT (precio de venta). Vender: entregas USDT, recibes CLP (precio de compra).
let side = 'buy', edited = 'top';
const usdtFmt = (v) => fmt(v, 2), clpFmt = (v) => fmt(v, 0);
function usdtQuote(r) {
  const buy = side === 'buy';
  const price = Number(buy ? rateOf(r.id)?.rate : rateOf(r.id)?.buyRate);
  const ok = statusOf(r.id) === 'on' && price > 0;
  // Casilla de arriba: lo que entrega el cliente; abajo: lo que recibe.
  $('u-top-l').textContent = buy ? 'Pagas' : 'Entregas';
  $('u-top-c').textContent = buy ? 'CLP' : 'USDT';
  $('u-bot-l').textContent = 'Recibes';
  $('u-bot-c').textContent = buy ? 'USDT' : 'CLP';
  $('u-top').placeholder = buy ? 'Ej. 100.000' : 'Ej. 100';
  $('u-bot').placeholder = buy ? 'Ej. 100' : 'Ej. 100.000';
  $('dest-note').textContent = buy ? r.note : 'Envías los USDT a la wallet o cuenta de Binance que te indiquemos (la red se confirma por WhatsApp). JM Cambios es un comerciante independiente, no es Binance.';
  if (!ok) {
    $('u-line').innerHTML = '<b>Mercado inestable</b><span>El precio se confirma por WhatsApp.</span>';
    $('wa').innerHTML = waButtons(`Hola, quiero ${buy ? 'comprar' : 'vender'} USDT. ¿Me das el precio de este momento?`, 'Pedir precio');
    return;
  }
  $('u-line').innerHTML = `<b class="num">1 USDT = ${fmt(price, 2)} CLP</b><span>Comisión 0 % · Sin cargos extras · Mínimo ${clpFmt(buy ? r.min : r.buyMin)} CLP</span>`;
  const src = $(edited === 'top' ? 'u-top' : 'u-bot'), dst = $(edited === 'top' ? 'u-bot' : 'u-top');
  if (!src.value.trim()) { dst.value = ''; $('wa').innerHTML = waButtons(`Hola, quiero ${buy ? 'comprar' : 'vender'} USDT.`); return; }
  // Lo que escribe el cliente está en USDT o en CLP según la casilla y el lado.
  const srcIsUsdt = (edited === 'top') !== buy;
  const x = (srcIsUsdt ? usdtNum : amountNum)(src.value);
  let usdt, clp;
  if (srcIsUsdt) {
    usdt = x;
    // Comprar: cobra redondeado al peso. Vender: paga hacia abajo (sin pagar de más).
    clp = buy ? Math.round(usdt * price) : Math.floor(Math.round(usdt * price * 100) / 100);
  } else {
    clp = x;
    // Comprar: USDT a entregar, hacia abajo. Vender: USDT que debe entregar para recibir ese monto, hacia arriba.
    usdt = buy ? Math.floor((clp / price) * 100) / 100 : Math.ceil(Math.round((clp / price) * 1e6) / 1e4) / 100;
  }
  const good = Number.isFinite(usdt) && Number.isFinite(clp) && usdt > 0 && clp > 0;
  dst.value = good ? (srcIsUsdt ? clpFmt(clp) : usdtFmt(usdt)) : '';
  const min = buy ? r.min : r.buyMin;
  if (good && clp < min) {
    dst.value = '';  // bajo el mínimo no se cotiza
    $('u-line').innerHTML = `<b>Mínimo ${clpFmt(min)} CLP</b><span>${buy ? 'Compra' : 'Venta'} desde ${clpFmt(min)} CLP${buy ? '' : ` (unos ${usdtFmt(Math.ceil((min / price) * 100) / 100)} USDT)`}.</span>`;
    $('wa').innerHTML = waButtons(`Hola, quiero ${buy ? 'comprar' : 'vender'} USDT.`);
    return;
  }
  $('wa').innerHTML = waButtons(!good ? `Hola, quiero ${buy ? 'comprar' : 'vender'} USDT.` : buy
    ? `Hola, quiero comprar ${usdtFmt(usdt)} USDT pagando ${clpFmt(clp)} CLP (precio ${fmt(price, 2)} CLP por USDT, sin comisión). ¿Me confirmas?`
    : `Hola, quiero vender ${usdtFmt(usdt)} USDT y recibir ${clpFmt(clp)} CLP (precio ${fmt(price, 2)} CLP por USDT, sin comisión). ¿Me confirmas?`);
}
document.querySelectorAll('#u-tabs button').forEach((b) => b.onclick = () => {
  side = b.dataset.side; edited = 'top';
  document.querySelectorAll('#u-tabs button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  $('u-top').value = ''; $('u-bot').value = '';
  calc();
});
$('u-top').oninput = () => { edited = 'top'; calc(); };
$('u-bot').oninput = () => { edited = 'bot'; calc(); };

// Casilla vacía al inicio: se muestra la tasa del día y un ejemplo en gris según la moneda.
const EXAMPLES = { CLP: '100.000', COP: '200.000', EUR: '100', VES: '100.000', PEN: '300', USD: '100', USDT: '100', BRL: '500' };
function placeholder(r, o) {
  const cur = mode === 'send' ? o.cur : mode === 'bcv' || mode === 'eur' ? 'BCV' : r.cur;
  $('amount').placeholder = `Ej. ${cur === 'BCV' ? '20' : EXAMPLES[cur] || '100'}`;
}

function rateOnly(r, o, rate) {
  ['r-get', 'r-free', 'r-break', 'r-bcv'].forEach((id) => { $(id).hidden = true; });
  $('r-big').classList.add('ask');
  $('r-label').textContent = `Tasa del día · ${r.name}`;
  $('r-big').textContent = rate;
  $('r-send').textContent = 'Escribe el monto para ver cuánto recibe.';
  $('r-rate').textContent = '';
  $('r-min').textContent = r.min ? `Envío mínimo: ${fmt(r.min, 0)} ${o.cur}` : '';
  $('dest-note').textContent = r.note || '';
  $('wa').innerHTML = waButtons(`Hola, quiero cotizar un envío desde ${o.name} a ${dot(r.name)}`);
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

// Tasas apagadas (todas desde el panel, o ninguna activa): aviso "Actualizando tasas" y solo WhatsApp.
const allOff = () => data.paused || !ALL.some((r) => ['on', 'ask'].includes(statusOf(r.id)));
function render() {
  const off = Boolean(data) && allOff();
  $('paused').hidden = !off;
  ['from-q', 'origins', 'to-q', 'dests', 'other', 'quote', 'soon'].forEach((id) => { if (off) $(id).hidden = true; });
  $('from-q').hidden = off; $('origins').hidden = off;
  if (off) { $('wa').hidden = false; $('dest-note').textContent = ''; $('wa').innerHTML = waButtons('Hola, quiero cotizar un envío. ¿Qué tasas tienen hoy?'); return; }
  renderOrigins(); renderDests(); calc();
}

document.querySelectorAll('#modes button').forEach((b) => b.onclick = () => { setMode(b.dataset.mode); calc(); });
$('amount').oninput = calc;
['o-from', 'o-to', 'o-amount'].forEach((id) => { $(id).oninput = () => { otherQuote(); maybeCotiza(); }; });

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
// Colombia → Chile: la tasa sale en vivo de Vita Wallet (CriptoYa) + la ganancia del panel. Si no se puede leer: "Mercado inestable".
async function loadCoCl() {
  const r = data?.routes.find((x) => x.id === 'co-cl' && x.status === 'on');
  if (!r) return;
  const got = await copPerClp(r.margin_pct);
  if (!got) { r.status = 'ask'; r.rate = ''; r.active = false; return; }
  r.rate = got.rate.toFixed(2);
}
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
    if (!data) { $('error').hidden = false; $('error').textContent = 'No pudimos cargar las tasas. Revisa tu conexión o escríbenos por WhatsApp.'; data = { routes: [], bcv: null, bcv_eur: null }; }
  }
  await Promise.all([loadUsdt(), loadBrl(), loadCoCl()]);
  $('updated').textContent = data.paused ? 'Tasas en actualización' : data.updated
    ? 'Tasas del ' + new Date(data.updated).toLocaleString('es-CL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
    : 'Tasas aún no publicadas';
  if (origin !== OTHER && !SOON[origin] && route !== OTHER && (!route || !activeRoutes(origin).some((r) => r.id === route))) route = activeRoutes(origin)[0]?.id ?? null;
  render();
}
track('visita');
load().then(loadIndicators);
setInterval(() => load().then(loadIndicators), 5 * 60 * 1000);  // si el cliente deja la página abierta, ve la tasa nueva
