import { json, publicView, saveRates } from '../../lib/server.js';

// Público: tasas activas y dólar BCV para el cotizador.
export const onRequestGet = async ({ env }) => {
  const view = await publicView(env);
  delete view.bcv.errors;  // los motivos de falla solo se ven en el panel
  return json(view);
};

// Solo el panel (sesión iniciada): guarda las tasas del día.
export const onRequestPut = async ({ request, env }) => saveRates(request, env);
