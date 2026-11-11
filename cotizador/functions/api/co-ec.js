import { coEcView, saveCoEcCfg } from '../../lib/server.js';

// Solo el panel: comisión, mínimo, referencias y si se publica la ruta Colombia → Ecuador.
export const onRequestGet = async ({ request, env }) => coEcView(request, env);
export const onRequestPut = async ({ request, env }) => saveCoEcCfg(request, env);
