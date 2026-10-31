// Dirección única: quien entra por la dirección antigua (jmcambios.pages.dev) o por www llega a jmcambios.cl,
// con la misma página y los mismos datos del enlace (por ejemplo ?a=jamer). Las vistas previas (xxxx.jmcambios.pages.dev) no se tocan.
const MAIN = 'jmcambios.cl';
const MOVED = new Set(['jmcambios.pages.dev', 'www.jmcambios.cl']);

export const onRequest = async ({ request, next }) => {
  const url = new URL(request.url);
  if (!MOVED.has(url.hostname)) return next();
  url.hostname = MAIN;
  url.protocol = 'https:';
  url.port = '';
  return Response.redirect(url.toString(), 301);
};
