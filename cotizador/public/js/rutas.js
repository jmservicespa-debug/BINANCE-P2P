// Rutas de envío y cálculo de cotizaciones. Lo usan el cotizador, el panel y el servidor.
// Para agregar un país: una fila nueva aquí (origen, destino, moneda y si la tasa multiplica o divide).

export const ORIGINS = {
  CL: { name: 'Chile', cur: 'CLP' },
  CO: { name: 'Colombia', cur: 'COP' },
  EU: { name: 'Europa', cur: 'EUR' },
};

// op: 'mul' = monto × tasa (ej. CLP × 0,9320 = Bs) · 'div' = monto ÷ tasa (ej. CLP ÷ 1085 = USD).
// min: envío mínimo en la moneda de origen (sin min = sin mínimo).
export const ROUTES = [
  { id: 'cl-ve', from: 'CL', to: ['VE'], name: 'Venezuela', cur: 'VES', unit: 'Bolívares', op: 'mul', dec: 0, min: 10000 },
  { id: 'cl-pe', from: 'CL', to: ['PE'], name: 'Perú', cur: 'PEN', unit: 'Soles', op: 'mul', dec: 0, min: 10000 },
  { id: 'cl-co', from: 'CL', to: ['CO'], name: 'Colombia', cur: 'COP', unit: 'Pesos colombianos', op: 'mul', dec: 0, min: 10000 },
  { id: 'cl-ar', from: 'CL', to: ['AR'], name: 'Argentina', cur: 'ARS', unit: 'Pesos argentinos', op: 'mul', dec: 0, min: 10000 },
  { id: 'cl-us', from: 'CL', to: ['US'], name: 'EE. UU.', cur: 'USD', unit: 'Dólares Zelle', op: 'div', dec: 0, min: 40000,
    note: 'Pago solo por Zelle (no se paga a cuenta bancaria)' },
  { id: 'cl-br', from: 'CL', to: ['BR'], name: 'Brasil', cur: 'BRL', unit: 'Reales Pix', op: 'mul', dec: 0, min: 10000,
    note: 'Pago en reales por Pix' },
  { id: 'cl-pa', from: 'CL', to: ['PA', 'EC'], name: 'Panamá · Ecuador', cur: 'USD', unit: 'Dólares', op: 'div', dec: 0, min: 15000 },
  { id: 'co-ve', from: 'CO', to: ['VE'], name: 'Venezuela', cur: 'VES', unit: 'Bolívares', op: 'div', dec: 0, min: 20000,
    note: 'Pago en bolívares a cuenta bancaria o pago móvil · Su pago llega en minutos' },
  // Automática, con "cero adelante" como la publican todas las casas de cambio (ej. 0,2850): COP × tasa = CLP.
  // Tasa = (lo que paga Vita Chile por USDT ÷ precio de compra del USDT en Vita Colombia), menos la ganancia del panel.
  { id: 'co-cl', from: 'CO', to: ['CL'], name: 'Chile', cur: 'CLP', unit: 'Pesos chilenos', op: 'mul', dec: 0, min: 50000, auto: true,
    note: 'Recibe por transferencia bancaria en cualquier banco de Chile' },
  { id: 'eu-ve', from: 'EU', to: ['VE'], name: 'Venezuela', cur: 'VES', unit: 'Bolívares', op: 'mul', dec: 0, min: 20 },  // euros × tasa = bolívares
];

export const ADVISORS = {
  jamer: { name: 'Jamer Restrepo', phone: '56933529706', show: '+56 9 3352 9706' },
  miladys: { name: 'Miladys Gaviria', phone: '56933638659', show: '+56 9 3363 8659' },
};

// Casillas de las plantillas de flyer (1080×1080): [ruta, centro x, centro y].
export const FLYERS = {
  CL: { file: '/assets/flyer-chile.png', maxW: 300, size: 54, slots: [['cl-ve', 848, 314], ['cl-pe', 848, 406], ['cl-co', 848, 498], ['cl-us', 848, 590], ['cl-br', 848, 682], ['cl-pa', 848, 774], ['cl-ar', 848, 866]] },
  CO: { file: '/assets/flyer-colombia.png', maxW: 350, size: 84, slots: [['co-ve', 808, 459], ['co-cl', 808, 689]] },
  EU: { file: '/assets/flyer-europa.png', maxW: 440, size: 96, slots: [['eu-ve', 540, 700]] },
};

// Tasa escrita como en el flyer: "0.9320", "0,9320", "1085". Devuelve NaN si no es válida.
export function rateNum(s) {
  const t = String(s ?? '').trim().replace(',', '.');
  if (!/^\d+(\.\d+)?$/.test(t)) return NaN;
  const v = parseFloat(t);
  return v > 0 && v < 1e7 ? v : NaN;
}

// Monto escrito por el cliente: "100.000", "1.250,50", "100000".
export function amountNum(s) {
  const t = String(s ?? '').replace(/[^0-9.,]/g, '').replace(/\./g, '').replace(',', '.');
  return t ? parseFloat(t) : NaN;
}

// fee: cargo fijo en la moneda de origen que se descuenta antes de convertir (ej. 1 USD en Estados Unidos → Chile).
const feeOf = (route) => Number(route.fee) || 0;
export const convert = (route, rate, amount) => { const a = Math.max(0, amount - feeOf(route)); return route.op === 'mul' ? a * rateNum(rate) : a / rateNum(rate); };
export const invert = (route, rate, received) => (route.op === 'mul' ? received / rateNum(rate) : received * rateNum(rate)) + feeOf(route);

export function fmt(v, dec) {
  if (!Number.isFinite(v)) return '—';
  return new Intl.NumberFormat('es-CL', { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(v);
}

// USDT desde Chile: el precio no se escribe en el panel; sale de Vita (CriptoYa) + la ganancia configurada.
export const USDT_ROUTE = { id: 'cl-usdt', from: 'CL', to: ['USDT'], name: 'USDT', cur: 'USDT', sym: 'USDT', unit: 'Dólar Binance', op: 'div', dec: 2,
  min: 10000, buyMin: 15000,  // mínimos en CLP: cliente compra (nosotros vendemos) 10.000 · cliente vende (nosotros compramos) 15.000
  note: 'Recibes los USDT en tu wallet o cuenta de Binance (la red se confirma por WhatsApp). JM Cambios es un comerciante independiente, no es Binance.' };
// USDT desde Colombia: solo venta al cliente. Precio = USDT en Binance P2P Colombia (CriptoYa) + ganancia; mínimo editable en el panel.
// En Colombia se presenta como "dólar digital" (sin mencionar Binance), igual que en Brasil.
export const USDT_CO_ROUTE = { ...USDT_ROUTE, id: 'co-usdt', from: 'CO', min: 50000, buyMin: null, digital: true, unit: 'Dólar digital',
  note: 'Recibes los USDT en tu wallet (la red se confirma por WhatsApp). JM Cambios es un comerciante independiente.' };
// USDC en Chile y Colombia: mismo precio que el USDT de ese país (solo cambia la moneda); se ofrece si está marcado en el panel.
const usdcNote = 'Recibes los USDC en tu wallet (la red se confirma por WhatsApp). JM Cambios es un comerciante independiente.';
export const USDC_CL_ROUTE = { ...USDT_ROUTE, id: 'cl-usdc', to: ['USDC'], name: 'USDC', cur: 'USDC', sym: 'USDC', digital: true, unit: 'Dólar digital', note: usdcNote };
export const USDC_CO_ROUTE = { ...USDT_CO_ROUTE, id: 'co-usdc', to: ['USDC'], name: 'USDC', cur: 'USDC', sym: 'USDC', note: usdcNote };
// USDT desde Brasil: comprar y vender. Precio = USDT en reales (Binance P2P o Bybit P2P vía CriptoYa) ± la ganancia del panel.
// Mínimo: el equivalente a 10 USDT al precio del momento (se calcula al cargar).
// En Brasil se presenta como "dólar digital" (sin mencionar Binance).
// USDC desde Brasil: igual que USDT Brasil (mismas ganancias y referencia), se ofrece si está marcado en el panel.
export const USDC_BR_ROUTE = { id: 'br-usdc', from: 'BR', to: ['USDC'], name: 'USDC', cur: 'USDC', sym: 'USDC', op: 'div', dec: 2, min: 0, buyMin: 0, minUsdt: 10,
  digital: true, unit: 'Dólar digital', note: 'Recibes los USDC en tu wallet (la red se confirma por WhatsApp). JM Cambios es un comerciante independiente.' };
export const USDT_BR_ROUTE = { ...USDT_ROUTE, id: 'br-usdt', from: 'BR', min: 0, buyMin: 0, minUsdt: 10, digital: true, unit: 'Dólar digital',
  note: 'Recibes los USDT en tu wallet (la red se confirma por WhatsApp). JM Cambios es un comerciante independiente.' };

// Oro tokenizado (Chile y Colombia): 1 token = 1 onza troy de oro. Precio = CoinGecko en pesos ± la ganancia del panel.
// Cada token se envía por una sola red: PAXG por Ethereum (ERC-20) y XAUt por Solana.
const gold = (from, token, min) => ({ id: `${from.toLowerCase()}-${token.toLowerCase()}`, from, to: [token], cur: token, gold: true,
  sym: token === 'PAXG' ? 'PAXG' : 'XAUt', name: token === 'PAXG' ? 'PAXG · oro' : 'XAUt · oro',
  unit: token === 'PAXG' ? 'Pax Gold · 1 = 1 onza' : 'Tether Gold · 1 = 1 onza', op: 'div', dec: 6, min, buyMin: min,
  net: token === 'PAXG' ? 'Ethereum (ERC-20)' : 'Solana' });
// Bitcoin (Chile y Colombia): precio de CoinGecko en pesos ± la ganancia del panel. Se envía por Lightning Network;
// si el cliente prefiere la red principal (on-chain), asume la comisión de red.
const btc = (from, min) => ({ id: `${from.toLowerCase()}-btc`, from, to: ['BTC'], cur: 'BTC', sym: 'BTC', btc: true, name: 'Bitcoin',
  unit: 'BTC · red Lightning', op: 'div', dec: 8, min, buyMin: min, net: 'Lightning Network' });
export const BTC_ROUTES = [btc('CL', 10000), btc('CO', 30000)];
// Mínimos más altos que Bitcoin para que la comisión de red pese poco: 30.000 CLP y 100.000 COP.
export const GOLD_ROUTES = [gold('CL', 'XAUT', 30000), gold('CL', 'PAXG', 30000), gold('CO', 'XAUT', 100000), gold('CO', 'PAXG', 100000)];

// USDT admite decimales: "100,5" o "100.5" = cien y medio; "1.000" o "1.000,25" = mil.
export function usdtNum(v) {
  let t = String(v || '').trim().replace(/\s/g, '');
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
  else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, '');
  return /^\d+(\.\d+)?$/.test(t) ? parseFloat(t) : NaN;
}

export const belowMin = (route, sendAmount) => Boolean(route.min) && Number.isFinite(sendAmount) && sendAmount < route.min;

export const routeById = (id) => ROUTES.find((r) => r.id === id);

// Venezuela → Chile (automática): el cliente paga bolívares y recibe pesos chilenos.
// Tasa = (lo que paga Vita por USDT en CLP) ÷ (precio del USDT en bolívares del P2P elegido × (1 + ganancia)). VES × tasa = CLP.
// Brasil → Colombia (automática): el cliente paga reales y recibe pesos colombianos.
// Tasa = (lo que paga Binance P2P Colombia por USDT) ÷ (USDT en reales del exchange elegido × (1 + ajuste)). BRL × tasa = COP.
export const BR_CO_ROUTE = { id: 'br-co', from: 'BR', to: ['CO'], name: 'Colombia', cur: 'COP', unit: 'Pesos colombianos', op: 'mul', dec: 0, min: 50,
  note: 'Recibe en pesos colombianos por Nequi, Bancolombia u otro banco' };
export const CO_BR_ROUTE = { id: 'co-br', from: 'CO', to: ['BR'], name: 'Brasil', cur: 'BRL', unit: 'Reales Pix', op: 'div', dec: 0, min: 50000,
  note: 'Recibe en reales por Pix' };
export const BR_CL_ROUTE = { id: 'br-cl', from: 'BR', to: ['CL'], name: 'Chile', cur: 'CLP', unit: 'Pesos chilenos', op: 'mul', dec: 0, min: 50,
  note: 'Recibe por transferencia bancaria en cualquier banco de Chile' };
export const US_CL_ROUTE = { id: 'us-cl', from: 'US', to: ['CL'], name: 'Chile', cur: 'CLP', unit: 'Pesos chilenos', op: 'mul', dec: 0, min: 20, fee: 1,
  pay: 'Pago con link de Cash App',
  note: 'Pagas en dólares con un link de pago de Cash App (te lo enviamos por WhatsApp). Recibe por transferencia en cualquier banco de Chile' };
// Brasil → Venezuela: tasa manual que escribes cada día en el panel (reales × tasa = bolívares).
export const BR_VE_ROUTE = { id: 'br-ve', from: 'BR', to: ['VE'], name: 'Venezuela', cur: 'VES', unit: 'Bolívares', op: 'mul', dec: 0, min: 50,
  note: 'Pagas en reales por Pix. Recibe en bolívares en cualquier banco de Venezuela' };
// Europa → Chile: euros − tu ganancia → USDT comprados en Binance P2P con Wise (precio que anotas en el panel) → vendidos en Chile al precio de Vita.
// Chile → Europa: pesos − tu comisión, pasados a euros al cambio de Wise (pesos ÷ tasa = euros).
export const CL_EU_ROUTE = { id: 'cl-eu', from: 'CL', to: ['EU'], name: 'Europa', cur: 'EUR', unit: 'Euros', op: 'div', dec: 2, min: 20000,
  note: 'Recibe en euros en su cuenta bancaria en Europa' };
export const EU_CL_ROUTE = { id: 'eu-cl', from: 'EU', to: ['CL'], name: 'Chile', cur: 'CLP', unit: 'Pesos chilenos', op: 'mul', dec: 0, min: 20,
  note: 'Recibe por transferencia bancaria en cualquier banco de Chile' };
export const VE_CO_ROUTE = { id: 've-co', from: 'VE', to: ['CO'], name: 'Colombia', cur: 'COP', unit: 'Pesos colombianos', op: 'mul', dec: 0, min: 40000,
  note: 'Recibe en pesos colombianos por Nequi, Bancolombia u otro banco' };
export const VE_CL_ROUTE = { id: 've-cl', from: 'VE', to: ['CL'], name: 'Chile', cur: 'CLP', unit: 'Pesos chilenos', op: 'mul', dec: 0, min: 2000,
  note: 'Recibe por transferencia bancaria en cualquier banco de Chile' };
