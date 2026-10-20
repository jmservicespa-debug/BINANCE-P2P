// Lectura de la respuesta de CriptoYa (USDT/CLP). La usan el servidor y el panel (navegador).
// Se usa el precio de venta ("ask": lo que cuesta comprar USDT) de Vita Wallet, el proveedor de JM Cambios;
// si no viene, Binance P2P; y si tampoco, la mediana de los demás.

export const USDT_URL = 'https://criptoya.com/api/usdt/clp/1';
const USDT_RANGE = [300, 3000];  // CLP por USDT fuera de este rango = dato absurdo, se ignora

export function parseCriptoYa(text) {
  let d;
  try { d = typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; }
  if (!d || typeof d !== 'object') return null;
  const ok = (v) => Number.isFinite(v) && v >= USDT_RANGE[0] && v <= USDT_RANGE[1];
  const vitaKey = Object.keys(d).find((k) => /vita/i.test(k));
  const v = Number(vitaKey && d[vitaKey]?.ask);
  if (ok(v)) return { value: v, source: 'vita' };
  const b = Number(d.binancep2p?.ask);
  if (ok(b)) return { value: b, source: 'binancep2p' };
  const asks = Object.values(d).map((x) => Number(x?.ask)).filter(ok).sort((a, z) => a - z);
  if (!asks.length) return null;
  return { value: asks[Math.floor(asks.length / 2)], source: 'mediana' };
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
