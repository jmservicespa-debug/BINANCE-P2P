import assert from 'node:assert/strict';
import { test } from 'node:test';

import { onRequestGet as getRates, onRequestPut as putRates } from '../functions/api/tasas.js';
import { onRequestPost as postLogin } from '../functions/api/login.js';
import { onRequestGet as getSession } from '../functions/api/sesion.js';
import { amountNum, belowMin, convert, invert, rateNum, routeById, ROUTES } from '../public/js/rutas.js';
import { bcv, brlAuto, hashPassword, parseBcv, parseCriptoYa, parseDolarApi, usdtRef, validate } from '../lib/server.js';
import { brlPerClp, parseBrl } from '../public/js/criptoya.js';
import { onRequestGet as getUsdt, onRequestPut as putUsdt } from '../functions/api/usdt.js';

const ORIGIN = 'https://jmcambios.com';

function kv() {
  const m = new Map();
  return { get: async (k) => (m.has(k) ? m.get(k) : null), put: async (k, v) => { m.set(k, v); }, delete: async (k) => { m.delete(k); }, m };
}

async function env() {
  return { TASAS: kv(), SESSION_SECRET: 'secreto-de-prueba', ADMIN_PASSWORD_HASH: await hashPassword('clave-larga-123', new Uint8Array(16).fill(7), 1000) };
}

const req = (path, { method = 'GET', body, cookie, origin = ORIGIN } = {}) => new Request(ORIGIN + path, {
  method, body: body === undefined ? undefined : JSON.stringify(body),
  headers: { 'content-type': 'application/json', ...(origin ? { origin } : {}), ...(cookie ? { cookie } : {}) },
});

const RATES = { 'cl-ve': '0.9320', 'cl-pe': '0.003180', 'cl-co': '2.95', 'cl-us': '1085', 'cl-br': '0.0058', 'cl-pa': '1100', 'co-ve': '3.75' };

function noBcv() { globalThis.fetch = async () => { throw new Error('sin red'); }; }

test('cálculos con las tasas del flyer', () => {
  const r = (id) => routeById(id);
  assert.equal(convert(r('cl-ve'), '0.9320', 100000), 93200);
  assert.equal(Math.round(convert(r('cl-us'), '1085', 100000) * 100) / 100, 92.17);
  assert.equal(Math.round(convert(r('co-ve'), '3,75', 100000) * 100) / 100, 26666.67);
  assert.equal(Math.round(invert(r('co-ve'), '3.75', 26666.67)), 100000);
  assert.equal(Math.round(convert(r('cl-br'), '0.0058', 100000)), 580);
  assert.equal(amountNum('1.250,50'), 1250.5);
  assert.equal(amountNum('100.000'), 100000);
  assert.ok(Number.isNaN(rateNum('1.0.5')) && Number.isNaN(rateNum('')) && Number.isNaN(rateNum('-3')));
  assert.equal(ROUTES.length, 10);
  assert.equal(convert(r('eu-ve'), '256,80', 100), 25680);  // Europa → Venezuela: euros × tasa = bolívares
  // Sin decimales en ninguna ruta (montos completos para pagar por P2P).
  assert.ok(ROUTES.every((x) => x.dec === 0));
  assert.equal(Math.round(convert(r('co-ve'), '3.75', 100000)), 26667);  // 26.666,67 → sube
  assert.equal(Math.round(convert(r('cl-us'), '1085', 100000)), 92);     // 92,17 → baja
  // Mínimos por ruta (moneda de origen).
  assert.ok(belowMin(r('cl-ve'), 9999) && !belowMin(r('cl-ve'), 10000));
  assert.ok(belowMin(r('cl-us'), 39999) && !belowMin(r('cl-us'), 40000));
  assert.ok(belowMin(r('cl-pa'), 14999) && belowMin(r('co-ve'), 19999) && !belowMin(r('co-ve'), 20000));
  assert.ok(belowMin(r('cl-br'), 9999) && !belowMin(r('cl-br'), 10000));
});

test('validación: tasa vacía o inválida en una ruta activa', () => {
  const { errors } = validate({ rates: { ...RATES, 'cl-pe': 'abc' }, active: {} });
  assert.deepEqual(errors, ['cl-pe']);
  const off = validate({ rates: { ...RATES, 'cl-pe': '' }, status: { 'cl-pe': 'off' } });
  assert.deepEqual(off.errors, []);
});

test('login, guardar tasas y vista pública', async () => {
  noBcv();
  const e = await env();
  // Sin sesión no se puede guardar.
  assert.equal((await putRates({ request: req('/api/tasas', { method: 'PUT', body: { rates: RATES } }), env: e })).status, 401);
  // Contraseña mala → 401; buena → cookie.
  assert.equal((await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'mala' } }), env: e })).status, 401);
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  assert.equal(ok.status, 200);
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  assert.match(ok.headers.get('set-cookie'), /HttpOnly; Secure; SameSite=Strict/);
  // Desde otro sitio, aunque tenga la cookie: rechazado.
  assert.equal((await putRates({ request: req('/api/tasas', { method: 'PUT', body: { rates: RATES }, cookie, origin: 'https://otro.com' }), env: e })).status, 403);
  const saved = await putRates({ request: req('/api/tasas', { method: 'PUT', body: { rates: RATES, status: { 'cl-br': 'off' }, bcv_manual: '250,5', brl: { ref: '495,62', margin_pct: '8' } }, cookie }), env: e });
  assert.equal(saved.status, 200);
  const view = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  assert.equal(view.routes.find((r) => r.id === 'cl-ve').rate, '0.9320');
  assert.equal(view.routes.find((r) => r.id === 'cl-br').active, false);
  assert.deepEqual(view.bcv, { value: 250.5, date: null, source: 'manual' });  // el BCV no respondió
  assert.equal(JSON.stringify(view).includes('495,62'), false);  // el proveedor y tu ganancia no se publican
  const ses = await getSession({ request: req('/api/sesion', { cookie }), env: e });
  assert.equal(ses.status, 200);
  const sv = (await ses.json()).saved;
  assert.equal(sv.bcv_manual, '250,5');
  assert.deepEqual(sv.brl, { ref: '495,62', margin_pct: '8', auto: false, cal_cross: null });
  assert.equal((await getSession({ request: req('/api/sesion'), env: e })).status, 401);
});

test('mercado inestable: no publica la tasa y el cliente la pide por WhatsApp', async () => {
  noBcv();
  const e = await env();
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  // La tasa de Venezuela queda guardada (0.9320) pero no se publica; Perú en pausa sin tasa no da error.
  const r = await putRates({ request: req('/api/tasas', { method: 'PUT', cookie,
    body: { rates: { ...RATES, 'cl-pe': '' }, status: { 'cl-ve': 'ask', 'cl-pe': 'ask', 'cl-br': 'off' } } }), env: e });
  assert.equal(r.status, 200);
  const view = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  const ve = view.routes.find((x) => x.id === 'cl-ve');
  assert.deepEqual([ve.status, ve.rate, ve.active], ['ask', '', false]);
  assert.equal(view.routes.find((x) => x.id === 'cl-br').status, 'off');
  assert.equal(view.routes.find((x) => x.id === 'cl-co').status, 'on');
  const ses = await (await getSession({ request: req('/api/sesion', { cookie }), env: e })).json();
  assert.equal(ses.saved.rates['cl-ve'], '0.9320');  // al volver a Activa no hay que escribirla de nuevo
  // Datos guardados con el formato anterior (active: false) siguen funcionando.
  await e.TASAS.put('tasas', JSON.stringify({ rates: RATES, active: { 'cl-us': false }, updated: 1 }));
  const old = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  assert.equal(old.routes.find((x) => x.id === 'cl-us').status, 'off');
  assert.equal(old.routes.find((x) => x.id === 'cl-ve').status, 'on');
});

test('bloqueo tras 5 intentos fallidos', async () => {
  const e = await env();
  for (let i = 0; i < 5; i++) await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'x' } }), env: e });
  const r = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  assert.equal(r.status, 429);
});

test('cookie alterada o vencida no sirve', async () => {
  noBcv();
  const e = await env();
  const put = (cookie) => putRates({ request: req('/api/tasas', { method: 'PUT', body: { rates: RATES }, cookie }), env: e });
  assert.equal((await put('jmc_s=9999999999.AAAA')).status, 401);
  assert.equal((await put('jmc_s=1.abc')).status, 401);
});

test('dólar BCV leído de la página oficial y guardado 1 hora', async () => {
  const html = '<div id="dolar" class="col"><div><span> USD </span></div><div class="centrado"><strong> 36,56230000 </strong></div></div>'
    + '<div class="pull-right dinpro center">Fecha Valor: <span class="date-display-single" property="dc:date" content="2026-10-21T00:00:00-04:00">martes</span></div>';
  assert.deepEqual(parseBcv(html), { value: 36.5623, date: '2026-10-21' });
  assert.equal(parseBcv('<html>cambió el diseño</html>'), null);
  let calls = 0;
  globalThis.fetch = async () => { calls++; return new Response(html); };
  const e = await env();
  const a = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  const b = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  assert.equal(a.bcv.source, 'bcv');
  assert.equal(b.bcv.value, 36.5623);
  assert.equal(calls, 3);  // dólar (BCV) + euro (BCV sin euro en esta página y DolarApi); la segunda visita usa lo guardado
});

test('euro BCV: se lee de la misma página del BCV, con respaldo y valor manual propios', async () => {
  const html = '<div id="euro" class="col"><div><span> EUR </span></div><div class="centrado"><strong> 41,23450000 </strong></div></div>'
    + '<div id="dolar" class="col"><div><span> USD </span></div><div class="centrado"><strong> 36,56230000 </strong></div></div>';
  assert.equal(parseBcv(html, 'euro').value, 41.2345);
  assert.equal(parseBcv(html).value, 36.5623);
  globalThis.fetch = async () => new Response(html);
  const v = await (await getRates({ request: req('/api/tasas'), env: await env() })).json();
  assert.equal(v.bcv.value, 36.5623);
  assert.deepEqual(v.bcv_eur, { value: 41.2345, date: null, source: 'bcv' });
  noBcv();
  const e = await env();
  assert.deepEqual(await bcv(e, '41,5', 1_000_000, 'eur'), { value: 41.5, date: null, source: 'manual', errors: ['bcv: sin red', 'dolarapi: sin red'] });
  assert.deepEqual(validate({ rates: RATES, bcv_manual_eur: 'abc' }).errors, ['bcv_eur']);
});

test('dólar BCV: si la página del BCV falla usa DolarApi; si todo falla, el manual y el motivo', async () => {
  assert.deepEqual(parseDolarApi('{"fuente":"oficial","promedio":881.88,"fechaActualizacion":"2026-10-20T12:00:00.000Z"}'), { value: 881.88, date: '2026-10-20' });
  assert.equal(parseDolarApi('no es json'), null);
  const urls = [];
  globalThis.fetch = async (url) => {
    urls.push(String(url));
    if (String(url).includes('bcv.org.ve')) throw new TypeError('certificado inválido');
    return new Response('{"promedio":881.88,"fechaActualizacion":"2026-10-20T12:00:00Z"}');
  };
  const e = await env();
  const v = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  assert.deepEqual(v.bcv, { value: 881.88, date: '2026-10-20', source: 'dolarapi' });
  // Todo falla: valor manual, motivo guardado (solo para el panel) y sin reintentar en cada visita.
  let calls = 0;
  globalThis.fetch = async () => { calls++; return new Response('caído', { status: 503 }); };
  const e2 = await env();
  const r = await bcv(e2, '881,88', 1_000_000);
  assert.equal(r.source, 'manual');
  assert.deepEqual(r.errors, ['bcv: respondió 503', 'dolarapi: respondió 503']);
  await bcv(e2, '881,88', 1_000_000 + 60_000);
  assert.equal(calls, 2);  // un intento por fuente; el segundo pedido no vuelve a consultar
  await e2.TASAS.put('tasas', JSON.stringify({ rates: RATES, bcv_manual: '881,88', updated: 1 }));
  const pub = await (await getRates({ request: req('/api/tasas'), env: e2 })).json();
  assert.equal(pub.bcv.errors, undefined);
});

test('USDT/CLP: referencia de CriptoYa (Binance P2P), ganancia y respaldo manual', async () => {
  const body = JSON.stringify({ binancep2p: { ask: 948.5, bid: 940 }, buda: { ask: 951, bid: 939 }, raro: { ask: 5 } });
  assert.deepEqual(parseCriptoYa(body), { value: 948.5, source: 'binancep2p', bid: 940, bid_source: 'binancep2p' });
  assert.deepEqual(parseCriptoYa(JSON.stringify({ vitawallet: { ask: 982.14, bid: 970 } })), { value: 982.14, source: 'vita', bid: 970, bid_source: 'vita' });
  assert.deepEqual(parseCriptoYa(JSON.stringify({ vitawallet: { ask: 955.2 }, binancep2p: { ask: 948.5 } })), { value: 955.2, source: 'vita' });
  assert.deepEqual(parseCriptoYa(JSON.stringify({ a: { ask: 950 }, b: { ask: 960 }, c: { ask: 10 } })), { value: 960, source: 'mediana' });
  assert.equal(parseCriptoYa('Invalid pair'), null);
  let calls = 0;
  globalThis.fetch = async () => { calls++; return new Response(body); };
  const e = await env();
  // Sin sesión no se ve ni se guarda.
  assert.equal((await getUsdt({ request: req('/api/usdt'), env: e })).status, 401);
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  const v = await (await getUsdt({ request: req('/api/usdt', { cookie }), env: e })).json();
  assert.equal(v.margin_pct, '8');
  assert.equal(v.ref.value, 948.5);
  await getUsdt({ request: req('/api/usdt', { cookie }), env: e });
  assert.equal(calls, 1);  // guardado 2 minutos
  assert.equal((await putUsdt({ request: req('/api/usdt', { method: 'PUT', cookie, body: { margin_pct: '80' } }), env: e })).status, 400);
  const s = await (await putUsdt({ request: req('/api/usdt', { method: 'PUT', cookie, body: { margin_pct: '7,5', manual: '950' } }), env: e })).json();
  assert.equal(s.margin_pct, '7.5');
  assert.equal(s.buy_margin_pct, '8');  // sin dato se mantiene la ganancia al comprar
  assert.equal((await putUsdt({ request: req('/api/usdt', { method: 'PUT', cookie, body: { margin_pct: '8', buy_margin_pct: '60' } }), env: e })).status, 400);
  assert.equal((await (await putUsdt({ request: req('/api/usdt', { method: 'PUT', cookie, body: { margin_pct: '8', buy_margin_pct: '6,5' } }), env: e })).json()).buy_margin_pct, '6.5');
  // Desactivado: no aparece para nadie (tampoco con sesión). Activado: aparece para todos.
  assert.equal((await (await getRates({ request: req('/api/tasas'), env: e })).json()).usdt, undefined);
  assert.equal((await (await getRates({ request: req('/api/tasas', { cookie }), env: e })).json()).usdt, undefined);
  await putUsdt({ request: req('/api/usdt', { method: 'PUT', cookie, body: { margin_pct: '8', buy_margin_pct: '8', published: true } }), env: e });
  assert.deepEqual((await (await getRates({ request: req('/api/tasas'), env: e })).json()).usdt, { margin_pct: '8', buy_margin_pct: '8' });
  globalThis.fetch = async () => new Response(body);
  // Fuente caída: usa el valor manual y dice por qué.
  globalThis.fetch = async () => new Response('caído', { status: 502 });
  globalThis.fetch = async () => new Response('caído', { status: 502 });
  const r = await usdtRef(e, '950', Date.now() + 10 * 60 * 1000);
  assert.deepEqual([r.value, r.source, r.error], [950, 'manual', 'respondió 502']);
});

test('Brasil automático: mercado cripto, calibración con el proveedor y factor combinado', async () => {
  assert.equal(parseBrl(JSON.stringify({ a: { ask: 5.04 }, b: { ask: 5.05 }, c: { ask: 5.03 }, raro: { ask: 0.5 } })), 5.04);
  const fake = async (u) => new Response(u.includes('/brl/') ? '{"binance":{"ask":5.04},"bybit":{"ask":5.04}}' : '{"vitawallet":{"ask":982.14}}');
  const cross = await brlPerClp(fake);
  assert.ok(Math.abs(cross - 5.04 / 982.14) < 1e-12);  // 0,005132 reales por peso (Google decía 0,005119)
  assert.equal(brlAuto({ auto: false, cal_cross: cross, ref: '495,62', margin_pct: '8' }), null);
  const a = brlAuto({ auto: true, cal_cross: cross, ref: '495,62', margin_pct: '8' });
  // En el momento de calibrar, la tasa automática = la que da el proveedor + 8 % (0,004589).
  assert.ok(Math.abs(cross * a.k - 0.004589) < 0.000002);
  assert.deepEqual(Object.keys(a).sort(), ['cal', 'k']);  // no se publican ni el proveedor ni la ganancia
});

test('apagar todo: un interruptor oculta todas las tasas sin borrarlas', async () => {
  noBcv();
  const { onRequestPut: putPausa } = await import('../functions/api/pausa.js');
  const e = await env();
  await e.TASAS.put('tasas', JSON.stringify({ rates: RATES, updated: 1 }));
  assert.equal((await putPausa({ request: req('/api/pausa', { method: 'PUT', body: { paused: true } }), env: e })).status, 401);
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  assert.equal((await putPausa({ request: req('/api/pausa', { method: 'PUT', cookie, body: { paused: true }, origin: 'https://otro.com' }), env: e })).status, 403);
  assert.equal((await putPausa({ request: req('/api/pausa', { method: 'PUT', cookie, body: { paused: 'si' } }), env: e })).status, 400);
  assert.equal((await putPausa({ request: req('/api/pausa', { method: 'PUT', cookie, body: { paused: true } }), env: e })).status, 200);
  const pub = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  assert.deepEqual([pub.paused, pub.routes.length], [true, 0]);
  const ses = await (await getSession({ request: req('/api/sesion', { cookie }), env: e })).json();
  assert.equal(ses.paused, true);
  assert.equal(ses.saved.rates['cl-ve'], '0.9320');  // lo guardado sigue ahí
  await putPausa({ request: req('/api/pausa', { method: 'PUT', cookie, body: { paused: false } }), env: e });
  const on = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  assert.equal(on.paused, undefined);
  assert.equal(on.routes.find((r) => r.id === 'cl-ve').rate, '0.9320');
});

test('Colombia → Chile automático: Vita Colombia ÷ Vita Chile + ganancia; activa sin tasa escrita', async () => {
  const { clpPerCop, vitaPrice, USDT_COP_URL, USDT_URL } = await import('../public/js/criptoya.js');
  assert.equal(vitaPrice('{"vitawallet":{"ask":3196,"bid":3190}}', 'ask', [1500, 8000]), 3196);
  assert.equal(vitaPrice('{"binancep2p":{"ask":3196}}', 'ask', [1500, 8000]), null);  // sin Vita: no se inventa
  // Colombia: precio de COMPRA de Vita (ask 3.196). Chile: lo que PAGA Vita (bid 940).
  const bodies = { [USDT_COP_URL]: '{"vitawallet":{"ask":3196,"bid":3190}}', [USDT_URL]: '{"vitawallet":{"ask":950,"bid":940}}' };
  const fake = async (u) => new Response(bodies[u]);
  const got = await clpPerCop('3', fake);
  assert.equal(got.cop, 3196); assert.equal(got.clp, 940);
  assert.equal(got.rate.toFixed(4), (940 / 3196 / 1.03).toFixed(4));  // ≈ 0,2855 CLP por COP (cero adelante)
  assert.equal(Math.round(convert(routeById('co-cl'), '0.2857', 100000)), 28570);  // 100.000 COP × 0,2857
  // Mismo resultado que la forma antigua (100.000 COP ÷ 3,50 ≈ 28.571 CLP): solo cambia cómo se escribe la tasa.
  assert.ok(Math.abs(100000 * got.rate - 100000 / ((3196 / 940) * 1.03)) < 0.01);
  assert.equal(await clpPerCop('3', async () => new Response('caído', { status: 503 })), null);
  // En el panel se activa sin escribir tasa (solo la ganancia), y la vista pública manda la ganancia.
  const v = validate({ rates: RATES, status: { 'co-cl': 'on' }, cocl: { margin_pct: '3' } });
  assert.deepEqual(v.errors, []);
  assert.deepEqual(validate({ rates: RATES, cocl: { margin_pct: '80' } }).errors, ['co-cl-margen']);
});

test('tasa sugerida Chile → Venezuela: compra en Vita Chile (ask) y venta en Binance P2P Venezuela (bid)', async () => {
  const { marketClVe, SUG_CLP_URL, SUG_VES_URL } = await import('../public/js/criptoya.js');
  const bodies = { [SUG_CLP_URL]: '{"vitawallet":{"ask":950,"bid":940},"binancep2p":{"ask":955,"bid":945}}',
    [SUG_VES_URL]: '{"binancep2p":{"ask":905,"bid":890},"otro":{"ask":2,"bid":1}}' };
  const m = await marketClVe(async (u) => new Response(bodies[u]));
  assert.equal(m.clp.value, 950); assert.equal(m.clp.source, 'vitawallet');
  assert.equal(m.ves.value, 890);
  assert.equal(m.cross.toFixed(4), (890 / 950).toFixed(4));  // ≈ 0,9368 Bs por CLP, sin ganancia
  assert.equal(await marketClVe(async () => new Response('caído', { status: 503 })), null);
});

test('USDT Colombia: referencia de Binance P2P Colombia y configuración del panel', async () => {
  const { usdtCopRef } = await import('../public/js/criptoya.js');
  assert.deepEqual(usdtCopRef('{"binancep2p":{"ask":3180,"bid":3150},"vitawallet":{"ask":3196}}'), { value: 3180, source: 'binancep2p' });
  assert.deepEqual(usdtCopRef('{"vitawallet":{"ask":3196,"bid":3190}}'), { value: 3196, source: 'vita' });
  assert.equal(usdtCopRef('{"binancep2p":{"ask":5}}'), null);  // dato absurdo
  const { onRequestGet: getCo, onRequestPut: putCo } = await import('../functions/api/usdt-co.js');
  noBcv();
  const e = await env();
  const login = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = login.headers.get('set-cookie').split(';')[0];
  assert.equal((await (await getRates({ request: req('/api/tasas'), env: e })).json()).usdt_co, undefined);  // apagado al inicio
  assert.equal((await putCo({ request: req('/api/usdt-co', { method: 'PUT', body: { margin_pct: '2', min: '50.000', published: true }, cookie }), env: e })).status, 200);
  assert.deepEqual((await (await getRates({ request: req('/api/tasas'), env: e })).json()).usdt_co, { margin_pct: '2', min: 50000, buy_margin_pct: '3', buy_min: 50000 });
  assert.equal((await putCo({ request: req('/api/usdt-co', { method: 'PUT', body: { margin_pct: '90', min: '50000' }, cookie }), env: e })).status, 400);
  assert.equal((await getCo({ request: req('/api/usdt-co'), env: e })).status, 401);
});

test('JM Rewards: el botón del cotizador parte apagado y solo el panel lo enciende', async () => {
  const { onRequestGet: getJr, onRequestPut: putJr } = await import('../functions/api/rewards.js');
  noBcv();
  const e = await env();
  const login = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = login.headers.get('set-cookie').split(';')[0];
  assert.equal((await (await getRates({ request: req('/api/tasas'), env: e })).json()).rewards, undefined);  // apagado al inicio
  assert.equal((await getJr({ request: req('/api/rewards'), env: e })).status, 401);
  assert.equal((await putJr({ request: req('/api/rewards', { method: 'PUT', body: { published: true } }), env: e })).status, 401);
  assert.equal((await putJr({ request: req('/api/rewards', { method: 'PUT', body: { published: true }, cookie }), env: e })).status, 200);
  assert.deepEqual((await (await getRates({ request: req('/api/tasas'), env: e })).json()).rewards, { url: 'https://rewards.jmcambios.cl/' });
  assert.equal((await putJr({ request: req('/api/rewards', { method: 'PUT', body: { published: false }, cookie }), env: e })).status, 200);
  assert.equal((await (await getRates({ request: req('/api/tasas'), env: e })).json()).rewards, undefined);
});

test('Colombia → Chile con tasa fija: se publica la fija y no la automática', async () => {
  const { publicView } = await import('../lib/server.js');
  noBcv();
  const e = await env();
  assert.deepEqual(validate({ rates: RATES, status: { 'co-cl': 'on' }, cocl: { margin_pct: '3', fixed: 'abc' } }).errors, ['co-cl-fija']);
  assert.deepEqual(validate({ rates: RATES, status: { 'co-cl': 'on' }, cocl: { margin_pct: '3', fixed: '3.25' } }).errors, ['co-cl-fija']);  // sin cero adelante: no
  const fija = validate({ rates: RATES, status: { 'co-cl': 'on' }, cocl: { margin_pct: '3', fixed: '0.2850' } });
  assert.deepEqual(fija.errors, []);
  const r = (await publicView(e, { ...fija.data, updated: 1 })).routes.find((x) => x.id === 'co-cl');
  assert.deepEqual([r.rate, r.fixed, r.margin_pct], ['0.2850', true, undefined]);
  // Sin tasa fija: sigue automática (el navegador la calcula con la ganancia).
  const auto = validate({ rates: RATES, status: { 'co-cl': 'on' }, cocl: { margin_pct: '3', fixed: '' } });
  const a = (await publicView(e, { ...auto.data, updated: 1 })).routes.find((x) => x.id === 'co-cl');
  assert.deepEqual([a.rate, a.fixed, a.margin_pct], ['', undefined, '3']);
});

test('una tasa fija guardada al estilo antiguo (÷ 3,50) se convierte sola a la de cero adelante', async () => {
  const { coclZero, loadRates } = await import('../lib/server.js');
  assert.equal(coclZero({ cocl: { margin_pct: '3', fixed: '3.50' } }).cocl.fixed, '0.2857');
  assert.equal(coclZero({ cocl: { margin_pct: '3', fixed: '0.2850' } }).cocl.fixed, '0.2850');  // ya nueva: no se toca
  assert.equal(coclZero({ cocl: { margin_pct: '3', fixed: null } }).cocl.fixed, null);
  const e = await env();
  await e.TASAS.put('tasas', JSON.stringify({ rates: {}, status: { 'co-cl': 'on' }, cocl: { margin_pct: '3', fixed: '3,50' } }));
  const s = await loadRates(e);
  assert.equal(s.cocl.fixed, '0.2857');
  assert.equal(Math.round(convert(routeById('co-cl'), s.cocl.fixed, 100000)), 28570);  // ≈ lo mismo que 100.000 ÷ 3,50
});

test('la dirección antigua y www llevan a jmcambios.cl con la misma página', async () => {
  const { onRequest } = await import('../functions/_middleware.js');
  const next = async () => new Response('sitio');
  const go = (u) => onRequest({ request: new Request(u), next });
  const r1 = await go('https://jmcambios.pages.dev/?a=jamer');
  assert.equal(r1.status, 301); assert.equal(r1.headers.get('location'), 'https://jmcambios.cl/?a=jamer');
  const r2 = await go('https://www.jmcambios.cl/panel/');
  assert.equal(r2.headers.get('location'), 'https://jmcambios.cl/panel/');
  assert.equal(await (await go('https://jmcambios.cl/')).text(), 'sitio');               // la principal no se redirige
  assert.equal(await (await go('https://abc123.jmcambios.pages.dev/')).text(), 'sitio');  // vistas previas tampoco
});

test('oro tokenizado y USDT Brasil: se activan desde el panel y aparecen en la vista pública', async () => {
  noBcv();
  const { onRequestPut: putOro } = await import('../functions/api/oro.js');
  const { onRequestPut: putBr } = await import('../functions/api/usdt-br.js');
  const e = await env();
  // Sin sesión no se puede activar.
  assert.equal((await putOro({ request: req('/api/oro', { method: 'PUT', body: { margin_pct: '3', buy_margin_pct: '3', cl: true } }), env: e })).status, 401);
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  // Apagado por defecto: no aparece.
  let pub = await (await getRates({ env: e })).json();
  assert.equal(pub.gold, undefined); assert.equal(pub.usdt_br, undefined);
  // Ganancia fuera de rango → rechazado.
  assert.equal((await putOro({ request: req('/api/oro', { method: 'PUT', cookie, body: { margin_pct: '80', buy_margin_pct: '3', cl: true } }), env: e })).status, 400);
  assert.equal((await putOro({ request: req('/api/oro', { method: 'PUT', cookie, body: { margin_pct: '2,5', buy_margin_pct: '4', cl: true, co: false } }), env: e })).status, 200);
  assert.equal((await putBr({ request: req('/api/usdt-br', { method: 'PUT', cookie, body: { margin_pct: '3', buy_margin_pct: '3', published: true } }), env: e })).status, 200);
  pub = await (await getRates({ env: e })).json();
  assert.deepEqual(pub.gold, { margin_pct: '2.5', buy_margin_pct: '4', cl: true, co: false, fee: null, tokens: ['XAUT'], private: false });
  // Comisión de red activada: se publica en dólares por token.
  assert.equal((await putOro({ request: req('/api/oro', { method: 'PUT', cookie, body: { margin_pct: '3', buy_margin_pct: '3', cl: true, fee_on: true, fee_paxg: '1,5', fee_xaut: '1' } }), env: e })).status, 200);
  assert.deepEqual((await (await getRates({ env: e })).json()).gold.fee, { PAXG: 1.5, XAUT: 1 });
  assert.equal((await putOro({ request: req('/api/oro', { method: 'PUT', cookie, body: { margin_pct: '3', buy_margin_pct: '3', cl: true, fee_on: true, fee_paxg: '99' } }), env: e })).status, 400);
  assert.deepEqual(pub.usdt_br, { margin_pct: '3', buy_margin_pct: '3' });
});

test('precios: oro de CoinGecko en pesos y USDT en reales (Binance P2P, luego Bybit P2P)', async () => {
  const { parseGold, usdtBrlRef } = await import('../public/js/criptoya.js');
  const g = parseGold('{"pax-gold":{"usd":4077.01,"clp":3960487,"cop":13204532},"tether-gold":{"usd":4072.08,"clp":3955702,"cop":13188578}}');
  assert.deepEqual(g, { PAXG: { USD: 4077.01, CLP: 3960487, COP: 13204532 }, XAUT: { USD: 4072.08, CLP: 3955702, COP: 13188578 } });
  assert.equal(parseGold('{"pax-gold":{"clp":5}}'), null);  // dato absurdo
  assert.equal(usdtBrlRef({ binancep2p: { ask: 5.6, bid: 5.5 }, bybitp2p: { ask: 5.7, bid: 5.4 } }).source, 'binancep2p');
  assert.equal(usdtBrlRef({ bybitp2p: { ask: 5.7, bid: 5.4 } }).value, 5.7);
});

test('Bitcoin: se activa desde el panel y el precio sale de CoinGecko en pesos', async () => {
  noBcv();
  const { onRequestPut: putBtc } = await import('../functions/api/btc.js');
  const { parseGold } = await import('../public/js/criptoya.js');
  const e = await env();
  assert.equal((await putBtc({ request: req('/api/btc', { method: 'PUT', body: { margin_pct: '3', buy_margin_pct: '3', cl: true } }), env: e })).status, 401);
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  assert.equal((await (await getRates({ env: e })).json()).btc, undefined);
  assert.equal((await putBtc({ request: req('/api/btc', { method: 'PUT', cookie, body: { margin_pct: '2', buy_margin_pct: '3', cl: false, co: true } }), env: e })).status, 200);
  assert.deepEqual((await (await getRates({ env: e })).json()).btc, { margin_pct: '2', buy_margin_pct: '3', cl: false, co: true, private: false });
  assert.equal((await putBtc({ request: req('/api/btc', { method: 'PUT', cookie, body: { margin_pct: '2', buy_margin_pct: '3', co: true, private: true } }), env: e })).status, 200);
  assert.equal((await (await getRates({ env: e })).json()).btc.private, true);
  assert.deepEqual(parseGold('{"bitcoin":{"clp":95000000,"cop":420000000}}'), { BTC: { CLP: 95000000, COP: 420000000 } });
  assert.equal(parseGold('{"bitcoin":{"clp":95}}'), null);
});

test('precio del oro y Bitcoin: Binance (USDT) × USDT en pesos de CriptoYa; CoinGecko de respaldo', async () => {
  const { marketCoins, parseBinance } = await import('../public/js/criptoya.js');
  assert.deepEqual(parseBinance('[{"symbol":"PAXGUSDT","price":"4000.00"},{"symbol":"BTCUSDT","price":"100000.0"}]'), { PAXG: 4000, BTC: 100000 });
  assert.equal(parseBinance('[{"symbol":"PAXGUSDT","price":"3"}]'), null);
  const ok = (body) => ({ ok: true, text: async () => body });
  const fake = (map) => async (u) => { for (const [k, v] of Object.entries(map)) if (u.includes(k)) return v === null ? { ok: false } : ok(v); return { ok: false }; };
  const m = await marketCoins(fake({ 'binance.vision': '[{"symbol":"PAXGUSDT","price":"4000"},{"symbol":"BTCUSDT","price":"100000"}]',
    'usdt/clp': '{"vitawallet":{"ask":960,"bid":940},"binancep2p":{"ask":950,"bid":945}}', 'usdt/cop': '{"binancep2p":{"ask":4000,"bid":3950}}' }));
  assert.equal(m.source, 'binance');
  assert.deepEqual(m.XAUT, { USD: 4000, CLP: 3800000, COP: 16000000 });
  assert.deepEqual(m.BTC, { USD: 100000, CLP: 95000000, COP: 400000000 });
  // Binance caído: CoinGecko.
  const r = await marketCoins(fake({ 'coingecko': '{"pax-gold":{"usd":4077,"clp":3960487,"cop":13204532}}' }));
  assert.equal(r.source, 'coingecko'); assert.equal(r.PAXG.CLP, 3960487);
});

test('precio en dólares por el servidor: prueba fuentes en orden y guarda 2 minutos', async () => {
  const { cryptoUsd } = await import('../lib/server.js');
  const e = await env();
  const calls = [];
  globalThis.fetch = async (u) => { calls.push(String(u)); const s = String(u);
    if (s.includes('binance')) return new Response('', { status: 451 });
    if (s.includes('kraken')) return new Response(JSON.stringify({ result: { PAXGUSD: { c: ['4010.5', '1'] }, XXBTZUSD: { c: ['101000.1', '1'] } } }));
    if (s.includes('usdt/clp')) return new Response(JSON.stringify({ binancep2p: { ask: 950, bid: 940 } }));
    if (s.includes('usdt/cop')) return new Response(JSON.stringify({ binancep2p: { ask: 4000, bid: 3950 } }));
    return new Response('', { status: 500 }); };
  const r = await cryptoUsd(e, 1000);
  assert.equal(r.PAXG, 4010.5); assert.equal(r.BTC, 101000.1); assert.equal(r.paxg_src, 'kraken');
  assert.deepEqual(r.tries, ['binance:451', 'binance:451', 'kraken:200', 'criptoya:200', 'criptoya:200']);
  assert.equal(r.USDT_CLP, 950); assert.equal(r.USDT_COP, 4000);
  const n = calls.length;
  await cryptoUsd(e, 60000);  // dentro de 2 minutos: no vuelve a consultar
  assert.equal(calls.length, n);
});

test('Venezuela → Chile: se activa desde el panel y la tasa es Vita CLP ÷ (USDT Bs × (1 + ganancia))', async () => {
  noBcv();
  const { onRequestPut: putVeCl } = await import('../functions/api/ve-cl.js');
  const { clpPerVes } = await import('../public/js/criptoya.js');
  const e = await env();
  assert.equal((await putVeCl({ request: req('/api/ve-cl', { method: 'PUT', body: { margin_pct: '3', min: '2000', source: 'bybitp2p', published: true } }), env: e })).status, 401);
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  assert.equal((await (await getRates({ env: e })).json()).ve_cl, undefined);
  assert.equal((await putVeCl({ request: req('/api/ve-cl', { method: 'PUT', cookie, body: { margin_pct: '4', min: '3.000', source: 'bybitp2p', published: true } }), env: e })).status, 200);
  assert.deepEqual((await (await getRates({ env: e })).json()).ve_cl, { margin_pct: '4', min: 3000, source: 'bybitp2p' });
  const fake = async (u) => ({ ok: true, text: async () => (String(u).includes('/ves/') ? '{"bybitp2p":{"ask":400,"bid":395},"binancep2p":{"ask":410}}' : '{"vitawallet":{"ask":990,"bid":980}}') });
  const r = await clpPerVes('bybitp2p', '4', fake);
  assert.equal(r.ves, 400); assert.equal(r.clp, 980);
  assert.ok(Math.abs(r.rate - 980 / (400 * 1.04)) < 1e-9);
});

test('Brasil → Colombia: tasa = Binance P2P COP (ask, precio alto) ÷ (USDT BRL del exchange × (1 + ajuste))', async () => {
  noBcv();
  const { onRequestPut: putBrCo } = await import('../functions/api/br-co.js');
  const { copPerBrl } = await import('../public/js/criptoya.js');
  const e = await env();
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  assert.equal((await (await getRates({ env: e })).json()).br_co, undefined);
  assert.equal((await putBrCo({ request: req('/api/br-co', { method: 'PUT', cookie, body: { margin_pct: '2', profit_pct: '1,5', min: '50', source: 'foxbit', published: true } }), env: e })).status, 200);
  assert.deepEqual((await (await getRates({ env: e })).json()).br_co, { margin_pct: '3.5', min: 50, source: 'foxbit' });
  assert.equal((await putBrCo({ request: req('/api/br-co', { method: 'PUT', cookie, body: { margin_pct: '2', profit_pct: '80', min: '50', source: 'foxbit', published: true } }), env: e })).status, 400);
  const fake = async (u) => ({ ok: true, text: async () => (String(u).includes('/brl/') ? '{"foxbit":{"ask":5.5,"bid":5.4}}' : '{"binancep2p":{"ask":3900,"bid":3850}}') });
  const r = await copPerBrl('foxbit', '2', fake);
  assert.equal(r.brl, 5.5); assert.equal(r.cop, 3900);
  assert.ok(Math.abs(r.rate - 3900 / (5.5 * 1.02)) < 1e-9);
});

test('Colombia → Brasil: tasa = Binance P2P COP (ask) × (1 + ganancia) ÷ precio de compra del exchange en reales', async () => {
  noBcv();
  const { onRequestPut: putCoBr } = await import('../functions/api/co-br.js');
  const { copPerBrlSell } = await import('../public/js/criptoya.js');
  const e = await env();
  assert.equal((await putCoBr({ request: req('/api/co-br', { method: 'PUT', body: { profit_pct: '3', min: '50000', source: 'foxbit', published: true } }), env: e })).status, 401);
  const ok = await postLogin({ request: req('/api/login', { method: 'POST', body: { password: 'clave-larga-123' } }), env: e });
  const cookie = ok.headers.get('set-cookie').split(';')[0];
  assert.equal((await (await getRates({ env: e })).json()).co_br, undefined);
  assert.equal((await putCoBr({ request: req('/api/co-br', { method: 'PUT', cookie, body: { profit_pct: '3', min: '50.000', source: 'foxbit', published: true } }), env: e })).status, 200);
  assert.deepEqual((await (await getRates({ env: e })).json()).co_br, { profit_pct: '3', min: 50000, source: 'foxbit' });
  const fake = async (u) => ({ ok: true, text: async () => (String(u).includes('/brl/') ? '{"foxbit":{"ask":5.5,"bid":5.4}}' : '{"binancep2p":{"ask":3900,"bid":3850}}') });
  const r = await copPerBrlSell('foxbit', '3', fake);
  assert.equal(r.brl, 5.4); assert.equal(r.cop, 3900);
  assert.ok(Math.abs(r.rate - 3900 * 1.03 / 5.4) < 1e-9);
});
