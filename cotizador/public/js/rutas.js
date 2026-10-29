// Rutas de envío y cálculo de cotizaciones. Lo usan el cotizador, el panel y el servidor.
// Para agregar un país: una fila nueva aquí (origen, destino, moneda y si la tasa multiplica o divide).

export const ORIGINS = {
  CL: { name: 'Chile', cur: 'CLP' },
  CO: { name: 'Colombia', cur: 'COP' },
};

// op: 'mul' = monto × tasa (ej. CLP × 0,9320 = Bs) · 'div' = monto ÷ tasa (ej. CLP ÷ 1085 = USD).
// min: envío mínimo en la moneda de origen (sin min = sin mínimo).
export const ROUTES = [
  { id: 'cl-ve', from: 'CL', to: ['VE'], name: 'Venezuela', cur: 'VES', unit: 'Bolívares', op: 'mul', dec: 0, min: 10000 },
  { id: 'cl-pe', from: 'CL', to: ['PE'], name: 'Perú', cur: 'PEN', unit: 'Soles', op: 'mul', dec: 0, min: 10000 },
  { id: 'cl-co', from: 'CL', to: ['CO'], name: 'Colombia', cur: 'COP', unit: 'Pesos colombianos', op: 'mul', dec: 0, min: 10000 },
  { id: 'cl-us', from: 'CL', to: ['US'], name: 'EE. UU.', cur: 'USD', unit: 'Dólares Zelle', op: 'div', dec: 0, min: 40000,
    note: 'Pago solo por Zelle (no se paga a cuenta bancaria)' },
  { id: 'cl-br', from: 'CL', to: ['BR'], name: 'Brasil', cur: 'BRL', unit: 'Reales Pix', op: 'mul', dec: 0, min: 10000,
    note: 'Pago en reales por Pix' },
  { id: 'cl-pa', from: 'CL', to: ['PA', 'EC'], name: 'Panamá · Ecuador', cur: 'USD', unit: 'Dólares', op: 'div', dec: 0, min: 15000 },
  { id: 'co-ve', from: 'CO', to: ['VE'], name: 'Venezuela', cur: 'VES', unit: 'Bolívares', op: 'div', dec: 0, min: 20000,
    note: 'Pago en bolívares a cuenta bancaria o pago móvil · Su pago llega en minutos' },
];

export const ADVISORS = {
  jamer: { name: 'Jamer Restrepo', phone: '56933529706', show: '+56 9 3352 9706' },
  miladys: { name: 'Miladys Gaviria', phone: '56933638659', show: '+56 9 3363 8659' },
};

// Casillas de las plantillas de flyer (1080×1080): [ruta, centro x, centro y].
export const FLYERS = {
  CL: { file: '/assets/flyer-chile.png', maxW: 280, size: 58, slots: [['cl-ve', 862, 311], ['cl-pe', 862, 421], ['cl-co', 862, 531], ['cl-us', 862, 641], ['cl-br', 862, 751], ['cl-pa', 862, 861]] },
  CO: { file: '/assets/flyer-colombia.png', maxW: 420, size: 84, slots: [['co-ve', 540, 686]] },
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

export const convert = (route, rate, amount) => route.op === 'mul' ? amount * rateNum(rate) : amount / rateNum(rate);
export const invert = (route, rate, received) => route.op === 'mul' ? received / rateNum(rate) : received * rateNum(rate);

export function fmt(v, dec) {
  if (!Number.isFinite(v)) return '—';
  return new Intl.NumberFormat('es-CL', { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(v);
}

// USDT desde Chile: el precio no se escribe en el panel; sale de Vita (CriptoYa) + la ganancia configurada.
export const USDT_ROUTE = { id: 'cl-usdt', from: 'CL', to: ['USDT'], name: 'USDT', cur: 'USDT', unit: 'Dólar Binance · Tether', op: 'div', dec: 2,
  min: 10000, buyMin: 15000,  // mínimos en CLP: cliente compra (nosotros vendemos) 10.000 · cliente vende (nosotros compramos) 15.000
  note: 'Recibes los USDT en tu wallet o cuenta de Binance (la red se confirma por WhatsApp)' };

// USDT admite decimales: "100,5" o "100.5" = cien y medio; "1.000" o "1.000,25" = mil.
export function usdtNum(v) {
  let t = String(v || '').trim().replace(/\s/g, '');
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
  else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, '');
  return /^\d+(\.\d+)?$/.test(t) ? parseFloat(t) : NaN;
}

export const belowMin = (route, sendAmount) => Boolean(route.min) && Number.isFinite(sendAmount) && sendAmount < route.min;

export const routeById = (id) => ROUTES.find((r) => r.id === id);
