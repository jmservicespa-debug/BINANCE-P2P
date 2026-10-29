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
// COP por cada CLP con la ganancia ya incluida (más alta = llegan menos CLP). null si falta algún precio.
export async function copPerClp(marginPct, fetchFn = fetch) {
  const [c, l] = await Promise.all([USDT_COP_URL, USDT_URL].map((u) => fetchFn(u, { cache: 'no-store' }).then((r) => (r.ok ? r.text() : null)).catch(() => null)));
  const cop = c && vitaPrice(c, 'ask', COP_RANGE), clp = l && vitaPrice(l, 'bid', CLP_RANGE);
  if (!cop || !clp) return null;
  const rate = (cop / clp) * (1 + Number(marginPct || 0) / 100);
  return rate >= 1 && rate <= 10 ? { rate, cop, clp } : null;
}
