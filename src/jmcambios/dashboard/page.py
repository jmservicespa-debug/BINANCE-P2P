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
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&family=Michroma&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0E161E;--card:#17222D;--line:#24313D;--border:#2C3A47;--text:#E8EDF2;--muted:#9AA7B4;--soft:#C3CCD5;
  --accent:#D3A6E8;--accent-bg:#35193F;--real:#8DB8F2;--real-bg:#1B2C44;--calc-bg:#252F39;--inf:#F2B66D;--inf-bg:#3A2A16;
  --up:#7FD4C1;--down:#F28B82;--down-bg:#3A1E1E;--ask:#F2B66D;--bid:#7FB3F2;
  --mono:'IBM Plex Mono',ui-monospace,Menlo,Consolas,monospace;--sans:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);-webkit-text-size-adjust:100%}
main{max-width:520px;margin:0 auto;padding:0 16px 96px}
header{padding:20px 4px 12px;display:flex;flex-direction:column;gap:10px}
.row{display:flex;justify-content:space-between;align-items:center;gap:8px}
.brand{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.brand .mark{width:34px;height:34px;flex:none;border-radius:8px;background:#F7F7F7;display:grid;place-items:center}
.brand .mark svg{width:24px;height:28px}
.brand .word{font-family:'Michroma',var(--sans);font-size:15px;letter-spacing:.06em;line-height:1.1;color:var(--text)}
.brand .tag{display:block;font-family:'Michroma',var(--sans);font-size:7.5px;letter-spacing:.18em;color:var(--muted);margin-top:3px}
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
/* Pantalla completa (monitor): las tres secciones a la vez, sin pestañas. */
.coltitle{display:none}
@media (min-width: 1100px){
  main{max-width:1680px;padding:0 24px 32px}
  #cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.25fr) minmax(0,1fr);gap:20px;align-items:start}
  #cols > div.hidden{display:block}
  .coltitle{display:block;font-size:12px;letter-spacing:.08em;color:var(--muted);margin:4px 4px 10px}
  .big{font-size:28px}
  #lmin,#lmax{width:150px}
}
nav{position:fixed;left:0;right:0;bottom:0;background:#0B1218;border-top:1px solid var(--line);display:flex;justify-content:center;padding:8px 8px calc(8px + env(safe-area-inset-bottom))}
nav div{display:flex;gap:6px;max-width:520px;width:100%}
@media (min-width: 1100px){nav{display:none}}
nav button{flex:1;min-height:44px;font-size:13px}
.hidden{display:none}
[hidden]{display:none!important}
.todo{border:1px solid var(--accent);margin-top:4px}
.act{display:flex;flex-direction:column;gap:2px;padding:8px 10px;border-radius:10px;background:var(--calc-bg)}
.act .what{font-size:16px;font-weight:700}
.act.up .what{color:var(--up)}.act.down .what{color:var(--down)}.act.keep .what{color:var(--soft)}
.act.flash{animation:flash 1s ease-in-out 3}
@keyframes flash{50%{background:var(--accent-bg)}}
@media (min-width: 1100px){#todolist{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
th{color:var(--muted);font-weight:500;padding:4px 2px;border-bottom:1px solid var(--line)}td{padding:5px 2px;border-bottom:1px solid var(--line)}
input{font:inherit;font-size:14px;width:118px;min-height:36px;padding:0 10px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--text)}
@media (prefers-color-scheme: light){
  :root:not([data-theme="dark"]){--bg:#F4F6F8;--card:#FFFFFF;--line:#E3E8ED;--border:#D5DCE3;--text:#14202B;--muted:#5D6B78;--soft:#3B4955;
  --accent:#531463;--accent-bg:#F1E4F5;--real:#2558A8;--real-bg:#E3ECFA;--calc-bg:#ECEFF2;--inf:#9A5B0C;--inf-bg:#FBEBD5;--up:#0F7A66;--down:#B3261E;--down-bg:#FBE4E2;--ask:#C77A12;--bid:#2F6FD0}
  :root:not([data-theme="dark"]) nav{background:#FFFFFF}
}
</style>
</head>
<body>
<main>
<header>
  <div class="row">
    <div><div class="brand"><span class="mark"><svg xmlns="http://www.w3.org/2000/svg" viewBox="20 14 450 522" aria-hidden="true"><clipPath id="jmhex"><polygon points="245,22 462,148 462,402 245,528 28,402 28,148"/></clipPath><g clip-path="url(#jmhex)" fill="#531463"><rect x="0" y="0" width="250" height="365"/><rect x="283" y="0" width="77" height="550"/><rect x="0" y="395" width="360" height="155"/><rect x="385" y="0" width="165" height="550"/></g></svg></span><span class="word">JMCAMBIOS<span class="tag">SPEED AND TRUST</span></span></div><h1 id="title">Mercado USDT/COP</h1></div>
    <span class="pill" id="mode">…</span>
  </div>
  <div class="chips"><span class="chip real">Binance = dato real</span><span class="chip calc">Cálculo = sistema</span><span class="chip inf">Inferido = estimación</span></div>
  <span class="muted" id="updated">Cargando…</span>
  <div id="stale"></div>
  <section class="card todo" id="todo" hidden>
    <div class="row"><h2>Qué hacer ahora</h2><button id="snd" title="Suena cuando cambia lo que hay que hacer">🔕 Sonido</button></div>
    <div id="todolist"></div>
    <span class="muted">Sugerencia del escenario equilibrado (o "tu puesto" si arrancaste el monitor con --puesto), sin regalar margen en las órdenes de tu mínimo. El precio lo cambias tú en la app de Binance.</span>
  </section>
</header>

<div id="cols">
<div id="tab-mercado"><div class="coltitle">MERCADO</div>
  <div class="grid">
    <div class="card"><span class="label">Mejor precio para COMPRAR</span><span class="big" id="ask">—</span><span class="muted" style="color:var(--real)" id="askn"></span><span class="muted mono" id="askv"></span><span class="muted" id="askr"></span></div>
    <div class="card"><span class="label">Mejor precio para VENDER</span><span class="big" id="bid">—</span><span class="muted" style="color:var(--real)" id="bidn"></span><span class="muted mono" id="bidv"></span><span class="muted" id="bidr"></span></div>
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

<div id="tab-precios" class="hidden"><div class="coltitle">PRECIOS Y ESTRATEGIAS</div>
  <section class="card"><div class="row"><h2>Mi capital</h2><span class="chip calc">Tú eliges</span></div>
    <span class="muted">Con cuánto empiezas. Se suman y restan tus órdenes de Binance desde que lo guardas.</span>
    <div class="row"><label class="label" for="capcop">Pesos (COP)</label><input id="capcop" type="text" inputmode="numeric" placeholder="ej. 1.500.000"></div>
    <div class="row"><label class="label" for="capusdt">USDT</label><input id="capusdt" type="text" inputmode="decimal" placeholder="ej. 500"></div>
    <div class="row"><span class="muted" id="capsince"></span><div class="btns"><button id="capsave">Guardar desde ahora</button></div></div>
    <div id="capout"></div>
  </section>
  <section class="card"><div class="row"><h2>Mis métodos de pago</h2><span class="chip calc">Tú eliges</span></div>
    <span class="muted">Las estrategias y la competencia por monto se calculan solo contra quienes aceptan alguno de estos.</span>
    <div class="btns" id="metbtns" style="flex-wrap:wrap"></div>
    <div class="row"><span class="muted" id="methint"></span><div class="btns"><button id="metreset">Mis anuncios</button></div></div>
  </section>
  <section class="card"><div class="row"><h2>Escenarios de precio</h2><span class="chip calc">Cálculo</span></div>
    <span class="muted" id="costs"></span><div id="prio"></div></section>
  <section class="card"><div class="row"><h2>Ganancia libre que buscas</h2><span class="chip calc">Tú eliges</span></div>
    <div class="btns" id="mbtns"><button data-m="0.5">0,5 %</button><button data-m="1">1 %</button><button data-m="1.5">1,5 %</button><button data-m="2">2 %</button></div>
    <div class="row"><label class="muted" for="mcustom">Otro valor en %</label><input id="mcustom" type="number" inputmode="decimal" min="0" max="10" step="0.1" placeholder="p. ej. 1,2"></div>
    <span class="muted" id="mhint"></span>
    <div class="row"><span class="label">Montos por orden (COP)</span>
      <div class="btns"><input id="lmin" type="text" inputmode="numeric" placeholder="mín. ej. 50000" aria-label="Monto mínimo">
      <input id="lmax" type="text" inputmode="numeric" placeholder="máx. ej. 500000" aria-label="Monto máximo"></div></div>
    <div class="row"><span class="muted" id="lhint"></span><div class="btns"><button id="lapply">Aplicar</button><button id="lreset">Mis anuncios</button></div></div>
    <div class="row"><label class="label" for="rank">Tu puesto (opcional)</label>
      <div class="btns"><input id="rank" type="number" inputmode="numeric" min="1" max="50" placeholder="ej. 5" style="width:80px"></div></div>
    <div class="row"><span class="label">Competidores</span><div class="btns" id="vbtns"><button data-v="1">Solo verificados</button><button data-v="0">Todos</button></div></div>
  </section>
  <div id="scen"></div>
  <section class="card"><div class="row"><h2>Competencia por monto</h2><span class="chip real">Binance</span></div>
    <span class="muted">Anuncios que atienden cada tramo y comparten tus métodos. Busca tramos con pocos competidores y buen precio.</span>
    <div id="tramos" class="muted">—</div></section>
  <section class="card"><div class="row"><h2>Cómo trabajan los mejores</h2><span class="chip calc">Últimos 3 días</span></div>
    <span class="muted">Comerciantes con más órdenes en 30 días y lo que hacen. "Diferencia propia" = su venta − su compra al mismo tiempo.</span>
    <div id="pattern"></div><div id="comerciantes" class="muted">Cargando…</div>
    <span class="muted">Puede no ser su margen real: algunos operan remesas u otros mercados y sus costos no se conocen.</span></section>
  <section class="card"><div class="row"><h2>Mis anuncios</h2><span class="chip real">Binance</span></div><div id="myads" class="muted">—</div></section>
  <div id="pwarn"></div>
  <p class="muted">Nada se modifica en Binance desde aquí: tú decides y cambias el precio en la app. Puesto = estimación por precio.</p>
</div>

<div id="tab-resultados" class="hidden"><div class="coltitle">RESULTADOS Y ALERTAS</div>
  <section class="card" id="today-card"><div class="row"><h2>Hoy</h2><span class="chip calc">Cálculo</span></div>
    <div class="row"><span class="big" id="t-real">—</span><span class="muted" id="t-goal"></span></div>
    <div class="bar"><span id="t-bar" style="left:0;width:0;background:var(--up)"></span></div>
    <div class="kv"><span>Compras / ventas hoy</span><b id="t-ops">—</b></div>
    <div class="kv"><span>Inventario sin vender</span><b id="t-inv">—</b></div>
    <div class="muted" id="t-since"></div><div class="muted" id="t-warn"></div>
  </section>
  <section class="card"><div class="row"><h2>Bitácora de órdenes</h2><div class="btns" id="bbtns"><button data-d="1" class="on">Hoy</button><button data-d="7">7 días</button></div></div>
    <span class="muted">Órdenes que entraron por tus anuncios: cuánto tardaron en llenarse, en qué puesto estabas y el margen de tu par compra/venta en ese momento.</span>
    <div id="bitacora" class="muted">—</div></section>
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
// Horas en Chile (donde está la persona); "Hoy" y las metas siguen contando el día de Colombia.
const hhmm = (ts) => new Date(ts * 1000).toLocaleTimeString('es-CL', {timeZone: 'America/Santiago', hour: '2-digit', minute: '2-digit'});
const hhmmCO = (ts) => new Date(ts * 1000).toLocaleTimeString('es-CO', {timeZone: 'America/Bogota', hour: '2-digit', minute: '2-digit'});
const dmy = (ts) => new Date(ts * 1000).toLocaleString('es-CL', {timeZone: 'America/Santiago', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'});
let hours = 6;
const WIDE = window.matchMedia('(min-width: 1100px)');
const shown = (id) => WIDE.matches || !$(id).classList.contains('hidden');
WIDE.addEventListener?.('change', () => refresh());
let margin = null;  // % elegido en el panel (null = el de la configuración)
try { const v = localStorage.getItem('jmc_margen'); if (v !== null && v !== '') margin = +v; } catch (e) {}
let lastState = null;
let limits = null;  // [min, max] elegidos en el panel (null = los de tus anuncios)
try { const v = JSON.parse(localStorage.getItem('jmc_limites') || 'null'); if (Array.isArray(v) && v.length === 2) limits = v; } catch (e) {}
let verified = null;  // true/false elegido en el panel (null = el de la configuración)
try { const v = localStorage.getItem('jmc_verificados'); if (v === '1' || v === '0') verified = v === '1'; } catch (e) {}
const MODES = {OBSERVATION: 'Modo: Observación', RECOMMENDATION: 'Modo: Recomendación', AUTOMATIC: 'Modo: Automático'};
const NAMES = {conservador: 'Conservador', equilibrado: 'Equilibrado', agresivo: 'Agresivo', 'como los mejores': 'Como los mejores', 'tu puesto': 'Tu puesto'};
const HINT = {conservador: 'más margen, menos órdenes', equilibrado: 'recomendado por defecto', agresivo: 'primer puesto, menos margen',
  'como los mejores': 'misma distancia al mejor precio que los líderes', 'tu puesto': 'el puesto que elegiste, con tu margen mínimo'};

// Mejor precio real: el primero con al menos N COP de plata acumulada detrás (los de arriba con poca plata = posible carnada).
function realBest(r) {
  if (!r) return '';
  if (r.price === null) return `Real: el libro entero no suma ${fmt(r.min_liquidity, 0)} COP`;
  if (!r.bait || r.price === r.best) return `Real: ${fmt(r.price)} ✓`;
  return `<b>Real: ${fmt(r.price)}</b> · ${r.bait} arriba con solo ${fmt(r.bait_fiat, 0)} COP (posible carnada)`;
}

function renderEstado(s) {
  if (!s.available) { $('updated').textContent = s.message; return; }
  const m = s.market || {};
  $('title').textContent = `Mercado ${m.asset || 'USDT'}/${m.fiat || 'COP'}`;
  $('mode').textContent = MODES[s.mode] || s.mode;
  $('updated').textContent = `Actualizado ${hhmm(s.cycle_ts)} hora Chile · ${hhmmCO(s.cycle_ts)} Colombia`;
  $('stale').innerHTML = s.age_s > 300 ? `<div class="bad">Datos de hace ${Math.round(s.age_s / 60)} min: ¿está corriendo el monitor en el computador?</div>` : '';
  $('ask').textContent = fmt(m.ask?.best); $('askn').textContent = m.ask ? `Binance · ${m.ask.ads} anuncios` : '';
  $('bid').textContent = fmt(m.bid?.best); $('bidn').textContent = m.bid ? `Binance · ${m.bid.ads} anuncios` : '';
  $('askv').textContent = m.ask?.verified_best != null ? `Verificados: ${fmt(m.ask.verified_best)}` : '';
  $('bidv').textContent = m.bid?.verified_best != null ? `Verificados: ${fmt(m.bid.verified_best)}` : '';
  $('askr').innerHTML = realBest(m.ask?.real_best); $('bidr').innerHTML = realBest(m.bid?.real_best);
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
  renderTodo(s);
}

// Qué hacer ahora: una línea por anuncio (subir / bajar / mantener). Suena (si se activa) cuando cambia.
let sound = false;
try { sound = localStorage.getItem('jmc_sonido') === '1'; } catch (e) {}
let lastTodo = null;
const setSnd = () => { $('snd').textContent = sound ? '🔔 Sonido' : '🔕 Sonido'; $('snd').classList.toggle('on', sound); };
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.25].forEach(t => { const o = ctx.createOscillator(), g = ctx.createGain(); o.frequency.value = 880;
      g.gain.setValueAtTime(0.15, ctx.currentTime + t); g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + t + 0.2);
      o.connect(g).connect(ctx.destination); o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.2); });
  } catch (e) {}
}
function renderTodo(s) {
  const box = $('todo');
  if (s.mode === 'OBSERVATION') {
    box.hidden = false;
    $('todolist').innerHTML = '<div class="warn">En modo Observación no se sugieren cambios. Pon JMC_MODE=RECOMMENDATION en el archivo .env y reinicia el monitor.</div>';
    return;
  }
  const acts = s.actions || [];
  box.hidden = !acts.length;
  if (!acts.length) return;
  const sig = acts.map(a => a.side + a.move + (a.to ?? '')).join('|');
  const changed = lastTodo !== null && sig !== lastTodo;
  $('todolist').innerHTML = acts.map(a => {
    const kind = a.side === 'BUY' ? 'COMPRA' : 'VENTA';
    let what, cls;
    if (a.move === 'subir' || a.move === 'bajar') {
      cls = a.move === 'subir' ? 'up' : 'down';
      what = `${kind}: ${a.move === 'subir' ? '⬆ SUBE' : '⬇ BAJA'} a <span class="mono">${fmt(a.to)}</span>`;
    } else if (a.move === 'mantener') { cls = 'keep'; what = `${kind}: ✓ mantén <span class="mono">${fmt(a.price)}</span>`; }
    else { cls = 'keep'; what = `${kind}: fuera de línea`; }
    const where = a.small_rank ? `<b>#${a.small_rank} de ${a.small_total}</b> para clientes de tu mínimo con tus bancos · #${a.rank} de ${a.total} en todo el mercado`
      : `puesto #${a.rank} de ${a.total} en todo el mercado`;
    const now = a.move === 'subir' || a.move === 'bajar'
      ? `<span class="muted">Ahora ${fmt(a.price)} (${a.delta > 0 ? '+' : ''}${fmt(a.delta)}) · ${where}</span>`
      : a.move === 'mantener' ? `<span class="muted">${where}</span>`
      : a.small_rank ? `<span class="muted">Si lo activas a ${fmt(a.price)}: <b>#${a.small_rank} de ${a.small_total}</b> para clientes de tu mínimo con tus bancos · #${a.rank} en todo el mercado</span>` : '';
    return `<div class="act ${cls}${changed && cls !== 'keep' ? ' flash' : ''}"><span class="what">${what}</span>${now}
      <span class="muted">${esc(a.reason)}</span>${a.note ? `<span class="muted">${esc(a.note)}</span>` : ''}</div>`;
  }).join('');
  if (changed && sound && acts.some(a => a.move === 'subir' || a.move === 'bajar')) beep();
  lastTodo = sig;
}
setSnd();
$('snd').onclick = () => { sound = !sound; try { localStorage.setItem('jmc_sonido', sound ? '1' : '0'); } catch (e) {} setSnd(); if (sound) beep(); };

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
    <div class="muted">puesto #${a.rank} de ${a.total}${a.suggested !== null && bal ? ` · sugerido <b class="mono">${fmt(a.side === 'BUY' ? bal.buy.price : bal.sell.price)}</b>` : ''}${a.gap !== null && a.gap < 0 ? ` · <span class="neg">regalando ${fmt(-a.gap)} COP</span>` : ''}</div>${ladderLine(s, a)}`).join('');
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
  $('lapply').onclick = () => {
  const a = parseCop($('lmin').value), b = parseCop($('lmax').value);
  if (Number.isNaN(a) && Number.isNaN(b)) setLimits(null);  // vacío = límites de tus anuncios
  else if (a > 0 && b > a) setLimits([a, b]); else $('lhint').innerHTML = '<span class="neg">El mínimo debe ser menor que el máximo</span>';
};
$('lreset').onclick = () => setLimits(null);
document.querySelectorAll('#bbtns button').forEach(b => b.onclick = () => {
  bdays = +b.dataset.d; document.querySelectorAll('#bbtns button').forEach(o => o.classList.toggle('on', o === b)); renderBitacora();
});
document.querySelectorAll('#vbtns button').forEach(b => b.classList.toggle('on', (b.dataset.v === '1') === v));
  const prof = s.profiles?.buy;
  $('lhint').textContent = limits ? `Estrategia para ${fmt(limits[0], 0)}–${fmt(limits[1], 0)}`
    : (prof ? `De tus anuncios: ${fmt(prof.min_fiat, 0)}–${fmt(prof.max_fiat, 0)}` : '');
  if (document.activeElement !== $('lmin') && document.activeElement !== $('lmax')) {
    $('lmin').value = limits ? fmt(limits[0], 0) : ''; $('lmax').value = limits ? fmt(limits[1], 0) : '';
  }
  renderTramos(v);
  if (shown('tab-precios')) { renderMerchants(v); renderCapital(); renderMethods(); }
  try {
    const r = await api('/api/escenarios?margen=' + m + '&verificados=' + (v ? 1 : 0)
      + (limits ? '&min=' + limits[0] + '&max=' + limits[1] : '') + metQ() + (rank ? '&puesto=' + rank : ''));
    if (r.available) renderPlan(r);
  } catch (e) { renderPlan(s.plan); }
}

const dur = (x) => x === null || x === undefined ? '—' : x < 3600 ? Math.max(1, Math.round(x / 60)) + ' min' : Math.floor(x / 3600) + ' h ' + String(Math.round(x % 3600 / 60)).padStart(2, '0') + ' min';
const LADDER = {subir: ['⬆', 'good', 'Sube el margen'], bajar: ['⬇', 'neg', 'Baja el margen'], mantener: ['•', '', 'Mantén el precio']};
function ladderLine(s, a) {
  const st = (s.ladder || []).find(x => x.side === a.side);
  if (!st || !a.online) return '';
  const [icon, cls, verb] = LADDER[st.action] || LADDER.mantener;
  const to = st.suggested !== null ? ` a <b class="mono">${fmt(st.suggested)}</b>` : '';
  const m = st.margin_after !== null && st.margin_now !== null ? ` · margen del par ${pct(st.margin_now, 2)} → ${pct(st.margin_after, 2)}`
    : st.margin_now !== null ? ` · margen del par ${pct(st.margin_now, 2)}` : '';
  const low = st.below_min ? ' · <span class="neg">queda por debajo de tu mínimo</span>' : '';
  return `<div class="muted" style="margin:2px 0 8px">Escalera: <span class="${cls}">${icon} ${verb}</span>${to} · ${esc(st.reason)}${m}${low}</div>`;
}

let bdays = 1;
async function renderBitacora() {
  try {
    const b = await api('/api/bitacora?dias=' + bdays);
    const r = (lastState || {}).ladder_rules;
    const rule = r ? `<span class="muted">Escalera: se llenó en menos de ${r.fast_min} min → subir ${fmt(r.step_pct, 1)} punto · más de ${r.slow_min} min sin órdenes → bajar.</span>` : '';
    if (!b.fills.length) {
      $('bitacora').innerHTML = (b.logged ? 'Todavía no entran órdenes por tus anuncios en este periodo.' : 'Aún no hay registro de tus anuncios: necesita la API key y el monitor corriendo.') + '<br>' + rule;
      return;
    }
    const th = 'style="text-align:right"';
    const sum = `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums;margin-top:8px">
      <tr><th style="text-align:left">Lado</th><th style="text-align:left">Puesto</th><th ${th}>Órdenes</th><th ${th}>Espera</th><th ${th}>Margen</th></tr>
      ${b.by_rank.map(x => `<tr><td>${x.side === 'BUY' ? 'Compra' : 'Venta'}</td><td>${esc(x.rank)}</td><td ${th}>${x.orders}</td>
        <td ${th}>${dur(x.median_wait_s)}</td><td ${th} class="mono">${x.median_margin === null ? '—' : pct(x.median_margin, 2)}</td></tr>`).join('')}</table></div>
      <span class="muted">Espera y margen: la mediana de cada grupo.</span>`;
    const list = b.fills.map(f => `<div class="kv"><span>${dmy(f.ts)} · ${f.side === 'BUY' ? 'COMPRA' : 'VENTA'} · ${fmt(f.fiat, 0)} COP</span><b class="mono">${fmt(f.price)}</b></div>
      <div class="muted" style="margin-bottom:6px">${f.rank ? 'puesto #' + f.rank : 'puesto —'} · tardó ${dur(f.wait_s)}${f.pair_margin !== null ? ' · margen del par ' + pct(f.pair_margin, 2) : ''}${f.status === 'COMPLETED' ? '' : ' · ' + esc(f.status)}</div>`).join('');
    $('bitacora').innerHTML = sum + '<h3 style="margin:12px 0 4px;font-size:14px;color:var(--text)">Órdenes</h3>' + list + rule;
  } catch (e) { $('bitacora').textContent = 'Sin datos de la bitácora todavía.'; }
}

async function renderTramos(v) {
  try {
    const t = await api('/api/tramos?verificados=' + (v ? 1 : 0) + metQ());
    const table = (rows, title) => `<h3 style="margin:10px 0 4px;font-size:14px;color:var(--text)">${title}</h3>
      <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums">
      <tr><th style="text-align:left">Tramo</th><th style="text-align:right">Anuncios</th><th style="text-align:right">Mejor</th><th style="text-align:right">Tu puesto</th></tr>
      ${rows.map(x => `<tr><td>${esc(x.label)}</td><td style="text-align:right">${x.ads}</td><td style="text-align:right" class="mono">${fmt(x.best)}</td>
        <td style="text-align:right">${x.my_rank && x.ads ? '#' + x.my_rank : '—'}</td></tr>`).join('')}</table></div>`;
    let sug = '';
    if (t.opportunities) {
      const best = t.suggested;
      sug = `<h3 style="margin:14px 0 4px;font-size:14px;color:var(--text)">¿En qué tramo operar?</h3>
        <span class="muted">Margen libre si quedas de primero comprando y vendiendo en ese tramo (mínimo ${pct(t.min_margin, 2)}).</span>
        <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums">
        <tr><th style="text-align:left">Tramo</th><th style="text-align:right">Diferencia</th><th style="text-align:right">Margen libre</th><th style="text-align:right">Compet.</th></tr>
        ${t.opportunities.map((o, i) => `<tr style="${i === best ? 'background:var(--accent-bg);color:var(--accent);font-weight:600' : ''}">
          <td>${esc(o.label)}${i === best ? ' ★' : ''}</td><td style="text-align:right" class="mono">${fmt(o.gap)}</td>
          <td style="text-align:right" class="mono ${o.margin !== null && o.margin < 0 ? 'neg' : ''}">${pct(o.margin)}</td><td style="text-align:right">${o.competitors}</td></tr>`).join('')}</table></div>`;
      if (best !== null && best !== undefined) {
        const o = t.opportunities[best];
        sug += `<div class="${o.meets_min ? 'warn' : 'bad'}" style="margin-top:8px">Sugerido: <b>${esc(o.label)}</b> · comprar a ${fmt(o.buy_at)} y vender a ${fmt(o.sell_at)} → ${pct(o.margin)} libre con ${o.competitors} competidores.`
          + (o.meets_min ? '' : '<br>Ningún tramo da tu margen mínimo estando de primero en los dos lados: espera que el precio se mueva o cede puesto en un lado.')
          + '</div><span class="muted">Los tramos grandes piden más capital por orden y suelen tener menos clientes (el volumen real no es verificable).</span>';
      }
    }
    $('tramos').innerHTML = table(t.buy || [], 'Compra (compiten con tu anuncio de compra)') + table(t.sell || [], 'Venta (compiten con tu anuncio de venta)') + sug;
  } catch (e) { $('tramos').textContent = 'Sin datos de tramos todavía.'; }
}

let lastMerchants = 0;
async function renderMerchants(v) {
  if (Date.now() - lastMerchants < 120000 && $('comerciantes').dataset.v === String(v)) return;
  lastMerchants = Date.now(); $('comerciantes').dataset.v = String(v);
  try {
    const c = await api('/api/comerciantes?verificados=' + (v ? 1 : 0));
    const hrs = (h) => { if (!h.length) return '—'; const out = []; let a = h[0], b = h[0];
      for (const x of h.slice(1).concat([null])) { if (x === b + 1) { b = x; continue; } out.push(a === b ? a + ' h' : `${a}–${b + 1} h`); if (x !== null) a = b = x; }
      return out.join(', '); };
    const p = c.pattern;
    $('pattern').innerHTML = p && p.two_sided ? `<div class="warn" style="margin:6px 0">Patrón de los ${p.two_sided} que compran y venden cerca de los primeros puestos (≤ #${p.active_rank}; se excluyen ${p.excluded} con un lado casi inactivo): diferencia propia típica
      <b>${fmt(p.own_spread)} COP (${fmt(p.own_spread_pct, 3)} %)</b> · puesto compra #${fmt(p.rank_buy, 0)}, venta #${fmt(p.rank_sell, 0)}
      · montos ${fmt(p.min_fiat, 0)}–${fmt(p.max_fiat, 0)}${p.reprices_per_hour !== null ? ` · cambian el precio ${fmt(p.reprices_per_hour, 1)} veces/hora` : ''}</div>` : '';
    $('comerciantes').innerHTML = (c.notes || []).map(n => `<div>⚠ ${esc(n)}</div>`).join('') + c.merchants.map((m, i) => `
      <div style="border-top:1px solid var(--line);padding:8px 0">
        <div class="kv"><span><b style="color:var(--text)">${i + 1}. ${esc(m.nickname)}</b> · ${esc(m.sides)}</span><b>${m.orders} órd.</b></div>
        ${m.own_spread !== null ? `<div>Diferencia propia <b class="mono" style="color:var(--text)">${fmt(m.own_spread)} COP (${fmt(m.own_spread_pct, 3)} %)</b>${m.net_with_my_costs !== null ? ` · con tus costos ${pct(m.net_with_my_costs)}` : ''}</div>` : ''}
        <div>${m.rank_buy !== null ? `compra #${fmt(m.rank_buy, 0)} ` : ''}${m.rank_sell !== null ? `venta #${fmt(m.rank_sell, 0)} ` : ''}· presente ${fmt(m.presence * 100, 0)} % · ${fmt(m.min_fiat, 0)}–${fmt(m.max_fiat, 0)}</div>
        <div>${esc(m.methods.join(', '))} · activo ${hrs(m.active_hours)}${m.reprices_per_hour !== null ? ` · ${fmt(m.reprices_per_hour, 1)} cambios/h` : ''}</div>
      </div>`).join('');
  } catch (e) { $('comerciantes').textContent = 'Sin datos todavía.'; }
}

function parseCop(t) { const x = (t || '').replace(/[^0-9]/g, ''); return x ? +x : NaN; }
function setLimits(v) {
  limits = v;
  try { v ? localStorage.setItem('jmc_limites', JSON.stringify(v)) : localStorage.removeItem('jmc_limites'); } catch (e) {}
  if (lastState) renderPlanFor(lastState);
}

// Puesto objetivo elegido en el panel (escenario "tu puesto"; null = no se muestra).
let rank = null;
try { const v = +localStorage.getItem('jmc_puesto'); if (v >= 1 && v <= 50) rank = v; } catch (e) {}
if (rank) $('rank').value = rank;
$('rank').onchange = () => {
  const v = Math.round(+$('rank').value);
  rank = v >= 1 && v <= 50 ? v : null;
  try { rank ? localStorage.setItem('jmc_puesto', rank) : localStorage.removeItem('jmc_puesto'); } catch (e) {}
  if (lastState) renderPlanFor(lastState);
};

// Métodos de pago elegidos en el panel (null = los de tus anuncios).
let methods = null;
try { const v = JSON.parse(localStorage.getItem('jmc_metodos') || 'null'); if (Array.isArray(v) && v.length) methods = v; } catch (e) {}
const metQ = () => methods ? '&metodos=' + encodeURIComponent(methods.join(',')) : '';
let metList = null;
async function renderMethods() {
  try { metList = metList || await api('/api/metodos'); } catch (e) { return; }
  const ids = [...new Set([...(metList.mine || []), ...(methods || []), ...metList.book.map(x => x.id)])];
  const sel = new Set(methods || metList.mine || []);
  const count = Object.fromEntries(metList.book.map(x => [x.id, x.ads]));
  $('metbtns').innerHTML = ids.map(id => `<button data-id="${esc(id)}" class="${sel.has(id) ? 'on' : ''}">${esc(id)}${count[id] ? ` <span class="muted">${count[id]}</span>` : ''}</button>`).join('');
  $('methint').textContent = methods ? `Elegidos en el panel: ${methods.join(', ')}` : `De tus anuncios: ${(metList.mine || []).join(', ') || '—'}`;
  document.querySelectorAll('#metbtns button').forEach(b => b.onclick = () => {
    const cur = new Set(methods || metList.mine || []);
    cur.has(b.dataset.id) ? cur.delete(b.dataset.id) : cur.add(b.dataset.id);
    setMethods(cur.size ? [...cur] : null);
  });
}
function setMethods(v) {
  methods = v;
  try { v ? localStorage.setItem('jmc_metodos', JSON.stringify(v)) : localStorage.removeItem('jmc_metodos'); } catch (e) {}
  renderMethods();
  if (lastState) renderPlanFor(lastState);
}

// Mi capital: pesos y USDT al inicio (guardados en este navegador) → saldo actual con tus órdenes.
let cap = null;
try { const v = JSON.parse(localStorage.getItem('jmc_capital') || 'null'); if (v && v.since) cap = v; } catch (e) {}
const parseUsdt = (t) => { let x = String(t || '').trim(); if (x.includes(',')) x = x.replace(/\./g, '').replace(',', '.'); return x === '' ? NaN : +x; };
const CAPS = {pesos: ['Cargado de pesos', 'neg'], usdt: ['Cargado de USDT', 'neg'], equilibrado: ['Balance sano', 'good'], 'sin precio': ['Sin precio de referencia', '']};
async function renderCapital() {
  if (!cap) { $('capout').innerHTML = ''; $('capsince').textContent = 'Sin capital guardado'; return; }
  if (document.activeElement !== $('capcop')) $('capcop').value = fmt(cap.cop, 0);
  if (document.activeElement !== $('capusdt')) $('capusdt').value = fmt(cap.usdt, 2);
  $('capsince').textContent = 'Desde ' + dmy(cap.since);
  try {
    const c = await api(`/api/capital?pesos=${cap.cop}&usdt=${cap.usdt}&desde=${cap.since}`);
    const [label, cls] = CAPS[c.status] || ['', ''];
    const share = c.cop_share === null ? null : c.cop_share * 100;
    $('capout').innerHTML = `
      <div class="kv"><span>Pesos ahora</span><b>${fmt(c.cop, 0)} COP</b></div>
      <div class="kv"><span>USDT ahora</span><b>${fmt(c.usdt, 2)} USDT</b></div>
      <div class="muted">${c.buys} compras · ${c.sells} ventas desde que guardaste${c.price ? ' · USDT a ' + fmt(c.price) : ''}</div>
      ${share === null ? '' : `<div class="bar"><span style="left:0;width:${share}%;background:var(--bid)"></span></div>
      <div class="row muted"><span>Pesos ${fmt(share, 0)} %</span><span class="${cls}">${label}</span><span>USDT ${fmt(100 - share, 0)} %</span></div>`}
      ${c.advice.map(a => `<div class="muted">• ${esc(a)}</div>`).join('')}
      ${c.warnings.map(w => `<div class="warn">${esc(w)}</div>`).join('')}
      ${c.max_buy_order && c.max_sell_order ? '<div class="row"><span class="muted">Llevar ese máximo a las estrategias</span><button id="capuse">Usar estos montos</button></div>' : ''}`;
    const use = $('capuse');
    if (use) use.onclick = () => {
      const lo = limits ? limits[0] : (lastState?.profiles?.buy?.min_fiat || 50000);
      const hi = Math.min(c.max_buy_order, c.max_sell_order);
      if (hi > lo) setLimits([lo, hi]); else $('lhint').innerHTML = '<span class="neg">El máximo sugerido queda bajo tu mínimo</span>';
    };
  } catch (e) { $('capout').innerHTML = '<span class="muted">No se pudo calcular el capital.</span>'; }
}
$('capsave').onclick = () => {
  const c = parseCop($('capcop').value), u = parseUsdt($('capusdt').value);
  if (!(c >= 0) || !(u >= 0)) { $('capsince').innerHTML = '<span class="neg">Escribe los pesos y los USDT</span>'; return; }
  cap = {cop: c, usdt: u, since: Math.floor(Date.now() / 1000)};
  try { localStorage.setItem('jmc_capital', JSON.stringify(cap)); } catch (e) {}
  renderCapital();
};
$('metreset').onclick = () => setMethods(null);

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
    if (shown('tab-resultados')) {
      const [r, a] = await Promise.all([api('/api/rentabilidad'), api('/api/alertas')]); renderRent(r); renderAlerts(a); renderBitacora();
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
