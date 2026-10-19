# PROJECT_STATE — documento de referencia entre sesiones

> Leer este archivo al empezar cualquier sesión nueva. Actualizarlo al terminar cada cambio.

## Proyecto
Agente inteligente Binance P2P USDT/COP para **JM Cambios** (comerciante verificado).
Rama de desarrollo: `claude/binance-p2p-trading-agent-madi2s`.

## Estado de fases

| Fase | Estado |
|---|---|
| 1. Viabilidad e integraciones | ✅ Diagnóstico · ✅ Verificación real ejecutada 2026-10-18 (16 OK / 2 error) · ⏳ Pendiente: confirmar cuenta de la key (0 anuncios/órdenes/métodos de pago) y resolver `getReferencePrice` |
| 2. Monitor de anuncios | ✅ Cerrada 2026-10-19: ejecución real continua ~33 h (2026-10-17 23:37 → 2026-10-19 08:59 COT) sin errores ni caídas, snapshots guardados |
| 3. Historial y liquidez | ✅ 2026-10-19: datos reales importados (1.958 ciclos, ~33 h) y consultas funcionando en el PC del usuario. Seguir acumulando días hábiles. |
| 4. Competencia y rentabilidad | ✅ Implementada y ejecutada con la cuenta oficial 2026-10-19 (119 pruebas OK): `jmcambios-negocio sincronizar/costos/rentabilidad/competencia`; 4.597 órdenes, comisiones reales observadas integradas. Rentabilidad COP sin ciclos todavía (sin historial de comerciante COP) · Aprobada por el usuario 2026-10-19 |
| 5. Presión y motor de precios | ✅ 2026-10-19 (137 pruebas OK): `jmcambios-negocio presion` / `recomendar` ejecutados con datos reales en el PC del usuario (modo RECOMMENDATION), línea de presión en el monitor · Aprobada por el usuario 2026-10-19 |
| 6. Panel y alertas | 🟡 Implementada 2026-10-19 (154 pruebas OK; panel verificado en Chromium 390 px claro/oscuro sin errores): `jmcambios-monitor --panel`, `jmcambios-panel`, `jmcambios-alertas configurar/probar` · ✅ 2026-10-19 en el PC del usuario: Telegram conectado (@JMCambios_Alertas_bot), panel abierto en su Android por Wi-Fi como acceso directo con ícono JM (Chrome no permite 'Instalar' sin HTTPS) · ⏳ 1–2 días de uso para ajustar alertas antes de la Fase 7 |
| 7–10 | ⛔ No iniciadas |

## Decisiones tomadas
- Integración oficial: **C2C Agent SAPI** (`/sapi/v1/c2c/agent/*`, HMAC, base `https://api.binance.com`) + API pública agent (`/bapi/c2c/v1/public/c2c/agent/*`, base `https://www.binance.com`). Fuente: `github.com/binance/binance-skills-hub/skills/binance/p2p` v1.1.0.
- **No** se usa el endpoint web `bapi/c2c/v2/friendly/c2c/adv/search` (no documentado).
- Firma SAPI C2C: **no ordenar parámetros**, codificación RFC 3986, HMAC-SHA256.
- `ads/update` exige el **objeto completo** (leer `getDetailByNo` → fusionar → enviar); si no, error `-9000`.
- Stack: Python 3.12+, httpx, pydantic v2, SQLite→PostgreSQL, FastAPI+PWA, Telegram, pytest.
- Modo por defecto OBSERVACIÓN; AUTOMÁTICO requiere 4 condiciones (ver `src/jmcambios/config.py`).
- Nunca: marcar pagado, liberar USDT, apelar, endpoints no oficiales, guardar contraseñas/2FA.

## Hechos verificados vs. pendientes
- Verificado en documentación oficial: ver `docs/FASE1_VIABILIDAD.md` §2.
- **No verificado en ejecución**: el entorno de desarrollo no tiene salida a binance.com (proxy 403). Ninguna llamada real ejecutada aún.

## Perfil operativo del usuario (2026-10-18)
- Opera **principalmente en Venezuela (VES)**; en COP tiene poca actividad reciente y ningún anuncio activo ahora.
- **Aclarado:** la API key verificada es de una **cuenta de prueba** sin actividad; por eso 0 anuncios/órdenes/métodos de pago. No es un fallo. La cuenta oficial (comerciante, con anuncios) aún no se ha verificado.
- Datos de mercado (público + `ads/search`) no dependen de la cuenta → verificados y suficientes para la Fase 2.
- Pendiente antes de Fase 4: key de solo lectura de la **cuenta oficial** para verificar mis anuncios, órdenes, comisiones y métodos de pago.
- La arquitectura ya parametriza `JMC_FIAT`; extender a USDT/VES es candidato natural tras la Fase 2 (decisión pendiente del usuario).

## Objetivo de negocio (2026-10-18)
- Meta del usuario (aclarada): **~40 USD diarios (≈ 127.000 COP a TRM 3.174,67) con 10–15 millones COP** → 1,27 %/día con 10 M o 0,85 %/día con 15 M (≈ 25–38 % mensual). Considerada por el usuario como "conservadora"; se le advirtió que es exigente frente a spreads observados (0–0,37 % en la cima) y que la viabilidad se medirá con simulación antes de comprometer capital.
- Sin historial reciente de P2P en COP (opera ventas directas por remesas) → no hay línea base propia; se calibrará con simulación sobre snapshots (Fases 5/7/8).
- **Decisión del usuario:** el P2P COP se evalúa como negocio independiente; **no** se combina con su operación de remesas (ya rentable).
- Relación clave: ganancia diaria = capital × margen neto por ciclo × ciclos/día.

## Hoja de ruta futura (después de la Fase 10, pedida por el usuario 2026-10-18)
- Más exchanges: **OKX, Bybit** (nuevos adaptadores `MarketSource`; verificar antes qué APIs P2P oficiales ofrecen).
- Más mercados/países y **alertas de arbitraje entre exchanges** (comprar barato en uno, vender en otro), con costo neto completo: comisiones, retiro/red de USDT, tiempo de transferencia, capital repartido.
- **Triangulación BRL / COP / CLP** (y otros fiat): cálculo de rutas USDT entre monedas con todos los costos y tipos de cambio; requiere cuentas/medios de pago locales y revisión normativa por país.
- Diseño: el dominio ya es independiente del exchange y de la moneda (`venue`, `asset`, `fiat` en cada `Ad`/`MarketSnapshot`).

## Contexto del usuario (aclarado 2026-10-19)
- Hoy usa la cuenta oficial casi solo para **vender en VES** (salida de remesas); compra USDT en COP solo para eso. **No tiene historial como comerciante en COP**.
- Objetivo del proyecto: **empezar a operar como comerciante USDT/COP** (anuncios propios de compra y venta), reduciendo la dependencia de las remesas.
- Consecuencia: la rentabilidad de la Fase 4 no tiene ciclos COP que medir todavía. Se valida con: comisiones reales (`costos`, rol MAKER en VES como referencia), `competencia` (precios límite sin anuncios COP) y, después, con simulación (Fases 7–8) usando la misma calculadora. Opción a decidir por el usuario: arrancar en pequeño en Modo Recomendación para generar datos reales.

## Primer análisis de competencia real (2026-10-19 10:07 COT)
- Mercado: mejor venta 3.155 · mejor compra 3.160 (cruzado).
- Anuncio COMPRA propio (fuera de línea): 3.150, 550 USDT, 200k–3M COP, Daviplata/Davivienda → puesto estimado #7 de 355, 10 COP detrás del mejor.
- Anuncio VENTA propio (fuera de línea): 3.130, 1.100 USDT → 25 COP POR DEBAJO del mejor (regalaría 0,79 %). Se añadió aviso "regalando margen".
- Comisión maker según `commissionRate` de los anuncios: 0,2 % por lado → ciclo ≈ 0,4 % + 4x1000 (0–0,4 %). Para 0,3 % neto hace falta ≈ 0,7–1,1 % entre compra y venta; con venta a 3.155, comprar máx. 3.133 (cuenta exenta) / 3.121 (con 4x1000).
- `costos` (300 órdenes, antes del arreglo de paginación): TODAS como TAKER. Comisión real cobrada (comisión ÷ cantidad): compras 0,047 %, ventas 0,162 % (el campo de tasa viene en 0). Ya se usan por defecto en el análisis de cruces (antes se suponía 0 %).
- Con comisiones reales, el cruce de −4,41 COP visto el domingo NO era rentable. Hay que reimportar (`jmcambios-history importar`) para recalcular los cruces históricos.
- Bug corregido: el historial agent entrega máx. 50 filas/página; la sincronización cortaba en la primera página (300 de ~4.700 órdenes). Ahora pagina por total con 50 filas.

## Comisiones reales y cruces recalculados (2026-10-19, 4.597 órdenes de la cuenta oficial)
- `costos` (todas las monedas; comisión ÷ cantidad, OBSERVADO): MAKER compra 0,181 % · MAKER venta 0,008 % · TAKER compra 0,025 % · TAKER venta 0,142 %.
- Ciclo de comerciante (maker en ambos lados) ≈ 0,19 % + 4x1000 (0–0,4 %), no el 0,4 % que sugería el `commissionRate` de los anuncios (0,2 %).
- El sistema ahora usa las comisiones observadas en todas partes: `observed_fee` (primero COP, si no hay ≥5 órdenes, todas las monedas). Cruces: `taker_fees_from_orders` desde la base (`monitor`, `history importar`); por defecto 0,025 % / 0,142 %. `competencia`: comisión maker observada por lado, y si no hay datos, `commissionRate` del anuncio.
- `history cruces` tras reimportar: 226 ciclos cruzados, 36 episodios, **8 aprovechables** (p. ej. 12,97 COP/USDT = 0,416 % domingo 21:18; 15,88 COP = 0,507 % lunes 07:55). Conclusión: los cruces son esporádicos y pequeños → complemento con alerta; el núcleo de la estrategia son anuncios maker (Fase 5).

## Verificación con la CUENTA OFICIAL (2026-10-19 14:41 UTC, key `NpSMV...1Pze`, solo lectura, IP 181.42.23.142)
- 19 OK / 2 error (solo `getReferencePrice`). Categoría de anuncios: `profession` (comerciante). 4 anuncios propios, 30 métodos de pago.
- Órdenes: ~780 por ventana de 30 días, estable 6 meses (716–822); 23.098 órdenes históricas. Compras 30 d: 29 (COP 27, EUR 2). Ventas: mayoría VES (47/50 en la muestra).
- Historial trae `advertisementRole` (MAKER/TAKER), `takerCommission`, `takerCommissionRate`, `takerAmount`, `payMethodName`, `unitPrice`.
- Endpoint clásico `/sapi/v1/c2c/orderMatch/listUserOrderHistory`: máx. 50 filas/página y peso UID alto (900–1800). Usar el agent (`/sapi/v1/c2c/agent/...`, peso IP 1).
- `getReferencePrice`: -31002 con el cuerpo documentado; tradeType "0" → -1102 (se clasificaba mal como AUTH; corregido). Se añadieron variantes.
- La IP pública del usuario cambia tras cortes de internet → la key deja de funcionar hasta actualizar la IP en Binance. Se añadió aviso en monitor y verificador.

## Hallazgos con datos reales (2026-10-17 23:37 → 2026-10-19 ~09:00, mayormente fin de semana)
- 1.958 ciclos; 219 con cruce de precios (11,2 %); 35 episodios; 18 aprovechables con los métodos del usuario.
- Los cruces duran 0–9 min (casi todos 1–3 ciclos). Netos típicos 0,3–6 COP/USDT (0,01–0,2 %) por 57–580 USDT.
- Excepciones: 76,35 COP/USDT (2,4 %, 166 USDT, 1 ciclo — sospechoso: posible error/anuncio con condiciones ocultas o trampa), 19,53 (0,63 %, 953 USDT, 4 min, dom 21:18), 22,48 (0,72 %, 546 USDT, 8 min, lun 07:55).
- Suma optimista de lo aprovechable visible ≈ 50.000 COP en ~33 h → los cruces son complemento, no la estrategia principal (meta ≈ 127.000 COP/día). La estrategia base debe ser con anuncios propios (maker).
- Perfil lunes: 07:00 dif. prom. 6,18 (13 % cruce); 08:00 2,07 (29 % cruce, 3 % aprovechable).

## Entorno del usuario
- PC Windows, Python 3.12.10, Git 2.55, proyecto en `C:\Users\Jamer\Documents\BINANCE-P2P`, venv `.venv`.
- El Bloc de notas / `Read-Host` no guardaron las claves; usar siempre `python -m jmcambios.tools.set_keys`.

## Estructura
```
docs/FASE1_VIABILIDAD.md   diagnóstico Fase 1
docs/ARQUITECTURA.md       módulos, flujo, modos
src/jmcambios/
  config.py                configuración y resolución de modo efectivo
  logging_utils.py         logs JSON con redacción de secretos
  connectors/binance/
    endpoints.py           catálogo de endpoints oficiales (lectura/escritura)
    signing.py             firma HMAC SAPI C2C
    client.py              cliente HTTP (solo lectura en Fase 1)
  tools/verify_integration.py   verificador de solo lectura (CLI jmcambios-verify)
tests/                     pruebas unitarias (sin red)
```

## Costos operativos informados por el usuario (2026-10-18)
- Único costo bancario: **GMF 4x1000 (0,4 %)** sobre los débitos/salidas de COP de las cuentas bancarias.
- No hay comisiones por transferencia en sus métodos de pago.
- Comisión de Binance (maker): se obtiene de la API (`commissionRate`/`commission` de las órdenes), no se configura a mano.
- Aplicación prevista en Fase 4: el GMF grava el COP **pagado** al comprar USDT; el COP recibido al vender no paga GMF al entrar.
- **Exención informada por el usuario:** los pagos entre **Davivienda y Daviplata** (misma entidad) están **exentos** del 4x1000. Pagos hacia otros bancos/billeteras → 0,4 %.
- Implementación: tasa GMF **configurable por método de pago** (p. ej. Davivienda/Daviplata = 0 %, resto = 0,4 %), no fija. Así el motor de precios puede preferir anuncios con métodos exentos cuando el margen sea ajustado.
- El usuario paga **principalmente desde Bancolombia y Nequi** (2026-10-18).
- Modelo a implementar: el GMF depende de la **cuenta de origen** del débito (y de su exención/tope mensual), no del método del vendedor. Configuración por cuenta de origen: `gmf_rate`, `exempt`, `monthly_exempt_cap_cop`. Supuesto inicial: Bancolombia y Nequi = 0,4 %; Davivienda↔Daviplata = 0 % (según el usuario).
- **Verificado por el usuario en sus extractos:** Davivienda y Daviplata **nunca** cobran GMF; Bancolombia y Nequi **sí**. Se usa como dato observado.
- Riesgo: si la exención se debe a cuenta marcada exenta / bajo monto, tiene **tope mensual**. Implementar en Fase 4: acumulado mensual de débitos por cuenta + alerta al acercarse al tope (valor del tope a confirmar con Davivienda).
- Advertencia comunicada al usuario: la exención del GMF en Colombia suele depender de la cuenta marcada como exenta (una por persona, con tope mensual en UVT) o de los depósitos de bajo monto (Nequi/Daviplata, con tope), no de que origen y destino sean de la misma entidad. Validar la tasa efectiva con los **extractos bancarios** antes de la Fase 4.

## Fase 5 — diseño (2026-10-19)
- `analysis/pressure.py`: por ventana (5/15/30/60, pesos 0,15/0,30/0,30/0,25) señales normalizadas −1..1: mejor precio ASK/BID (observado, 0,1 % = señal completa, peso 1), liquidez anunciada (observado, 10 %, peso 0,6; menos oferta ASK o más demanda BID = alcista), consumo sin cambio de precio ASK−BID (inferido, 1 %, peso 0,8). Confianza = √cobertura × (0,3 + 0,7·acuerdo); solo inferidas ⇒ ≤ 50; incompleto ×0,8; datos > 10 min ⇒ ≤ 20. |puntaje| < 15 neutral, ≥ 40 fuerte.
- `pricing/engine.py`: precio = superar por 0,01 al competidor compatible nº k (8/3/1). Margen del ciclo m = 1 − P_b(1+c_s)(1+gmf)/(P_s(1−c_b)) con gmf de la cuenta exenta. Margen objetivo por escenario: mínimo + 0,30 / 0,15 / 0 pp. Si no alcanza se abre la diferencia (P_b/k^w, P_s·k^(1−w)); w = 0,25 con presión alcista (cede la venta), 0,75 bajista, 0,5 neutral o confianza < 50.
- Hallazgo con datos reales: el mercado suele estar apretado/cruzado; con el margen mínimo no se puede estar de primero en ambos lados a la vez → la estrategia es elegir lado según presión y horario (horas con mayor diferencial del historial).
- Escenarios monótonos: el conservador nunca compra más caro ni vende más barato que el equilibrado (bug visto con datos reales y corregido).
- Primera ejecución real (2026-10-19 11:27 COT): mercado cruzado (venta 3.149 / compra 3.160). Presión neutral +11, confianza 50 (vendedores −9 COP en 60 min; posibles ejecuciones: 33.830 USDT consumidos a vendedores vs 9.763 a compradores [inferido]). Equilibrado: comprar 3.135,44 (#10 de 145 compatibles) / vender 3.155,59 (#4 de 278), margen 0,45 % ≈ 14,21 COP/USDT → meta 127.000 COP/día exige ≈ 8.935 USDT/día = 2,8× capital de 10 M. Horas con mayor diferencial en días hábiles: 02–04 h (≈ 17–18 COP), muestra aún pequeña.
- Inventario de 4.100 USDT a 3.239 en `recomendar` = compras COP que salieron por remesas (VES); el cálculo COP no ve esas salidas.
- Pendiente de fases posteriores: decisión con 7 validaciones (Fase 8), panel (Fase 6), simulación (Fase 7).

## Fase 6 — diseño (2026-10-19)
- `monitor/advisor.py` tras cada ciclo: lee mis anuncios cada N ciclos (5 por defecto), calcula escenarios (`pricing.plan`) y posiciones, evalúa reglas (`alerts/rules.py`), envía por `AlertManager` (enfriamiento por clave usando la tabla `alerts`) y escribe `data/estado.json` de forma atómica.
- Alertas de anuncios propios solo en modo RECOMMENDATION/AUTOMATIC (en OBSERVATION no se sugieren precios).
- Panel: `http.server` de la biblioteca estándar (sin dependencias nuevas), GET solamente (POST → 405), clave en `?t=` comparada con `hmac.compare_digest`, sin registrar URLs (llevan la clave). Acceso fuera de casa = VPS (pendiente).
- Telegram: token y chat_id en `.env` (redactados en registros vía `Settings.secret_values()`); los errores de red no propagan la URL con el token.

## Meta de margen del usuario (2026-10-19)
- Busca **≥ 1 % libre por ciclo** (≈ 31,5 COP/USDT). Referencia del mercado colombiano: 2 % bruto − 4x1000 ≈ 1,6 % (≈ 1,4 % tras comisión Binance).
- Para 1 % libre la diferencia compra→venta debe ser ≈ 1,2 % (≈ 38 COP) pagando desde cuenta exenta, ≈ 1,6 % (≈ 50 COP) con 4x1000.
- Con 1 % y 10 M COP, la meta de 127.000 COP/día exige ≈ 1,3 vueltas/día. La Fase 7 debe medir con qué frecuencia el mercado da esas diferencias (incluida la estrategia temporal: comprar en baja y vender en alza) y comparar 20–60 COP por USDT.
- Configurable con `JMC_MARGEN_MIN` (en %, por defecto 0,3; el usuario usará 1).
- Panel: selector de ganancia (0,5/1/1,5/2 % u otro) → `/api/escenarios?margen=X` recalcula con el último libro de `ad_states`, costos/perfiles/presión de `estado.json`. Solo vista (se recuerda en el navegador); no cambia alertas.

## Ideas registradas
- Producto por suscripción (pedido del usuario 2026-10-19): multiusuario en servidor con IP fija, keys de terceros cifradas y solo lectura, configuración por usuario (bancos/4x1000, moneda, márgenes), registro y pagos, revisión legal (condiciones de Binance para terceros, Ley 1581 de 2012). Riesgo: suscriptores con la misma estrategia compiten entre sí. Primero validar con resultados reales del usuario. Mantener nada personal fijo en el código.

## Próximos pasos
1. ✅ API key de solo lectura creada (IP whitelist) y guardada con `python -m jmcambios.tools.set_keys`.
2. ✅ `jmcambios-verify` ejecutado en el PC Windows del usuario (resultados en docs/FASE1_VIABILIDAD.md §11).
2b. ✅ Aclarado: la key verificada es de una cuenta de prueba.
2c. ✅ Fase 2 aprobada por el usuario: **solo USDT/COP por ahora**; más mercados y exchanges en el futuro (arquitectura preparada).
2e. ✅ Primera ejecución real del monitor (2026-10-17 23:37 COT): 194 anuncios ASK / 126 comerciantes; 188 BID / 144 comerciantes; mejor ASK 3.160, mejor BID 3.150, spread +10 COP (0,317 %). **Mapeo de lados confirmado** (spread positivo, sin avisos de lado distinto). Libro completo recorrido.
2f. ✅ Prueba de 24 h superada (~33 h).
- Observaciones: cruces de precio reales (spread negativo, p. ej. −4,41 COP el domingo 08:26) → mejorar alerta para indicar si el cruce es ejecutable (método de pago común, montos compatibles, neto con/sin 4x1000). Lunes 08:59: 279 ASK / 340 BID; liquidez BID 12,8 M USDT con un comerciante concentrando 39 % (HHI 1815).
3. ✅ Fase 3 entregada; siguiente: Fase 4 (requiere API key de solo lectura de la CUENTA OFICIAL para órdenes y comisiones reales). Antes era: Fase 3 (historial, estadísticas 5/15/30/60 min, por hora y tipo de día) + mejora de la alerta de cruce. El usuario debe mantener el monitor corriendo para acumular días hábiles.
- Observación para Fase 4: con spread de 10 COP (0,32 %) en la cima del libro, el GMF de 0,4 % (Bancolombia/Nequi) lo vuelve negativo; solo pagando desde Davivienda/Daviplata (exentas) queda margen. Métodos más frecuentes: BreBKeys, Nequi, BancolombiaSA.
2d. ⏳ Antes de Fase 4: key de solo lectura de la cuenta oficial + `jmcambios-verify`.
3. ✅ Costos: recibidos (solo 4x1000).
4. Con el informe: actualizar matriz 🔎 → ✅/⛔ y comenzar Fase 2.
