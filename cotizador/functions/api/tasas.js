import { json, loadUsdtCfg, publicView, saveRates } from '../../lib/server.js';

// Público: tasas activas y dólar BCV para el cotizador.
// USDT desde Chile: aparece solo si está activado en el panel (para todos por igual).
export const onRequestGet = async ({ env }) => {
  const view = await publicView(env);
  delete view.bcv.errors;  // los motivos de falla solo se ven en el panel
  const cfg = await loadUsdtCfg(env);
  if (cfg.published) view.usdt = { margin_pct: cfg.margin_pct };
  return json(view);
};

// Solo el panel (sesión iniciada): guarda las tasas del día.
export const onRequestPut = async ({ request, env }) => saveRates(request, env);
