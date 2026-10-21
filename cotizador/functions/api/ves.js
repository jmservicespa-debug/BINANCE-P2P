import { vesView } from '../../lib/server.js';

// Solo el panel: prueba del precio de Binance P2P en bolívares (verificados, Pago Móvil, ~30 USD).
export const onRequestGet = async ({ request, env }) => vesView(request, env);
