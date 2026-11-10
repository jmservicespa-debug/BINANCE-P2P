import { coPeView, saveCoPeCfg } from '../../lib/server.js';

// Solo el panel: comisión, mínimo, referencias y si se publica la ruta Colombia → Perú.
export const onRequestGet = async ({ request, env }) => coPeView(request, env);
export const onRequestPut = async ({ request, env }) => saveCoPeCfg(request, env);
