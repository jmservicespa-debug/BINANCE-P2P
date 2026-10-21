import { isAdmin, isPaused, json, loadRates, publicView } from '../../lib/server.js';

// Panel: si hay sesión, devuelve lo guardado (incluido el dólar BCV manual) y lo que ve el público.
export const onRequestGet = async ({ request, env }) => {
  if (!(await isAdmin(request, env))) return json({ error: 'sin sesión' }, 401);
  const saved = await loadRates(env);
  return json({ saved, view: await publicView(env, saved), paused: await isPaused(env) });
};
