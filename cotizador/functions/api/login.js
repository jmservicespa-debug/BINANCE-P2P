import { login } from '../../lib/server.js';

export const onRequestPost = async ({ request, env }) => login(request, env);
