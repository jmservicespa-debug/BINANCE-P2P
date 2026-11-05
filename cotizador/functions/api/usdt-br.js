import { saveUsdtBrCfg, usdtBrView } from '../../lib/server.js';

// Solo el panel: ganancias y si se publica USDT desde Brasil.
export const onRequestGet = async ({ request, env }) => usdtBrView(request, env);
export const onRequestPut = async ({ request, env }) => saveUsdtBrCfg(request, env);
