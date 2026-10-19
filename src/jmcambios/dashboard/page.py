"""Página única del panel (HTML + CSS + JS en línea, sin dependencias externas obligatorias)."""

PAGE = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0E161E">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="referrer" content="no-referrer">
<title>JM Cambios</title>
<link rel="icon" type="image/png" href="/icon.png">
<link rel="apple-touch-icon" href="/icon.png">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0E161E;--card:#17222D;--line:#24313D;--border:#2C3A47;--text:#E8EDF2;--muted:#9AA7B4;--soft:#C3CCD5;
  --accent:#7FD4C1;--accent-bg:#1E3A34;--real:#8DB8F2;--real-bg:#1B2C44;--calc-bg:#252F39;--inf:#F2B66D;--inf-bg:#3A2A16;
  --up:#7FD4C1;--down:#F28B82;--down-bg:#3A1E1E;--ask:#F2B66D;--bid:#7FB3F2;
  --mono:'IBM Plex Mono',ui-monospace,Menlo,Consolas,monospace;--sans:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);-webkit-text-size-adjust:100%}
main{max-width:520px;margin:0 auto;padding:0 16px 96px}
header{padding:20px 4px 12px;display:flex;flex-direction:column;gap:10px}
.row{display:flex;justify-content:space-between;align-items:center;gap:8px}
.brand{font-size:13px;color:var(--muted);letter-spacing:.04em}
h1{font-size:22px;margin:2px 0 0;font-weight:700}
.pill{font-size:12px;font-weight:600;padding:6px 10px;border-radius:999px;background:var(--accent-bg);color:var(--accent);white-space:nowrap}
.chips{display:flex;gap:8px;flex-wrap:wrap;font-size:11px}
.chip{padding:3px 8px;border-radius:6px;font-size:11px;white-space:nowrap}
.real{background:var(--real-bg);color:var(--real)}.calc{background:var(--calc-bg);color:var(--soft)}.inf{background:var(--inf-bg);color:var(--inf)}
.muted{color:var(--muted);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.card{background:var(--card);border-radius:14px;padding:14px;display:flex;flex-direction:column;gap:6px;min-width:0}
.span2{grid-column:span 2}
section{margin-top:14px}
h2{font-size:15px;margin:0;font-weight:600}
.label{font-size:12px;color:var(--muted)}
.big{font-family:var(--mono);font-size:24px;font-weight:600}
.mid{font-family:var(--mono);font-size:18px;font-weight:600}
.mono{font-family:var(--mono)}
.warn{background:var(--inf-bg);color:var(--inf);border-radius:10px;padding:10px 12px;font-size:13px}
.bad{background:var(--down-bg);color:var(--down);border-radius:10px;padding:10px 12px;font-size:13px}
.good{color:var(--up)}.neg{color:var(--down)}
.bar{height:10px;border-radius:999px;background:var(--line);position:relative;overflow:hidden}
.bar>span{position:absolute;top:0;bottom:0;border-radius:999px}
svg{width:100%;height:auto;display:block}
.btns{display:flex;gap:4px}
button{font:inherit;font-size:12px;min-height:32px;padding:0 10px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer}
button.on{border-color:var(--accent);background:var(--accent-bg);color:var(--accent)}
.sc{border:1px solid var(--border)}
.sc.pick{border-color:var(--accent)}
.kv{display:flex;justify-content:space-between;gap:8px;font-size:13px}
.kv b{font-family:var(--mono);font-weight:600}
ul{margin:0;padding-left:18px}li{margin:4px 0;font-size:13px}
.alert{border-left:3px solid var(--border);padding:6px 10px;display:flex;flex-direction:column;gap:2px}
.alert.urgente{border-color:var(--down)}.alert.importante{border-color:var(--inf)}.alert.info{border-color:var(--real)}
.alert p{margin:0;font-size:13px;white-space:pre-line;color:var(--soft)}
nav{position:fixed;left:0;right:0;bottom:0;background:#0B1218;border-top:1px solid var(--line);display:flex;justify-content:center;padding:8px 8px calc(8px + env(safe-area-inset-bottom))}
nav div{display:flex;gap:6px;max-width:520px;width:100%}
nav button{flex:1;min-height:44px;font-size:13px}
.hidden{display:none}
input{font:inherit;font-size:14px;width:96px;min-height:36px;padding:0 10px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--text)}
@media (prefers-color-scheme: light){
  :root:not([data-theme="dark"]){--bg:#F4F6F8;--card:#FFFFFF;--line:#E3E8ED;--border:#D5DCE3;--text:#14202B;--muted:#5D6B78;--soft:#3B4955;
  --accent:#0F7A66;--accent-bg:#DDF3EE;--real:#2558A8;--real-bg:#E3ECFA;--calc-bg:#ECEFF2;--inf:#9A5B0C;--inf-bg:#FBEBD5;--up:#0F7A66;--down:#B3261E;--down-bg:#FBE4E2;--ask:#C77A12;--bid:#2F6FD0}
  :root:not([data-theme="dark"]) nav{background:#FFFFFF}
}
</style>
</head>
<body>
<main>
<header>
  <div class="row">
    <div><div class="brand">JM CAMBIOS</div><h1 id="title">Mercado USDT/COP</h1></div>
    <span class="pill" id="mode">…</span>
  </div>
  <div class="chips"><span class="chip real">Binance = dato real</span><span class="chip calc">Cálculo = sistema</span><span class="chip inf">Inferido = estimación</span></div>
  <span class="muted" id="updated">Cargando…</span>
  <div id="stale"></div>
</header>

<div id="tab-mercado">
  <div class="grid">
    <div class="card"><span class="label">Mejor precio para COMPRAR</span><span class="big" id="ask">—</span><span class="muted" style="color:var(--real)" id="askn"></span><span class="muted mono" id="askv"></span></div>
    <div class="card"><span class="label">Mejor precio para VENDER</span><span class="big" id="bid">—</span><span class="muted" style="color:var(--real)" id="bidn"></span><span class="muted mono" id="bidv"></span></div>
    <div class="card span2"><div class="row"><div><span class="label">Diferencial entre mejores precios</span><div class="mid" id="spread">—</div></div><span class="chip calc">Cálculo</span></div><div id="cross"></div></div>
  </div>
  <section class="card">
    <div class="row"><h2>Precios</h2><div class="btns" id="hbtns"><button data-h="1">1h</button><button data-h="6" class="on">6h</button><button data-h="24">24h</button><button data-h="72">3d</button></div></div>
    <div id="chart"></div>
    <div class="row muted"><span><span style="color:var(--ask)">●</span> mejor venta (compras tú)</span><span><span style="color:var(--bid)">●</span> mejor compra (vendes tú)</span></div>
  </section>
  <section class="card">
    <div class="row"><h2>Presión del mercado</h2><span class="chip calc">Cálculo</span></div>
    <div class="row"><span class="mid" id="plabel">—</span><span class="muted" id="pconf"></span></div>
    <div class="bar"><span id="pbar"></span></div>
    <div class="row muted"><span>bajista −100</span><span>0</span><span>+100 alcista</span></div>
    <ul id="psig"></ul>
    <div class="muted" id="pnotes"></div>
  </section>
  <section class="grid">
    <div class="card"><span class="label">Liquidez vendedores</span><span class="mid" id="askq">—</span><span class="muted">USDT anunciados</span></div>
    <div class="card"><span class="label">Liquidez compradores</span><span class="mid" id="bidq">—</span><span class="muted">USDT anunciados</span></div>
  </section>
</div>

<div id="tab-precios" class="hidden">
  <section class="card"><div class="row"><h2>Escenarios de precio</h2><span class="chip calc">Cálculo</span></div>
    <span class="muted" id="costs"></span><div id="prio"></div></section>
  <section class="card"><div class="row"><h2>Ganancia libre que buscas</h2><span class="chip calc">Tú eliges</span></div>
    <div class="btns" id="mbtns"><button data-m="0.5">0,5 %</button><button data-m="1">1 %</button><button data-m="1.5">1,5 %</button><button data-m="2">2 %</button></div>
    <div class="row"><label class="muted" for="mcustom">Otro valor en %</label><input id="mcustom" type="number" inputmode="decimal" min="0" max="10" step="0.1" placeholder="p. ej. 1,2"></div>
    <span class="muted" id="mhint"></span>
    <div class="row"><span class="label">Competidores</span><div class="btns" id="vbtns"><button data-v="1">Solo verificados</button><button data-v="0">Todos</button></div></div>
  </section>
  <div id="scen"></div>
  <section class="card"><div class="row"><h2>Mis anuncios</h2><span class="chip real">Binance</span></div><div id="myads" class="muted">—</div></section>
  <div id="pwarn"></div>
  <p class="muted">Nada se modifica en Binance desde aquí: tú decides y cambias el precio en la app. Puesto = estimación por precio.</p>
</div>

<div id="tab-resultados" class="hidden">
  <section class="card" id="today-card"><div class="row"><h2>Hoy</h2><span class="chip calc">Cálculo</span></div>
    <div class="row"><span class="big" id="t-real">—</span><span class="muted" id="t-goal"></span></div>
    <div class="bar"><span id="t-bar" style="left:0;width:0;background:var(--up)"></span></div>
    <div class="kv"><span>Compras / ventas hoy</span><b id="t-ops">—</b></div>
    <div class="kv"><span>Inventario sin vender</span><b id="t-inv">—</b></div>
    <div class="muted" id="t-since"></div><div class="muted" id="t-warn"></div>
  </section>
  <section class="card" id="cap-card"><div class="row"><h2>Tope exento 4x1000</h2><span class="chip inf">Estimado</span></div>
    <div class="row"><span class="mid" id="c-used">—</span><span class="muted" id="c-cap"></span></div>
    <div class="bar"><span id="c-bar" style="left:0;width:0"></span></div>
    <div class="muted" id="c-note"></div>
  </section>
  <section class="card"><div class="row"><h2>Rentabilidad COP · 30 días</h2><span class="chip calc">Cálculo</span></div>
    <div class="kv"><span>Beneficio realizado</span><b id="real">—</b></div>
    <div class="kv"><span>Compras / ventas</span><b id="ops">—</b></div>
    <div class="kv"><span>Margen bruto por USDT</span><b id="mpu">—</b></div>
    <div id="days"></div>
    <span class="muted">Realizado = ciclos cerrados con costo conocido. El monitor descarga tus órdenes solo cada ~15 min.</span>
    <div id="rwarn"></div>
  </section>
  <section class="card"><h2>Alertas recientes</h2><div id="alerts" class="muted">—</div></section>
</div>
</main>
<nav><div><button data-tab="mercado" class="on">Mercado</button><button data-tab="precios">Precios</button><button data-tab="resultados">Resultados</button></div></nav>

<script>
const T = new URLSearchParams(location.search).get('t') || '';
const nf = (d) => new Intl.NumberFormat('es-CO', {minimumFractionDigits: d, maximumFractionDigits: d});
const fmt = (v, d = 2) => v === null || v === undefined || Number.isNaN(v) ? '—' : nf(d).format(v);
const pct = (v, d = 3) => v === null || v === undefined ? '—' : fmt(v * 100, d) + ' %';
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = (id) => document.getElementById(id);
const api = (p) => fetch(p + (p.includes('?') ? '&' : '?') + 't=' + encodeURIComponent(T), {cache: 'no-store'}).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
const hhmm = (ts) => new Date(ts * 1000).toLocaleTimeString('es-CO', {timeZone: 'America/Bogota', hour: '2-digit', minute: '2-digit'});
const dmy = (ts) => new Date(ts * 1000).toLocaleString('es-CO', {timeZone: 'America/Bogota', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'});
let hours = 6;
let margin = null;  // % elegido en el panel (null = el de la configuración)
try { const v = localStorage.getItem('jmc_margen'); if (v !== null && v !== '') margin = +v; } catch (e) {}
let lastState = null;
let verified = null;  // true/false elegido en el panel (null = el de la configuración)
try { const v = localStorage.getItem('jmc_verificados'); if (v === '1' || v === '0') verified = v === '1'; } catch (e) {}
const MODES = {OBSERVATION: 'Modo: Observación', RECOMMENDATION: 'Modo: Recomendación', AUTOMATIC: 'Modo: Automático'};
const NAMES = {conservador: 'Conservador', equilibrado: 'Equilibrado', agresivo: 'Agresivo'};
const HINT = {conservador: 'más margen, menos órdenes', equilibrado: 'recomendado por defecto', agresivo: 'primer puesto, menos margen'};

function renderEstado(s) {
  if (!s.available) { $('updated').textContent = s.message; return; }
  const m = s.market || {};
  $('title').textContent = `Mercado ${m.asset || 'USDT'}/${m.fiat || 'COP'}`;
  $('mode').textContent = MODES[s.mode] || s.mode;
  $('updated').textContent = `Actualizado ${hhmm(s.cycle_ts)} · hora Colombia`;
  $('stale').innerHTML = s.age_s > 300 ? `<div class="bad">Datos de hace ${Math.round(s.age_s / 60)} min: ¿está corriendo el monitor en el computador?</div>` : '';
  $('ask').textContent = fmt(m.ask?.best); $('askn').textContent = m.ask ? `Binance · ${m.ask.ads} anuncios` : '';
  $('bid').textContent = fmt(m.bid?.best); $('bidn').textContent = m.bid ? `Binance · ${m.bid.ads} anuncios` : '';
  $('askv').textContent = m.ask?.verified_best != null ? `Verificados: ${fmt(m.ask.verified_best)}` : '';
  $('bidv').textContent = m.bid?.verified_best != null ? `Verificados: ${fmt(m.bid.verified_best)}` : '';
  $('spread').textContent = m.spread === undefined ? '—' : `${fmt(m.spread)} COP · ${fmt(m.spread_pct, 3)}%`;
  $('askq').textContent = fmt(m.ask?.qty, 0); $('bidq').textContent = fmt(m.bid?.qty, 0);
  const c = s.cross;
  $('cross').innerHTML = !c ? '' : c.executable
    ? `<div class="warn">Cruce APROVECHABLE: neto ≈ ${fmt(c.net)} COP/USDT (${fmt(c.net_pct, 3)}%) · hasta ${fmt(c.max_qty)} USDT · pagar por ${esc(c.pay)}, cobrar por ${esc(c.receive)}</div>`
    : `<div class="muted">Mercado cruzado ${fmt(c.gross)} COP, no aprovechable con tus métodos.</div>`;
  const p = s.pressure;
  if (p && p.windows.length) {
    $('plabel').textContent = `${p.label} (${p.score > 0 ? '+' : ''}${fmt(p.score, 0)})`;
    $('pconf').textContent = `confianza ${p.confidence}/100`;
    const b = $('pbar'); const w = Math.abs(p.score) / 2;
    b.style.left = p.score >= 0 ? '50%' : (50 - w) + '%'; b.style.width = w + '%';
    b.style.background = p.score >= 0 ? 'var(--up)' : 'var(--down)';
    $('psig').innerHTML = p.signals.map(g => `<li>${g.up ? '↑' : '↓'} ${esc(g.name)} (${g.window} min): ${esc(g.detail)} <span class="chip ${g.provenance === 'observado' ? 'real' : 'inf'}">${esc(g.provenance)}</span></li>`).join('');
    $('pnotes').innerHTML = [...p.notes, ...p.unverifiable.map(u => u + ' [no verificable]')].map(esc).join('<br>');
  } else { $('plabel').textContent = 'sin datos suficientes'; }

  const k = s.costs || {};
  $('costs').textContent = `Comisión maker compra ${pct(k.maker_buy)} · venta ${pct(k.maker_sell)} · 4x1000 ${pct(k.gmf)} (exenta) / ${pct(k.gmf_worst)} · margen mínimo ${pct(k.min_margin, 2)}`;
  renderPlanFor(s);
  renderOperation(s);
}

const compat = (sp) => sp.rank_compatible <= sp.compatible_total
  ? `#${sp.rank_compatible} de ${sp.compatible_total} compatibles` : `detrás de los ${sp.compatible_total} compatibles`;

function renderPlan(pl) {
  const PRIO = {comprar: 'Presión alcista: prioriza COMPRAR', vender: 'Presión bajista: prioriza VENDER', equilibrado: 'Sin señal clara: margen repartido'};
  const who = (pl?.merchants_only ?? lastState?.merchants_only ?? true) ? 'Competencia: solo comerciantes verificados' : 'Competencia: todos los anunciantes';
  $('prio').innerHTML = pl ? `<span class="muted">${PRIO[pl.priority] || ''}<br>${who}</span>` : '';
  $('scen').innerHTML = (pl?.scenarios || []).map(sc => `
    <section class="card sc ${sc.name === 'equilibrado' ? 'pick' : ''}">
      <div class="row"><h2>${NAMES[sc.name]}</h2><span class="muted">${HINT[sc.name]}</span></div>
      <div class="kv"><span>Comprar a</span><b>${fmt(sc.buy.price)}</b></div>
      <div class="muted">puesto ≈ #${sc.buy.rank} · ${compat(sc.buy)}${sc.buy.adjusted ? ' · ajustado por margen' : ''}</div>
      <div class="kv"><span>Vender a</span><b>${fmt(sc.sell.price)}</b></div>
      <div class="muted">puesto ≈ #${sc.sell.rank} · ${compat(sc.sell)}${sc.sell.adjusted ? ' · ajustado por margen' : ''}</div>
      <div class="kv"><span>Margen del ciclo</span><b class="${sc.margin_worst < 0 ? '' : 'good'}">${pct(sc.margin)} <span class="muted">(${pct(sc.margin_worst)} con 4x1000)</span></b></div>
      <div class="kv"><span>Ganancia por USDT</span><b>${fmt(sc.net_per_unit)} COP</b></div>
    </section>`).join('');
  const s = lastState || {my_ads: []};
  const bal = (pl?.scenarios || []).find(x => x.name === 'equilibrado');
  $('myads').innerHTML = !s.my_ads.length ? 'Sin anuncios leídos (necesita la API key y el monitor corriendo).' : s.my_ads.map(a => `
    <div class="kv"><span>${a.side === 'BUY' ? 'COMPRA' : 'VENTA'} ${esc(a.id)} · ${a.online ? '<span class="good">en línea</span>' : 'fuera de línea'}</span><b>${fmt(a.price)}</b></div>
    <div class="muted">puesto #${a.rank} de ${a.total}${a.suggested !== null && bal ? ` · sugerido <b class="mono">${fmt(a.side === 'BUY' ? bal.buy.price : bal.sell.price)}</b>` : ''}${a.gap !== null && a.gap < 0 ? ` · <span class="neg">regalando ${fmt(-a.gap)} COP</span>` : ''}</div>`).join('');
  $('pwarn').innerHTML = (pl?.warnings || []).map(w => `<div class="warn" style="margin-top:10px">${esc(w)}</div>`).join('');
}

async function renderPlanFor(s) {
  lastState = s;
  const cfg = (s.costs?.min_margin ?? 0.003) * 100;
  const m = margin === null ? cfg : margin;
  document.querySelectorAll('#mbtns button').forEach(b => b.classList.toggle('on', Math.abs(+b.dataset.m - m) < 1e-9));
  const ref = s.market?.ask?.best || s.market?.bid?.best;
  $('mhint').innerHTML = `Agresivo ≥ ${fmt(m, 2)} % · equilibrado ≥ ${fmt(m + 0.15, 2)} % · conservador ≥ ${fmt(m + 0.3, 2)} % libre`
    + (ref ? ` (≈ ${fmt(ref * m / 100, 0)}–${fmt(ref * (m + 0.3) / 100, 0)} COP por USDT)` : '')
    + `<br>Solo cambia lo que ves aquí. Las alertas usan el margen de la configuración (${fmt(cfg, 2)} %).`;
  const cfgV = s.merchants_only ?? true;
  const v = verified === null ? cfgV : verified;
  document.querySelectorAll('#vbtns button').forEach(b => b.classList.toggle('on', (b.dataset.v === '1') === v));
  if (Math.abs(m - cfg) < 1e-9 && v === cfgV) { renderPlan(s.plan ? {...s.plan, merchants_only: cfgV} : s.plan); return; }
  try {
    const r = await api('/api/escenarios?margen=' + m + '&verificados=' + (v ? 1 : 0));
    if (r.available) renderPlan(r);
  } catch (e) { renderPlan(s.plan); }
}

function setVerified(v) {
  verified = v;
  try { localStorage.setItem('jmc_verificados', v ? '1' : '0'); } catch (e) {}
  if (lastState) renderPlanFor(lastState);
}

function setMargin(v) {
  margin = (v === null || Number.isNaN(v) || v < 0 || v > 10) ? null : Math.round(v * 100) / 100;
  try { margin === null ? localStorage.removeItem('jmc_margen') : localStorage.setItem('jmc_margen', margin); } catch (e) {}
  if (lastState) renderPlanFor(lastState);
}

function renderOperation(s) {
  const t = s.today;
  $('today-card').classList.toggle('hidden', !t);
  if (t) {
    $('t-real').innerHTML = `<span class="${t.realized < 0 ? 'neg' : 'good'}">${fmt(t.realized, 0)}</span>`;
    $('t-goal').textContent = `de ${fmt(t.goal, 0)} COP · ${fmt(t.progress * 100, 0)} %`;
    const tb = $('t-bar'); tb.style.width = Math.max(0, Math.min(100, t.progress * 100)) + '%';
    tb.style.background = t.progress >= 1 ? 'var(--up)' : 'var(--accent)';
    $('t-ops').textContent = `${t.buys} / ${t.sells}`;
    $('t-inv').textContent = t.inventory_qty > 0.5 ? `${fmt(t.inventory_qty)} USDT a ${fmt(t.inventory_avg_cost)}` : 'ninguno';
    if (t.inventory_qty > 0.5 && t.inventory_since) {
      const h = (Date.now() / 1000 - t.inventory_since) / 3600;
      $('t-since').innerHTML = `Comprado hace ${h < 1 ? Math.round(h * 60) + ' min' : fmt(h, 1) + ' h'}`
        + (h >= 6 ? ' · <span class="neg">capital quieto: revisa tu precio de venta</span>' : '');
    } else { $('t-since').textContent = ''; }
    $('t-warn').innerHTML = t.warnings.map(w => '⚠ ' + esc(w)).join('<br>');
  }
  const c = s.exempt;
  $('cap-card').classList.toggle('hidden', !c);
  if (c) {
    $('c-used').textContent = `${fmt(c.used, 0)} COP`;
    $('c-cap').textContent = `de ${fmt(c.cap, 0)} · ${fmt(c.ratio * 100, 0)} %`;
    const cb = $('c-bar'); cb.style.width = Math.min(100, c.ratio * 100) + '%';
    cb.style.background = c.ratio >= 1 ? 'var(--down)' : c.ratio >= 0.8 ? 'var(--inf)' : 'var(--up)';
    $('c-note').innerHTML = (c.exceeded ? '<span class="neg">Tope superado: los escenarios ya incluyen el 4x1000.</span><br>' : `Quedan ${fmt(c.remaining, 0)} COP este mes (${esc(c.month)}).<br>`)
      + `Pagos P2P por ${c.accounts.map(esc).join(', ')} (${c.orders} órdenes). Otros débitos de esas cuentas no se ven aquí.`;
  }
}

function renderSerie(d) {
  const pts = d.points.filter(p => p[1] !== null && p[2] !== null);
  if (pts.length < 2) { $('chart').innerHTML = '<p class="muted">Aún no hay suficiente historial.</p>'; return; }
  const W = 340, H = 150, P = 4;
  const t0 = pts[0][0], t1 = pts[pts.length - 1][0];
  const vals = pts.flatMap(p => [p[1], p[2]]);
  let lo = Math.min(...vals), hi = Math.max(...vals); if (hi - lo < 1) { hi += 1; lo -= 1; }
  const x = t => P + (W - 2 * P) * (t - t0) / Math.max(1, t1 - t0);
  const y = v => P + (H - 2 * P) * (1 - (v - lo) / (hi - lo));
  const line = i => pts.map(p => `${x(p[0]).toFixed(1)},${y(p[i]).toFixed(1)}`).join(' ');
  const grid = [lo, (lo + hi) / 2, hi].map(v => `<line x1="0" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${W - 2}" y="${v === hi ? y(v) + 11 : y(v) - 3}" text-anchor="end" font-size="9" fill="var(--muted)">${fmt(v, 0)}</text>`).join('');
  $('chart').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mejor precio de venta y de compra">${grid}
    <polyline fill="none" stroke="var(--ask)" stroke-width="2" points="${line(1)}"/><polyline fill="none" stroke="var(--bid)" stroke-width="2" points="${line(2)}"/></svg>
    <div class="row muted"><span>${hhmm(t0)}</span><span>${hhmm(t1)}</span></div>`;
}

function renderRent(r) {
  $('real').innerHTML = `<span class="${r.realized < 0 ? 'neg' : 'good'}">${fmt(r.realized, 0)} COP</span>`;
  $('ops').textContent = `${r.buys} / ${r.sells}`;
  $('mpu').textContent = r.margin_per_unit === null ? '—' : fmt(r.margin_per_unit) + ' COP';
  const mx = Math.max(1, ...r.by_day.map(d => Math.abs(d.realized)));
  $('days').innerHTML = r.by_day.map(d => `<div class="kv"><span class="muted">${esc(d.day)}</span><span style="flex:1;margin:0 8px;align-self:center" class="bar"><span style="left:0;width:${(Math.abs(d.realized) / mx * 100).toFixed(0)}%;background:${d.realized < 0 ? 'var(--down)' : 'var(--up)'}"></span></span><b>${fmt(d.realized, 0)}</b></div>`).join('');
  $('rwarn').innerHTML = r.warnings.map(w => `<div class="muted">⚠ ${esc(w)}</div>`).join('');
}

function renderAlerts(a) {
  $('alerts').innerHTML = !a.length ? 'Sin alertas todavía.' : a.map(x => `<div class="alert ${esc(x.severity)}"><span class="muted">${dmy(x.ts)} · ${esc(x.severity)}</span><b>${esc(x.title)}</b><p>${esc(x.body)}</p></div>`).join('');
}

async function refresh() {
  try {
    const [s, d] = await Promise.all([api('/api/estado'), api('/api/serie?horas=' + hours)]);
    renderEstado(s); renderSerie(d);
    if (!$('tab-resultados').classList.contains('hidden')) {
      const [r, a] = await Promise.all([api('/api/rentabilidad'), api('/api/alertas')]); renderRent(r); renderAlerts(a);
    }
  } catch (e) {
    $('stale').innerHTML = `<div class="bad">No se pudo conectar con el computador (${esc(e.message)}). ¿Estás en la misma red Wi-Fi y el monitor sigue abierto?</div>`;
  }
}
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(o => o.classList.toggle('on', o === b));
  ['mercado', 'precios', 'resultados'].forEach(t => $('tab-' + t).classList.toggle('hidden', t !== b.dataset.tab));
  window.scrollTo(0, 0); refresh();
});
document.querySelectorAll('#hbtns button').forEach(b => b.onclick = () => {
  hours = +b.dataset.h; document.querySelectorAll('#hbtns button').forEach(o => o.classList.toggle('on', o === b)); refresh();
});
document.querySelectorAll('#mbtns button').forEach(b => b.onclick = () => { $('mcustom').value = ''; setMargin(+b.dataset.m); });
document.querySelectorAll('#vbtns button').forEach(b => b.onclick = () => setVerified(b.dataset.v === '1'));
$('mcustom').onchange = () => { const v = $('mcustom').value.replace(',', '.'); setMargin(v === '' ? null : +v); };
refresh(); setInterval(refresh, 30000);
</script>
</body>
</html>
"""
