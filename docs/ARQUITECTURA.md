# Arquitectura — JM Cambios P2P Agent

## Principios

1. **Lógica de negocio independiente del exchange.** Todo el análisis trabaja sobre modelos de dominio propios (`jmcambios.domain`). Binance es un *adaptador* (`jmcambios.connectors.binance`). Añadir otro mercado o exchange = nuevo adaptador.
2. **Seguro por defecto.** Modo OBSERVACIÓN por defecto; escritura solo con varias llaves simultáneas (ver `config.py → effective_mode`).
3. **Procedencia explícita del dato.** Cada valor lleva su procedencia: `OBSERVED` (Binance), `CALCULATED` (sistema), `INFERRED` (estimación), `UNVERIFIABLE`.
4. **Todo queda auditado.** Ninguna decisión sin registro.

## Módulos (nombres estables — no renombrar)

| # | Módulo | Paquete | Fase |
|---|---|---|---|
| 1 | Conector de datos Binance P2P | `jmcambios.connectors.binance` | 1 (base), 2 |
| 2 | Validador y normalizador | `jmcambios.normalizer` | 2 |
| 3 | Base de datos histórica | `jmcambios.storage.history` (SQLite: `snapshots`, `cycles`, `ad_states` solo-cambios) | 3 |
| 4 | Analizador de competencia | `jmcambios.analysis.competition` (posición estimada, competidores por delante, precios límite) | 4 |
| 5 | Detector de cambios de liquidez | `jmcambios.analysis.liquidity` (ventanas 5/15/30/60, perfil horario, episodios de cruce) · `jmcambios.analysis.pressure` (presión −100..100 + confianza, señales observado/inferido/no verificable) | 3, 5 |
| 6 | Motor de precios | `jmcambios.pricing.engine` (3 escenarios por puesto objetivo entre compatibles + margen mínimo por escenario; concesión según presión) | 5 |
| 7 | Calculadora de rentabilidad | `jmcambios.profitability` (costo promedio, realizado/estimado, 4x1000 con rango) | 4 |
| 8 | Motor de decisión | `jmcambios.decision` | 5, 8 |
| 9 | Ejecutor de acciones autorizadas | `jmcambios.executor` | 9 |
| 10 | Sistema de riesgos | `jmcambios.risk` | 5, 9 |
| 11 | Panel de control | `jmcambios.dashboard` (servidor stdlib de solo lectura + clave; lee `data/estado.json` y la base) | 6 |
| 12 | Sistema de alertas | `jmcambios.alerts` (Telegram Bot API `sendMessage`, SMTP; reglas + enfriamiento por clave; tabla `alerts`) · asesor del monitor `jmcambios.monitor.advisor` | 6 |
| 13 | Auditoría y registro | `jmcambios.audit` | 2+ |
| — | Modelos de dominio (independientes del exchange) | `jmcambios.domain` | 2 |
| — | Estadísticas de snapshot y filtros de relevancia | `jmcambios.analysis.market_stats`, `jmcambios.analysis.filters` | 2 |
| — | Monitor periódico + registro de snapshots | `jmcambios.monitor` | 2 |
| — | Cruces de precio (aprovechables con mis métodos) | `jmcambios.analysis.crossing` | 3 |
| — | Importación de snapshots a la base | `jmcambios.storage.importer` | 3 |
| — | Cuenta propia: órdenes y anuncios | `jmcambios.domain.account`, `jmcambios.connectors.binance.account` | 4 |
| — | Configuración y modos | `jmcambios.config` | 1 |
| — | Herramientas (verificador, etc.) | `jmcambios.tools` | 1 |

## Flujo de datos

```
          ┌────────────────────── Binance ──────────────────────┐
          │ Public agent API (sin auth)   C2C Agent SAPI (HMAC) │
          └───────────────┬───────────────────────┬─────────────┘
                          │ (1) Conector          │
                          ▼                       │
                 (2) Normalizador ── rechaza datos incoherentes
                          │
                          ▼
                 (3) Almacenamiento histórico (snapshots)
                          │
         ┌────────────────┼──────────────────┐
         ▼                ▼                  ▼
 (4) Competencia   (5) Liquidez      (7) Rentabilidad ◄── mis órdenes + costos
         └────────┬───────┴──────────────────┘
                  ▼
          (6) Motor de precios — 3 escenarios
                  ▼
          (8) Motor de decisión ──► (10) Riesgos: 7 validaciones + kill-switch
                  │                         │
       OBSERVACIÓN│RECOMENDACIÓN            │ AUTOMÁTICO (solo si todo OK)
                  ▼                         ▼
     (11) Panel / (12) Alertas      (9) Ejecutor idempotente ──► Binance
                  └──────────── (13) Auditoría ◄──────────┘
```

## Convenciones de dominio

- `Side.ASK`: el **anunciante vende** USDT (en Binance se obtiene con `tradeType=BUY`). Compite con mis anuncios de venta.
- `Side.BID`: el **anunciante compra** USDT (`tradeType=SELL`). Compite con mis anuncios de compra.
- Mejor precio: ASK = el más bajo; BID = el más alto. Spread = mejor ASK − mejor BID (negativo ⇒ anomalía).
- Cantidades = **liquidez anunciada**. El volumen ejecutado del mercado no es observable.
- Nuevo exchange/mercado = nuevo adaptador que implemente `MarketSource.fetch(side) -> MarketSnapshot`; el análisis no cambia.

## Modos

| Modo | Lee mercado | Recomienda | Escribe en Binance |
|---|---|---|---|
| `OBSERVATION` (defecto) | ✅ | ❌ | ❌ |
| `RECOMMENDATION` | ✅ | ✅ (aprobación manual) | ❌ |
| `AUTOMATIC` | ✅ | ✅ | ✅ solo acciones permitidas, tras validaciones |

`AUTOMATIC` se degrada automáticamente a `RECOMMENDATION` si falta: `AUTO_MODE_ENABLED=true`, credenciales de escritura, informe de verificación aprobado o límites de riesgo configurados.

## Seguridad de credenciales

- Dos juegos de credenciales separados: `BINANCE_API_KEY/SECRET` (lectura) y `BINANCE_TRADE_API_KEY/SECRET` (gestión de anuncios, Fase 9).
- `SecretStr` en configuración; `jmcambios.logging_utils.RedactingFilter` enmascara keys y elimina `signature`.
- Firma HMAC-SHA256 **sin ordenar parámetros** (requisito SAPI C2C), con codificación RFC 3986.
