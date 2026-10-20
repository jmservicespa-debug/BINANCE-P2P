# Cotizador JM Cambios

Panel privado de tasas + cotizador público + flyers automáticos. Independiente del agente P2P:
no usa llaves de Binance ni toca la cuenta.

- `/` — cotizador para clientes. `/?a=jamer` y `/?a=miladys` llevan el WhatsApp de cada asesor
  (el celular del cliente lo recuerda). Sin `?a=` muestra un solo botón sin nombre (línea de Jamer).
- `/panel/` — panel de Jamer (con contraseña): tasas del día, dólar BCV manual de respaldo y flyers
  listos para descargar o compartir a WhatsApp.
- Dólar BCV: se lee de https://www.bcv.org.ve/ y, si falla, de la copia de DolarApi (no oficial); máx. una vez por hora. Si no se puede leer, usa el
  último valor bueno o el valor manual del panel. Verificado en línea (2026-10-20): la página del BCV no
  responde desde Cloudflare; DolarApi sí (881,88 Bs/USD, igual al valor oficial del día). Publicado en https://jmcambios.pages.dev

## Brasil desde el proveedor (solo panel)

- Debajo de Chile → Brasil: escribes cuántos reales da el proveedor por 100.000 CLP y tu ganancia (8 % por defecto).
  Precio del real = (100.000 ÷ BRL del proveedor) × (1 + ganancia); la tasa del flyer = 1 ÷ ese precio (6 decimales),
  se pone sola en la casilla de Brasil. El proveedor y la ganancia se guardan solo para el panel; el público ve la tasa final.
- **Brasil automático** (casilla, apagada por defecto): la tasa sigue al mercado cripto de CriptoYa
  (BRL por USDT ÷ CLP por USDT de Vita), leído desde el navegador. Al guardar se calibra: se anota el mercado de ese
  momento junto al número del proveedor. Público: solo un factor combinado `k` y el mercado de calibración.
  Si no hay dato o el mercado se movió más de 2 % desde la calibración → "Mercado inestable" hasta recalibrar.

## Calculadora USDT (solo panel)

- Referencia USDT/CLP de CriptoYa (API pública, sin clave): precio de venta (`ask`) de Vita Wallet (el proveedor);
  si no viene, Binance P2P; si tampoco, la mediana de los exchanges. Se guarda 2 minutos. Verificado (2026-10-20): CriptoYa rechaza (403) las consultas desde Cloudflare;
  el panel la consulta desde el navegador y funciona (Vita 982,14 CLP). Respaldo manual si la fuente falla. Rango aceptado 300–3.000 CLP.
- Precio de venta = referencia × (1 + ganancia %), por defecto 8 %. Cobrar = USDT × precio (entero);
  entregar = CLP ÷ precio (2 decimales, hacia abajo). En el cotizador público aparece **USDT** en Chile solo si está marcada la casilla
  "USDT activo en el cotizador" (se guarda al instante); sin marcar no aparece para nadie.
  El precio lo lee el navegador del cliente desde CriptoYa (Vita + ganancia); si no puede, queda como "Mercado inestable".
- **Comprar y vender**: en el cotizador, con USDT elegido, los botones son "Compro (en pesos)", "Compro (en USDT)" y
  "Vendo USDT". Al vender, el cliente entrega USDT y recibe pesos al **precio de compra** = precio de compra (`bid`) de Vita
  − ganancia al comprar (8 % por defecto, editable en el panel). Pesos a pagar = USDT × precio de compra (entero, hacia abajo).
  Sin dato de compra, "Vendo USDT" queda como "Mercado inestable".

## Otros países

- Botón de origen **Brasil** (bandera): por ahora solo muestra el aviso **Próximamente** (envíos desde Brasil a Chile, Colombia y Venezuela, y cambio de USDT). Se configura en `SOON` de `public/js/cotizador.js`.

- Botón de origen **Otro país** y recuadro **Otro destino** (en Chile y Colombia): el cliente escribe origen, destino y
  monto aproximado, y el botón **Pedir tasa** abre WhatsApp con el mensaje armado. No se publica ninguna tasa.

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

Montos sin decimales (redondeo normal: desde ,50 sube; por debajo, baja).

Hacia Venezuela hay un tercer modo, **Equivalente en dólares BCV**: el cliente escribe a cuántos USD (al dólar BCV del día) deben equivaler los bolívares que llegan; se calcula cuántos Bs son y cuánto pagar en CLP/COP. En Venezuela siempre se reciben bolívares.

Mínimos de envío (moneda de origen, campo `min`): Chile → VE/PE/CO/BR 10.000 CLP · EE. UU. 40.000 CLP · Panamá/Ecuador 15.000 CLP; Colombia → VE 20.000 COP.

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
