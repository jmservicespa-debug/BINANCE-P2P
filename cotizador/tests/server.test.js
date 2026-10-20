import assert from 'node:assert/strict';
import { test } from 'node:test';

import { onRequestGet as getRates, onRequestPut as putRates } from '../functions/api/tasas.js';
import { onRequestPost as postLogin } from '../functions/api/login.js';
import { onRequestGet as getSession } from '../functions/api/sesion.js';
import { amountNum, belowMin, convert, invert, rateNum, routeById, ROUTES } from '../public/js/rutas.js';
import { bcv, hashPassword, parseBcv, parseCriptoYa, parseDolarApi, usdtRef, validate } from '../lib/server.js';
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
  assert.equal(ROUTES.length, 7);
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
  const saved = await putRates({ request: req('/api/tasas', { method: 'PUT', body: { rates: RATES, status: { 'cl-br': 'off' }, bcv_manual: '250,5' }, cookie }), env: e });
  assert.equal(saved.status, 200);
  const view = await (await getRates({ request: req('/api/tasas'), env: e })).json();
  assert.equal(view.routes.find((r) => r.id === 'cl-ve').rate, '0.9320');
  assert.equal(view.routes.find((r) => r.id === 'cl-br').active, false);
  assert.deepEqual(view.bcv, { value: 250.5, date: null, source: 'manual' });  // el BCV no respondió
  const ses = await getSession({ request: req('/api/sesion', { cookie }), env: e });
  assert.equal(ses.status, 200);
  assert.equal((await ses.json()).saved.bcv_manual, '250,5');
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
  assert.equal(calls, 1);
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
  assert.deepEqual(parseCriptoYa(body), { value: 948.5, source: 'binancep2p' });
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
  // Desactivado: no aparece para nadie (tampoco con sesión). Activado: aparece para todos.
  assert.equal((await (await getRates({ request: req('/api/tasas'), env: e })).json()).usdt, undefined);
  assert.equal((await (await getRates({ request: req('/api/tasas', { cookie }), env: e })).json()).usdt, undefined);
  await putUsdt({ request: req('/api/usdt', { method: 'PUT', cookie, body: { margin_pct: '8', published: true } }), env: e });
  assert.deepEqual((await (await getRates({ request: req('/api/tasas'), env: e })).json()).usdt, { margin_pct: '8' });
  globalThis.fetch = async () => new Response(body);
  // Fuente caída: usa el valor manual y dice por qué.
  globalThis.fetch = async () => new Response('caído', { status: 502 });
  globalThis.fetch = async () => new Response('caído', { status: 502 });
  const r = await usdtRef(e, '950', Date.now() + 10 * 60 * 1000);
  assert.deepEqual([r.value, r.source, r.error], [950, 'manual', 'respondió 502']);
});
