import { goldView, saveGoldCfg } from '../../lib/server.js';

// Solo el panel: ganancias y si se publica el oro tokenizado en Chile y en Colombia.
export const onRequestGet = async ({ request, env }) => goldView(request, env);
export const onRequestPut = async ({ request, env }) => saveGoldCfg(request, env);
