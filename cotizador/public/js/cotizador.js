import { ADVISORS, BTC_ROUTES, BR_CO_ROUTE, CO_BR_ROUTE, BR_CL_ROUTE, US_CL_ROUTE, VE_CL_ROUTE, VE_CO_ROUTE, BR_VE_ROUTE, GOLD_ROUTES, ORIGINS, ROUTES, USDT_BR_ROUTE, USDC_BR_ROUTE, USDT_CO_ROUTE, USDT_ROUTE, amountNum, belowMin, convert, fmt, invert, usdtNum, rateNum } from './rutas.js?v=77';
import { setRewardsNav } from './rewards-nav.js?v=77';
import { BRL_BRAKE, GOLD_URL, USDT_BRL_URL, USDT_COP_URL, USDT_URL, brlPerClp, clpPerCop, parseCriptoYa, parseGold, usdtBrlRef, usdtCopRef, usdtCopBid, marketCoins, clpPerVes, copPerBrl, copPerBrlSell, clpPerBrl, clpPerUsd, copPerVes, refFrom, cyFetch, CLP_RANGE, COP_RANGE, BRL_RANGE } from './criptoya.js?v=77';
import { esc, flag, flags } from './ui.js?v=77';

const $ = (id) => document.getElementById(id);
const MAIN_LINE = 'jamer';
const dot = (t) => (t.endsWith('.') ? t : `${t}.`);  // "EE. UU." ya termina en punto  // a quién escribe quien llega sin enlace de asesor

// Asesor: solo cuando viene en el enlace (?a=jamer). El enlace general muestra siempre "Escribir por WhatsApp", sin nombre.
let adv = new URLSearchParams(location.search).get('a');
if (!ADVISORS[adv]) adv = null;
try { localStorage.removeItem('jmc_asesor'); } catch { /* lo recordado por la versión anterior ya no se usa */ }

let data = null, origin = 'CL', route = null, mode = 'send';
// Dos secciones: "Envíos" (remesas) y "USDT, oro y Bitcoin" (comprar o vender). ?k=cripto abre la segunda.
// Enlace privado (?k=privado): muestra el oro y Bitcoin aunque estén en modo privado en el panel. Se recuerda en esta pestaña.
const PRIV = (() => { const q = new URLSearchParams(location.search).get('k') === 'privado';
  try { if (q) sessionStorage.setItem('jmc_priv', '1'); return q || sessionStorage.getItem('jmc_priv') === '1'; } catch { return q; } })();
let kind = ['cripto', 'privado'].includes(new URLSearchParams(location.search).get('k')) ? 'asset' : 'send';
// Enlace directo a una ruta (ej. ?r=cl-pe desde la página de Perú): abre el cotizador en ese país.
{ const want = ROUTES.find((x) => x.id === new URLSearchParams(location.search).get('r')); if (want) { origin = want.from; route = want.id; } }
const OTHER = 'OTHER';  // origen u otro destino fuera de las rutas principales: tasa por WhatsApp
const CUR_NAME = { CLP: 'pesos', COP: 'pesos', EUR: 'euros', VES: 'bolívares', PEN: 'soles', USD: 'dólares', BRL: 'reales' };
const LONG_NAME = { CLP: 'pesos chilenos', COP: 'pesos colombianos' };
// Dólar y euro BCV con 2 decimales (el cálculo usa el valor completo que publica el BCV).
const bcvFmt = (v) => fmt(v, 2);
const fmt2 = (v) => fmt(v, Number.isInteger(v) ? 0 : 2);  // 100 → "100"; 100,5 → "100,50"
// Orígenes que se muestran con su bandera y el aviso "Próximamente", con los destinos que vendrán.
const SOON = { BR: { name: 'Brasil', to: [['PE', 'Perú'], ['CO', 'Colombia'], ['VE', 'Venezuela']] } };
const GLOBE = '<svg class="flag" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="var(--box)" stroke="var(--box-line)"/><path d="M1 12h22M12 1c3 3.2 4.5 7 4.5 11S15 19.8 12 23c-3-3.2-4.5-7-4.5-11S9 4.2 12 1z" fill="none" stroke="var(--accent)" stroke-width="1.4"/></svg>';
const rateOf = (id) => data?.routes.find((r) => r.id === id);
const statusOf = (id) => rateOf(id)?.status ?? (rateOf(id)?.active ? 'on' : 'off');
// Se muestran las rutas activas y las de mercado inestable (estas sin tasa: se pide por WhatsApp).
const ALL = [...ROUTES, VE_CL_ROUTE, VE_CO_ROUTE, BR_VE_ROUTE, BR_CO_ROUTE, CO_BR_ROUTE, BR_CL_ROUTE, US_CL_ROUTE, USDT_ROUTE, USDT_CO_ROUTE, USDT_BR_ROUTE, USDC_BR_ROUTE, ...GOLD_ROUTES, ...BTC_ROUTES];
// Brasil aparece como "Próximamente" hasta que se activa alguna de sus rutas (USDT desde Brasil) en el panel.
const ORIG = { ...ORIGINS, BR: { name: 'Brasil', cur: 'BRL' }, VE: { name: 'Venezuela', cur: 'VES' }, US: { name: 'Estados Unidos', cur: 'USD' } };
// Marca de Binance junto a "dólar Binance" (la gente conoce el USDT así). JM Cambios es comerciante independiente.
const BNB = '<svg class="bnb" viewBox="0 0 126 126" aria-hidden="true"><g fill="#F0B90B"><path d="M63 46 80 63 63 80 46 63z"/>'
  + '<path d="M28 54 37 63 28 72 19 63zM98 54 107 63 98 72 89 63z"/><path d="M63 9 96 42 84 54 63 33 42 54 30 42z"/><path d="M63 117 30 84 42 72 63 93 84 72 96 84z"/></g></svg>';
const isAsset = (r) => ['USDT', 'USDC'].includes(r.cur) || Boolean(r.gold || r.btc);
const activeRoutes = (o, k = kind) => ALL.filter((r) => r.from === o && isAsset(r) === (k === 'asset') && ['on', 'ask'].includes(statusOf(r.id)));
const isSoon = (o) => kind === 'send' && Boolean(SOON[o]) && !(data && activeRoutes(o).length);
// Países desde donde se puede pagar cripto u oro (solo los que tienen algo encendido en el panel).
const assetOrigins = () => ['CL', 'CO', 'BR'].filter((o) => activeRoutes(o, 'asset').length);
// Productos encendidos en el panel (en cualquier país): el nombre de la pestaña y el texto muestran solo esos.
function assetKinds() {
  const all = ['CL', 'CO', 'BR'].flatMap((o) => activeRoutes(o, 'asset'));
  return [['USDT', all.some((r) => r.cur === 'USDT')], ['USDC', all.some((r) => r.cur === 'USDC')], ['oro', all.some((r) => r.gold)], ['Bitcoin', all.some((r) => r.btc)]].filter(([, on]) => on).map(([n]) => n);
}
const listEs = (xs) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} y ${xs.at(-1)}`);
function setKind(k) {
  kind = k;
  document.querySelectorAll('#kind button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.k === k)));
  if (k === 'asset' && !assetOrigins().includes(origin)) origin = assetOrigins()[0] || 'CL';
  if (k === 'send' && !ORIGINS[origin] && !(origin === 'VE' && activeRoutes('VE', 'send').length)) origin = 'CL';
  route = activeRoutes(origin)[0]?.id ?? (k === 'send' ? OTHER : null);
  ['amount', 'u-top', 'u-bot'].forEach((id) => { $(id).value = ''; });
}
document.querySelectorAll('#kind button').forEach((b) => b.onclick = () => { if (b.dataset.k !== kind) { setKind(b.dataset.k); render(); } });

function renderOrigins() {
  const asset = kind === 'asset';
  $('from-q').innerHTML = `<b>1</b> ${asset ? '¿Con qué moneda pagas o recibes?' : '¿Desde dónde envías?'}`;
  $('lead').innerHTML = asset
    ? `Compra o vende ${listEs(assetKinds().map((n) => `<b>${n === 'oro' ? 'oro tokenizado' : n}</b>`))} con ${listEs(assetOrigins().map((o) => ({ CL: 'pesos chilenos', CO: 'pesos colombianos', BR: 'reales' }[o])))}. Lo recibes directo en tu wallet.`
    : 'Envía dinero desde Chile, Colombia, Europa, Reino Unido, México y muchos países más. ¿No encuentras tu país? Elige <b>Otro país</b> y te damos la tasa por WhatsApp.';
  if (asset) {
    $('origins').innerHTML = assetOrigins().map((k) => `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} ${esc(ORIG[k].name)}</button>`).join('');
  } else $('origins').innerHTML = Object.entries(ORIGINS).map(([k, o]) =>
    `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} ${esc(o.name)}</button>`).join('')
    + ['VE', 'US'].filter((k) => activeRoutes(k, 'send').length).map((k) => `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} ${esc(ORIG[k].name)}</button>`).join('')  // solo si está activa en el panel
    + Object.entries(SOON).map(([k, s]) => `<button data-o="${k}" aria-pressed="${k === origin}">${flag(k)} ${esc(s.name)}</button>`).join('')
    + `<button data-o="${OTHER}" aria-pressed="${origin === OTHER}">${GLOBE} Otro país</button>`;
  $('origins').querySelectorAll('button').forEach((b) => b.onclick = () => {
    origin = b.dataset.o; route = origin === OTHER || isSoon(origin) ? null : activeRoutes(origin)[0]?.id ?? (kind === 'asset' ? null : OTHER);
    ['o-to', 'o-amount', ...(origin === OTHER ? ['o-from'] : [])].forEach((id) => { $(id).value = ''; });
    $('amount').value = '';
    render();
  });
}

function renderDests() {
  $('dests').hidden = origin === OTHER || isSoon(origin);
  $('to-q').hidden = $('dests').hidden;
  $('to-q').innerHTML = `<b>2</b> ${kind === 'asset' ? '¿Qué quieres comprar o vender?' : '¿A qué país envías?'}`;
  if ($('dests').hidden) return;
  // Oro: un solo botón "Oro tokenizado"; el token (XAUt o PAXG) se elige después.
  const all = activeRoutes(origin), golds = all.filter((r) => r.gold);
  const goldPick = golds.find((r) => r.id === route) || golds[0];
  const list = all.filter((r) => !r.gold || r === goldPick);
  $('dests').innerHTML = list.map((r) => r.btc
    ? `<button data-r="${r.id}" aria-pressed="${r.id === route}">${flag('BTC')}<span>Bitcoin<small>BTC · red Lightning${statusOf(r.id) === 'ask' ? '<br>Mercado inestable' : ''}</small></span></button>`
    : r.gold
    ? `<button data-r="${r.id}" aria-pressed="${golds.some((g) => g.id === route)}">${flag('XAUT')}<span>Oro tokenizado<small>${golds.length > 1 ? 'XAUt o PAXG' : `${r.sym} · red ${r.net.replace(' (ERC-20)', '')}`} · 1 = 1 onza</small></span></button>` : `<button data-r="${r.id}" aria-pressed="${r.id === route}">${flags(r.to)}<span>${esc(r.name)}<small>${r.cur === 'USDT' && !r.digital ? BNB : ''}${esc(r.unit)} (${esc(r.sym || r.cur)})${statusOf(r.id) === 'ask' ? '<br>Mercado inestable' : ''}</small></span></button>`).join('')
    + (kind === 'asset' ? '' : `<button data-r="${OTHER}" aria-pressed="${route === OTHER}">${GLOBE}<span>Otro destino<small>Tasa por WhatsApp</small></span></button>`);
  $('dests').querySelectorAll('button').forEach((b) => b.onclick = () => {
    if (mode !== 'send' && b.dataset.r !== route) $('amount').value = '';  // la casilla está en la moneda del destino
    route = b.dataset.r; render();
  });
}

// Otro país (origen) u otro destino: sin tasa publicada; el cliente la pide por WhatsApp.
function otherQuote() {
  const fixed = origin !== OTHER;
  if (fixed) $('o-from').value = ORIG[origin].name;
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
  const countries = [...new Set([...(isSoon(origin) ? [] : r?.to || []), origin])].filter((c) => TICK[c]);
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
  calc();  // con la TRM ya leída, la cotización hacia Colombia muestra su equivalente en dólares
}

// Seguimiento (solo conteos, sin datos de la persona): una visita y una cotización por ruta en cada sesión, y cada clic en WhatsApp.
function track(e, r) {
  try { if (localStorage.getItem('jmc_no_contar') === '1') return; } catch { /* sin almacenamiento: se cuenta */ }  // equipo del dueño (se marca en el panel)
  const k = `jmc_${e}_${r || ''}`;
  try { if (e !== 'whatsapp') { if (sessionStorage.getItem(k)) return; sessionStorage.setItem(k, '1'); } } catch { /* sin almacenamiento: se cuenta igual */ }
  fetch('/api/evento', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ e, r }), keepalive: true }).catch(() => {});
}
const currentRoute = () => (isSoon(origin) ? null : origin === OTHER || route === OTHER ? 'otro' : route);
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
  const soon = isSoon(origin);
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
  const o = ORIG[origin];
  const isAsset = ['USDT', 'USDC'].includes(r?.cur) || Boolean(r?.gold || r?.btc);  // USDT, oro tokenizado y Bitcoin: comprar o vender
  $('usdt-ui').hidden = !isAsset;
  $('std').hidden = isAsset;
  if (isAsset) $('h-cot').textContent = r.gold ? `Oro tokenizado · ${r.sym}` : r.btc ? 'Bitcoin (BTC)' : r.digital ? `${r.sym} · dólar digital` : 'USDT · dólar Binance';
  if (isAsset) { usdtQuote(r); return; }
  if (!r) { $('r-get').hidden = true; $('r-free').hidden = true; $('r-break').hidden = true; $('share').hidden = true; $('r-min').textContent = ''; $('r-big').textContent = '—'; $('r-send').textContent = ''; $('r-rate').textContent = ''; $('r-bcv').hidden = true; $('wa').innerHTML = waButtons(''); return; }
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
  // Cuando el cliente parte de lo que debe llegar, lo que paga se redondea HACIA ARRIBA a un número redondo
  // (CLP a la centena, COP al mil, EUR al euro): la familia recibe exactamente lo pedido y nunca se cobra de menos.
  const send = mode === 'send' ? Math.round(x) : roundUpPay(invert(r, rate, target), o.cur);
  // Cargo fijo (Estados Unidos → Chile): no se muestra aparte, va dentro de la tasa de ese monto: tasa × (monto − cargo) ÷ monto.
  const fee = Number(r.fee) || 0;
  const tasa = fee && send > fee ? (rateNum(rate) * (send - fee) / send).toFixed(2) : rate;
  const get = Math.round(mode === 'send' ? (fee ? send * rateNum(tasa) : convert(r, rate, send)) : target);
  if (belowMin(r, send)) { minimum(r, o, send); return; }
  $('r-big').classList.remove('ask');
  $('r-free').hidden = false;
  $('r-free-t').textContent = 'Comisión 0 % · Sin cargos extras';
  $('r-break').hidden = false;
  $('r-break').innerHTML = [
    ['Monto a enviar', `${fmt(send, 0)} ${o.cur}`],
    ['Comisión', `0 ${o.cur}`],
    ['Cargos extras', `0 ${o.cur}`],
    ['Tasa del día', tasa],
    ...(r.pay ? [['Forma de pago', r.pay]] : []),
    ['Cálculo', `${fmt(send, 0)} ${o.cur} ${r.op === 'mul' ? '×' : '÷'} ${tasa} ${mode === 'send' ? '=' : '≈'} ${fmt(get, r.dec)} ${r.cur}`],
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
  // Hacia Colombia (llegan pesos): equivalente en dólares a la TRM del día.
  const trm = ind?.co?.trm?.value, trmOk = r.to.includes('CO') && r.cur === 'COP' && trm > 0;
  $('r-bcv').hidden = !(bcvOk || eurOk || trmOk);
  $('t-usd-rows').hidden = !trmOk;
  if (trmOk) {
    $('t-rate').textContent = `${fmt(trm, 2)} COP/USD`;
    $('t-usd').textContent = `${fmt(get / trm, 2)} USD`;
    $('t-date').textContent = day(ind.co.trm);
  }
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
    : `Hola, quiero enviar ${fmt(send, 0)} ${o.cur} desde ${o.name} a ${dot(r.name)} Según el cotizador recibe ${fmt(get, r.dec)} ${r.cur} (tasa ${tasa}, sin comisión).${r.pay ? ` ${r.pay}.` : ''} ¿Me confirmas?`;
  $('wa').innerHTML = waButtons(text);
  lastQuote = ok ? { from: [r.from], fromLabel: `Envías desde ${o.name}`, fromAmt: `${fmt(send, 0)} ${o.cur}`,
    to: r.to, toLabel: `Recibe en ${r.name}`, toAmt: `${fmt(get, r.dec)} ${r.cur}`, rate: tasa,
    text: shareText(r, o, send, get, mode === 'eur' && eurOk ? ['EUR', eur, 'euro BCV'] : bcvOk ? ['USD', bcv, 'dólar BCV'] : trmOk ? ['USD', trm, 'dólar TRM'] : null) } : null;
  $('share').hidden = !ok;
}

// Monto por debajo del mínimo de la ruta: no se cotiza, se indica el mínimo.
function minimum(r, o, send) {
  $('r-get').hidden = true;
  $('r-free').hidden = true;
  $('r-break').hidden = true;
  $('share').hidden = true;
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
  $('share').hidden = true;
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
  let [give, take] = [CUR_NAME[ORIG[r.from]?.cur] || 'monto', CUR_NAME[r.cur] || r.cur];
  if (give === take && LONG_NAME[ORIG[r.from]?.cur]) [give, take] = [LONG_NAME[ORIG[r.from].cur], LONG_NAME[r.cur]];
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
let uQuote = null;
function usdtQuote(r) {
  uQuote = null; $('u-share').hidden = true;
  const cur = ORIG[r.from].cur;  // pesos chilenos, colombianos o reales
  const sym = r.sym || 'USDT', dec = r.dec ?? 2, k = 10 ** dec;
  const af = (v) => fmt(v, dec);  // cantidad de USDT u oro
  const pf = (v) => fmt(v, v >= 1000 ? 0 : 2);  // precio por unidad
  const sellOk = Boolean(r.buyMin);  // todas las rutas tienen mínimo de compra: se puede comprar y vender
  $('u-tabs').hidden = !sellOk;
  // Oro: el cliente elige qué token recibir (solo los que están activos en su país).
  // Solo se elige token si hay más de uno encendido; con uno solo (ej. XAUt) va directo.
  $('g-tok').hidden = !r.gold || activeRoutes(r.from).filter((x) => x.gold).length < 2;
  if (r.gold) $('g-tok').querySelectorAll('button').forEach((b) => {
    const id = `${r.from.toLowerCase()}-${b.dataset.tok.toLowerCase()}`;
    b.hidden = !activeRoutes(r.from).some((x) => x.id === id);
    b.setAttribute('aria-pressed', String(id === r.id));
  });
  if (!sellOk) side = 'buy';
  const buy = side === 'buy';
  $('u-tabs').querySelector('[data-side="buy"]').textContent = `Comprar ${sym}`;
  $('u-tabs').querySelector('[data-side="sell"]').textContent = `Vender ${sym}`;
  const price = Number(buy ? rateOf(r.id)?.rate : rateOf(r.id)?.buyRate);
  const ok = statusOf(r.id) === 'on' && price > 0;
  // Oro al comprar: comisión de red ya descontada de lo que recibe (si está activada en el panel).
  const fee = buy && r.gold ? Number(rateOf(r.id)?.feeTok) || 0 : 0, feeUsd = fee ? Number(rateOf(r.id)?.feeUsd) : 0;
  // Casilla de arriba: lo que entrega el cliente; abajo: lo que recibe.
  const pesoEx = cur === 'COP' ? '200.000' : cur === 'BRL' ? '500' : '100.000', assetEx = r.gold ? '0,01' : r.btc ? '0,001' : '100';
  $('u-top-l').textContent = buy ? 'Pagas' : 'Entregas';
  $('u-top-c').textContent = buy ? cur : sym;
  $('u-bot-l').textContent = 'Recibes';
  $('u-bot-c').textContent = buy ? sym : cur;
  $('u-top').placeholder = `Ej. ${buy ? pesoEx : assetEx}`;
  $('u-bot').placeholder = `Ej. ${buy ? assetEx : pesoEx}`;
  const issuer = r.cur === 'PAXG' ? 'Paxos' : 'Tether';
  $('dest-note').textContent = r.btc
    ? `${buy ? 'Enviamos BTC por Lightning Network.' : 'Envíanos tus BTC por Lightning Network.'} Si prefieres la red principal (on-chain), la comisión de red la asumes tú. Verifica que tu wallet use la red correcta antes de ${buy ? 'comprar' : 'vender'}. El precio de Bitcoin sube y baja. JM Cambios es un comerciante independiente.`
    : r.gold
    ? `${buy ? `Enviamos ${sym} solo por la red ${r.net}.` : `Envíanos tus ${sym} solo por la red ${r.net}.`} Verifica que tu wallet use esa red antes de ${buy ? 'comprar' : 'vender'}. El precio del oro sube y baja. JM Cambios es un comerciante independiente, no es ${issuer}.`
    : buy ? r.note : r.digital ? `Envías los ${sym} a la wallet que te indiquemos (la red se confirma por WhatsApp). JM Cambios es un comerciante independiente.` : 'Envías los USDT a la wallet o cuenta de Binance que te indiquemos (la red se confirma por WhatsApp). JM Cambios es un comerciante independiente, no es Binance.';
  // Ayuda para crear la wallet según el producto (solo oro y Bitcoin).
  $('w-help').hidden = !(r.gold || r.btc);
  if (r.gold || r.btc) $('w-help-body').innerHTML = (r.btc
    ? '<p><b>Bitcoin por Lightning:</b> descarga <b>Phoenix</b> (Android o iPhone), créala y toca <b>Recibir</b> para generar tu factura Lightning; esa nos la mandas por WhatsApp.</p>'
    : r.cur === 'XAUT'
      ? '<p><b>XAUt por Solana:</b> descarga <b>Phantom</b> (Android o iPhone), créala y copia tu dirección de <b>Solana</b> desde <b>Recibir</b>.</p>'
      : '<p><b>PAXG por Ethereum:</b> descarga <b>MetaMask</b> o <b>Trust Wallet</b>, créala y copia tu dirección de <b>Ethereum</b> desde <b>Recibir</b>.</p>')
    + '<p>Guarda tus 12 o 24 palabras secretas en papel y <b>nunca se las compartas a nadie</b>, ni siquiera a nosotros. ¿Prefieres ayuda? '
    + `<a href="https://wa.me/${(ADVISORS[adv] || ADVISORS[MAIN_LINE]).phone}?text=${encodeURIComponent(`Hola, quiero comprar ${sym} y necesito ayuda para crear mi wallet.`)}" target="_blank" rel="noopener">Escríbenos y te guiamos</a>.</p>`;
  const netTxt = r.btc ? ' Red: Lightning Network (on-chain, asumiendo la comisión de red).' : r.net ? ` Red: ${r.net}.` : '';
  if (!ok) {
    $(edited === 'top' ? 'u-bot' : 'u-top').value = '';  // sin precio no se calcula nada
    $('u-line').innerHTML = '<b>Mercado inestable</b><span>El precio se confirma por WhatsApp.</span>';
    $('wa').innerHTML = waButtons(`Hola, quiero ${buy ? 'comprar' : 'vender'} ${sym}. ¿Me das el precio de este momento?`, 'Pedir precio');
    return;
  }
  $('u-line').innerHTML = `<b class="num">1 ${esc(sym)}${r.gold ? ' (1 onza)' : ''} = ${pf(price)} ${cur}</b>${r.gold || r.btc ? '<span class="valid">Precio válido por 10 minutos · se confirma al momento de pagar</span>' : ''}<span>Comisión 0 %${fee ? ' · ' + `Comisión de red (≈ US$${fmt(feeUsd, feeUsd % 1 ? 2 : 0)}) ya descontada` : ' · Sin cargos extras'} · Mínimo ${clpFmt(buy ? r.min : r.buyMin)} ${cur}</span>`
    + (r.btc ? `<span class="net">⚡&nbsp;${buy ? 'Se envía' : 'Envíalo'} por&nbsp;<b>Lightning Network</b>. On-chain: la comisión de red la asumes tú.</span>`
      : r.net ? `<span class="net">⚠️&nbsp;${buy ? 'Se envía' : 'Envíalo'} solo por la red&nbsp;<b>${esc(r.net)}</b></span>` : '');
  const src = $(edited === 'top' ? 'u-top' : 'u-bot'), dst = $(edited === 'top' ? 'u-bot' : 'u-top');
  if (!src.value.trim()) { dst.value = ''; $('wa').innerHTML = waButtons(`Hola, quiero ${buy ? 'comprar' : 'vender'} ${sym}.`); return; }
  // Lo que escribe el cliente está en USDT/oro o en pesos según la casilla y el lado.
  const srcIsAsset = (edited === 'top') !== buy;
  const x = (srcIsAsset ? usdtNum : amountNum)(src.value);
  let qty, clp;
  if (srcIsAsset) {
    qty = x;
    // Comprar: cobra redondeado al peso. Vender: paga hacia abajo (sin pagar de más).
    clp = buy ? Math.round((qty + fee) * price) : Math.floor(Math.round(qty * price * 100) / 100);
  } else {
    clp = x;
    // Comprar: cantidad a entregar, hacia abajo. Vender: cantidad que debe entregar para recibir ese monto, hacia arriba.
    qty = buy ? Math.floor((clp / price - fee) * k) / k : Math.ceil(Math.round((clp / price) * k * 1e4) / 1e4) / k;
  }
  const good = Number.isFinite(qty) && Number.isFinite(clp) && qty > 0 && clp > 0;
  // Compartir: solo montos, sin mostrar el precio por unidad.
  uQuote = good ? { from: [buy ? r.from : r.to[0]], fromLabel: buy ? 'Pagas' : 'Entregas', fromAmt: buy ? `${clpFmt(clp)} ${cur}` : `${af(qty)} ${sym}`,
    to: [buy ? r.to[0] : r.from], toLabel: 'Recibes', toAmt: buy ? `${af(qty)} ${sym}` : `${clpFmt(clp)} ${cur}`, rate: null, gold: Boolean(r.gold), btc: Boolean(r.btc), digital: Boolean(r.digital),
    text: [`✅ Cotización JM Cambios · ${buy ? 'Compra' : 'Venta'} de ${sym}${r.gold ? ' (oro tokenizado)' : ''}`,
      `Pagas: ${buy ? `${clpFmt(clp)} ${cur}` : `${af(qty)} ${sym}`}`,
      `Recibes: ${buy ? `${af(qty)} ${sym}` : `${clpFmt(clp)} ${cur}`}`,
      ...(fee ? [`Comisión de red (≈ US$${fmt(feeUsd, feeUsd % 1 ? 2 : 0)}) ya descontada`] : []),
      ...(r.btc ? ['Red: Lightning Network (on-chain: comisión de red a cargo del cliente)'] : r.net ? [`Red: ${r.net}`] : []),
      'Comisión 0 %',
      'Cotiza tu operación 👉 https://jmcambios.cl'].join('\n') } : null;
  dst.value = good ? (srcIsAsset ? clpFmt(clp) : af(qty)) : '';
  const min = buy ? r.min : r.buyMin;
  if (good && clp < min) {
    dst.value = ''; uQuote = null; $('u-share').hidden = true;  // bajo el mínimo no se cotiza
    $('u-line').innerHTML = `<b>Mínimo ${clpFmt(min)} ${cur}</b><span>${buy ? 'Compra' : 'Venta'} desde ${clpFmt(min)} ${cur}${buy ? '' : ` (unos ${af(Math.ceil((min / price) * k) / k)} ${esc(sym)})`}.</span>`;
    $('wa').innerHTML = waButtons(`Hola, quiero ${buy ? 'comprar' : 'vender'} ${sym}.`);
    return;
  }
  $('wa').innerHTML = waButtons(!good ? `Hola, quiero ${buy ? 'comprar' : 'vender'} ${sym}.` : buy
    ? `Hola, quiero comprar ${af(qty)} ${sym} pagando ${clpFmt(clp)} ${cur} (precio ${pf(price)} ${cur} por ${sym}, sin comisión${fee ? `, comisión de red de ≈ US$${fmt(feeUsd, feeUsd % 1 ? 2 : 0)} ya descontada` : ''}).${netTxt} ¿Me confirmas?`
    : `Hola, quiero vender ${af(qty)} ${sym} y recibir ${clpFmt(clp)} ${cur} (precio ${pf(price)} ${cur} por ${sym}, sin comisión).${netTxt} ¿Me confirmas?`);
  $('u-share').hidden = !uQuote;
}
document.querySelectorAll('#g-tok button').forEach((b) => b.onclick = () => {
  route = `${origin.toLowerCase()}-${b.dataset.tok.toLowerCase()}`; edited = 'top';
  $('u-top').value = ''; $('u-bot').value = '';
  render();
});
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
  ['r-get', 'r-free', 'r-break', 'r-bcv', 'share'].forEach((id) => { $(id).hidden = true; });
  $('r-big').classList.add('ask');
  $('r-label').textContent = `Tasa del día · ${r.name}`;
  const fee = Number(r.fee) || 0;  // con cargo fijo, la tasa depende del monto: se muestra la de 100
  $('r-big').textContent = fee ? (rateNum(rate) * (100 - fee) / 100).toFixed(2) : rate;
  $('r-send').textContent = fee ? `Tasa para un envío de 100 ${o.cur}; montos mayores tienen mejor tasa. Escribe el monto para ver cuánto recibe.` : 'Escribe el monto para ver cuánto recibe.';
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

const PAY_STEP = { CLP: 100, COP: 1000, EUR: 1 };
function roundUpPay(v, cur) {
  const step = PAY_STEP[cur] || 1;
  return Math.ceil(Math.round(v * 100) / 100 / step) * step;  // quita el ruido de decimales antes de subir
}

// Horario de atención: lunes a domingo, 10:00 a 22:30 (hora de Chile).
function openNow() {
  const parts = new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
  const h = Number(parts.find((p) => p.type === 'hour')?.value), m = Number(parts.find((p) => p.type === 'minute')?.value);
  return h * 60 + m >= 600 && h * 60 + m < 1350;
}

// Texto que acompaña la imagen al compartir: los montos claros, en la moneda de cada uno.
function shareText(r, o, send, get, bcvRef) {
  const recv = r.cur === 'VES' ? `${fmt(get, 0)} Bs` : `${fmt(get, r.dec)} ${r.cur}`;
  return [`✅ Cotización JM Cambios · Envío a ${r.name}`,
    `Pagas: ${fmt(send, 0)} ${o.cur}`,
    `Recibe: ${recv}`,
    ...(bcvRef ? [`Equivale a: ${fmt(get / bcvRef[1], 2)} ${bcvRef[0]} (${bcvRef[2]})`] : []),
    'Comisión 0 %',
    ...(r.pay ? [r.pay] : []),
    'Cotiza tu envío 👉 https://jmcambios.cl'].join('\n');
}

// ------------------------------------------------------------------ compartir la cotización como imagen
let lastQuote = null;
// Bandera del país en un círculo (para la imagen de la cotización).
async function drawFlag(g, code, cx, cy, r, ring = '#fff') {
  const svg = flag(code).replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" ');
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  try {
    const img = await new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = url; });
    g.save(); g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.clip(); g.drawImage(img, cx - r, cy - r, r * 2, r * 2); g.restore();
    g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.lineWidth = 5; g.strokeStyle = ring; g.stroke();
  } catch { /* sin bandera si no se pudo dibujar */ } finally { URL.revokeObjectURL(url); }
}
async function shareQuote(q) {
  if (!q) return;
  // Imagen con la apariencia de jmcambios.cl: fondo claro, ondas suaves, letra Inter y tarjeta morada para lo que recibe.
  await Promise.all(['800 96px Inter', '600 34px Inter', '700 40px Inter', '400 44px Michroma'].map((f) => document.fonts.load(f).catch(() => null)));
  await document.fonts.ready;
  const c = document.createElement('canvas'); c.width = 1080; c.height = 1350;
  const g = c.getContext('2d');
  const F = (w, px) => `${w} ${px}px Inter, "Segoe UI", system-ui, sans-serif`;
  const bg = g.createLinearGradient(0, 0, 0, 1350); bg.addColorStop(0, '#F7F4FB'); bg.addColorStop(.55, '#FFFFFF'); bg.addColorStop(1, '#FFFFFF');
  g.fillStyle = bg; g.fillRect(0, 0, 1080, 1350);
  // Ondas moradas de la marca, suaves, arriba a la derecha (si no cargan, la imagen sale igual).
  try {
    const o = await new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = '/assets/ondas-arriba.jpg'; });
    g.save(); g.globalAlpha = .5; g.globalCompositeOperation = 'multiply'; g.drawImage(o, 380, 0, 700, 460); g.restore();
    const fx = g.createLinearGradient(380, 0, 640, 0); fx.addColorStop(0, '#F7F4FB'); fx.addColorStop(1, 'rgba(247,244,251,0)'); g.fillStyle = fx; g.fillRect(380, 0, 260, 460);
    const fy = g.createLinearGradient(0, 300, 0, 460); fy.addColorStop(0, 'rgba(250,248,253,0)'); fy.addColorStop(1, '#FAF8FD'); g.fillStyle = fy; g.fillRect(380, 300, 700, 160);
  } catch { /* sin ondas */ }
  // Logo JM (el mismo del sitio): hexágono recortando las barras de la marca.
  g.save(); g.translate(80, 78); g.scale(90 / 450, 90 / 450); g.translate(-20, -14);
  g.beginPath(); [[245, 22], [462, 148], [462, 402], [245, 528], [28, 402], [28, 148]].forEach(([x, y]) => g.lineTo(x, y)); g.closePath(); g.clip();
  g.fillStyle = '#4A1259'; [[0, 0, 250, 365], [283, 0, 77, 550], [0, 395, 360, 155], [385, 0, 165, 550]].forEach(([x, y, w, h]) => g.fillRect(x, y, w, h));
  g.restore();
  g.textAlign = 'left'; g.fillStyle = '#16111D'; g.font = '400 44px Michroma, Inter, sans-serif'; g.fillText('JMCAMBIOS', 190, 146);
  const card = (y, h, fill, line) => {
    g.save(); g.shadowColor = 'rgba(22,17,29,.10)'; g.shadowBlur = 40; g.shadowOffsetY = 16;
    g.fillStyle = fill; g.beginPath(); g.roundRect(80, y, 920, h, 36); g.fill(); g.restore();
    if (line) { g.strokeStyle = line; g.lineWidth = 2; g.beginPath(); g.roundRect(81, y + 1, 918, h - 2, 35); g.stroke(); }
  };
  // Una bandera por país (ej. Panamá · Ecuador lleva dos), algo superpuestas; el texto se corre a la derecha.
  const flagRow = async (codes, y, ring) => { for (let i = codes.length - 1; i >= 0; i--) await drawFlag(g, codes[i], 152 + i * 50, y, 30, ring); return 198 + (codes.length - 1) * 50; };
  card(240, 250, '#FFFFFF', '#E6E1EE');
  let tx = await flagRow(q.from, 314, '#FFFFFF');
  g.fillStyle = '#6B6578'; g.font = F(600, 34); g.fillText(q.fromLabel, tx, 326);
  g.fillStyle = '#16111D'; g.font = F(800, 92); g.fillText(q.fromAmt, 120, 446, 840);
  const purple = g.createLinearGradient(80, 520, 1000, 840); purple.addColorStop(0, '#3A0F48'); purple.addColorStop(1, '#5A1D6E');
  card(520, 330, purple);
  tx = await flagRow(q.to, 594, 'rgba(255,255,255,.9)');
  g.fillStyle = 'rgba(255,255,255,.78)'; g.font = F(600, 34); g.fillText(q.toLabel, tx, 606);
  g.fillStyle = '#FFFFFF'; g.font = F(800, 100); g.fillText(q.toAmt, 120, 730, 840);
  g.font = F(700, 28); const chip = q.chip || '✓  Comisión 0 % · Sin cargos extras'; const cw = g.measureText(chip).width + 48;
  g.fillStyle = '#E8F6EF'; g.beginPath(); g.roundRect(120, 768, cw, 52, 26); g.fill();
  g.fillStyle = '#0B6B45'; g.fillText(chip, 144, 804);
  g.fillStyle = '#6B6578'; g.font = F(500, 30);
  if (q.rate) {
    g.fillText(`Tasa ${q.rate}`, 84, 928);
    g.fillText('Tasa referencial: se confirma por WhatsApp antes de enviar.', 84, 972);
  } else {
    g.fillText('Monto referencial: se confirma por WhatsApp antes de operar.', 84, 928);
    g.font = F(500, 24); g.fillText(q.gold ? 'Oro tokenizado: 1 token = 1 onza. JM Cambios es un comerciante independiente, no es Paxos ni Tether.' : q.btc ? 'Red Lightning; on-chain, comisión de red a cargo del cliente. JM Cambios es comerciante independiente.' : q.digital ? 'JM Cambios es un comerciante independiente.' : 'JM Cambios es un comerciante independiente, no es Binance.', 84, 968, 912);
  }
  g.fillStyle = '#4A1259'; g.beginPath(); g.roundRect(80, 1096, 920, 116, 28); g.fill();
  g.fillStyle = '#FFFFFF'; g.textAlign = 'center'; g.font = F(700, 42); g.fillText('Cotiza tú también en jmcambios.cl', 540, 1168);
  g.fillStyle = '#6B6578'; g.font = F(500, 24); g.fillText('JM Services SpA · Atención todos los días, 10:00 a 22:30 h', 540, 1282);
  const blob = await new Promise((ok) => c.toBlob(ok, 'image/png'));
  const file = new File([blob], 'cotizacion-jmcambios.png', { type: 'image/png' });
  // Texto corto y sin números: los montos ya van en la imagen.
  const text = q.text;
  try {
    if (navigator.canShare?.({ files: [file] })) { await navigator.share({ files: [file], text }); return; }
  } catch (e) { if (e?.name === 'AbortError') return; }
  // Sin compartir nativo (computador): se descarga la imagen y se abre WhatsApp con el texto.
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = file.name; a.click();
  window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener');
}
$('share').onclick = () => lastQuote && shareQuote(lastQuote);
$('u-share').onclick = () => uQuote && shareQuote(uQuote);

// Tasas apagadas (todas desde el panel, o ninguna activa): aviso "Actualizando tasas" y solo WhatsApp.
const allOff = () => data.paused || !ALL.some((r) => ['on', 'ask'].includes(statusOf(r.id)));
function render() {
  const off = Boolean(data) && allOff();
  $('paused').hidden = !off;
  if (off) {  // de noche (fuera de 10:00–22:30, hora de Chile): "volvemos mañana"; de día: "actualizando"
    const night = !openNow();
    $('paused').classList.toggle('night', night);
    $('paused-t').textContent = night ? '🌙 Ya cerramos por hoy' : 'Actualizando tasas';
    $('paused-p').textContent = night
      ? 'Volvemos mañana a las 10:00 con las tasas del día. Igual puedes escribirnos por WhatsApp y te respondemos apenas abramos.'
      : 'Estamos actualizando las tasas del día. Vuelve en un rato o escríbenos por WhatsApp.';
  }
  ['from-q', 'origins', 'to-q', 'dests', 'other', 'quote', 'soon'].forEach((id) => { if (off) $(id).hidden = true; });
  $('from-q').hidden = off; $('origins').hidden = off;
  if (off) { $('wa').hidden = false; $('dest-note').textContent = ''; $('wa').innerHTML = waButtons('Hola, quiero cotizar un envío. ¿Qué tasas tienen hoy?'); return; }
  // Tarjetas y preguntas de oro/Bitcoin: solo si quien mira puede cotizarlos (público, o con el enlace privado).
  { const all = ['CL', 'CO'].flatMap((o) => activeRoutes(o, 'asset'));
    const vis = { gold: all.some((r) => r.gold), btc: all.some((r) => r.btc) };
    document.querySelectorAll('[data-only]').forEach((e) => { e.hidden = !e.dataset.only.split(' ').some((k) => vis[k]); }); }
  // La pestaña "USDT, oro y Bitcoin" solo aparece si hay algo encendido en el panel.
  $('kind').hidden = !assetOrigins().length;
  { const k = assetKinds(); const t = listEs(k); $('kind').querySelector('[data-k="asset"]').textContent = t ? t.charAt(0).toUpperCase() + t.slice(1) : 'USDT'; }
  document.querySelectorAll('#kind button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.k === kind)));
  if (kind === 'asset' && !assetOrigins().length) setKind('send');
  renderOrigins(); renderDests(); calc();
  paisBg();
}
// Mapa del mundo al fondo: se ilumina la ruta que el cliente está cotizando (ej. Chile → Venezuela).
let rutaNow = '';
function paisBg() {
  // Título según el país de origen elegido: "Conectamos Colombia con el mundo", "Conectamos Brasil con el mundo"…
  const from = origin === OTHER ? 'tu país' : ORIG[origin]?.name || SOON[origin]?.name || 'Chile';
  const tt = document.getElementById('mm-t');
  if (tt) tt.textContent = `Conectamos ${from} con el mundo`;
  const r = ROUTES.find((x) => x.id === route);
  const id = r ? `${r.from}-${r.to[0]}` : `o-${origin}`;
  if (id === rutaNow) return;
  rutaNow = id;
  document.querySelectorAll('#mapa-bg .on').forEach((e) => e.classList.remove('on'));
  if (!r) { const t = document.getElementById('mm-ruta'); if (t) t.textContent = ''; document.getElementById(`nd-${origin}`)?.classList.add('on'); return; }
  document.getElementById(`ln-${id}`)?.classList.add('on');
  document.getElementById(`nd-${r.from}`)?.classList.add('on');
  document.getElementById(`nd-${r.to[0]}`)?.classList.add('on');
  const pais = { CL: 'Chile', CO: 'Colombia', VE: 'Venezuela', PE: 'Perú', BR: 'Brasil', AR: 'Argentina', US: 'EE. UU.', PA: 'Panamá', MX: 'México', EC: 'Ecuador', EU: 'Europa', GB: 'Reino Unido' };
  const t = document.getElementById('mm-ruta');
  if (t) t.textContent = pais[r.from] && pais[r.to[0]] ? `${pais[r.from]} → ${pais[r.to[0]]}` : '';
}


document.querySelectorAll('#modes button').forEach((b) => b.onclick = () => { setMode(b.dataset.mode); calc(); });
$('amount').oninput = calc;
['o-from', 'o-to', 'o-amount'].forEach((id) => { $(id).oninput = () => { otherQuote(); maybeCotiza(); }; });

// USDT: el precio de Vita (CriptoYa) se lee desde el navegador del cliente y se le suma la ganancia.
async function loadUsdt() {
  if (!data?.usdt) { data.routes = data.routes.filter((x) => x.id !== USDT_ROUTE.id); return; }
  let ref = null;
  try {
    const res = await cyFetch(USDT_URL, { cache: 'no-store' });
    const t = res.ok ? await res.text() : null;
    ref = !t ? null : data.usdt.source ? refFrom(t, CLP_RANGE, data.usdt.source) : parseCriptoYa(t);  // referencia elegida en el panel
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
  if (!r || r.fixed) return;  // tasa fija del panel: se usa tal cual
  const got = await clpPerCop(r.margin_pct);
  if (!got) { r.status = 'ask'; r.rate = ''; r.active = false; return; }
  r.rate = got.rate.toFixed(4);
}
// USDT desde Colombia: precio de Binance P2P Colombia (CriptoYa, leído en el navegador) + la ganancia del panel.
async function loadUsdtCo() {
  data.routes = data.routes.filter((x) => x.id !== USDT_CO_ROUTE.id);
  if (!data?.usdt_co) return;
  USDT_CO_ROUTE.min = Number(data.usdt_co.min) || 50000;
  USDT_CO_ROUTE.buyMin = Number(data.usdt_co.buy_min) || USDT_CO_ROUTE.min;  // también le compramos USDT al cliente
  let ref = null, bid = null;
  try { const res = await cyFetch(USDT_COP_URL, { cache: 'no-store' }); const t = res.ok ? await res.text() : null;
    if (t && data.usdt_co.source) { ref = refFrom(t, COP_RANGE, data.usdt_co.source); bid = ref?.bid ?? null; } else { ref = t && usdtCopRef(t); bid = t && usdtCopBid(t); }
  } catch { ref = null; }
  const price = ref ? ref.value * (1 + Number(data.usdt_co.margin_pct) / 100) : NaN;
  const buy = bid ? bid * (1 - Number(data.usdt_co.buy_margin_pct ?? 3) / 100) : NaN;
  data.routes.push({ id: USDT_CO_ROUTE.id, status: Number.isFinite(price) ? 'on' : 'ask', rate: Number.isFinite(price) ? price.toFixed(2) : '',
    buyRate: Number.isFinite(buy) && buy > 0 ? buy.toFixed(2) : '' });
}
// USDT desde Brasil: precio de Binance P2P (o Bybit P2P) en reales vía CriptoYa ± las ganancias del panel.
async function loadUsdtBr() {
  data.routes = data.routes.filter((x) => x.id !== USDT_BR_ROUTE.id && x.id !== USDC_BR_ROUTE.id);
  if (!data?.usdt_br) return;
  let ref = null;
  try { const res = await cyFetch(USDT_BRL_URL, { cache: 'no-store' }); const t = res.ok ? await res.text() : null; ref = !t ? null : data.usdt_br.source ? refFrom(t, BRL_RANGE, data.usdt_br.source) : usdtBrlRef(t); } catch { ref = null; }
  const price = ref ? ref.value * (1 + Number(data.usdt_br.margin_pct) / 100) : NaN;
  const buy = ref?.bid ? ref.bid * (1 - Number(data.usdt_br.buy_margin_pct) / 100) : NaN;
  // Mínimo: el equivalente a 10 USDT al precio del momento.
  USDT_BR_ROUTE.min = Number.isFinite(price) ? Math.ceil(USDT_BR_ROUTE.minUsdt * price) : 0;
  USDT_BR_ROUTE.buyMin = Number.isFinite(buy) && buy > 0 ? Math.ceil(USDT_BR_ROUTE.minUsdt * buy) : 0;
  const q = { status: Number.isFinite(price) ? 'on' : 'ask', rate: Number.isFinite(price) ? price.toFixed(4) : '', buyRate: Number.isFinite(buy) && buy > 0 ? buy.toFixed(4) : '' };
  data.routes.push({ id: USDT_BR_ROUTE.id, ...q });
  // USDC: mismo precio que el USDT (solo cambia la moneda que se entrega o recibe).
  if (data.usdt_br.usdc) { USDC_BR_ROUTE.min = USDT_BR_ROUTE.min; USDC_BR_ROUTE.buyMin = USDT_BR_ROUTE.buyMin; data.routes.push({ id: USDC_BR_ROUTE.id, ...q }); }
}
// Oro tokenizado (Chile y Colombia): precio de CoinGecko en pesos ± las ganancias del panel.
async function loadGold() {
  const ids = GOLD_ROUTES.map((r) => r.id);
  data.routes = data.routes.filter((x) => !ids.includes(x.id));
  if (!data?.gold || (data.gold.private && !PRIV)) return;  // privado: solo con el enlace
  const toks = data.gold.tokens || ['XAUT', 'PAXG'];  // tokens encendidos en el panel
  const list = GOLD_ROUTES.filter((r) => data.gold[r.from.toLowerCase()] && toks.includes(r.cur));
  if (!list.length) return;
  let g = null;
  g = await marketCoins();
  for (const r of list) {
    const ref = g?.[r.cur]?.[ORIG[r.from].cur];
    const price = ref ? ref * (1 + Number(data.gold.margin_pct) / 100) : NaN;
    const buy = ref ? ref * (1 - Number(data.gold.buy_margin_pct) / 100) : NaN;
    // Comisión de red (dólares) pasada a tokens con el precio del token en dólares: se descuenta de lo que recibe al comprar.
    const feeUsd = Number(data.gold.fee?.[r.cur]) || 0, usd = g?.[r.cur]?.USD;
    data.routes.push({ id: r.id, status: Number.isFinite(price) ? 'on' : 'ask', rate: Number.isFinite(price) ? price.toFixed(2) : '',
      buyRate: Number.isFinite(buy) && buy > 0 ? buy.toFixed(2) : '', feeUsd, feeTok: feeUsd > 0 && usd > 0 ? feeUsd / usd : 0 });
  }
}
// Bitcoin (Chile y Colombia): precio de CoinGecko en pesos ± las ganancias del panel.
async function loadBtc() {
  const ids = BTC_ROUTES.map((r) => r.id);
  data.routes = data.routes.filter((x) => !ids.includes(x.id));
  if (!data?.btc || (data.btc.private && !PRIV)) return;  // privado: solo con el enlace
  const list = BTC_ROUTES.filter((r) => data.btc[r.from.toLowerCase()]);
  if (!list.length) return;
  let g = null;
  g = await marketCoins();
  for (const r of list) {
    const ref = g?.BTC?.[ORIG[r.from].cur];
    const price = ref ? ref * (1 + Number(data.btc.margin_pct) / 100) : NaN;
    const buy = ref ? ref * (1 - Number(data.btc.buy_margin_pct) / 100) : NaN;
    data.routes.push({ id: r.id, status: Number.isFinite(price) ? 'on' : 'ask', rate: Number.isFinite(price) ? price.toFixed(0) : '',
      buyRate: Number.isFinite(buy) && buy > 0 ? buy.toFixed(0) : '' });
  }
}
// Venezuela → Chile: USDT en bolívares del P2P elegido (+ ganancia) y lo que paga Vita por USDT en CLP.
async function loadVeCl() {
  data.routes = data.routes.filter((x) => x.id !== VE_CL_ROUTE.id);
  if (!data?.ve_cl) return;
  VE_CL_ROUTE.min = Number(data.ve_cl.min) || 2000;
  const got = await clpPerVes(data.ve_cl.source, data.ve_cl.margin_pct);
  data.routes.push({ id: VE_CL_ROUTE.id, status: got ? 'on' : 'ask', rate: got ? got.rate.toFixed(4) : '', active: true });
}
// Brasil → Colombia: USDT en reales del exchange elegido (+ ajuste) y lo que paga Binance P2P Colombia por USDT.
async function loadBrCo() {
  data.routes = data.routes.filter((x) => x.id !== BR_CO_ROUTE.id);
  if (!data?.br_co) return;
  BR_CO_ROUTE.min = Number(data.br_co.min) || 50;
  const got = await copPerBrl(data.br_co.source, data.br_co.margin_pct);
  data.routes.push({ id: BR_CO_ROUTE.id, status: got ? 'on' : 'ask', rate: got ? got.rate.toFixed(2) : '', active: true });
}
// Colombia → Brasil: USDT en Binance P2P Colombia (+ ganancia) vendido en Brasil al precio de compra del exchange elegido.
async function loadCoBr() {
  data.routes = data.routes.filter((x) => x.id !== CO_BR_ROUTE.id);
  if (!data?.co_br) return;
  CO_BR_ROUTE.min = Number(data.co_br.min) || 50000;
  const got = await copPerBrlSell(data.co_br.source, data.co_br.profit_pct);
  data.routes.push({ id: CO_BR_ROUTE.id, status: got ? 'on' : 'ask', rate: got ? got.rate.toFixed(2) : '', active: true });
}
// Brasil → Chile: USDT en reales del exchange elegido (+ ganancia) vendido en Chile a lo que paga Vita.
async function loadBrCl() {
  data.routes = data.routes.filter((x) => x.id !== BR_CL_ROUTE.id);
  if (!data?.br_cl) return;
  BR_CL_ROUTE.min = Number(data.br_cl.min) || 50;
  const got = await clpPerBrl(data.br_cl.source, data.br_cl.profit_pct);
  data.routes.push({ id: BR_CL_ROUTE.id, status: got ? 'on' : 'ask', rate: got ? got.rate.toFixed(2) : '', active: true });
}
// Estados Unidos → Chile: dólares (menos el cargo fijo) vendidos a lo que paga Vita por USDT, menos la comisión.
async function loadUsCl() {
  data.routes = data.routes.filter((x) => x.id !== US_CL_ROUTE.id);
  if (!data?.us_cl) return;
  US_CL_ROUTE.min = Number(data.us_cl.min) || 20;
  US_CL_ROUTE.fee = Number(data.us_cl.fee) || 0;
  const got = await clpPerUsd(data.us_cl.profit_pct);
  data.routes.push({ id: US_CL_ROUTE.id, status: got ? 'on' : 'ask', rate: got ? got.rate.toFixed(2) : '', active: true });
}
// Venezuela → Colombia: USDT en bolívares (+ ganancia) vendido en Colombia al precio de venta del exchange elegido.
async function loadVeCo() {
  data.routes = data.routes.filter((x) => x.id !== VE_CO_ROUTE.id);
  if (!data?.ve_co) return;
  VE_CO_ROUTE.min = Number(data.ve_co.min) || 40000;
  const got = await copPerVes(data.ve_co.source, data.ve_co.cop_source, data.ve_co.profit_pct);
  data.routes.push({ id: VE_CO_ROUTE.id, status: got ? 'on' : 'ask', rate: got ? got.rate.toFixed(4) : '', active: true });
}
// Brasil → Venezuela: tasa manual del panel.
function loadBrVe() {
  data.routes = data.routes.filter((x) => x.id !== BR_VE_ROUTE.id);
  if (!data?.br_ve) return;
  BR_VE_ROUTE.min = Number(data.br_ve.min) || 50;
  data.routes.push({ id: BR_VE_ROUTE.id, status: 'on', rate: String(data.br_ve.rate), active: true });
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
  await Promise.all([loadUsdt(), loadUsdtCo(), loadUsdtBr(), loadGold(), loadBtc(), loadVeCl(), loadVeCo(), loadBrVe(), loadBrCo(), loadCoBr(), loadBrCl(), loadUsCl(), loadBrl(), loadCoCl()]);
  // Botón de JM Rewards: solo aparece si se activó en el panel.
  $('jmr').hidden = !data.rewards?.url;
  if (data.rewards?.url) $('jmr').href = data.rewards.url;
  setRewardsNav(data.rewards?.url);  // botón de la barra superior: "Entrar" cuando Rewards está publicado
  $('updated').textContent = data.paused ? 'Tasas en actualización' : data.updated
    ? 'Tasas del ' + new Date(data.updated).toLocaleString('es-CL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
    : 'Tasas aún no publicadas';
  if (kind === 'asset' && assetOrigins().length && !assetOrigins().includes(origin)) origin = assetOrigins()[0];
  if (origin !== OTHER && !isSoon(origin) && route !== OTHER && (!route || !activeRoutes(origin).some((r) => r.id === route))) route = activeRoutes(origin)[0]?.id ?? null;
  render();
}
track('visita');
load().then(loadIndicators);
setInterval(() => load().then(loadIndicators), 5 * 60 * 1000);  // si el cliente deja la página abierta, ve la tasa nueva
