import { saveVeClCfg, veClView } from '../../lib/server.js';

// Solo el panel: ganancia, mínimo, P2P de referencia y si se publica la ruta Venezuela → Chile.
export const onRequestGet = async ({ request, env }) => veClView(request, env);
export const onRequestPut = async ({ request, env }) => saveVeClCfg(request, env);
