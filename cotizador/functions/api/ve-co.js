import { veCoView, saveVeCoCfg } from '../../lib/server.js';

// Solo el panel: ganancia, mínimo, referencias y si se publica la ruta Venezuela → Colombia.
export const onRequestGet = async ({ request, env }) => veCoView(request, env);
export const onRequestPut = async ({ request, env }) => saveVeCoCfg(request, env);
