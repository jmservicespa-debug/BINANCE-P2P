import { euClView, saveEuClCfg } from '../../lib/server.js';

// Solo el panel: ganancia, precio del USDT en euros (Binance P2P · Wise), mínimo y si se publica Europa → Chile.
export const onRequestGet = async ({ request, env }) => euClView(request, env);
export const onRequestPut = async ({ request, env }) => saveEuClCfg(request, env);
