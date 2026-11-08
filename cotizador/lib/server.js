// Lógica del servidor del cotizador (Cloudflare Pages Functions).
// Guarda las tasas en KV (`env.TASAS`), protege el panel con contraseña y lee el dólar BCV.

import { ROUTES, rateNum } from '../public/js/rutas.js';
import { CLP_RANGE, COP_RANGE, USDT_COP_URL, USDT_URL, binanceP2pAsk, parseCriptoYa, usdtCopRef } from '../public/js/criptoya.js';

export { parseCriptoYa };

const COOKIE = 'jmc_s';
const SESSION_S = 12 * 3600;
const LOGIN_MAX = 5; // intentos fallidos por IP cada 15 min
const BCV_URL = 'https://www.bcv.org.ve/';
const BCV_TTL_S = 3600;

export function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...headers },
  });
}

const enc = new TextEncoder();
const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

function sameBytes(a, b) {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a[i] ^ b[i];
  return d === 0;
}

// ADMIN_PASSWORD_HASH = "pbkdf2$<iteraciones>$<sal b64>$<hash b64>" (lo genera scripts/hash-password.mjs).
export async function hashPassword(password, salt, iterations = 100000) {
  const key = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations }, key, 256);
  return `pbkdf2$${iterations}$${b64(salt)}$${b64(bits)}`;
}

export async function checkPassword(password, stored) {
  const [kind, it, salt, hash] = String(stored || '').split('$');
  if (kind !== 'pbkdf2' || !it || !salt || !hash) return false;
  const again = await hashPassword(String(password || ''), unb64(salt), Number(it));
  return sameBytes(unb64(again.split('$')[3]), unb64(hash));
}

async function hmac(secret, text) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return b64(await crypto.subtle.sign('HMAC', key, enc.encode(text)));
}

export async function sessionCookie(env, now = Date.now()) {
  const exp = Math.floor(now / 1000) + SESSION_S;
  const token = `${exp}.${await hmac(env.SESSION_SECRET, String(exp))}`;
  return `${COOKIE}=${token}; Path=/; Max-Age=${SESSION_S}; HttpOnly; Secure; SameSite=Strict`;
}

export const clearCookie = () => `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;

export async function isAdmin(request, env, now = Date.now()) {
  if (!env.SESSION_SECRET) return false;
  const raw = (request.headers.get('cookie') || '').split(/;\s*/).find((c) => c.startsWith(COOKIE + '='));
  if (!raw) return false;
  const [exp, sig] = raw.slice(COOKIE.length + 1).split('.');
  if (!exp || !sig || Number(exp) * 1000 < now) return false;
  return sameBytes(enc.encode(sig), enc.encode(await hmac(env.SESSION_SECRET, exp)));
}

// Los cambios solo se aceptan desde el mismo sitio (además de la cookie SameSite=Strict).
export function sameOrigin(request) {
  const origin = request.headers.get('origin');
  return origin !== null && origin === new URL(request.url).origin;
}

export async function login(request, env) {
  if (!sameOrigin(request)) return json({ error: 'origen no permitido' }, 403);
  if (!env.ADMIN_PASSWORD_HASH || !env.SESSION_SECRET) return json({ error: 'El panel aún no tiene contraseña configurada.' }, 503);
  const ip = request.headers.get('cf-connecting-ip') || 'local';
  const key = `login:${ip}`;
  const fails = Number((await env.TASAS.get(key)) || 0);
  if (fails >= LOGIN_MAX) return json({ error: 'Demasiados intentos. Espera 15 minutos.' }, 429);
  let body = {};
  try { body = await request.json(); } catch { /* cuerpo vacío o inválido */ }
  if (!(await checkPassword(body.password, env.ADMIN_PASSWORD_HASH))) {
    await env.TASAS.put(key, String(fails + 1), { expirationTtl: 900 });
    return json({ error: 'Contraseña incorrecta.' }, 401);
  }
  await env.TASAS.delete(key);
  return json({ ok: true }, 200, { 'set-cookie': await sessionCookie(env) });
}

// ------------------------------------------------------------------ tasas

export async function loadRates(env) {
  let s;
  try { s = JSON.parse((await env.TASAS.get('tasas')) || 'null'); } catch { s = null; }
  return coclZero(s || { rates: {}, status: {}, bcv_manual: null, updated: null });
}
// Colombia → Chile pasó a la tasa "con cero adelante" (COP × 0,2850 = CLP). Una tasa fija guardada al estilo
// antiguo (COP ÷ 3,50) se convierte sola a su equivalente (1 ÷ 3,50 = 0,2857): el cliente recibe exactamente lo mismo.
export function coclZero(s) {
  const f = rateNum(s?.cocl?.fixed);
  if (f && f >= 1) s.cocl = { ...s.cocl, fixed: (1 / f).toFixed(4) };
  return s;
}

// Estado de cada ruta: 'on' calcula con la tasa · 'ask' mercado inestable, tasa por WhatsApp · 'off' no se muestra.
export const STATUSES = ['on', 'ask', 'off'];

export function statusOf(saved, id) {
  const s = saved?.status?.[id];
  if (STATUSES.includes(s)) return s;
  if (!String(saved?.rates?.[id] ?? '').trim()) return 'off';  // ruta nueva sin tasa todavía: apagada hasta que se active
  return saved?.active?.[id] === false ? 'off' : 'on';  // datos guardados antes de existir los estados
}

export function validate(body) {
  const errors = [];
  const rates = {}, status = {};
  for (const r of ROUTES) {
    const raw = String(body?.rates?.[r.id] ?? '').trim();
    const st = statusOf(body, r.id);
    if (st === 'on' && !r.auto && !rateNum(raw)) errors.push(r.id);  // la tasa se guarda aunque esté en pausa (las automáticas no la llevan)
    rates[r.id] = raw;
    status[r.id] = st;
  }
  const manual = (v) => (v == null || String(v).trim() === '' ? null : String(v).trim());
  const bcv = manual(body?.bcv_manual), bcvEur = manual(body?.bcv_manual_eur);
  if (bcv !== null && !rateNum(bcv)) errors.push('bcv');
  if (bcvEur !== null && !rateNum(bcvEur)) errors.push('bcv_eur');
  // Datos del proveedor para calcular Brasil: solo se guardan para el panel, nunca se publican.
  const brl = body?.brl && typeof body.brl === 'object'
    ? { ref: String(body.brl.ref ?? '').slice(0, 20), margin_pct: String(body.brl.margin_pct ?? '').slice(0, 10),
        auto: body.brl.auto === true, cal_cross: Number(body.brl.cal_cross) > 0 ? Number(body.brl.cal_cross) : null } : null;
  // Colombia → Chile: la ganancia (%) calcula la sugerida; la tasa fija (si la hay) es la que se publica.
  const m = String(body?.cocl?.margin_pct ?? '3').trim().replace(',', '.');
  if (!(m !== '' && Number(m) >= 0 && Number(m) <= 50)) errors.push('co-cl-margen');
  const fixed = manual(body?.cocl?.fixed);
  if (fixed !== null && !(rateNum(fixed) < 1)) errors.push('co-cl-fija');  // con cero adelante (ej. 0.2850)
  return { errors, data: { rates, status, bcv_manual: bcv, bcv_manual_eur: bcvEur, cocl: { margin_pct: m, fixed }, ...(brl ? { brl } : {}) } };
}

export async function saveRates(request, env, now = Date.now()) {
  if (!sameOrigin(request)) return json({ error: 'origen no permitido' }, 403);
  if (!(await isAdmin(request, env, now))) return json({ error: 'Inicia sesión de nuevo.' }, 401);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'datos inválidos' }, 400); }
  const { errors, data } = validate(body);
  if (errors.length) return json({ error: 'Hay tasas inválidas.', fields: errors }, 400);
  const saved = { ...data, updated: now };
  await env.TASAS.put('tasas', JSON.stringify(saved));
  return json(await publicView(env, saved, now));
}

// ------------------------------------------------------------------ dólar BCV

// La página del BCV muestra cada moneda en <div id="dolar"> / <div id="euro"> … <strong> 36,56230000 </strong>.
export function parseBcv(html, id = 'dolar') {
  const m = new RegExp(`id=["']${id}["'][\\s\\S]{0,600}?<strong>\\s*([\\d.,]+)\\s*<\\/strong>`, 'i').exec(html || '');
  if (!m) return null;
  const v = parseFloat(m[1].replace(/\./g, '').replace(',', '.'));
  if (!(v > 0)) return null;
  const d = /Fecha Valor:[\s\S]{0,300}?content=["']([^"']+)["']/i.exec(html);
  return { value: v, date: d ? d[1].slice(0, 10) : null };
}

// Respaldo: DolarApi publica una copia del dólar oficial del BCV (fuente no oficial).
// Respuesta esperada: {"fuente":"oficial","promedio":36.56,"fechaActualizacion":"2026-10-21T..."}
export function parseDolarApi(text) {
  let d;
  try { d = JSON.parse(text); } catch { return null; }
  const v = Number(d?.promedio ?? d?.precio);
  if (!(v > 0)) return null;
  return { value: v, date: typeof d.fechaActualizacion === 'string' ? d.fechaActualizacion.slice(0, 10) : null };
}

// Dólar y euro oficiales: misma página del BCV y, de respaldo, la copia de DolarApi.
const BCV_SOURCES = {
  usd: [
    { name: 'bcv', url: BCV_URL, parse: (t) => parseBcv(t, 'dolar') },
    { name: 'dolarapi', url: 'https://ve.dolarapi.com/v1/dolares/oficial', parse: parseDolarApi },
  ],
  eur: [
    { name: 'bcv', url: BCV_URL, parse: (t) => parseBcv(t, 'euro') },
    { name: 'dolarapi', url: 'https://ve.dolarapi.com/v1/euros/oficial', parse: parseDolarApi },
  ],
};
const BCV_KEYS = { usd: ['bcv', 'bcv_err'], eur: ['bcv_eur', 'bcv_eur_err'] };
const BCV_RETRY_S = 600;  // si todas las fuentes fallan, no se reintenta en cada visita

async function tryBcvSources(cur) {
  const errors = [];
  for (const s of BCV_SOURCES[cur]) {
    try {
      const res = await fetch(s.url, { headers: { 'user-agent': 'Mozilla/5.0 (cotizador JM Cambios)', accept: '*/*' }, signal: AbortSignal.timeout(6000) });
      if (!res.ok) { errors.push(`${s.name}: respondió ${res.status}`); continue; }
      const got = s.parse(await res.text());
      if (got) return { got: { ...got, source: s.name }, errors };
      errors.push(`${s.name}: no se encontró el valor en la respuesta`);
    } catch (e) {
      errors.push(`${s.name}: ${e?.name === 'TimeoutError' ? 'no respondió a tiempo' : (e?.message || 'error de conexión')}`);
    }
  }
  return { got: null, errors };
}

export async function bcv(env, manual, now = Date.now(), cur = 'usd') {
  const [key, errKey] = BCV_KEYS[cur];
  let cached = null, fail = null;
  try { cached = JSON.parse((await env.TASAS.get(key)) || 'null'); } catch { cached = null; }
  if (cached && now - cached.ts < BCV_TTL_S * 1000) return { value: cached.value, date: cached.date, source: cached.source || 'bcv' };
  try { fail = JSON.parse((await env.TASAS.get(errKey)) || 'null'); } catch { fail = null; }
  if (!fail || now - fail.ts >= BCV_RETRY_S * 1000) {
    const { got, errors } = await tryBcvSources(cur);
    if (got) {
      await env.TASAS.put(key, JSON.stringify({ ...got, ts: now }));
      await env.TASAS.delete(errKey);
      return got;
    }
    fail = { ts: now, errors };
    await env.TASAS.put(errKey, JSON.stringify(fail));
  }
  const why = fail?.errors || [];
  if (manual && rateNum(manual)) return { value: rateNum(manual), date: null, source: 'manual', errors: why };
  if (cached) return { value: cached.value, date: cached.date, source: 'bcv-anterior', errors: why };
  return { value: null, date: null, source: null, errors: why };
}

// Brasil automático: solo se publica un factor combinado (proveedor y ganancia no se pueden separar)
// y el valor del mercado al calibrar. Tasa = (reales por peso del mercado ahora) × k.
export function brlAuto(b) {
  if (!b?.auto || !(b.cal_cross > 0)) return null;
  const ref = Number(String(b.ref || '').replace(/\./g, '').replace(',', '.'));
  const m = Number(String(b.margin_pct || '').replace(',', '.'));
  if (!(ref > 0) || !(m >= 0 && m <= 50)) return null;
  const gap = (ref / 100000) / b.cal_cross;  // cuánto da el proveedor frente al mercado (ej. 0,968)
  return { k: Number((gap / (1 + m / 100)).toFixed(6)), cal: b.cal_cross };
}

export async function publicView(env, saved, now = Date.now()) {
  const s = saved || (await loadRates(env));
  return {
    updated: s.updated,
    // Con mercado inestable no se publica la tasa guardada: el cliente la pide por WhatsApp.
    routes: ROUTES.map((r) => {
      let status = statusOf(s, r.id);
      if (status === 'on' && !r.auto && !rateNum(s.rates[r.id])) status = 'off';
      const out = { id: r.id, status, rate: status === 'on' && !r.auto ? s.rates[r.id] : '', active: status === 'on' };
      if (r.auto && status === 'on') {
        // Con tasa fija se publica esa; sin ella, el navegador la calcula en vivo con CriptoYa (Vita + ganancia).
        if (rateNum(s.cocl?.fixed)) { out.rate = s.cocl.fixed; out.fixed = true; } else out.margin_pct = s.cocl?.margin_pct ?? '3';
      }
      if (r.id === 'cl-br' && status === 'on') { const a = brlAuto(s.brl); if (a) out.auto = a; }
      return out;
    }),
    bcv: await bcv(env, s.bcv_manual, now),
    bcv_eur: await bcv(env, s.bcv_manual_eur, now, 'eur'),
  };
}

// ------------------------------------------------------------------ Apagar todo

// Un solo interruptor para apagar (y volver a encender) todas las tasas, sin tocar las guardadas.
export const isPaused = async (env) => (await env.TASAS.get('paused')) === '1';

export async function setPaused(request, env, now = Date.now()) {
  if (!sameOrigin(request)) return json({ error: 'origen no permitido' }, 403);
  if (!(await isAdmin(request, env, now))) return json({ error: 'Inicia sesión de nuevo.' }, 401);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'datos inválidos' }, 400); }
  if (typeof body?.paused !== 'boolean') return json({ error: 'datos inválidos' }, 400);
  await env.TASAS.put('paused', body.paused ? '1' : '0');
  return json({ paused: body.paused });
}

// ------------------------------------------------------------------ USDT/CLP (solo panel)

// Referencia del precio del USDT en pesos chilenos para la calculadora del panel (CriptoYa, API pública).
const USDT_TTL_S = 120;

export async function loadUsdtCfg(env) {
  try { return { margin_pct: '8', buy_margin_pct: '8', manual: null, published: false, ...JSON.parse((await env.TASAS.get('usdt_cfg')) || '{}') }; }
  catch { return { margin_pct: '8', buy_margin_pct: '8', manual: null, published: false }; }
}

export async function usdtRef(env, manual, now = Date.now()) {
  let cached = null;
  try { cached = JSON.parse((await env.TASAS.get('usdt')) || 'null'); } catch { cached = null; }
  if (cached && now - cached.ts < USDT_TTL_S * 1000) return { ...cached, age_s: Math.round((now - cached.ts) / 1000) };
  let error;
  try {
    const res = await fetch(USDT_URL, {
      headers: { accept: 'application/json', 'user-agent': 'JMCambios-cotizador/1.0 (+https://jmcambios.cl)' },
      signal: AbortSignal.timeout(6000),
    });
    const got = res.ok ? parseCriptoYa(await res.text()) : null;
    if (got) {
      const fresh = { ...got, ts: now };
      await env.TASAS.put('usdt', JSON.stringify(fresh));
      return { ...fresh, age_s: 0 };
    }
    error = res.ok ? 'respuesta sin precio válido' : `respondió ${res.status}`;
  } catch (e) {
    error = e?.name === 'TimeoutError' ? 'no respondió a tiempo' : (e?.message || 'error de conexión');
  }
  if (manual && rateNum(manual)) return { value: rateNum(manual), source: 'manual', ts: now, age_s: 0, error };
  if (cached) return { ...cached, age_s: Math.round((now - cached.ts) / 1000), error };
  return { value: null, source: null, ts: null, age_s: null, error };
}

export async function usdtView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  const cfg = await loadUsdtCfg(env);
  return json({ ...cfg, ref: await usdtRef(env, cfg.manual, now) });
}

export async function saveUsdtCfg(request, env, now = Date.now()) {
  if (!sameOrigin(request)) return json({ error: 'origen no permitido' }, 403);
  if (!(await isAdmin(request, env, now))) return json({ error: 'Inicia sesión de nuevo.' }, 401);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'datos inválidos' }, 400); }
  const pct = (v) => { const t = String(v ?? '').trim().replace(',', '.'); return t !== '' && Number(t) >= 0 && Number(t) <= 50 ? t : null; };
  const margin = pct(body?.margin_pct);
  if (margin === null) return json({ error: 'La ganancia debe estar entre 0 y 50 %.' }, 400);
  // Ganancia al comprar USDT (precio de compra = bid − %). Si no viene, se mantiene la guardada.
  const buy = body?.buy_margin_pct == null ? (await loadUsdtCfg(env)).buy_margin_pct : pct(body.buy_margin_pct);
  if (buy === null) return json({ error: 'La ganancia al comprar debe estar entre 0 y 50 %.' }, 400);
  const manual = body?.manual == null || String(body.manual).trim() === '' ? null : String(body.manual).trim();
  if (manual !== null && !rateNum(manual)) return json({ error: 'El valor manual no es válido.' }, 400);
  const source = body?.source == null ? ((await loadUsdtCfg(env)).source ?? '') : srcOk(body.source);
  if (source === null) return json({ error: 'Elige una referencia válida.' }, 400);
  const cfg = { margin_pct: margin, buy_margin_pct: buy, manual, source, published: body?.published === true };
  await env.TASAS.put('usdt_cfg', JSON.stringify(cfg));
  return json({ ...cfg, ref: await usdtRef(env, manual, now) });
}

// ------------------------------------------------------------------ USDT/COP (venta al cliente en Colombia)

// Colombia: vender USDT al cliente y también comprárselo (precio de compra = bid de Binance P2P − ganancia al comprar).
const COP_CFG = { margin_pct: '2', min: '50000', published: false, buy_margin_pct: '3', buy_min: '50000' };
export async function loadUsdtCoCfg(env) {
  try { return { ...COP_CFG, ...JSON.parse((await env.TASAS.get('usdt_co_cfg')) || '{}') }; } catch { return { ...COP_CFG }; }
}
export async function usdtCoView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadUsdtCoCfg(env));
}
export async function saveUsdtCoCfg(request, env, now = Date.now()) {
  if (!sameOrigin(request)) return json({ error: 'origen no permitido' }, 403);
  if (!(await isAdmin(request, env, now))) return json({ error: 'Inicia sesión de nuevo.' }, 401);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'datos inválidos' }, 400); }
  const m = String(body?.margin_pct ?? '').trim().replace(',', '.');
  if (!(m !== '' && Number(m) >= 0 && Number(m) <= 50)) return json({ error: 'La ganancia debe estar entre 0 y 50 %.' }, 400);
  const min = String(body?.min ?? '').replace(/\D/g, '');
  if (!(Number(min) >= 1000 && Number(min) <= 100000000)) return json({ error: 'El mínimo no es válido.' }, 400);
  const bm = String(body?.buy_margin_pct ?? '3').trim().replace(',', '.');
  if (!(bm !== '' && Number(bm) >= 0 && Number(bm) <= 50)) return json({ error: 'La ganancia al comprar debe estar entre 0 y 50 %.' }, 400);
  const bmin = String(body?.buy_min ?? min).replace(/\D/g, '');
  if (!(Number(bmin) >= 1000 && Number(bmin) <= 100000000)) return json({ error: 'El mínimo al comprar no es válido.' }, 400);
  const source = srcOk(body?.source ?? '');
  if (source === null) return json({ error: 'Elige una referencia válida.' }, 400);
  const cfg = { margin_pct: m, min, published: body?.published === true, buy_margin_pct: bm, buy_min: bmin, source };
  await env.TASAS.put('usdt_co_cfg', JSON.stringify(cfg));
  return json(cfg);
}

// ------------------------------------------------------------------ USDT Brasil y oro tokenizado (Chile y Colombia)
// El precio lo calcula el navegador del cliente (CriptoYa / CoinGecko) con estas ganancias; aquí solo se guardan.
// Exchange de referencia elegido en el panel ('' = automático, como antes).
const srcOk = (v) => { const s = String(v ?? '').trim(); return s === '' || /^[a-z0-9_]{2,30}$/i.test(s) ? s : null; };
const pctOk = (v) => { const t = String(v ?? '').trim().replace(',', '.'); return t !== '' && Number(t) >= 0 && Number(t) <= 50 ? t : null; };
async function loadCfg(env, key, defaults) {
  try { return { ...defaults, ...JSON.parse((await env.TASAS.get(key)) || '{}') }; } catch { return { ...defaults }; }
}
async function adminBody(request, env, now) {
  if (!sameOrigin(request)) return { error: json({ error: 'origen no permitido' }, 403) };
  if (!(await isAdmin(request, env, now))) return { error: json({ error: 'Inicia sesión de nuevo.' }, 401) };
  try { return { body: await request.json() }; } catch { return { error: json({ error: 'datos inválidos' }, 400) }; }
}

export const BR_CFG = { margin_pct: '3', buy_margin_pct: '3', published: false };
export const loadUsdtBrCfg = (env) => loadCfg(env, 'usdt_br_cfg', BR_CFG);
export async function usdtBrView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadUsdtBrCfg(env));
}
export async function saveUsdtBrCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const m = pctOk(body?.margin_pct), b = pctOk(body?.buy_margin_pct);
  if (m === null || b === null) return json({ error: 'Las ganancias deben estar entre 0 y 50 %.' }, 400);
  const source = srcOk(body?.source ?? '');
  if (source === null) return json({ error: 'Elige una referencia válida.' }, 400);
  const cfg = { margin_pct: m, buy_margin_pct: b, published: body?.published === true, source, usdc: body?.usdc === true };
  await env.TASAS.put('usdt_br_cfg', JSON.stringify(cfg));
  return json(cfg);
}

// Comisión de red al enviar el oro al cliente (dólares por envío), opcional: se descuenta de lo que recibe al comprar.
export const GOLD_CFG = { margin_pct: '3', buy_margin_pct: '3', cl: false, co: false, fee_on: false, fee_paxg: '1', fee_xaut: '1', xaut: true, paxg: false, private: false };
export const loadGoldCfg = (env) => loadCfg(env, 'gold_cfg', GOLD_CFG);
export async function goldView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadGoldCfg(env));
}
export async function saveGoldCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const m = pctOk(body?.margin_pct), b = pctOk(body?.buy_margin_pct);
  if (m === null || b === null) return json({ error: 'Las ganancias deben estar entre 0 y 50 %.' }, 400);
  const usd = (v, d) => { const t = String(v ?? d).trim().replace(',', '.'); return t !== '' && Number(t) >= 0 && Number(t) <= 50 ? t : null; };
  const fp = usd(body?.fee_paxg, '1'), fx = usd(body?.fee_xaut, '1');
  if (fp === null || fx === null) return json({ error: 'La comisión de red debe estar entre 0 y 50 dólares.' }, 400);
  const cfg = { margin_pct: m, buy_margin_pct: b, cl: body?.cl === true, co: body?.co === true, fee_on: body?.fee_on === true, fee_paxg: fp, fee_xaut: fx,
    xaut: body?.xaut !== false, paxg: body?.paxg === true, private: body?.private === true };
  await env.TASAS.put('gold_cfg', JSON.stringify(cfg));
  return json(cfg);
}

export const BTC_CFG = { margin_pct: '3', buy_margin_pct: '3', cl: false, co: false, private: false };
export const loadBtcCfg = (env) => loadCfg(env, 'btc_cfg', BTC_CFG);
export async function btcView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadBtcCfg(env));
}
export async function saveBtcCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const m = pctOk(body?.margin_pct), b = pctOk(body?.buy_margin_pct);
  if (m === null || b === null) return json({ error: 'Las ganancias deben estar entre 0 y 50 %.' }, 400);
  const cfg = { margin_pct: m, buy_margin_pct: b, cl: body?.cl === true, co: body?.co === true, private: body?.private === true };
  await env.TASAS.put('btc_cfg', JSON.stringify(cfg));
  return json(cfg);
}

// ------------------------------------------------------------------ Precio del oro (PAXG) y Bitcoin en dólares, leído por el servidor
// El navegador no siempre puede leer Binance o CoinGecko (bloqueos entre sitios); el servidor sí. Se prueban varias fuentes
// públicas en orden y se guarda 2 minutos. El cotizador lo multiplica por el USDT en pesos (CriptoYa).
const CRYPTO_TTL_S = 120;
const okGold = (v) => Number.isFinite(v) && v >= 500 && v <= 30000;
const okBtc = (v) => Number.isFinite(v) && v >= 5000 && v <= 1000000;
export const CRYPTO_SOURCES = [
  ['binance', 'https://data-api.binance.vision/api/v3/ticker/price?symbols=%5B%22PAXGUSDT%22,%22BTCUSDT%22%5D', (d) => {
    const px = (s) => Number(Array.isArray(d) ? d.find((x) => x?.symbol === s)?.price : NaN); return { PAXG: px('PAXGUSDT'), BTC: px('BTCUSDT') }; }],
  ['binance', 'https://api.binance.com/api/v3/ticker/price?symbols=%5B%22PAXGUSDT%22,%22BTCUSDT%22%5D', (d) => {
    const px = (s) => Number(Array.isArray(d) ? d.find((x) => x?.symbol === s)?.price : NaN); return { PAXG: px('PAXGUSDT'), BTC: px('BTCUSDT') }; }],
  ['kraken', 'https://api.kraken.com/0/public/Ticker?pair=PAXGUSD,XBTUSD', (d) => {
    const r = d?.result || {}; const k = (re) => Number(r[Object.keys(r).find((x) => re.test(x))]?.c?.[0]);
    return { PAXG: k(/^PAXG/), BTC: k(/^X?XBTZ?USD/) }; }],
  ['coingecko', 'https://api.coingecko.com/api/v3/simple/price?ids=pax-gold,bitcoin&vs_currencies=usd', (d) => ({ PAXG: Number(d?.['pax-gold']?.usd), BTC: Number(d?.bitcoin?.usd) })],
];
export async function cryptoUsd(env, now = Date.now()) {
  let cached = null;
  try { cached = JSON.parse((await env.TASAS.get('crypto_usd2')) || 'null'); } catch { cached = null; }
  if (cached && now - cached.ts < CRYPTO_TTL_S * 1000) return cached;
  const out = { ts: now, tries: [] };
  for (const [name, url, read] of CRYPTO_SOURCES) {
    if (out.PAXG && out.BTC) break;
    try {
      const res = await fetch(url, { headers: { accept: 'application/json', 'user-agent': 'JMCambios-cotizador/1.0' }, cf: { cacheTtl: 60 } });
      out.tries.push(`${name}:${res.status}`);
      if (!res.ok) continue;
      const v = read(await res.json());
      if (!out.PAXG && okGold(v.PAXG)) { out.PAXG = v.PAXG; out.paxg_src = name; }
      if (!out.BTC && okBtc(v.BTC)) { out.BTC = v.BTC; out.btc_src = name; }
    } catch { out.tries.push(`${name}:error`); }
  }
  // USDT en pesos (Binance P2P vía CriptoYa; si no viene, el respaldo de siempre), para Chile y Colombia.
  const text = async (u) => { try { const r = await fetch(u, { headers: { accept: 'application/json' } }); out.tries.push(`criptoya:${r.status}`); return r.ok ? await r.text() : null; } catch { out.tries.push('criptoya:error'); return null; } };
  if (out.PAXG || out.BTC) {
    const [c, o] = await Promise.all([text(USDT_URL), text(USDT_COP_URL)]);
    const clp = c && (binanceP2pAsk(c, CLP_RANGE) ?? parseCriptoYa(c)?.value), cop = o && (binanceP2pAsk(o, COP_RANGE) ?? usdtCopRef(o)?.value);
    if (clp) out.USDT_CLP = clp;
    if (cop) out.USDT_COP = cop;
  }
  if (out.PAXG || out.BTC) await env.TASAS.put('crypto_usd2', JSON.stringify(out));
  else if (cached && now - cached.ts < 30 * 60 * 1000) return { ...cached, stale: true, tries: out.tries };  // respaldo: último precio (máx. 30 min)
  return out;
}

// ------------------------------------------------------------------ Brasil → Colombia (automática)
export const BRCO_CFG = { margin_pct: '2', profit_pct: '0', min: '50', source: 'bitget', published: false };
// Ajuste total que usa el cotizador: costo de compra + tu ganancia (se suman).
export const brCoTotalPct = (c) => String(Math.round((Number(c.margin_pct || 0) + Number(c.profit_pct || 0)) * 1000) / 1000);
export const loadBrCoCfg = (env) => loadCfg(env, 'brco_cfg', BRCO_CFG);
export async function brCoView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadBrCoCfg(env));
}
export async function saveBrCoCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const m = pctOk(body?.margin_pct);
  if (m === null) return json({ error: 'El ajuste de precio debe estar entre 0 y 50 %.' }, 400);
  const p = pctOk(body?.profit_pct ?? '0');
  if (p === null) return json({ error: 'Tu ganancia debe estar entre 0 y 50 %.' }, 400);
  const min = String(body?.min ?? '').replace(/\D/g, '');
  if (!(Number(min) >= 1 && Number(min) <= 10000000)) return json({ error: 'El mínimo no es válido.' }, 400);
  const source = String(body?.source ?? '').trim();
  if (!/^[a-z0-9_]{2,30}$/i.test(source)) return json({ error: 'Elige el exchange de referencia.' }, 400);
  const cfg = { margin_pct: m, profit_pct: p, min, source, published: body?.published === true };
  await env.TASAS.put('brco_cfg', JSON.stringify(cfg));
  return json(cfg);
}

// ------------------------------------------------------------------ Colombia → Brasil (automática)
export const COBR_CFG = { profit_pct: '0', min: '50000', source: 'bitget', published: false };
export const loadCoBrCfg = (env) => loadCfg(env, 'cobr_cfg', COBR_CFG);
export async function coBrView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadCoBrCfg(env));
}
export async function saveCoBrCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const p = pctOk(body?.profit_pct ?? '0');
  if (p === null) return json({ error: 'Tu ganancia debe estar entre 0 y 50 %.' }, 400);
  const min = String(body?.min ?? '').replace(/\D/g, '');
  if (!(Number(min) >= 1 && Number(min) <= 1000000000)) return json({ error: 'El mínimo no es válido.' }, 400);
  const source = String(body?.source ?? '').trim();
  if (!/^[a-z0-9_]{2,30}$/i.test(source)) return json({ error: 'Elige el exchange de referencia.' }, 400);
  const cfg = { profit_pct: p, min, source, published: body?.published === true };
  await env.TASAS.put('cobr_cfg', JSON.stringify(cfg));
  return json(cfg);
}

// ------------------------------------------------------------------ Brasil → Chile (automática)
export const BRCL_CFG = { profit_pct: '0', min: '50', source: 'bitget', published: false };
export const loadBrClCfg = (env) => loadCfg(env, 'brcl_cfg', BRCL_CFG);
export async function brClView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadBrClCfg(env));
}
export async function saveBrClCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const p = pctOk(body?.profit_pct ?? '0');
  if (p === null) return json({ error: 'Tu ganancia debe estar entre 0 y 50 %.' }, 400);
  const min = String(body?.min ?? '').replace(/\D/g, '');
  if (!(Number(min) >= 1 && Number(min) <= 10000000)) return json({ error: 'El mínimo no es válido.' }, 400);
  const source = String(body?.source ?? '').trim();
  if (!/^[a-z0-9_]{2,30}$/i.test(source)) return json({ error: 'Elige el exchange de referencia.' }, 400);
  const cfg = { profit_pct: p, min, source, published: body?.published === true };
  await env.TASAS.put('brcl_cfg', JSON.stringify(cfg));
  return json(cfg);
}

// ------------------------------------------------------------------ Estados Unidos → Chile (automática)
export const USCL_CFG = { profit_pct: '0', fee: '1', min: '20', published: false };
export const loadUsClCfg = (env) => loadCfg(env, 'uscl_cfg', USCL_CFG);
export async function usClView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadUsClCfg(env));
}
export async function saveUsClCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const p = pctOk(body?.profit_pct ?? '0');
  if (p === null) return json({ error: 'Tu comisión debe estar entre 0 y 50 %.' }, 400);
  const fee = String(body?.fee ?? '1').trim().replace(',', '.');
  if (!(fee !== '' && Number(fee) >= 0 && Number(fee) <= 50)) return json({ error: 'El cargo fijo debe estar entre 0 y 50 dólares.' }, 400);
  const min = String(body?.min ?? '').replace(/\D/g, '');
  if (!(Number(min) >= 1 && Number(min) <= 100000)) return json({ error: 'El mínimo no es válido.' }, 400);
  if (Number(min) <= Number(fee)) return json({ error: 'El mínimo debe ser mayor que el cargo fijo.' }, 400);
  const cfg = { profit_pct: p, fee, min, published: body?.published === true };
  await env.TASAS.put('uscl_cfg', JSON.stringify(cfg));
  return json(cfg);
}

// ------------------------------------------------------------------ Venezuela → Chile (automática)
export const VECO_CFG = { profit_pct: '0', min: '2000', source: 'bybitp2p', cop_source: 'binancep2p', published: false };
export const loadVeCoCfg = (env) => loadCfg(env, 'veco_cfg', VECO_CFG);
export async function veCoView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadVeCoCfg(env));
}
export async function saveVeCoCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const p = pctOk(body?.profit_pct ?? '0');
  if (p === null) return json({ error: 'Tu ganancia debe estar entre 0 y 50 %.' }, 400);
  const min = String(body?.min ?? '').replace(/\D/g, '');
  if (!(Number(min) >= 1 && Number(min) <= 100000000)) return json({ error: 'El mínimo no es válido.' }, 400);
  const ok = (v) => /^[a-z0-9_]{2,30}$/i.test(String(v ?? '').trim());
  if (!ok(body?.source)) return json({ error: 'Elige el P2P de bolívares.' }, 400);
  if (!ok(body?.cop_source)) return json({ error: 'Elige la referencia en Colombia.' }, 400);
  const cfg = { profit_pct: p, min, source: String(body.source).trim(), cop_source: String(body.cop_source).trim(), published: body?.published === true };
  await env.TASAS.put('veco_cfg', JSON.stringify(cfg));
  return json(cfg);
}
export const VECL_CFG = { margin_pct: '3', min: '2000', source: 'bybitp2p', published: false };
export const loadVeClCfg = (env) => loadCfg(env, 'vecl_cfg', VECL_CFG);
export async function veClView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json(await loadVeClCfg(env));
}
export async function saveVeClCfg(request, env, now = Date.now()) {
  const { body, error } = await adminBody(request, env, now);
  if (error) return error;
  const m = pctOk(body?.margin_pct);
  if (m === null) return json({ error: 'La ganancia debe estar entre 0 y 50 %.' }, 400);
  const min = String(body?.min ?? '').replace(/\D/g, '');
  if (!(Number(min) >= 1 && Number(min) <= 100000000)) return json({ error: 'El mínimo no es válido.' }, 400);
  const source = String(body?.source ?? '').trim();
  if (!/^[a-z0-9_]{2,30}$/i.test(source)) return json({ error: 'Elige el P2P de referencia.' }, 400);
  const cfg = { margin_pct: m, min, source, published: body?.published === true };
  await env.TASAS.put('vecl_cfg', JSON.stringify(cfg));
  return json(cfg);
}

// ------------------------------------------------------------------ JM Rewards (botón de registro en el cotizador)

// La dirección es fija (la app de JM Rewards); desde el panel solo se enciende o apaga el botón. Parte apagado.
export const REWARDS_URL = 'https://rewards.jmcambios.cl/';
export async function loadRewardsCfg(env) {
  try { return { published: false, ...JSON.parse((await env.TASAS.get('rewards_cfg')) || '{}') }; } catch { return { published: false }; }
}
export async function rewardsView(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'sin sesión' }, 401);
  return json({ ...(await loadRewardsCfg(env)), url: REWARDS_URL });
}
export async function saveRewardsCfg(request, env, now = Date.now()) {
  if (!sameOrigin(request)) return json({ error: 'origen no permitido' }, 403);
  if (!(await isAdmin(request, env, now))) return json({ error: 'Inicia sesión de nuevo.' }, 401);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'datos inválidos' }, 400); }
  const cfg = { published: body?.published === true };
  await env.TASAS.put('rewards_cfg', JSON.stringify(cfg));
  return json({ ...cfg, url: REWARDS_URL });
}
