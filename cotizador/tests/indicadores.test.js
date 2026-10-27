import assert from 'node:assert/strict';
import { test } from 'node:test';

import { onRequestGet as getInd } from '../functions/api/indicadores.js';
import { SOURCES, indicators, parseBtc, parseFx, parseTrm, parseUsdtVes } from '../lib/indicadores.js';

const kv = () => { const m = new Map(); return { get: async (k) => m.get(k) ?? null, put: async (k, v) => { m.set(k, v); }, delete: async (k) => { m.delete(k); } }; };

const BODIES = {
  [SOURCES.trm]: '[{"valor":"4123.45","unidad":"COP","vigenciadesde":"2026-10-27T00:00:00.000","vigenciahasta":"2026-10-27T00:00:00.000"}]',
  [SOURCES.fx]: '{"amount":1.0,"base":"USD","date":"2026-10-24","rates":{"BRL":5.5,"EUR":0.8}}',
  [SOURCES.btc]: '{"bitcoin":{"cop":412345678}}',
  [SOURCES.usdtVes]: '{"binancep2p":{"ask":300.5,"bid":299.5,"time":1},"otro":{"ask":310,"bid":305}}',
};

test('indicadores: lectura de cada fuente', () => {
  assert.deepEqual(parseTrm(BODIES[SOURCES.trm]), { value: 4123.45, date: '2026-10-27' });
  assert.equal(parseTrm('[]'), null);
  const fx = parseFx(BODIES[SOURCES.fx]);
  assert.equal(fx.brl_usd, 5.5); assert.equal(fx.usd_eur, 1.25); assert.equal(fx.brl_eur, 6.875);
  assert.equal(parseFx('{"rates":{"BRL":5.5}}'), null);
  assert.equal(parseBtc(BODIES[SOURCES.btc]), 412345678);
  assert.deepEqual(parseUsdtVes(BODIES[SOURCES.usdtVes]), { value: 300, source: 'binancep2p' });
  assert.deepEqual(parseUsdtVes('{"a":{"ask":10,"bid":8},"b":{"ask":20,"bid":18}}'), { value: 19, source: 'mediana' });
});

test('indicadores: se calculan, se guardan 1 hora y una fuente caída solo quita su dato', async () => {
  let calls = 0;
  globalThis.fetch = async (url) => { calls++; return url === SOURCES.btc ? new Response('caído', { status: 503 }) : new Response(BODIES[url]); };
  const env = { TASAS: kv() };
  const d = await (await getInd({ env })).json();
  assert.deepEqual(d.co.trm, { value: 4123.45, date: '2026-10-27' });
  assert.equal(d.co.eur.value, 4123.45 * 1.25);  // euro en pesos = TRM × dólares por euro
  assert.equal(d.co.btc, undefined);
  assert.deepEqual(d.br.usd, { value: 5.5, date: '2026-10-24' });
  assert.equal(d.ve.usdt.value, 300);
  await getInd({ env });
  assert.equal(calls, 4);  // la segunda visita usa lo guardado
  // Más tarde todo falla: se siguen mostrando los últimos datos.
  globalThis.fetch = async () => { throw new Error('sin red'); };
  const later = await indicators(env, Date.now() + 2 * 3600 * 1000);
  assert.equal(later.co.trm.value, 4123.45);
});
