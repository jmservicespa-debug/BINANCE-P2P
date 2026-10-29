import { isPaused, json, loadUsdtCfg, loadUsdtCoCfg, publicView, saveRates } from '../../lib/server.js';

// Público: tasas activas y dólar y euro BCV para el cotizador.
// USDT desde Chile: aparece solo si está activado en el panel (para todos por igual).
export const onRequestGet = async ({ env }) => {
  // Todo apagado desde el panel: el cotizador muestra "Actualizando tasas" y no se publica ninguna tasa.
  if (await isPaused(env)) return json({ paused: true, routes: [], bcv: null, bcv_eur: null });
  const view = await publicView(env);
  delete view.bcv.errors;  // los motivos de falla solo se ven en el panel
  delete view.bcv_eur.errors;
  const cfg = await loadUsdtCfg(env);
  if (cfg.published) view.usdt = { margin_pct: cfg.margin_pct, buy_margin_pct: cfg.buy_margin_pct };
  const co = await loadUsdtCoCfg(env);
  if (co.published) view.usdt_co = { margin_pct: co.margin_pct, min: Number(co.min) };
  return json(view);
};

// Solo el panel (sesión iniciada): guarda las tasas del día.
export const onRequestPut = async ({ request, env }) => saveRates(request, env);
