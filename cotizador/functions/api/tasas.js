import { edgeGet, edgePut, TASAS_VIEW_KEY, isPaused, json, loadBtcCfg, loadBrCoCfg, brCoTotalPct, loadCoBrCfg, loadBrClCfg, loadUsClCfg, loadGoldCfg, loadVeClCfg, loadVeCoCfg, loadBrVeCfg, loadEuClCfg, loadClEuCfg, loadCoPeCfg, loadCoEcCfg, loadCoEuCfg, loadRewardsCfg, loadUsdtBrCfg, loadUsdtCfg, loadUsdtCoCfg, publicView, REWARDS_URL, saveRates } from '../../lib/server.js';

// Público: tasas activas y dólar y euro BCV para el cotizador.
// USDT desde Chile: aparece solo si está activado en el panel (para todos por igual).
export const onRequestGet = async ({ env }) => {
  // Se guarda 30 s en la caché del borde: así cada visita no lee KV (límite diario). Al guardar en el panel se borra.
  const now = Date.now(), hit = await edgeGet(TASAS_VIEW_KEY);
  if (hit && now - hit.ts < 30 * 1000) return json(hit.view);
  const view = await buildView(env);
  await edgePut(TASAS_VIEW_KEY, { ts: now, view }, 30);
  return json(view);
};
async function buildView(env) {
  // Todo apagado desde el panel: el cotizador muestra "Actualizando tasas" y no se publica ninguna tasa.
  if (await isPaused(env)) return { paused: true, routes: [], bcv: null, bcv_eur: null };
  const view = await publicView(env);
  delete view.bcv.errors;  // los motivos de falla solo se ven en el panel
  delete view.bcv_eur.errors;
  const cfg = await loadUsdtCfg(env);
  if (cfg.published) view.usdt = { margin_pct: cfg.margin_pct, buy_margin_pct: cfg.buy_margin_pct, ...(cfg.source ? { source: cfg.source } : {}), ...(cfg.usdc ? { usdc: true } : {}) };
  const co = await loadUsdtCoCfg(env);
  if (co.published) view.usdt_co = { margin_pct: co.margin_pct, min: Number(co.min), buy_margin_pct: co.buy_margin_pct ?? '3', buy_min: Number(co.buy_min ?? co.min), ...(co.source ? { source: co.source } : {}), ...(co.usdc ? { usdc: true } : {}) };
  const br = await loadUsdtBrCfg(env);
  if (br.published) view.usdt_br = { margin_pct: br.margin_pct, buy_margin_pct: br.buy_margin_pct, ...(br.source ? { source: br.source } : {}), ...(br.usdc ? { usdc: true } : {}) };
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
  const coeu = await loadCoEuCfg(env);
  if (coeu.published) view.co_eu = { profit_pct: coeu.profit_pct, min: Number(coeu.min), cop_source: coeu.cop_source, clp_eur: coeu.clp_eur || '' };
  const coec = await loadCoEcCfg(env);
  if (coec.published) view.co_ec = { profit_pct: coec.profit_pct, min: Number(coec.min), cop_source: coec.cop_source, usd_source: coec.usd_source };
  const cope = await loadCoPeCfg(env);
  if (cope.published) view.co_pe = { profit_pct: cope.profit_pct, min: Number(cope.min), cop_source: cope.cop_source, pen_source: cope.pen_source };
  const cleu = await loadClEuCfg(env);
  if (cleu.published) view.cl_eu = { profit_pct: cleu.profit_pct, min: Number(cleu.min), mode: cleu.mode || 'auto', fixed: cleu.fixed || '' };
  const eucl = await loadEuClCfg(env);
  if (eucl.published) view.eu_cl = { profit_pct: eucl.profit_pct, eur_usdt: eucl.eur_usdt || '', min: Number(eucl.min), mode: eucl.mode || 'auto', premium_pct: eucl.premium_pct ?? '0' };
  const brve = await loadBrVeCfg(env);
  if (brve.published && brve.rate) view.br_ve = { rate: brve.rate, min: Number(brve.min) };
  const veco = await loadVeCoCfg(env);
  if (veco.published) view.ve_co = { profit_pct: veco.profit_pct, min: Number(veco.min), source: veco.source, cop_source: veco.cop_source };
  const vecl = await loadVeClCfg(env);
  if (vecl.published) view.ve_cl = { margin_pct: vecl.margin_pct, min: Number(vecl.min), source: vecl.source };
  if ((await loadRewardsCfg(env)).published) view.rewards = { url: REWARDS_URL };
  return view;
}

// Solo el panel (sesión iniciada): guarda las tasas del día.
export const onRequestPut = async ({ request, env }) => saveRates(request, env);
