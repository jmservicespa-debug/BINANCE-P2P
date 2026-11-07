import { brClView, saveBrClCfg } from '../../lib/server.js';

// Solo el panel: ganancia, mínimo, exchange de Brasil y si se publica la ruta Brasil → Chile.
export const onRequestGet = async ({ request, env }) => brClView(request, env);
export const onRequestPut = async ({ request, env }) => saveBrClCfg(request, env);
