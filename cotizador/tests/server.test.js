import assert from 'node:assert/strict';
import { test } from 'node:test';

import { onRequestGet as getRates, onRequestPut as putRates } from '../functions/api/tasas.js';
import { onRequestPost as postLogin } from '../functions/api/login.js';
import { onRequestGet as getSession } from '../functions/api/sesion.js';
import { amountNum, convert, invert, rateNum, routeById, ROUTES } from '../public/js/rutas.js';
import { hashPassword, parseBcv, validate } from '../lib/server.js';

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
});

test('validación: tasa vacía o inválida en una ruta activa', () => {
  const { errors } = validate({ rates: { ...RATES, 'cl-pe': 'abc' }, active: {} });
  assert.deepEqual(errors, ['cl-pe']);
  const off = validate({ rates: { ...RATES, 'cl-pe': '' }, active: { 'cl-pe': false } });
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
  const saved = await putRates({ request: req('/api/tasas', { method: 'PUT', body: { rates: RATES, active: { 'cl-br': false }, bcv_manual: '250,5' }, cookie }), env: e });
  assert.equal(saved.status, 200);
  const view = await (await getRates({ env: e })).json();
  assert.equal(view.routes.find((r) => r.id === 'cl-ve').rate, '0.9320');
  assert.equal(view.routes.find((r) => r.id === 'cl-br').active, false);
  assert.deepEqual(view.bcv, { value: 250.5, date: null, source: 'manual' });  // el BCV no respondió
  const ses = await getSession({ request: req('/api/sesion', { cookie }), env: e });
  assert.equal(ses.status, 200);
  assert.equal((await ses.json()).saved.bcv_manual, '250,5');
  assert.equal((await getSession({ request: req('/api/sesion'), env: e })).status, 401);
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
  const a = await (await getRates({ env: e })).json();
  const b = await (await getRates({ env: e })).json();
  assert.equal(a.bcv.source, 'bcv');
  assert.equal(b.bcv.value, 36.5623);
  assert.equal(calls, 1);
});
