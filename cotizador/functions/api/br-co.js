import { brCoView, saveBrCoCfg } from '../../lib/server.js';

// Solo el panel: ajuste, mínimo, exchange de referencia y si se publica la ruta Brasil → Colombia.
export const onRequestGet = async ({ request, env }) => brCoView(request, env);
export const onRequestPut = async ({ request, env }) => saveBrCoCfg(request, env);
