import assert from 'node:assert/strict';
import { test } from 'node:test';

import { onRequestGet as getStats } from '../functions/api/estadisticas.js';
import { onRequestPost as postEvent } from '../functions/api/evento.js';
import { chileDay, report, track } from '../lib/estadisticas.js';
import { hashPassword, sessionCookie } from '../lib/server.js';

const ORIGIN = 'https://jmcambios.pages.dev';
const kv = () => { const m = new Map(); return { get: async (k) => m.get(k) ?? null, put: async (k, v) => { m.set(k, v); }, delete: async (k) => { m.delete(k); } }; };
const ev = (body, origin = ORIGIN) => new Request(ORIGIN + '/api/evento', { method: 'POST', body: JSON.stringify(body), headers: { 'content-type': 'application/json', ...(origin ? { origin } : {}) } });

test('estadísticas: cuenta visitas, cotizaciones y WhatsApp por día y por ruta', async () => {
  const env = { TASAS: kv(), SESSION_SECRET: 's' };
  const now = Date.UTC(2026, 10, 1, 15);  // 1 de noviembre, mediodía en Chile
  for (const b of [{ e: 'visita' }, { e: 'visita' }, { e: 'cotiza', r: 'cl-ve' }, { e: 'whatsapp', r: 'cl-ve' }, { e: 'cotiza', r: 'inventada' }]) {
    assert.equal((await track(ev(b), env, now)).status, 200);
  }
  assert.equal((await track(ev({ e: 'hackeo' }), env, now)).status, 400);
  assert.equal((await postEvent({ request: ev({ e: 'visita' }, 'https://otro.sitio'), env })).status, 403);
  const s = JSON.parse(await env.TASAS.get('stats:' + chileDay(now)));
  assert.deepEqual(s, { visita: 2, cotiza: 2, whatsapp: 1, rutas: { 'cl-ve': { cotiza: 1, whatsapp: 1 } } });
  // El informe es solo para el panel.
  assert.equal((await getStats({ request: new Request(ORIGIN + '/api/estadisticas'), env })).status, 401);
});

test('estadísticas: el día se corta a medianoche de Chile', () => {
  assert.equal(chileDay(Date.UTC(2026, 10, 2, 2)), '2026-11-01');  // 23:00 en Chile
  assert.equal(chileDay(Date.UTC(2026, 10, 2, 4)), '2026-11-02');
});

test('estadísticas: las visitas del dueño con sesión del panel no se cuentan', async () => {
  const env = { TASAS: kv(), SESSION_SECRET: 'secreto', ADMIN_PASSWORD_HASH: await hashPassword('x', new Uint8Array(16), 1000) };
  const now = Date.UTC(2026, 10, 1, 15);
  const cookie = (await sessionCookie(env, now)).split(';')[0];
  const mine = new Request(ORIGIN + '/api/evento', { method: 'POST', body: JSON.stringify({ e: 'visita' }), headers: { 'content-type': 'application/json', origin: ORIGIN, cookie } });
  assert.deepEqual(await (await track(mine, env, now)).json(), { ok: true, contado: false });
  await track(ev({ e: 'visita' }), env, now);  // un cliente
  assert.equal(JSON.parse(await env.TASAS.get('stats:' + chileDay(now))).visita, 1);
});
