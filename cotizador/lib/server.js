// Lógica del servidor del cotizador (Cloudflare Pages Functions).
// Guarda las tasas en KV (`env.TASAS`), protege el panel con contraseña y lee el dólar BCV.

import { ROUTES, rateNum } from '../public/js/rutas.js';

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
  try { return JSON.parse((await env.TASAS.get('tasas')) || 'null') || { rates: {}, status: {}, bcv_manual: null, updated: null }; }
  catch { return { rates: {}, status: {}, bcv_manual: null, updated: null }; }
}

// Estado de cada ruta: 'on' calcula con la tasa · 'ask' mercado inestable, tasa por WhatsApp · 'off' no se muestra.
export const STATUSES = ['on', 'ask', 'off'];

export function statusOf(saved, id) {
  const s = saved?.status?.[id];
  if (STATUSES.includes(s)) return s;
  return saved?.active?.[id] === false ? 'off' : 'on';  // datos guardados antes de existir los estados
}

export function validate(body) {
  const errors = [];
  const rates = {}, status = {};
  for (const r of ROUTES) {
    const raw = String(body?.rates?.[r.id] ?? '').trim();
    const st = statusOf(body, r.id);
    if (st === 'on' && !rateNum(raw)) errors.push(r.id);  // la tasa se guarda aunque esté en pausa
    rates[r.id] = raw;
    status[r.id] = st;
  }
  const bcv = body?.bcv_manual == null || String(body.bcv_manual).trim() === '' ? null : String(body.bcv_manual).trim();
  if (bcv !== null && !rateNum(bcv)) errors.push('bcv');
  return { errors, data: { rates, status, bcv_manual: bcv } };
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

// La página del BCV muestra el dólar en <div id="dolar"> … <strong> 36,56230000 </strong>.
export function parseBcv(html) {
  const m = /id=["']dolar["'][\s\S]{0,600}?<strong>\s*([\d.,]+)\s*<\/strong>/i.exec(html || '');
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

const BCV_SOURCES = [
  { name: 'bcv', url: BCV_URL, parse: parseBcv },
  { name: 'dolarapi', url: 'https://ve.dolarapi.com/v1/dolares/oficial', parse: parseDolarApi },
];
const BCV_RETRY_S = 600;  // si todas las fuentes fallan, no se reintenta en cada visita

async function tryBcvSources() {
  const errors = [];
  for (const s of BCV_SOURCES) {
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

export async function bcv(env, manual, now = Date.now()) {
  let cached = null, fail = null;
  try { cached = JSON.parse((await env.TASAS.get('bcv')) || 'null'); } catch { cached = null; }
  if (cached && now - cached.ts < BCV_TTL_S * 1000) return { value: cached.value, date: cached.date, source: cached.source || 'bcv' };
  try { fail = JSON.parse((await env.TASAS.get('bcv_err')) || 'null'); } catch { fail = null; }
  if (!fail || now - fail.ts >= BCV_RETRY_S * 1000) {
    const { got, errors } = await tryBcvSources();
    if (got) {
      await env.TASAS.put('bcv', JSON.stringify({ ...got, ts: now }));
      await env.TASAS.delete('bcv_err');
      return got;
    }
    fail = { ts: now, errors };
    await env.TASAS.put('bcv_err', JSON.stringify(fail));
  }
  const why = fail?.errors || [];
  if (manual && rateNum(manual)) return { value: rateNum(manual), date: null, source: 'manual', errors: why };
  if (cached) return { value: cached.value, date: cached.date, source: 'bcv-anterior', errors: why };
  return { value: null, date: null, source: null, errors: why };
}

export async function publicView(env, saved, now = Date.now()) {
  const s = saved || (await loadRates(env));
  return {
    updated: s.updated,
    // Con mercado inestable no se publica la tasa guardada: el cliente la pide por WhatsApp.
    routes: ROUTES.map((r) => {
      let status = statusOf(s, r.id);
      if (status === 'on' && !rateNum(s.rates[r.id])) status = 'off';
      return { id: r.id, status, rate: status === 'on' ? s.rates[r.id] : '', active: status === 'on' };
    }),
    bcv: await bcv(env, s.bcv_manual, now),
  };
}
