import { brVeView, saveBrVeCfg } from '../../lib/server.js';

// Solo el panel: tasa del día, mínimo y si se publica la ruta Brasil → Venezuela.
export const onRequestGet = async ({ request, env }) => brVeView(request, env);
export const onRequestPut = async ({ request, env }) => saveBrVeCfg(request, env);
