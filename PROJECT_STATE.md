# PROJECT_STATE — documento de referencia entre sesiones

> Leer este archivo al empezar cualquier sesión nueva. Actualizarlo al terminar cada cambio.

## Proyecto
Agente inteligente Binance P2P USDT/COP para **JM Cambios** (comerciante verificado).
Rama de desarrollo: `claude/binance-p2p-trading-agent-madi2s`.

## Estado de fases

| Fase | Estado |
|---|---|
| 1. Viabilidad e integraciones | ✅ Diagnóstico · ✅ Verificación real ejecutada 2026-10-18 (16 OK / 2 error) · ⏳ Pendiente: confirmar cuenta de la key (0 anuncios/órdenes/métodos de pago) y resolver `getReferencePrice` |
| 2. Monitor de anuncios | 🟡 Implementada (2026-10-18), 76 pruebas OK · ⏳ Pendiente: ejecución real en el PC del usuario ≥ 24 h sin errores no controlados |
| 3–10 | ⛔ No iniciadas |

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

## Próximos pasos
1. ✅ API key de solo lectura creada (IP whitelist) y guardada con `python -m jmcambios.tools.set_keys`.
2. ✅ `jmcambios-verify` ejecutado en el PC Windows del usuario (resultados en docs/FASE1_VIABILIDAD.md §11).
2b. ✅ Aclarado: la key verificada es de una cuenta de prueba.
2c. ✅ Fase 2 aprobada por el usuario: **solo USDT/COP por ahora**; más mercados y exchanges en el futuro (arquitectura preparada).
2e. ✅ Primera ejecución real del monitor (2026-10-17 23:37 COT): 194 anuncios ASK / 126 comerciantes; 188 BID / 144 comerciantes; mejor ASK 3.160, mejor BID 3.150, spread +10 COP (0,317 %). **Mapeo de lados confirmado** (spread positivo, sin avisos de lado distinto). Libro completo recorrido.
2f. ⏳ Usuario: dejar `jmcambios-monitor --interval 60 --brief` corriendo ~24 h para cerrar la Fase 2.
- Observación para Fase 4: con spread de 10 COP (0,32 %) en la cima del libro, el GMF de 0,4 % (Bancolombia/Nequi) lo vuelve negativo; solo pagando desde Davivienda/Daviplata (exentas) queda margen. Métodos más frecuentes: BreBKeys, Nequi, BancolombiaSA.
2d. ⏳ Antes de Fase 4: key de solo lectura de la cuenta oficial + `jmcambios-verify`.
3. ✅ Costos: recibidos (solo 4x1000).
4. Con el informe: actualizar matriz 🔎 → ✅/⛔ y comenzar Fase 2.
