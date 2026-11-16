import { cyProxy } from '../../lib/server.js';

// Respaldo: precios de CriptoYa leídos desde el servidor cuando el navegador no puede leerlos.
export const onRequestGet = async ({ request, env, waitUntil }) => cyProxy(request, env, Date.now(), fetch, typeof waitUntil === 'function' ? (p) => waitUntil(p) : null);
