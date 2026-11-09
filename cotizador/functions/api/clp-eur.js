import { clpEurView } from '../../lib/server.js';

// Pesos chilenos por euro (cambio de Wise; respaldo open.er-api), guardado 10 minutos.
export const onRequestGet = async ({ env }) => clpEurView(env);
