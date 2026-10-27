// Indicadores para la franja que va pasando en el cotizador (solo informativos, no cambian ninguna tasa).
// Se leen en el servidor, se guardan 1 hora en KV y, si una fuente falla, ese dato simplemente no se muestra.
//   Colombia: TRM (datos abiertos, Superfinanciera), euro en pesos (TRM × euro/dólar del BCE), BTC en pesos (CoinGecko).
//   Brasil:   dólar y euro en reales (BCE vía Frankfurter).
//   Venezuela: USDT promedio en Binance P2P (CriptoYa). El dólar y el euro BCV ya vienen en /api/tasas.

export const SOURCES = {
  trm: 'https://www.datos.gov.co/resource/32sa-8pi3.json?$limit=1&$order=vigenciadesde%20DESC',
  fx: 'https://api.frankfurter.dev/v1/latest?base=USD&symbols=BRL,EUR',
  btc: 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=cop',
  usdtVes: 'https://criptoya.com/api/usdt/ves/1',
};
const TTL_S = 3600;
const RETRY_S = 600;  // si todo falló, no se reintenta en cada visita

const json = (text) => { try { return typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; } };
const pos = (v) => (Number.isFinite(v) && v > 0 ? v : null);

// [{"valor":"4123.45","unidad":"COP","vigenciadesde":"2026-10-27T00:00:00.000",...}]
export function parseTrm(text) {
  const row = json(text)?.[0];
  const v = pos(Number(row?.valor));
  return v ? { value: v, date: typeof row.vigenciadesde === 'string' ? row.vigenciadesde.slice(0, 10) : null } : null;
}

// {"amount":1,"base":"USD","date":"2026-10-27","rates":{"BRL":5.41,"EUR":0.92}} → reales por dólar, dólares por euro.
export function parseFx(text) {
  const d = json(text);
  const brl = pos(Number(d?.rates?.BRL)), eur = pos(Number(d?.rates?.EUR));
  if (!brl || !eur) return null;
  return { brl_usd: brl, usd_eur: 1 / eur, brl_eur: brl / eur, date: typeof d.date === 'string' ? d.date : null };
}

// {"bitcoin":{"cop":412345678}}
export function parseBtc(text) {
  return pos(Number(json(text)?.bitcoin?.cop));
}

// CriptoYa USDT/VES: promedio entre compra y venta en Binance P2P (si no viene, la mediana de los demás).
export function parseUsdtVes(text) {
  const d = json(text);
  if (!d || typeof d !== 'object') return null;
  const mid = (x) => { const a = pos(Number(x?.ask)), b = pos(Number(x?.bid)); return a && b ? (a + b) / 2 : null; };
  const b = mid(d.binancep2p);
  if (b) return { value: b, source: 'binancep2p' };
  const all = Object.values(d).map(mid).filter(Boolean).sort((x, y) => x - y);
  return all.length ? { value: all[Math.floor(all.length / 2)], source: 'mediana' } : null;
}

async function get(url) {
  const res = await fetch(url, { headers: { accept: 'application/json', 'user-agent': 'Mozilla/5.0 (cotizador JM Cambios)' }, signal: AbortSignal.timeout(6000) });
  if (!res.ok) throw new Error(`respondió ${res.status}`);
  return res.text();
}

export async function readIndicators() {
  const [trm, fx, btc, ves] = await Promise.allSettled([SOURCES.trm, SOURCES.fx, SOURCES.btc, SOURCES.usdtVes].map(get));
  const ok = (r, parse) => (r.status === 'fulfilled' ? parse(r.value) : null);
  const t = ok(trm, parseTrm), f = ok(fx, parseFx), b = ok(btc, parseBtc), u = ok(ves, parseUsdtVes);
  const out = { co: {}, br: {}, ve: {} };
  if (t) out.co.trm = t;
  if (t && f) out.co.eur = { value: t.value * f.usd_eur, date: t.date };
  if (b) out.co.btc = { value: b };
  if (f) { out.br.usd = { value: f.brl_usd, date: f.date }; out.br.eur = { value: f.brl_eur, date: f.date }; }
  if (u) out.ve.usdt = u;
  return out;
}

const empty = (o) => !Object.keys(o.co).length && !Object.keys(o.br).length && !Object.keys(o.ve).length;

export async function indicators(env, now = Date.now()) {
  let cached = null;
  try { cached = JSON.parse((await env.TASAS.get('indicadores')) || 'null'); } catch { cached = null; }
  const ttl = cached && empty(cached.data) ? RETRY_S : TTL_S;
  if (cached && now - cached.ts < ttl * 1000) return cached.data;
  const data = await readIndicators();
  // Si ahora todo falló pero había datos de antes, se siguen mostrando los anteriores.
  const keep = empty(data) && cached && !empty(cached.data) ? cached.data : data;
  await env.TASAS.put('indicadores', JSON.stringify({ ts: now, data: keep }));
  return keep;
}
