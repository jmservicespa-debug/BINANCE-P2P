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

// Pesos colombianos por USDT (Binance P2P vía CriptoYa; si no viene, mediana). Lado bid: lo que paga el mercado por USDT.
export const USDT_COP_URL = 'https://criptoya.com/api/usdt/cop/1';
export function parseCop(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const ok = (v) => Number.isFinite(v) && v >= 1000 && v <= 20000;
  if (ok(Number(d.binancep2p?.bid))) return Number(d.binancep2p.bid);
  const bids = Object.values(d).map((x) => Number(x?.bid)).filter(ok).sort((a, z) => a - z);
  return bids.length ? bids[Math.floor(bids.length / 2)] : null;
}

export const BRL_BRAKE = 0.02;  // si el mercado se movió más de 2 % desde la calibración: "Mercado inestable"
