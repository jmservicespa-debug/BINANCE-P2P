import { clEuView, saveClEuCfg } from '../../lib/server.js';

// Solo el panel: comisión, cambio fijo o automático (Wise), mínimo y si se publica Chile → Europa.
export const onRequestGet = async ({ request, env }) => clEuView(request, env);
export const onRequestPut = async ({ request, env }) => saveClEuCfg(request, env);
