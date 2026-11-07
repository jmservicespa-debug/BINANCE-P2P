import { usClView, saveUsClCfg } from '../../lib/server.js';

// Solo el panel: comisión, cargo fijo, mínimo y si se publica la ruta Estados Unidos → Chile.
export const onRequestGet = async ({ request, env }) => usClView(request, env);
export const onRequestPut = async ({ request, env }) => saveUsClCfg(request, env);
