import { report } from '../../lib/estadisticas.js';

// Solo el panel: visitas, cotizaciones y clics en WhatsApp de los últimos 7 días.
export const onRequestGet = async ({ request, env }) => report(request, env);
