import { coEuView, saveCoEuCfg } from '../../lib/server.js';

// Solo el panel: ganancia, mínimo, referencia en Colombia, respaldo del cambio CLP/EUR y si se publica Colombia → Europa.
export const onRequestGet = async ({ request, env }) => coEuView(request, env);
export const onRequestPut = async ({ request, env }) => saveCoEuCfg(request, env);
