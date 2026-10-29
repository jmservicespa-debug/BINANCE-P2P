import { saveUsdtCoCfg, usdtCoView } from '../../lib/server.js';

// Solo el panel: ganancia, mínimo y si se publica la venta de USDT en Colombia.
export const onRequestGet = async ({ request, env }) => usdtCoView(request, env);
export const onRequestPut = async ({ request, env }) => saveUsdtCoCfg(request, env);
