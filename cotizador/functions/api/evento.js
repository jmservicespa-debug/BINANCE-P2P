import { track } from '../../lib/estadisticas.js';

// Público: el cotizador avisa una visita, una cotización o un clic en WhatsApp (solo se cuentan, sin datos personales).
export const onRequestPost = async ({ request, env }) => track(request, env);
