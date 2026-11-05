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
const COP_RANGE = [1500, 8000];  // COP por USDT fuera de este rango = dato absurdo
const CLP_RANGE = [300, 3000];
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
export const GOLD_URL = 'https://api.coingecko.com/api/v3/simple/price?ids=pax-gold,tether-gold&vs_currencies=clp,cop';
const GOLD_RANGE = { clp: [500000, 30000000], cop: [2000000, 100000000] };  // fuera de esto = dato absurdo
export function parseGold(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const out = {};
  for (const [id, token] of [['pax-gold', 'PAXG'], ['tether-gold', 'XAUT']]) {
    for (const cur of ['clp', 'cop']) {
      const v = Number(d[id]?.[cur]);
      if (Number.isFinite(v) && v >= GOLD_RANGE[cur][0] && v <= GOLD_RANGE[cur][1]) (out[token] ??= {})[cur.toUpperCase()] = v;
    }
  }
  return Object.keys(out).length ? out : null;
}
