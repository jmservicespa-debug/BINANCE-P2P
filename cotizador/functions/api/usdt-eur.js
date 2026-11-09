import { eurMarketView } from '../../lib/server.js';

// Euros por USDT en el mercado (Kraken / Binance / Frankfurter), guardado 5 minutos.
export const onRequestGet = async ({ env }) => eurMarketView(env);
