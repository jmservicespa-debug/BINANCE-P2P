import { btcView, saveBtcCfg } from '../../lib/server.js';

// Solo el panel: ganancias y si se publica Bitcoin en Chile y en Colombia.
export const onRequestGet = async ({ request, env }) => btcView(request, env);
export const onRequestPut = async ({ request, env }) => saveBtcCfg(request, env);
