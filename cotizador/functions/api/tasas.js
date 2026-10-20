import { isAdmin, json, loadUsdtCfg, publicView, saveRates } from '../../lib/server.js';

// Público: tasas activas y dólar BCV para el cotizador.
// USDT desde Chile: solo si está publicado, o como vista previa para Jamer con la sesión del panel abierta.
export const onRequestGet = async ({ request, env }) => {
  const view = await publicView(env);
  delete view.bcv.errors;  // los motivos de falla solo se ven en el panel
  const cfg = await loadUsdtCfg(env);
  if (cfg.published || (await isAdmin(request, env))) view.usdt = { margin_pct: cfg.margin_pct, preview: !cfg.published };
  return json(view);
};

// Solo el panel (sesión iniciada): guarda las tasas del día.
export const onRequestPut = async ({ request, env }) => saveRates(request, env);
