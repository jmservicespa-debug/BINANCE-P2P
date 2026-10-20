import { saveUsdtCfg, usdtView } from '../../lib/server.js';

// Solo el panel: precio de referencia USDT/CLP y la ganancia configurada.
export const onRequestGet = async ({ request, env }) => usdtView(request, env);
export const onRequestPut = async ({ request, env }) => saveUsdtCfg(request, env);
