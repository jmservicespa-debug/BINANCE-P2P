// Genera el valor de ADMIN_PASSWORD_HASH sin guardar la contraseña en ningún lado.
// Uso:  node cotizador/scripts/hash-password.mjs
// Escribe tu contraseña cuando la pida y copia la línea "pbkdf2$..." en el secreto del hosting.
import { createInterface } from 'node:readline';
import { hashPassword } from '../lib/server.js';

const rl = createInterface({ input: process.stdin, output: process.stdout });
rl.question('Contraseña del panel (mínimo 10 caracteres): ', async (pw) => {
  rl.close();
  if (pw.length < 10) {
    console.error('Muy corta: usa al menos 10 caracteres.');
    process.exit(1);
  }
  const hash = await hashPassword(pw, crypto.getRandomValues(new Uint8Array(16)));
  console.log('\nADMIN_PASSWORD_HASH =\n' + hash);
  console.log('\nSESSION_SECRET (otro secreto, cópialo también) =\n' + Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString('base64'));
});
