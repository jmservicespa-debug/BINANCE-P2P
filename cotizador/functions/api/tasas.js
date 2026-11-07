import { isPaused, json, loadBtcCfg, loadBrCoCfg, brCoTotalPct, loadCoBrCfg, loadBrClCfg, loadUsClCfg, loadGoldCfg, loadVeClCfg, loadRewardsCfg, loadUsdtBrCfg, loadUsdtCfg, loadUsdtCoCfg, publicView, REWARDS_URL, saveRates } from '../../lib/server.js';

// Público: tasas activas y dólar y euro BCV para el cotizador.
// USDT desde Chile: aparece solo si está activado en el panel (para todos por igual).
export const onRequestGet = async ({ env }) => {
  // Todo apagado desde el panel: el cotizador muestra "Actualizando tasas" y no se publica ninguna tasa.
  if (await isPaused(env)) return json({ paused: true, routes: [], bcv: null, bcv_eur: null });
  const view = await publicView(env);
  delete view.bcv.errors;  // los motivos de falla solo se ven en el panel
  delete view.bcv_eur.errors;
  const cfg = await loadUsdtCfg(env);
  if (cfg.published) view.usdt = { margin_pct: cfg.margin_pct, buy_margin_pct: cfg.buy_margin_pct, ...(cfg.source ? { source: cfg.source } : {}) };
  const co = await loadUsdtCoCfg(env);
  if (co.published) view.usdt_co = { margin_pct: co.margin_pct, min: Number(co.min), buy_margin_pct: co.buy_margin_pct ?? '3', buy_min: Number(co.buy_min ?? co.min), ...(co.source ? { source: co.source } : {}) };
  const br = await loadUsdtBrCfg(env);
  if (br.published) view.usdt_br = { margin_pct: br.margin_pct, buy_margin_pct: br.buy_margin_pct, ...(br.source ? { source: br.source } : {}) };
  const gold = await loadGoldCfg(env);
  if (gold.cl || gold.co) view.gold = { margin_pct: gold.margin_pct, buy_margin_pct: gold.buy_margin_pct, cl: gold.cl, co: gold.co,
    fee: gold.fee_on ? { PAXG: Number(gold.fee_paxg), XAUT: Number(gold.fee_xaut) } : null,
    tokens: [...(gold.xaut !== false ? ['XAUT'] : []), ...(gold.paxg === true ? ['PAXG'] : [])], private: gold.private === true };
  const btc = await loadBtcCfg(env);
  if (btc.cl || btc.co) view.btc = { margin_pct: btc.margin_pct, buy_margin_pct: btc.buy_margin_pct, cl: btc.cl, co: btc.co, private: btc.private === true };
  const uscl = await loadUsClCfg(env);
  if (uscl.published) view.us_cl = { profit_pct: uscl.profit_pct, fee: Number(uscl.fee), min: Number(uscl.min) };
  const brcl = await loadBrClCfg(env);
  if (brcl.published) view.br_cl = { profit_pct: brcl.profit_pct, min: Number(brcl.min), source: brcl.source };
  const cobr = await loadCoBrCfg(env);
  if (cobr.published) view.co_br = { profit_pct: cobr.profit_pct, min: Number(cobr.min), source: cobr.source };
  const brco = await loadBrCoCfg(env);
  if (brco.published) view.br_co = { margin_pct: brCoTotalPct(brco), min: Number(brco.min), source: brco.source };
  const vecl = await loadVeClCfg(env);
  if (vecl.published) view.ve_cl = { margin_pct: vecl.margin_pct, min: Number(vecl.min), source: vecl.source };
  if ((await loadRewardsCfg(env)).published) view.rewards = { url: REWARDS_URL };
  return json(view);
};

// Solo el panel (sesión iniciada): guarda las tasas del día.
export const onRequestPut = async ({ request, env }) => saveRates(request, env);
