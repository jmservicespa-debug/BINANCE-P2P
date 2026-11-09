import { wiseView } from '../../lib/server.js';

// Precio del USDT en euros pagando con Wise en Binance P2P (público, guardado 2 minutos).
export const onRequestGet = async ({ env }) => wiseView(env);
