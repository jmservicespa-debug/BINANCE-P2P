// Seguimiento simple del cotizador: visitas, cotizaciones y clics en WhatsApp por día (hora de Chile) y por ruta.
// Solo números: no se guarda ningún dato de la persona (ni IP, ni teléfono, ni monto).
// Los conteos son aproximados: KV no suma de forma atómica (dos visitas en el mismo instante pueden contar como una).
import { ROUTES, USDT_ROUTE } from '../public/js/rutas.js';
import { edgeGet, edgePut, isAdmin, json, sameOrigin } from './server.js';

export const EVENTS = ['visita', 'cotiza', 'whatsapp'];
const ROUTE_IDS = new Set([...ROUTES.map((r) => r.id), USDT_ROUTE.id, 'otro']);
const DAYS = 7;

export const chileDay = (ts) => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago' }).format(new Date(ts));
const key = (day) => `stats:${day}`;
const empty = () => ({ visita: 0, cotiza: 0, whatsapp: 0, rutas: {} });

async function load(env, day) {
  try { return { ...empty(), ...JSON.parse((await env.TASAS.get(key(day))) || 'null') }; } catch { return empty(); }
}


async function save(env, day, s) { await env.TASAS.put(key(day), JSON.stringify(s), { expirationTtl: 400 * 24 * 3600 }); }
// Suma lo acumulado en la caché al conteo guardado del día.
async function flush(env, buf) {
  if (!buf.s.visita && !buf.s.cotiza && !buf.s.whatsapp) return;
  const s = await load(env, buf.day);
  for (const k of EVENTS) s[k] += buf.s[k] || 0;
  for (const [rid, v] of Object.entries(buf.s.rutas || {})) { s.rutas[rid] = s.rutas[rid] || { cotiza: 0, whatsapp: 0 }; s.rutas[rid].cotiza += v.cotiza || 0; s.rutas[rid].whatsapp += v.whatsapp || 0; }
  await save(env, buf.day, s);
}

// Público (lo llama el cotizador): suma 1 al evento de hoy y, si viene, a su ruta.
export async function track(request, env, now = Date.now()) {
  if (!sameOrigin(request)) return json({ error: 'origen no permitido' }, 403);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'datos inválidos' }, 400); }
  const e = body?.e, r = body?.r;
  if (!EVENTS.includes(e)) return json({ error: 'evento desconocido' }, 400);
  if (await isAdmin(request, env, now)) return json({ ok: true, contado: false });  // el dueño con sesión del panel no se cuenta
  const day = chileDay(now);
  const add = (s) => {
    s[e] += 1;
    if (e !== 'visita' && ROUTE_IDS.has(r)) { s.rutas[r] = s.rutas[r] || { cotiza: 0, whatsapp: 0 }; s.rutas[r][e] += 1; }
  };
  // Para no gastar el límite diario de KV, los conteos se juntan en la caché del borde y se guardan cada 10 minutos.
  const edge = typeof caches !== 'undefined' && caches.default;
  if (!edge) { const s = await load(env, day); add(s); await save(env, day, s); return json({ ok: true }); }
  let buf = await edgeGet('stats_buf');
  if (buf && buf.day !== day) { await flush(env, buf); buf = null; }
  if (!buf) buf = { day, ts: now, s: empty() };
  add(buf.s);
  if (now - buf.ts >= 10 * 60 * 1000) { await flush(env, buf); buf = { day, ts: now, s: empty() }; }
  await edgePut('stats_buf', buf, 3 * 3600);
  return json({ ok: true });
}

// Solo el panel: los últimos 7 días (hoy primero).
export async function report(request, env, now = Date.now()) {
  if (!(await isAdmin(request, env, now))) return json({ error: 'Inicia sesión de nuevo.' }, 401);
  const days = [];
  for (let i = 0; i < DAYS; i++) {
    const day = chileDay(now - i * 24 * 3600 * 1000);
    days.push({ day, ...(await load(env, day)) });
  }
  // Suma lo que todavía está en la caché (los últimos minutos) para que el panel lo vea al tiro.
  const buf = await edgeGet('stats_buf');
  const d = buf && days.find((x) => x.day === buf.day);
  if (d) { for (const k of EVENTS) d[k] += buf.s[k] || 0;
    for (const [rid, v] of Object.entries(buf.s.rutas || {})) { d.rutas[rid] = d.rutas[rid] || { cotiza: 0, whatsapp: 0 }; d.rutas[rid].cotiza += v.cotiza || 0; d.rutas[rid].whatsapp += v.whatsapp || 0; } }
  return json({ days });
}
