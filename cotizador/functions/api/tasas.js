import { json, publicView, saveRates } from '../../lib/server.js';

// Público: tasas activas y dólar BCV para el cotizador.
export const onRequestGet = async ({ env }) => json(await publicView(env));

// Solo el panel (sesión iniciada): guarda las tasas del día.
export const onRequestPut = async ({ request, env }) => saveRates(request, env);
