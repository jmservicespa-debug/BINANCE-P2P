// Servidor local para probar el cotizador sin publicarlo (imita Cloudflare Pages).
// Uso:  DEV_PASSWORD=una-clave-larga node cotizador/scripts/dev-server.mjs   → http://localhost:8788
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

import * as tasas from '../functions/api/tasas.js';
import * as loginFn from '../functions/api/login.js';
import * as logoutFn from '../functions/api/logout.js';
import * as sesion from '../functions/api/sesion.js';
import * as usdtFn from '../functions/api/usdt.js';
import * as pausaFn from '../functions/api/pausa.js';
import * as indicadoresFn from '../functions/api/indicadores.js';
import * as eventoFn from '../functions/api/evento.js';
import * as estadisticasFn from '../functions/api/estadisticas.js';
import { hashPassword } from '../lib/server.js';

const ROOT = fileURLToPath(new URL('../public/', import.meta.url));
const PORT = Number(process.env.PORT || 8788);
const store = new Map();
const env = {
  TASAS: { get: async (k) => store.get(k) ?? null, put: async (k, v) => { store.set(k, v); }, delete: async (k) => { store.delete(k); } },
  SESSION_SECRET: 'solo-para-pruebas-locales',
  ADMIN_PASSWORD_HASH: await hashPassword(process.env.DEV_PASSWORD || 'clave-de-prueba', crypto.getRandomValues(new Uint8Array(16))),
};
const API = { '/api/tasas': tasas, '/api/login': loginFn, '/api/logout': logoutFn, '/api/sesion': sesion, '/api/usdt': usdtFn, '/api/pausa': pausaFn, '/api/indicadores': indicadoresFn, '/api/evento': eventoFn, '/api/estadisticas': estadisticasFn };
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg' };

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const mod = API[url.pathname];
  if (mod) {
    const handler = mod[`onRequest${req.method[0]}${req.method.slice(1).toLowerCase()}`];
    if (!handler) { res.writeHead(405).end(); return; }
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const request = new Request(url, { method: req.method, headers: req.headers, body: chunks.length ? Buffer.concat(chunks) : undefined });
    const out = await handler({ request, env });
    res.writeHead(out.status, Object.fromEntries(out.headers));
    res.end(Buffer.from(await out.arrayBuffer()));
    return;
  }
  let path = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, '');
  if (path.endsWith('/')) path += 'index.html';
  try {
    const body = await readFile(join(ROOT, path));
    res.writeHead(200, { 'content-type': TYPES[extname(path)] || 'application/octet-stream' }).end(body);
  } catch {
    res.writeHead(404).end('no encontrado');
  }
}).listen(PORT, () => console.log(`Cotizador local: http://localhost:${PORT}  ·  panel: http://localhost:${PORT}/panel/`));
