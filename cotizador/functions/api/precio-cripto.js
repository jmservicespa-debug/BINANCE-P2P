import { cryptoUsd, json } from '../../lib/server.js';

// Público: precio en dólares del oro (PAXG = 1 onza) y de Bitcoin, leído por el servidor (sin bloqueos del navegador).
export const onRequestGet = async ({ env }) => json(await cryptoUsd(env));
