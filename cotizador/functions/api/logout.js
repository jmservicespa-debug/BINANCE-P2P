import { clearCookie, json, sameOrigin } from '../../lib/server.js';

export const onRequestPost = async ({ request }) =>
  sameOrigin(request) ? json({ ok: true }, 200, { 'set-cookie': clearCookie() }) : json({ error: 'origen no permitido' }, 403);
