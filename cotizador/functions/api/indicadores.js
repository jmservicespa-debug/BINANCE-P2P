import { indicators } from '../../lib/indicadores.js';
import { json } from '../../lib/server.js';

// Público: indicadores de la franja que va pasando (TRM, euro, BTC, reales, USDT en bolívares). Solo informativos.
export const onRequestGet = async ({ env }) => json(await indicators(env));
