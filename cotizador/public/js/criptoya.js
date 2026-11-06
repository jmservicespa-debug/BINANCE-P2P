// Lectura de la respuesta de CriptoYa (USDT/CLP). La usan el servidor y el panel (navegador).
// Se usa el precio de venta ("ask": lo que cuesta comprar USDT) y el de compra ("bid") de Vita Wallet, el proveedor de JM Cambios;
// si no viene, Binance P2P; y si tampoco, la mediana de los demás.

export const USDT_URL = 'https://criptoya.com/api/usdt/clp/1';
const USDT_RANGE = [300, 3000];  // CLP por USDT fuera de este rango = dato absurdo, se ignora

// Devuelve { value, source } con el precio de venta (ask) y, si viene, bid: lo que paga el mercado por cada USDT
// (base del precio al que JM Cambios compra USDT). Misma prioridad para los dos: Vita, Binance P2P, mediana.
export function parseCriptoYa(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const ok = (v) => Number.isFinite(v) && v >= USDT_RANGE[0] && v <= USDT_RANGE[1];
  const vitaKey = Object.keys(d).find((k) => /vita/i.test(k));
  const pick = (side) => {
    const v = Number(vitaKey && d[vitaKey]?.[side]);
    if (ok(v)) return { value: v, source: 'vita' };
    const b = Number(d.binancep2p?.[side]);
    if (ok(b)) return { value: b, source: 'binancep2p' };
    const all = Object.values(d).map((x) => Number(x?.[side])).filter(ok).sort((a, z) => a - z);
    return all.length ? { value: all[Math.floor(all.length / 2)], source: 'mediana' } : null;
  };
  const ask = pick('ask');
  if (!ask) return null;
  const bid = pick('bid');
  return bid ? { ...ask, bid: bid.value, bid_source: bid.source } : ask;
}

// Brasil automático: precio del USDT en reales (mediana de los exchanges que lista CriptoYa).
export const USDT_BRL_URL = 'https://criptoya.com/api/usdt/brl/1';
const BRL_RANGE = [2, 20];  // reales por USDT fuera de este rango = dato absurdo

export function parseBrl(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const asks = Object.values(d).map((x) => Number(x?.ask)).filter((v) => Number.isFinite(v) && v >= BRL_RANGE[0] && v <= BRL_RANGE[1]).sort((a, z) => a - z);
  return asks.length ? asks[Math.floor(asks.length / 2)] : null;
}

// Reales por cada peso chileno según el mercado cripto: (BRL por USDT) ÷ (CLP por USDT).
export async function brlPerClp(fetchFn = fetch) {
  const [c, b] = await Promise.all([USDT_URL, USDT_BRL_URL].map((u) => fetchFn(u, { cache: 'no-store' }).then((r) => (r.ok ? r.text() : null)).catch(() => null)));
  const clp = c && parseCriptoYa(c), brl = b && parseBrl(b);
  return clp && brl ? brl / clp.value : null;
}

export const BRL_BRAKE = 0.02;  // si el mercado se movió más de 2 % desde la calibración: "Mercado inestable"

// Colombia → Chile automático: con los pesos colombianos se compran USDT al precio de compra de Vita Wallet en Colombia (ask)
// y esos USDT se venden al precio que paga Vita Wallet en Chile (bid). Tasa = COP por cada CLP (COP ÷ tasa = CLP).
export const USDT_COP_URL = 'https://criptoya.com/api/usdt/cop/1';
export function vitaPrice(text, side, range) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  const key = d && typeof d === 'object' ? Object.keys(d).find((k) => /vita/i.test(k)) : null;
  const v = Number(key && d[key]?.[side]);
  return Number.isFinite(v) && v >= range[0] && v <= range[1] ? v : null;
}
export const COP_RANGE = [1500, 8000];  // COP por USDT fuera de este rango = dato absurdo
export const CLP_RANGE = [300, 3000];
// CLP por cada COP ("cero adelante", ej. 0,2850) con la ganancia ya incluida (más baja = llegan menos CLP).
// La ganancia se aplica igual que antes (COP por CLP × (1 + %)), solo que expresada al revés. null si falta algún precio.
export async function clpPerCop(marginPct, fetchFn = fetch) {
  const [c, l] = await Promise.all([USDT_COP_URL, USDT_URL].map((u) => fetchFn(u, { cache: 'no-store' }).then((r) => (r.ok ? r.text() : null)).catch(() => null)));
  const cop = c && vitaPrice(c, 'ask', COP_RANGE), clp = l && vitaPrice(l, 'bid', CLP_RANGE);
  if (!cop || !clp) return null;
  const rate = (clp / cop) / (1 + Number(marginPct || 0) / 100);
  return rate >= 0.1 && rate < 1 ? { rate, cop, clp } : null;
}

// Tasa SUGERIDA Chile → Venezuela (solo para el panel; la que se publica la decides tú), como la calcula JM Cambios:
// base 30.000 CLP (≈ 30 USDT), compra de USDT en Vita Wallet Chile (ask, su proveedor) y venta en Binance P2P Venezuela (bid)
// para un monto de ~30 USDT. CriptoYa no filtra por Pago Móvil: es una aproximación (Pago Móvil suele pagar algo menos).
export const SUG_CLP_URL = 'https://criptoya.com/api/usdt/clp/30';
export const SUG_VES_URL = 'https://criptoya.com/api/usdt/ves/30';
// Venezuela → Chile: USDT en bolívares (precio para comprar, "ask") del P2P elegido en el panel, y lo que paga Vita en CLP ("bid").
export const USDT_VES_URL = 'https://criptoya.com/api/usdt/ves/1';
const VES_RANGE = [5, 100000];
export function vesExchanges(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return []; }
  if (!d || typeof d !== 'object') return [];
  return Object.entries(d).filter(([, x]) => Number(x?.ask) >= VES_RANGE[0] && Number(x?.ask) <= VES_RANGE[1]).map(([k, x]) => ({ key: k, ask: Number(x.ask) }));
}
export async function clpPerVes(source, marginPct, fetchFn = fetch) {
  const [v, l] = await Promise.all([USDT_VES_URL, USDT_URL].map((u) => fetchFn(u, { cache: 'no-store' }).then((r) => (r.ok ? r.text() : null)).catch(() => null)));
  const list = v ? vesExchanges(v) : [];
  const ves = list.find((x) => x.key === source)?.ask, clp = l && vitaPrice(l, 'bid', CLP_RANGE);
  if (!ves || !clp) return null;
  const rate = clp / (ves * (1 + Number(marginPct || 0) / 100));
  return rate > 0 ? { rate, ves, clp } : null;
}
function pick(text, side, prefer, range) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const ok = (v) => Number.isFinite(v) && v >= range[0] && v <= range[1];
  for (const re of prefer) {
    const k = Object.keys(d).find((x) => re.test(x));
    const v = Number(k && d[k]?.[side]);
    if (ok(v)) return { value: v, source: k };
  }
  return null;
}
export async function marketClVe(fetchFn = fetch) {
  const [c, v] = await Promise.all([SUG_CLP_URL, SUG_VES_URL].map((u) => fetchFn(u, { cache: 'no-store' }).then((r) => (r.ok ? r.text() : null)).catch(() => null)));
  const clp = c && pick(c, 'ask', [/vita/i, /^binancep2p$/i], [300, 3000]);
  const ves = v && pick(v, 'bid', [/^binancep2p$/i], [10, 1e6]);
  return clp && ves ? { clp, ves, cross: ves.value / clp.value } : null;  // cross = Bs por cada CLP, sin ganancia
}

// USDT en pesos colombianos para vender al cliente: precio de venta (ask) de Binance P2P Colombia (donde se recompra);
// si no viene, Vita Wallet; si tampoco, la mediana de los demás.
// Lo que paga el mercado por cada USDT en Colombia (bid): Binance P2P, si no Vita, si no la mediana.
export function usdtCopBid(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const ok = (v) => Number.isFinite(v) && v >= COP_RANGE[0] && v <= COP_RANGE[1];
  const b = Number(d.binancep2p?.bid);
  if (ok(b)) return b;
  const vk = Object.keys(d).find((k) => /vita/i.test(k));
  const v = Number(vk && d[vk]?.bid);
  if (ok(v)) return v;
  const all = Object.values(d).map((x) => Number(x?.bid)).filter(ok).sort((a, z) => a - z);
  return all.length ? all[Math.floor(all.length / 2)] : null;
}
export function usdtCopRef(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const ok = (v) => Number.isFinite(v) && v >= COP_RANGE[0] && v <= COP_RANGE[1];
  const b = Number(d.binancep2p?.ask);
  if (ok(b)) return { value: b, source: 'binancep2p' };
  const vk = Object.keys(d).find((k) => /vita/i.test(k));
  const v = Number(vk && d[vk]?.ask);
  if (ok(v)) return { value: v, source: 'vita' };
  const all = Object.values(d).map((x) => Number(x?.ask)).filter(ok).sort((a, z) => a - z);
  return all.length ? { value: all[Math.floor(all.length / 2)], source: 'mediana' } : null;
}

// USDT en reales para comprar y vender en Brasil: Binance P2P; si no viene, Bybit P2P; si tampoco, la mediana.
export function usdtBrlRef(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const ok = (v) => Number.isFinite(v) && v >= BRL_RANGE[0] && v <= BRL_RANGE[1];
  const bybit = Object.keys(d).filter((k) => /bybit/i.test(k)).sort((a, b) => /p2p/i.test(b) - /p2p/i.test(a))[0];
  const pick = (side) => {
    const b = Number(d.binancep2p?.[side]);
    if (ok(b)) return { value: b, source: 'binancep2p' };
    const y = Number(bybit && d[bybit]?.[side]);
    if (ok(y)) return { value: y, source: 'bybitp2p' };
    const all = Object.values(d).map((x) => Number(x?.[side])).filter(ok).sort((a, z) => a - z);
    return all.length ? { value: all[Math.floor(all.length / 2)], source: 'mediana' } : null;
  };
  const ask = pick('ask');
  if (!ask) return null;
  const bid = pick('bid');
  return bid ? { ...ask, bid: bid.value, bid_source: bid.source } : ask;
}

// Oro tokenizado: precio de 1 PAXG y 1 XAUt (1 onza) en pesos chilenos y colombianos, de CoinGecko (API pública).
export const GOLD_URL = 'https://api.coingecko.com/api/v3/simple/price?ids=pax-gold,tether-gold,bitcoin&vs_currencies=usd,clp,cop';
const GOLD_RANGE = { usd: [500, 30000], clp: [500000, 30000000], cop: [2000000, 100000000] };  // fuera de esto = dato absurdo
const BTC_RANGE = { usd: [5000, 1000000], clp: [5000000, 1000000000], cop: [20000000, 4000000000] };
export function parseGold(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const out = {};
  for (const [id, token] of [['pax-gold', 'PAXG'], ['tether-gold', 'XAUT'], ['bitcoin', 'BTC']]) {
    for (const cur of ['usd', 'clp', 'cop']) {
      const v = Number(d[id]?.[cur]), R = token === 'BTC' ? BTC_RANGE : GOLD_RANGE;
      if (Number.isFinite(v) && v >= R[cur][0] && v <= R[cur][1]) (out[token] ??= {})[cur.toUpperCase()] = v;
    }
  }
  return Object.keys(out).length ? out : null;
}

// Precios del oro tokenizado y de Bitcoin en pesos: Binance (PAXG/USDT y BTC/USDT) × USDT en pesos (CriptoYa:
// Binance P2P en Chile y en Colombia). XAUt y PAXG representan 1 onza de oro: se usa el precio de PAXG para los dos.
// Si Binance no responde, se usa CoinGecko como respaldo. Devuelve { PAXG, XAUT, BTC: { USD, CLP, COP }, source }.
export const BINANCE_URLS = ['https://data-api.binance.vision/api/v3/ticker/price?symbols=%5B%22PAXGUSDT%22,%22BTCUSDT%22%5D',
  'https://api.binance.com/api/v3/ticker/price?symbols=%5B%22PAXGUSDT%22,%22BTCUSDT%22%5D'];
export function parseBinance(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!Array.isArray(d)) return null;
  const px = (sym) => Number(d.find((x) => x?.symbol === sym)?.price);
  const paxg = px('PAXGUSDT'), btc = px('BTCUSDT');
  const out = {};
  if (paxg >= 500 && paxg <= 30000) out.PAXG = paxg;
  if (btc >= 5000 && btc <= 1000000) out.BTC = btc;
  return Object.keys(out).length ? out : null;
}
export function coinPrices(usd, clp, cop) {
  if (!usd) return null;
  const per = (v) => ({ USD: v, ...(clp ? { CLP: v * clp } : {}), ...(cop ? { COP: v * cop } : {}) });
  const out = {};
  if (usd.PAXG) { out.PAXG = per(usd.PAXG); out.XAUT = per(usd.PAXG); }
  if (usd.BTC) out.BTC = per(usd.BTC);
  return Object.keys(out).length ? out : null;
}
export function binanceP2pAsk(text, range) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  const v = Number(d?.binancep2p?.ask);
  return Number.isFinite(v) && v >= range[0] && v <= range[1] ? v : null;
}
export async function marketCoins(fetchFn = fetch) {
  const get = (u) => fetchFn(u, { cache: 'no-store' }).then((r) => (r.ok ? r.text() : null)).catch(() => null);
  let usd = null;
  // 1) Nuestro servidor (lee Binance, Kraken o CoinGecko sin bloqueos). 2) Binance directo desde el navegador.
  try {
    const s = JSON.parse((await get('/api/precio-cripto')) || 'null');
    if (s?.PAXG || s?.BTC) usd = { ...(s.PAXG ? { PAXG: s.PAXG } : {}), ...(s.BTC ? { BTC: s.BTC } : {}) };
    // El servidor también trae el USDT en pesos: con eso basta, sin más consultas desde el navegador.
    const full = usd && coinPrices(usd, s.USDT_CLP, s.USDT_COP);
    if (full && (s.USDT_CLP || s.USDT_COP)) return { ...full, source: 'binance' };
  } catch { usd = null; }
  if (!usd) for (const u of BINANCE_URLS) { usd = parseBinance(await get(u)); if (usd) break; }
  if (usd) {
    const [c, o] = await Promise.all([get(USDT_URL), get(USDT_COP_URL)]);
    // Misma fuente en Chile y Colombia: USDT en Binance P2P (si no viene, el respaldo de siempre).
    const clp = c && (binanceP2pAsk(c, CLP_RANGE) ?? parseCriptoYa(c)?.value), cop = o && (binanceP2pAsk(o, COP_RANGE) ?? usdtCopRef(o)?.value);
    const out = coinPrices(usd, clp, cop);
    if (out && (clp || cop)) return { ...out, source: 'binance' };
  }
  const g = parseGold(await get(GOLD_URL));  // respaldo
  return g ? { ...g, source: 'coingecko' } : null;
}
