// Binance P2P en bolívares (consulta pública de anuncios, sin llave ni cuenta). La usan el servidor y el panel.
// Precio de referencia: comerciantes verificados, con Pago Móvil, cuyo anuncio acepta una orden de ~30 USD.

const BASE = 'https://www.binance.com/bapi/c2c/v1/public/c2c/agent';
export const VES_METHODS_URL = `${BASE}/trade-methods?fiat=VES`;
// tradeType BUY = anuncios de quienes venden USDT (lo que cuesta comprar USDT con Bs); SELL = quienes compran USDT.
export const vesAdsUrl = (tradeType, method) => `${BASE}/ad-list?fiat=VES&asset=USDT&tradeType=${tradeType}&limit=20&tradeMethodIdentifiers=${encodeURIComponent(method)}`;
export const VES_MIN_USD = 30;
const VES_RANGE = [1, 100000];  // Bs por USDT fuera de este rango = dato absurdo

const parse = (text) => { try { return typeof text === 'string' ? JSON.parse(text) : text; } catch { return null; } };
const list = (d) => (Array.isArray(d?.data) ? d.data : Array.isArray(d?.data?.list) ? d.data.list : []);
const isPagoMovil = (m) => /pago\s*m[oó]vil/i.test(`${m?.identifier || ''} ${m?.tradeMethodName || ''}`) || /^pagomovil$/i.test(m?.identifier || '');

// Identificador de Pago Móvil según la lista de métodos de Binance para VES.
export function pagoMovilId(text) {
  return list(parse(text)).find(isPagoMovil)?.identifier || null;
}

// Filtra los anuncios y devuelve la mediana de los 5 primeros que cumplen (más o menos el precio "bueno" del mercado).
export function pickVes(text, minUsd = VES_MIN_USD) {
  const ads = list(parse(text)).map((x) => {
    const adv = x.adv || x;
    const price = Number(adv.price ?? x.price);
    return {
      price, nick: x.advertiser?.nickName || '',
      merchant: String(x.advertiser?.userType || '').toLowerCase() === 'merchant',
      min: Number(adv.minSingleTransAmount ?? adv.minTransAmount ?? x.minTransAmount),
      max: Number(adv.dynamicMaxSingleTransAmount ?? adv.maxSingleTransAmount ?? adv.maxTransAmount ?? x.maxTransAmount),
      pm: (adv.tradeMethods || x.tradeMethods || []).some(isPagoMovil),
    };
  });
  const ok = ads.filter((a) => a.merchant && a.pm && a.price >= VES_RANGE[0] && a.price <= VES_RANGE[1]
    && (!Number.isFinite(a.min) || a.min <= minUsd * a.price) && (!Number.isFinite(a.max) || a.max >= minUsd * a.price));
  const top = ok.slice(0, 5).map((a) => a.price).sort((a, z) => a - z);
  return { total: ads.length, count: ok.length, price: top.length ? top[Math.floor(top.length / 2)] : null, ads: ok.slice(0, 5).map(({ nick, price, min, max }) => ({ nick, price, min, max })) };
}

// Consulta completa (métodos → anuncios de compra y venta). fetchFn permite usarla en el servidor o en el navegador.
export async function vesP2P(fetchFn = fetch, opts = {}) {
  const get = async (url) => {
    const res = await fetchFn(url, opts);
    if (!res.ok) throw new Error(`respondió ${res.status}`);
    return res.text();
  };
  const method = pagoMovilId(await get(VES_METHODS_URL));
  if (!method) throw new Error('Binance no lista Pago Móvil para VES');
  const [buy, sell] = await Promise.all(['BUY', 'SELL'].map(async (t) => pickVes(await get(vesAdsUrl(t, method)))));
  return { method, buy, sell };
}
