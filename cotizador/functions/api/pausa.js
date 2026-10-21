import { setPaused } from '../../lib/server.js';

// Solo el panel: apaga o enciende todas las tasas de una vez.
export const onRequestPut = async ({ request, env }) => setPaused(request, env);
