// Seguimiento simple del cotizador: visitas, cotizaciones y clics en WhatsApp por día (hora de Chile) y por ruta.
// Solo números: no se guarda ningún dato de la persona (ni IP, ni teléfono, ni monto).
// Los conteos son aproximados: KV no suma de forma atómica (dos visitas en el mismo instante pueden contar como una).
import { ROUTES, USDT_ROUTE } from '../public/js/rutas.js';
import { isAdmin, json, sameOrigin } from './server.js';

export const EVENTS = ['visita', 'cotiza', 'whatsapp'];
const ROUTE_IDS = new Set([...ROUTES.map((r) => r.id), USDT_ROUTE.id, 'otro']);
const DAYS = 7;

export const chileDay = (ts) => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago' }).format(new Date(ts));
const key = (day) => `stats:${day}`;
const empty = () => ({ visita: 0, cotiza: 0, whatsapp: 0, rutas: {} });

async function load(env, day) {
  try { return { ...empty(), ...JSON.parse((await env.TASAS.get(key(day))) || 'null') }; } catch { return empty(); }
}

// Público (lo llama el cotizador): suma 1 al evento de hoy y, si viene, a su ruta.
export async function track(request, env, now = Date.now()) {
  if (!sameOrigin(request)) return json({ error: 'origen no permitido' }, 403);
  let body;
  try { body = await request.json(); } catch { return json({ error: 'datos inválidos' }, 400); }
  const e = body?.e, r = body?.r;
  if (!EVENTS.includes(e)) return json({ error: 'evento desconocido' }, 400);
  const day = chileDay(now);
  const s = await load(env, day);
  s[e] += 1;
  if (e !== 'visita' && ROUTE_IDS.has(r)) {
    s.rutas[r] = s.rutas[r] || { cotiza: 0, whatsapp: 0 };
    s.rutas[r][e] += 1;
  }
  await env.TASAS.put(key(day), JSON.stringify(s), { expirationTtl: 400 * 24 * 3600 });
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
  return json({ days });
}
