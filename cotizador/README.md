# Cotizador JM Cambios

Panel privado de tasas + cotizador público + flyers automáticos. Independiente del agente P2P:
no usa llaves de Binance ni toca la cuenta.

- `/` — cotizador para clientes. `/?a=jamer` y `/?a=miladys` llevan el WhatsApp de cada asesor
  (el celular del cliente lo recuerda). Sin `?a=` muestra un solo botón sin nombre (línea de Jamer).
- `/panel/` — panel de Jamer (con contraseña): tasas del día, dólar BCV manual de respaldo y flyers
  listos para descargar o compartir a WhatsApp.
- Dólar BCV: se lee de https://www.bcv.org.ve/ y, si falla, de la copia de DolarApi (no oficial); máx. una vez por hora. Si no se puede leer, usa el
  último valor bueno o el valor manual del panel. **Pendiente de verificar en línea** (desde el entorno
  de desarrollo no hay acceso a esa página).

## Estados de cada ruta (en el panel)

- **Activa**: el cotizador calcula con la tasa; el flyer la muestra.
- **Inestable · tasa por WhatsApp**: el país sigue en el cotizador con "Mercado inestable" y el botón
  "Pedir tasa por WhatsApp" (mensaje con el monto ya escrito); la tasa guardada NO se publica; el flyer dice CONSULTAR.
- **Apagada**: no aparece en el cotizador; el flyer muestra "—".

La tasa queda guardada en los tres estados: al volver a Activa no hay que escribirla de nuevo.

## Rutas (`public/js/rutas.js`)

| Desde | Hacia | Operación |
|---|---|---|
| Chile | Venezuela · Perú · Colombia · Brasil | CLP × tasa |
| Chile | EE. UU. · Panamá/Ecuador | CLP ÷ tasa |
| Colombia | Venezuela | COP ÷ tasa |

Para un país nuevo: una fila en `ROUTES` (y su casilla en la plantilla del flyer si va en el flyer).

## Probar en el computador

```
cd cotizador
npm test                                              # pruebas del servidor y los cálculos
DEV_PASSWORD=una-clave-larga node scripts/dev-server.mjs   # http://localhost:8788 y /panel/
```

## Publicar en internet (Cloudflare Pages, plan gratuito)

1. Crea una cuenta en https://dash.cloudflare.com (gratis).
2. **Workers & Pages → Create → Pages → Connect to Git**: elige este repositorio y la rama.
   - Root directory: `cotizador`
   - Build command: *(vacío)*
   - Build output directory: `public`
3. **Workers & Pages → KV → Create namespace**: nombre `jmcambios-tasas`.
   En el proyecto: **Settings → Bindings → Add → KV namespace**: variable `TASAS` → `jmcambios-tasas`.
4. Contraseña del panel, en TU computador (no la escribas en ningún chat):
   `python cotizador\scripts\hash_password.py` (o `node cotizador/scripts/hash-password.mjs`) → copia los dos valores que imprime.
   En el proyecto: **Settings → Variables and secrets → Add** (tipo *Secret*):
   `ADMIN_PASSWORD_HASH` y `SESSION_SECRET`.
5. **Deployments → Retry deployment** para que tome los secretos.
6. Dominio propio: **Custom domains → Set up a custom domain** (ej. `jmcambios.com`).
   Sin dominio funciona en `https://<proyecto>.pages.dev`.
7. Entra a `/panel/`, escribe las tasas y **Guardar y publicar**.

## Seguridad

- Contraseña guardada solo como hash PBKDF2; sesión con cookie firmada (HttpOnly, Secure, SameSite=Strict, 12 h).
- Cambios solo desde el mismo sitio; 5 intentos fallidos por IP → bloqueo de 15 min.
- El cotizador no pide ni guarda datos de clientes.
