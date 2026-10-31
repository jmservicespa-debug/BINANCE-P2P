import { rewardsView, saveRewardsCfg } from '../../lib/server.js';

// Solo el panel: enciende o apaga el botón "Gana JMC" (JM Rewards) en el cotizador.
export const onRequestGet = async ({ request, env }) => rewardsView(request, env);
export const onRequestPut = async ({ request, env }) => saveRewardsCfg(request, env);
