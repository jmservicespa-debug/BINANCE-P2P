import { coBrView, saveCoBrCfg } from '../../lib/server.js';

// Solo el panel: ganancia, mínimo, exchange de Brasil y si se publica la ruta Colombia → Brasil.
export const onRequestGet = async ({ request, env }) => coBrView(request, env);
export const onRequestPut = async ({ request, env }) => saveCoBrCfg(request, env);
