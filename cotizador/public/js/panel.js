import { ADVISORS, FLYERS, ORIGINS, ROUTES, amountNum, convert, fmt, rateNum, usdtNum } from './rutas.js?v=48';
import { esc, flag, flags } from './ui.js?v=48';
import { BRL_BRAKE, GOLD_URL, USDT_BRL_URL, USDT_COP_URL, USDT_URL, brlPerClp, clpPerCop, marketClVe, parseCriptoYa, parseGold, usdtBrlRef, usdtCopRef, marketCoins } from './criptoya.js?v=48';

const $ = (id) => document.getElementById(id);
const SOURCES = { bcv: 'leído del BCV', dolarapi: 'copia del BCV vía DolarApi, fuente no oficial', 'bcv-anterior': 'último valor leído', manual: 'valor manual' };
let saved = null;
const flyerBlobs = {};
const STATUS = [['on', 'Activa'], ['ask', 'Inestable · tasa por WhatsApp'], ['off', 'Apagada']];
const statusOf = (id) => saved.status?.[id] ?? (!String(saved.rates?.[id] ?? '').trim() || saved.active?.[id] === false ? 'off' : 'on');

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { 'content-type': 'application/json' }, credentials: 'same-origin', cache: 'no-store' });
  let body = {};
  try { body = await res.json(); } catch { /* respuesta vacía */ }
  return { status: res.status, body };
}

function showEditor(on) {
  $('login').hidden = on;
  ['power', 'mkt', 'editor', 'usdt', 'usdtco', 'usdtbr', 'oro', 'btcsec', 'rewards', 'flyers', 'stats', 'links', 'logout'].forEach((id) => { $(id).hidden = !on; });
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
  loadUsdtCo();
  loadUsdtBr();
  loadGoldCfg();
  loadBtcCfg();
  loadRewards();
  loadStats();
  renderSelf();
  checkMarket();
}

// ------------------------------------------------------------------ visitas del cotizador

const routeName = (id) => {
  if (id === 'otro') return 'Otro país';
  if (id === 'cl-usdt') return 'Chile → USDT';
  const r = ROUTES.find((x) => x.id === id);
  return r ? `${ORIGINS[r.from].name} → ${r.name}` : id;
};
const pct = (a, b) => (b ? `${Math.round((a / b) * 100)} %` : '—');
async function loadStats() {
  const { status, body } = await api('/api/estadisticas');
  if (status !== 200) { $('stats-body').textContent = 'No se pudieron leer las visitas.'; return; }
  const d = body.days, sum = (k, n) => d.slice(0, n).reduce((t, x) => t + (x[k] || 0), 0);
  const cols = [['Hoy', 1, 0], ['Ayer', 1, 1], ['7 días', 7, 0]];
  const val = (k, [, n, from]) => (from ? d[1][k] : sum(k, n));
  const rows = [['👀 Visitas', 'visita'], ['🧮 Cotizaron', 'cotiza'], ['💬 Clic en WhatsApp', 'whatsapp']];
  const rutas = {};
  for (const x of d) for (const [id, v] of Object.entries(x.rutas || {})) {
    rutas[id] = rutas[id] || { cotiza: 0, whatsapp: 0 };
    rutas[id].cotiza += v.cotiza || 0; rutas[id].whatsapp += v.whatsapp || 0;
  }
  const top = Object.entries(rutas).sort((a, b) => b[1].cotiza - a[1].cotiza);
  const max = Math.max(1, ...d.map((x) => x.visita || 0));
  $('stats-body').innerHTML = `
    <table class="stats"><thead><tr><th></th>${cols.map(([n]) => `<th>${n}</th>`).join('')}</tr></thead><tbody>
      ${rows.map(([n, k]) => `<tr><td>${n}</td>${cols.map((c) => `<td>${fmt(val(k, c), 0)}</td>`).join('')}</tr>`).join('')}
      <tr class="sub"><td>De cada 100 visitas, escriben</td>${cols.map((c) => `<td>${pct(val('whatsapp', c), val('visita', c))}</td>`).join('')}</tr>
    </tbody></table>
    <h3>Últimos 7 días</h3>
    <div class="days">${d.slice().reverse().map((x) => `<div class="day"><span>${x.day.slice(8)}/${x.day.slice(5, 7)}</span>
      <i style="width:${Math.round(((x.visita || 0) / max) * 100)}%"></i><b>${fmt(x.visita || 0, 0)}</b></div>`).join('')}</div>
    <h3>Rutas más cotizadas (7 días)</h3>
    ${top.length ? `<table class="stats"><thead><tr><th>Ruta</th><th>Cotizaron</th><th>WhatsApp</th></tr></thead><tbody>
      ${top.map(([id, v]) => `<tr><td>${esc(routeName(id))}</td><td>${fmt(v.cotiza, 0)}</td><td>${fmt(v.whatsapp, 0)}</td></tr>`).join('')}
    </tbody></table>` : '<span class="muted">Todavía no hay cotizaciones.</span>'}`;
}
$('stats-reload').onclick = loadStats;

// Tus propias visitas: con sesión del panel ya no se cuentan; además este equipo se puede marcar para siempre.
function renderSelf() {
  const off = lsGet('jmc_no_contar', '0') === '1';
  $('self-txt').textContent = off ? '✅ Este equipo no se cuenta en las visitas.' : 'Con la sesión del panel abierta tus visitas no se cuentan. Para no contarlas nunca desde este equipo:';
  $('self-btn').textContent = off ? 'Volver a contar este equipo' : 'No contar mis visitas en este equipo';
}
$('self-btn').onclick = () => { lsSet('jmc_no_contar', lsGet('jmc_no_contar', '0') === '1' ? '0' : '1'); renderSelf(); };

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
        <div><h3>${esc(o.name)} → ${esc(r.name)}</h3><span class="op"><b class="formula">${o.cur} ${r.op === 'mul' ? '×' : '÷'} tasa = ${r.cur}</b> · ${r.auto ? 'aquí va tu ganancia en % (calcula la sugerida con Vita Wallet) · la tasa fija va abajo' : esc(r.unit)}</span></div>
        <input type="text" id="in-${r.id}" value="${esc(r.auto ? (saved.cocl?.margin_pct ?? '3') : (saved.rates[r.id] || ''))}" inputmode="decimal" aria-label="${r.auto ? 'Ganancia %' : 'Tasa'} ${esc(o.name)} a ${esc(r.name)}">
        <span class="ex"><span id="ex-${r.id}"></span><select id="st-${r.id}" aria-label="Estado ${esc(o.name)} a ${esc(r.name)}">${STATUS.map(([v, t]) => `<option value="${v}"${v === st ? ' selected' : ''}>${t}</option>`).join('')}</select></span>
      </div>${r.id === 'cl-br' ? provBox() : ''}${r.id === 'cl-ve' ? sugBox() : ''}${r.auto ? fixBox() : ''}`;
    }).join('')).join('');
  for (const r of ROUTES) {
    if (r.auto) {  // Colombia → Chile: muestra la tasa de ahora con la ganancia escrita
      let seq = 0;
      const live = async () => {
        const n = ++seq, m = $('in-' + r.id).value.trim().replace(',', '.');
        $('in-' + r.id).classList.remove('bad');
        if (!(m !== '' && Number(m) >= 0 && Number(m) <= 50)) { $('ex-' + r.id).textContent = 'la ganancia va entre 0 y 50 %'; return; }
        $('ex-' + r.id).textContent = 'leyendo Vita Wallet…';
        const got = await clpPerCop(m);
        if (n !== seq) return;
        coclSug = got ? Number(got.rate.toFixed(4)) : null;
        $('ex-' + r.id).textContent = got
          ? `Sugerida: ${got.rate.toFixed(4)} (Vita: ${fmt(got.cop, 2)} COP y ${fmt(got.clp, 2)} CLP por USDT + tu ganancia)`
          : 'no se pudo leer Vita Wallet ahora';
        $('fx-use').hidden = !got;
        fixShow();
      };
      $('in-' + r.id).oninput = live;
      $('fx-co-cl').oninput = fixShow;
      $('fx-use').onclick = () => { if (coclSug) { $('fx-co-cl').value = coclSug.toFixed(4); fixShow(); } };
      live();
      $('st-' + r.id).onchange = (e) => $('row-' + r.id).classList.toggle('off', e.target.value !== 'on');
      continue;
    }
    const upd = () => {
      const amt = ORIGINS[r.from].cur === 'EUR' ? 100 : 100000;  // ejemplo con un monto típico de cada moneda
      const v = convert(r, $('in-' + r.id).value, amt);
      $('ex-' + r.id).textContent = Number.isFinite(v) ? `${fmt(amt, 0)} ${ORIGINS[r.from].cur} ${r.op === 'mul' ? '×' : '÷'} ${$('in-' + r.id).value.trim()} = ${fmt(v, r.dec)} ${r.cur}` : 'escribe una tasa válida';
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
  sugWire();
}

// Brasil: la tasa sale de lo que da el proveedor por 100.000 CLP más tu ganancia (el cliente solo ve la tasa final).
// ------------------------------------------------------------------ tasa sugerida Chile → Venezuela

const lsGet = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };
function sugBox() {
  return `<details class="sug" id="sug-cl-ve"${lsGet('jmc_sug_open', '1') === '1' ? ' open' : ''}>
    <summary>Ver tasa sugerida (mercado)</summary>
    <div class="row2">
      <label class="f" for="sug-m">Tu ganancia (%)<span class="amount"><input id="sug-m" inputmode="decimal" value="${esc(lsGet('jmc_sug_cl-ve', '8'))}"></span></label>
      <div class="sug-out"><span class="muted">Sugerida</span><b id="sug-rate">—</b></div>
    </div>
    <span class="muted" id="sug-detail">Leyendo el mercado…</span>
    <span class="muted" id="sug-mine"></span>
    <button class="btn ghost" id="sug-use" disabled>Usar la sugerida</button>
  </details>`;
}
let market = null;
function sugCalc() {
  const m = Number(String($('sug-m').value).replace(',', '.'));
  const mine = rateNum($('in-cl-ve').value);
  if (!market) { $('sug-rate').textContent = '—'; $('sug-use').disabled = true; $('sug-mine').textContent = ''; return; }
  const sug = Number.isFinite(m) && m >= 0 && m < 50 ? market.cross * (1 - m / 100) : NaN;
  $('sug-rate').textContent = Number.isFinite(sug) ? sug.toFixed(4) : '—';
  $('sug-use').disabled = !Number.isFinite(sug);
  $('sug-use').dataset.v = Number.isFinite(sug) ? sug.toFixed(4) : '';
  // Cuánto deja la tasa que tienes escrita, frente al mismo mercado.
  $('sug-mine').textContent = mine ? `Tu tasa ${$('in-cl-ve').value} deja ≈ ${fmt((1 - mine / market.cross) * 100, 1)} % frente al mercado.` : '';
}
async function sugLoad() {
  if (!$('sug-cl-ve')) return;
  $('sug-detail').textContent = 'Leyendo el mercado…';
  market = await marketClVe();
  sugShow();
}
function sugShow() {
  if (!$('sug-cl-ve')) return;
  $('sug-detail').textContent = market
    ? `Base 30.000 CLP: compras USDT en Chile a ${fmt(market.clp.value, 2)} CLP (${market.clp.source === 'binancep2p' ? 'Binance P2P' : 'Vita Wallet'}) y los vendes en Venezuela a ${fmt(market.ves.value, 2)} Bs (Binance P2P, ~30 USDT, sin filtro de Pago Móvil: por eso se usa 8 % = tu 7 % + ~1 % de Pago Móvil). Sin ganancia: ${market.cross.toFixed(4)}.`
    : 'No se pudo leer el mercado ahora (CriptoYa). Usa tu tasa de siempre.';
  sugCalc();
}
function sugWire() {
  if (!$('sug-cl-ve')) return;
  $('sug-cl-ve').ontoggle = () => { lsSet('jmc_sug_open', $('sug-cl-ve').open ? '1' : '0'); if ($('sug-cl-ve').open && !market) sugLoad(); };
  $('sug-m').oninput = () => { lsSet('jmc_sug_cl-ve', $('sug-m').value); sugCalc(); };
  $('in-cl-ve').addEventListener('input', sugCalc);
  $('sug-use').onclick = () => { $('in-cl-ve').value = $('sug-use').dataset.v; $('in-cl-ve').dispatchEvent(new Event('input')); };
  if ($('sug-cl-ve').open) sugLoad();
}

// ------------------------------------------------------------------ Colombia → Chile: tasa fija

// La tasa fija es la que ven los clientes y el flyer (no se mueve sola). La ganancia de arriba solo calcula la sugerida.
let coclSug = null;
function fixBox() {
  return `<div class="sug fix"><b>Tasa fija Colombia → Chile (la que ven los clientes y el flyer) · COP × tasa = CLP, con cero adelante</b>
    <div class="row2">
      <label class="f" for="fx-co-cl">Tu tasa fija
        <span class="amount"><input id="fx-co-cl" inputmode="decimal" autocomplete="off" value="${esc(saved.cocl?.fixed || '')}" placeholder="Ej. 0.2850"></span></label>
      <div class="sug-out"><button type="button" class="btn ghost" id="fx-use" hidden>Usar la sugerida</button></div>
    </div>
    <span class="muted" id="fx-ex"></span>
  </div>`;
}
function fixShow() {
  const v = rateNum($('fx-co-cl').value);
  $('fx-co-cl').classList.remove('bad');
  $('fx-ex').textContent = !$('fx-co-cl').value.trim()
    ? 'Vacía: el cotizador usa la tasa automática, que cambia todo el día. Escribe una tasa para dejarla fija.'
    : v >= 1 ? 'va con cero adelante, como la publican todas las casas de cambio (ej. 0.2850)'
    : v ? `100.000 COP × ${$('fx-co-cl').value.trim()} = ${fmt(100000 * v, 0)} CLP${coclSug ? ` · está a ${fmt(Math.abs((v / coclSug - 1) * 100), 1)} % de la sugerida` : ''}. Se publica al guardar.`
      : 'escribe una tasa válida (ej. 0.2850)';
}

// ------------------------------------------------------------------ aviso del mercado (Chile → Venezuela)

const sugPct = () => Number(String(lsGet('jmc_sug_cl-ve', '8')).replace(',', '.'));
async function checkMarket() {
  if (!saved) return;
  $('mkt-th').value = lsGet('jmc_mkt_th', '2');
  const th = Number(String($('mkt-th').value).replace(',', '.')) || 2;
  checkCoCl(th);
  market = await marketClVe();
  sugShow();
  const mine = statusOf('cl-ve') === 'on' ? rateNum(saved.rates['cl-ve']) : null;
  const box = $('mkt-msg');
  document.title = document.title.replace(/^⚠️ /, '');
  if (!market) { box.className = 'msg'; box.textContent = 'No se pudo leer el mercado ahora (CriptoYa). Se vuelve a intentar en 5 minutos.'; return; }
  const sug = market.cross * (1 - sugPct() / 100);
  if (!mine) { box.className = 'msg'; box.textContent = `Chile → Venezuela no está activa. Sugerida ahora: ${sug.toFixed(4)}.`; return; }
  const diff = (mine / sug - 1) * 100, real = (1 - mine / market.cross) * 100;
  const at = new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
  if (Math.abs(diff) <= th) {
    box.className = 'msg ok';
    box.textContent = `✅ ${at}: tu tasa ${saved.rates['cl-ve']} está a ${fmt(Math.abs(diff), 1)} % de la sugerida (${sug.toFixed(4)}). Todo en orden.`;
    return;
  }
  document.title = '⚠️ ' + document.title;
  box.className = 'msg warn';
  box.textContent = diff > 0
    ? `⚠️ ${at}: estás dando de más. Tu tasa ${saved.rates['cl-ve']} está ${fmt(diff, 1)} % por encima de la sugerida (${sug.toFixed(4)}); tu ganancia real bajó a ≈ ${fmt(real, 1)} %. Revisa y considera bajarla.`
    : `⚠️ ${at}: el mercado subió. Tu tasa ${saved.rates['cl-ve']} está ${fmt(-diff, 1)} % por debajo de la sugerida (${sug.toFixed(4)}); ganas ≈ ${fmt(real, 1)} %, pero puedes quedar menos competitivo. Considera subirla.`;
}
// Colombia → Chile: compara tu tasa fija con la sugerida de ahora (Vita + tu ganancia). Tasa más alta = llegan MÁS CLP.
async function checkCoCl(th) {
  const box = $('mkt-co'), fixed = statusOf('co-cl') === 'on' ? rateNum(saved.cocl?.fixed) : null;
  if (!fixed) { box.hidden = true; return; }
  box.hidden = false;
  const got = await clpPerCop(saved.cocl?.margin_pct ?? '3');
  if (!got) { box.className = 'msg'; box.textContent = 'Colombia → Chile: no se pudo leer Vita Wallet ahora. Se vuelve a intentar en 5 minutos.'; return; }
  const sug = Number(got.rate.toFixed(4)), diff = (fixed / sug - 1) * 100;
  const at = new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
  if (Math.abs(diff) <= th) {
    box.className = 'msg ok';
    box.textContent = `✅ ${at} · Colombia → Chile: tu tasa fija ${saved.cocl.fixed} está a ${fmt(Math.abs(diff), 1)} % de la sugerida (${sug.toFixed(4)}). Todo en orden.`;
    return;
  }
  if (!document.title.startsWith('⚠️')) document.title = '⚠️ ' + document.title;
  box.className = 'msg warn';
  box.textContent = diff > 0
    ? `⚠️ ${at} · Colombia → Chile: estás dando de más. Tu tasa fija ${saved.cocl.fixed} está ${fmt(diff, 1)} % por encima de la sugerida (${sug.toFixed(4)}): llegan más pesos chilenos de los que deberían. Actualízala.`
    : `⚠️ ${at} · Colombia → Chile: el mercado se movió a tu favor. Tu tasa fija ${saved.cocl.fixed} está ${fmt(-diff, 1)} % por debajo de la sugerida (${sug.toFixed(4)}): ganas más, pero puedes quedar menos competitivo. Considera actualizarla.`;
}
$('mkt-th').oninput = () => { lsSet('jmc_mkt_th', $('mkt-th').value); checkMarket(); };
setInterval(() => { if (saved && !$('mkt').hidden) checkMarket(); }, 5 * 60 * 1000);

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
  for (const r of ROUTES) { body.rates[r.id] = r.auto ? '' : $('in-' + r.id).value.trim(); body.status[r.id] = $('st-' + r.id).value; }
  body.cocl = { margin_pct: $('in-co-cl').value.trim(), fixed: $('fx-co-cl').value.trim() || null };
  body.brl = { ref: $('prov-brl').value.trim(), margin_pct: $('prov-m').value.trim(), auto: $('prov-auto').checked,
    cal_cross: brlCross };  // calibración: el mercado en el momento en que anotaste a tu proveedor
  if (body.brl.auto && !brlCross) {
    $('save-msg').hidden = false; $('save-msg').className = 'msg bad';
    $('save-msg').textContent = 'Reales automático necesita el precio del mercado y no se pudo leer. Desmarca la casilla o inténtalo de nuevo.';
    return;
  }
  const okPct = (v) => { const t = String(v).replace(',', '.'); return t !== '' && Number(t) >= 0 && Number(t) <= 50; };
  const bad = ROUTES.filter((r) => (r.auto ? !okPct(body.cocl.margin_pct) || (body.cocl.fixed && !(rateNum(body.cocl.fixed) < 1)) : body.status[r.id] === 'on' && !rateNum(body.rates[r.id])));
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
  checkMarket();
  drawFlyers();
};

// ------------------------------------------------------------------ flyers

const loadImg = (src) => new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = src; });

// Texto para el estado de WhatsApp, como lo publica JM Cambios: origen ➡️ banderas de los destinos, para copiar y pegar.
const emojiFlag = (c) => String.fromCodePoint(...[...c].map((ch) => 0x1F1E6 + ch.charCodeAt(0) - 65));
const STATUS_FLAGS = ['EC', 'CO', 'VE', 'DO', 'PE', 'AR', 'PA', 'MX', 'BR', 'UY', 'EU', 'ES', 'US'];
function autoStatusText(k) {
  return `${emojiFlag(k)}➡️${STATUS_FLAGS.filter((c) => c !== k).map(emojiFlag).join('')}💱\n`
    + `Pago Rápido y Seguro\n`
    + `Cotiza tu envío aquí 👉 ${location.origin}/`;
}
const statusKey = (k) => `jmc_estado_${k}`;
function renderStatusText() {
  for (const k of Object.keys(FLYERS)) {
    let mine = null;
    try { mine = localStorage.getItem(statusKey(k)); } catch { /* sin almacenamiento: texto automático */ }
    $('estado-' + k).value = mine || autoStatusText(k);
  }
}
document.querySelectorAll('textarea.estado').forEach((t) => t.oninput = () => {
  try { localStorage.setItem(statusKey(t.id.replace('estado-', '')), t.value); } catch { /* no se pudo recordar */ }
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
      let text = st === 'ask' ? 'CONSULTAR' : st === 'on' && rateNum(saved.rates[id]) ? saved.rates[id] : '—';
      if (ROUTES.find((r) => r.id === id)?.auto && st === 'on') {  // Colombia → Chile: tu tasa fija; sin ella, la de este momento (Vita + ganancia)
        if (rateNum(saved.cocl?.fixed)) text = saved.cocl.fixed;
        else { const got = await clpPerCop(saved.cocl?.margin_pct ?? '3'); text = got ? got.rate.toFixed(4) : 'CONSULTAR'; }
      }
      let size = f.size;
      do { g.font = `800 ${size}px Montserrat, sans-serif`; size -= 2; } while (g.measureText(text).width > f.maxW && size > 20);
      g.fillText(text, cx, cy + 3);
    }
    const blob = await new Promise((ok) => c.toBlob(ok, 'image/png'));
    flyerBlobs[k] = blob;
    $('fly-' + k).src = URL.createObjectURL(blob);
  }
}

const FLYER_SLUG = { CL: 'chile', CO: 'colombia', EU: 'europa' };
const flyerName = (k) => `tasas-${FLYER_SLUG[k] || k.toLowerCase()}-${new Date().toISOString().slice(0, 10)}.png`;
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


// ------------------------------------------------------------------ USDT Colombia (venta al cliente)

let ucRef = null;
const ucPct = () => Number(String($('uc-margin').value).replace(',', '.'));
let ucTrm = null;
function ucCalc() {
  const m = ucPct();
  const price = ucRef && m >= 0 && m <= 50 ? ucRef.value * (1 + m / 100) : NaN;
  $('uc-price').textContent = Number.isFinite(price) ? fmt(price, 2) : '—';
  // Comparación con la TRM (referencia para vender "a precio TRM o mejor").
  $('uc-trm').textContent = ucTrm && Number.isFinite(price)
    ? `· TRM hoy ${fmt(ucTrm, 2)}: tu precio está ${fmt(Math.abs((price / ucTrm - 1) * 100), 1)} % ${price >= ucTrm ? 'sobre' : 'bajo'} la TRM` : '';
}
async function loadUsdtCo() {
  const { status, body } = await api('/api/usdt-co');
  if (status !== 200) return;
  $('uc-margin').value = body.margin_pct; $('uc-min').value = fmt(Number(body.min), 0); $('uc-pub').checked = !!body.published;
  try { const res = await fetch(USDT_COP_URL, { cache: 'no-store' }); ucRef = res.ok ? usdtCopRef(await res.text()) : null; } catch { ucRef = null; }
  try { const r = await fetch('/api/indicadores', { cache: 'no-store' }); ucTrm = r.ok ? (await r.json())?.co?.trm?.value ?? null : null; } catch { ucTrm = null; }
  $('uc-ref').textContent = ucRef ? `${fmt(ucRef.value, 2)} COP` : '—';
  $('uc-src').textContent = ucRef ? `(${{ binancep2p: 'Binance P2P', vita: 'Vita Wallet', mediana: 'mediana de exchanges' }[ucRef.source]} vía CriptoYa)` : 'No se pudo leer CriptoYa ahora: el cotizador mostrará "Mercado inestable".';
  ucCalc();
}
async function saveUsdtCo() {
  const msg = $('uc-msg');
  const { status, body } = await api('/api/usdt-co', { method: 'PUT', body: JSON.stringify({ margin_pct: $('uc-margin').value, min: $('uc-min').value, published: $('uc-pub').checked }) });
  msg.hidden = false;
  if (status !== 200) { msg.className = 'msg bad'; msg.textContent = body.error || 'No se pudo guardar.'; return; }
  msg.className = 'msg'; msg.textContent = body.published ? 'Guardado: los clientes ya ven USDT desde Colombia.' : 'Guardado (USDT Colombia apagado en el cotizador).';
}
// ------------------------------------------------------------------ USDT Brasil (comprar y vender)

let ubRef = null;
const pctIn = (id) => Number(String($(id).value).replace(',', '.'));
function ubCalc() {
  const m = pctIn('ub-margin'), b = pctIn('ub-buy');
  $('ub-sell').textContent = ubRef && m >= 0 && m <= 50 ? fmt(ubRef.value * (1 + m / 100), 4) : '—';
  $('ub-bid').textContent = ubRef?.bid && b >= 0 && b <= 50 ? fmt(ubRef.bid * (1 - b / 100), 4) : '—';
}
async function loadUsdtBr() {
  const { status, body } = await api('/api/usdt-br');
  if (status !== 200) return;
  $('ub-margin').value = body.margin_pct; $('ub-buy').value = body.buy_margin_pct; $('ub-pub').checked = !!body.published;
  try { const res = await fetch(USDT_BRL_URL, { cache: 'no-store' }); ubRef = res.ok ? usdtBrlRef(await res.text()) : null; } catch { ubRef = null; }
  $('ub-ref').textContent = ubRef ? `${fmt(ubRef.value, 4)} BRL` : '—';
  $('ub-src').textContent = ubRef ? `(${{ binancep2p: 'Binance P2P', bybitp2p: 'Bybit P2P', mediana: 'mediana de exchanges' }[ubRef.source]} vía CriptoYa)` : 'No se pudo leer CriptoYa ahora: el cotizador mostrará "Mercado inestable".';
  ubCalc();
}
async function saveUsdtBr() {
  const msg = $('ub-msg');
  const { status, body } = await api('/api/usdt-br', { method: 'PUT', body: JSON.stringify({ margin_pct: $('ub-margin').value, buy_margin_pct: $('ub-buy').value, published: $('ub-pub').checked }) });
  msg.hidden = false;
  if (status !== 200) { msg.className = 'msg bad'; msg.textContent = body.error || 'No se pudo guardar.'; return; }
  msg.className = 'msg'; msg.textContent = body.published ? 'Guardado: los clientes ya ven USDT desde Brasil.' : 'Guardado (USDT Brasil apagado en el cotizador).';
}
$('ub-margin').oninput = ubCalc; $('ub-buy').oninput = ubCalc;
$('ub-save').onclick = saveUsdtBr; $('ub-pub').onchange = saveUsdtBr;

// ------------------------------------------------------------------ Oro tokenizado (Chile y Colombia)

let goRef = null;
function goCalc() {
  const m = pctIn('go-margin'), b = pctIn('go-buy');
  if (!goRef || !(m >= 0 && m <= 50 && b >= 0 && b <= 50)) { $('go-prices').textContent = goRef ? 'Revisa las ganancias (0 a 50 %).' : 'No se pudo leer el precio ahora: el cotizador mostrará "Mercado inestable". Revisa jmcambios.cl/api/precio-cripto.'; return; }
  $('go-prices').innerHTML = [['PAXG', 'PAXG'], ['XAUT', 'XAUt']].map(([t, n]) => ['CLP', 'COP'].map((c) => goRef[t]?.[c]
    ? `<div><b>${n}</b> en ${c}: vendes a <b class="num">${fmt(goRef[t][c] * (1 + m / 100), 0)}</b> · compras a <b class="num">${fmt(goRef[t][c] * (1 - b / 100), 0)}</b></div>` : '').join('')).join('');
}
async function loadGoldCfg() {
  const { status, body } = await api('/api/oro');
  if (status !== 200) return;
  $('go-margin').value = body.margin_pct; $('go-buy').value = body.buy_margin_pct; $('go-cl').checked = !!body.cl; $('go-co').checked = !!body.co;
  $('go-priv').checked = body.private === true; $('go-xaut').checked = body.xaut !== false; $('go-paxg').checked = body.paxg === true;
  $('go-fee').checked = !!body.fee_on; $('go-fee-x').value = body.fee_xaut ?? '1'; $('go-fee-p').value = body.fee_paxg ?? '1';
  goRef = await marketCoins();
  const src = goRef?.source === 'binance' ? 'Binance PAXG/USDT × USDT Binance P2P' : 'CoinGecko';
  $('go-ref').textContent = goRef ? `1 onza ≈ US$${fmt(goRef.PAXG?.USD, 2)} · ${fmt(goRef.PAXG?.CLP, 0)} CLP · ${fmt(goRef.PAXG?.COP, 0)} COP (${src})` : '—';
  goCalc();
}
async function saveGold() {
  const msg = $('go-msg');
  const { status, body } = await api('/api/oro', { method: 'PUT', body: JSON.stringify({ margin_pct: $('go-margin').value, buy_margin_pct: $('go-buy').value, cl: $('go-cl').checked, co: $('go-co').checked,
    fee_on: $('go-fee').checked, fee_xaut: $('go-fee-x').value, fee_paxg: $('go-fee-p').value, xaut: $('go-xaut').checked, paxg: $('go-paxg').checked, private: $('go-priv').checked }) });
  msg.hidden = false;
  if (status !== 200) { msg.className = 'msg bad'; msg.textContent = body.error || 'No se pudo guardar.'; return; }
  const on = [body.cl && 'Chile', body.co && 'Colombia'].filter(Boolean);
  msg.className = 'msg'; msg.textContent = on.length ? `Guardado: los clientes ya ven el oro desde ${on.join(' y ')}.` : 'Guardado (oro apagado en el cotizador).';
}
$('go-margin').oninput = goCalc; $('go-buy').oninput = goCalc;
$('go-save').onclick = saveGold; $('go-cl').onchange = saveGold; $('go-co').onchange = saveGold; $('go-fee').onchange = saveGold; $('go-xaut').onchange = saveGold; $('go-priv').onchange = saveGold; $('go-paxg').onchange = saveGold;

// ------------------------------------------------------------------ Bitcoin (Chile y Colombia)

let btRef = null;
function btCalc() {
  const m = pctIn('bt-margin'), b = pctIn('bt-buy');
  if (!btRef || !(m >= 0 && m <= 50 && b >= 0 && b <= 50)) { $('bt-prices').textContent = btRef ? 'Revisa las ganancias (0 a 50 %).' : 'No se pudo leer el precio ahora: el cotizador mostrará "Mercado inestable". Revisa jmcambios.cl/api/precio-cripto.'; return; }
  $('bt-prices').innerHTML = ['CLP', 'COP'].map((c) => btRef[c]
    ? `<div><b>BTC</b> en ${c}: vendes a <b class="num">${fmt(btRef[c] * (1 + m / 100), 0)}</b> · compras a <b class="num">${fmt(btRef[c] * (1 - b / 100), 0)}</b></div>` : '').join('');
}
async function loadBtcCfg() {
  const { status, body } = await api('/api/btc');
  if (status !== 200) return;
  $('bt-margin').value = body.margin_pct; $('bt-buy').value = body.buy_margin_pct; $('bt-cl').checked = !!body.cl; $('bt-co').checked = !!body.co; $('bt-priv').checked = body.private === true;
  btRef = (await marketCoins())?.BTC ?? null;
  $('bt-ref').textContent = btRef ? `US$${fmt(btRef.USD, 0)} · ${fmt(btRef.CLP, 0)} CLP · ${fmt(btRef.COP, 0)} COP` : '—';
  btCalc();
}
async function saveBtc() {
  const msg = $('bt-msg');
  const { status, body } = await api('/api/btc', { method: 'PUT', body: JSON.stringify({ margin_pct: $('bt-margin').value, buy_margin_pct: $('bt-buy').value, cl: $('bt-cl').checked, co: $('bt-co').checked, private: $('bt-priv').checked }) });
  msg.hidden = false;
  if (status !== 200) { msg.className = 'msg bad'; msg.textContent = body.error || 'No se pudo guardar.'; return; }
  const on = [body.cl && 'Chile', body.co && 'Colombia'].filter(Boolean);
  msg.className = 'msg'; msg.textContent = on.length ? `Guardado: los clientes ya ven Bitcoin desde ${on.join(' y ')}.` : 'Guardado (Bitcoin apagado en el cotizador).';
}
$('bt-margin').oninput = btCalc; $('bt-buy').oninput = btCalc;
$('bt-save').onclick = saveBtc; $('bt-cl').onchange = saveBtc; $('bt-co').onchange = saveBtc; $('bt-priv').onchange = saveBtc;

// ------------------------------------------------------------------ JM Rewards: botón en el cotizador (parte apagado)

async function loadRewards() {
  const { status, body } = await api('/api/rewards');
  if (status === 200) $('jr-pub').checked = !!body.published;
}
$('jr-pub').onchange = async () => {
  const msg = $('jr-msg');
  const { status, body } = await api('/api/rewards', { method: 'PUT', body: JSON.stringify({ published: $('jr-pub').checked }) });
  msg.hidden = false;
  if (status !== 200) { msg.className = 'msg bad'; msg.textContent = body.error || 'No se pudo guardar.'; $('jr-pub').checked = !$('jr-pub').checked; return; }
  msg.className = 'msg'; msg.textContent = body.published ? 'Activado: los clientes ya ven el botón de JM Rewards.' : 'Apagado: el botón de JM Rewards no aparece en el cotizador.';
};

$('uc-margin').oninput = ucCalc;
$('uc-save').onclick = saveUsdtCo;
$('uc-pub').onchange = saveUsdtCo;
