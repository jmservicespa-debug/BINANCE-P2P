# PROJECT_STATE — documento de referencia entre sesiones

> Leer este archivo al empezar cualquier sesión nueva. Actualizarlo al terminar cada cambio.

## Proyecto
Agente inteligente Binance P2P USDT/COP para **JM Cambios** (comerciante verificado).
Rama de desarrollo: `claude/binance-p2p-trading-agent-madi2s`.

## Estado de fases

| Fase | Estado |
|---|---|
| 1. Viabilidad e integraciones | ✅ Diagnóstico · ✅ Verificación real ejecutada 2026-10-18 (16 OK / 2 error) · ⏳ Pendiente: confirmar cuenta de la key (0 anuncios/órdenes/métodos de pago) y resolver `getReferencePrice` |
| 2. Monitor de anuncios | ⛔ No iniciada (bloqueada hasta cerrar Fase 1) |
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
- Dice tener >300 órdenes en total; la verificación devolvió 0 órdenes/0 métodos de pago → diagnosticando si la key es de otra cuenta o si el endpoint agent no devuelve su historial (se añadió comparación con el endpoint C2C clásico y ventanas de 6 meses).
- La arquitectura ya parametriza `JMC_FIAT`; extender a USDT/VES es candidato natural tras la Fase 2 (decisión pendiente del usuario).

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
2b. ⏳ Usuario: confirmar si la key es de la cuenta comerciante principal (no subcuenta) y si tiene anuncios/órdenes recientes; reejecutar `git pull` + `jmcambios-verify` para probar variantes de `getReferencePrice`.
3. ✅ Costos: recibidos (solo 4x1000).
4. Con el informe: actualizar matriz 🔎 → ✅/⛔ y comenzar Fase 2.
