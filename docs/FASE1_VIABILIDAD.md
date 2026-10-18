# FASE 1 — Diagnóstico técnico de viabilidad

**Proyecto:** Agente inteligente Binance P2P USDT/COP — JM Cambios
**Fecha del análisis:** 2026-10-18
**Estado:** Entregado para revisión. No se avanza a la Fase 2 sin aprobación.

---

## 0. Resumen ejecutivo

| Pregunta | Respuesta corta |
|---|---|
| ¿Se puede monitorear el mercado P2P USDT/COP con fuentes oficiales? | **Sí.** Binance publica endpoints de consulta pública y autenticados para buscar anuncios. |
| ¿Se pueden modificar mis anuncios por API? | **Sí, según la documentación oficial de Binance (abril 2026)**, mediante la "C2C Agent SAPI": publicar, actualizar y cambiar estado (online/offline/cerrar). **Requiere permiso de comerciante y una API key con permisos de escritura.** Falta verificarlo con *tu* cuenta. |
| ¿Se puede conocer el volumen realmente ejecutado del mercado? | **No.** Binance no publica las operaciones ejecutadas de terceros. Solo tus propias órdenes. Usaremos aproximaciones etiquetadas como *inferidas*. |
| ¿Se puede marcar como pagado / liberar USDT por API? | **No existe endpoint** y, además, el sistema **nunca** lo hará por diseño. |
| ¿Es viable el proyecto completo? | **Sí, con matices**: los modos Observación y Recomendación son plenamente viables. El modo Automático es técnicamente posible con la API oficial, pero debe confirmarse con tu cuenta (permisos, límites de frecuencia y condiciones de uso) antes de activarlo. |

> **Importante — lo que NO pude verificar desde aquí.** El entorno donde se desarrolló este análisis tiene el acceso de red a `binance.com` y `api.binance.com` **bloqueado** (el proxy devuelve 403). Por tanto **ninguna llamada real a Binance se ha ejecutado todavía**. Todo lo marcado como "confirmado" está confirmado **en la documentación oficial**, no en ejecución contra tu cuenta. Para cerrar esa brecha, este repositorio incluye un verificador de solo lectura (`jmcambios-verify`) que debes ejecutar tú desde tu PC o servidor (ver §8).

---

## 1. Fuentes investigadas

1. **Binance Skills Hub — skill oficial `p2p`** (repositorio `github.com/binance/binance-skills-hub`, carpeta `skills/binance/p2p`, versión 1.1.0 del 2026-04-20, commit revisado del 2026-09-11). Es material publicado por Binance ("Built by Binance") con la referencia completa de la **C2C Agent SAPI** (`references/agent-sapi-api.md`) y de autenticación (`references/authentication.md`).
2. **Documentación oficial Binance C2C** — `developers.binance.com/docs/c2c/rest-api`: endpoint `GET /sapi/v1/c2c/orderMatch/listUserOrderHistory` (historial C2C del usuario, máximo 30 días por consulta, solo últimos 6 meses, 100 filas por página).
3. Endpoint web interno `p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search` — usado por la web de Binance y por muchos bots de terceros. **No está documentado oficialmente**; lo descartamos como fuente principal (ver §4).

---

## 2. Matriz de funciones

Leyenda: ✅ Confirmado en documentación oficial · 🔎 Requiere verificación con tu cuenta · ⛔ No disponible por integración autorizada

### 2.1 Datos de mercado

| Función solicitada | Estado | Fuente / mecanismo | Notas |
|---|---|---|---|
| Precio de cada anuncio de compra/venta | ✅ | Público: `GET www.binance.com/bapi/c2c/v1/public/c2c/agent/ad-list` (máx. 20 anuncios por consulta). Autenticado: `POST api.binance.com/sapi/v1/c2c/agent/ads/search` (paginado `page`/`rows`). | El endpoint autenticado permite recorrer más profundidad del mercado. |
| Precio de referencia del mercado | ✅ | `POST /sapi/v1/c2c/agent/ads/getReferencePrice` y público `quote-price` | Útil como ancla para el control "diferencia máxima respecto al precio de referencia". |
| Mín/máx, mediana, promedio ponderado | ✅ (cálculo propio) | Calculado a partir de los anuncios recogidos | Etiquetado como *cálculo del sistema*. |
| Número de anuncios activos por lado | 🔎 | Campo `total` de la respuesta paginada de `ads/search` | Hay que comprobar que `total` refleje el total real y no un tope. |
| Cantidad de comerciantes competidores | ✅ (cálculo propio) | `advertiser.userNo` únicos | |
| USDT disponible por anuncio | ✅ | `surplusAmount`, `tradableQuantity` | Es *liquidez anunciada*, **no** volumen ejecutado. |
| Límites mín/máx por operación | ✅ | `minSingleTransAmount`, `maxSingleTransAmount` | |
| Métodos de pago | ✅ | `tradeMethods[].identifier` y `trade-methods` | Los identificadores para COP (p. ej. Bancolombia, Nequi…) deben obtenerse del endpoint, nunca escribirse a mano. |
| Reputación del comerciante | ✅ | `orderCount`, `monthOrderCount`, `monthFinishRate`, `advConfirmTime`, `userType` | Base para filtrar anuncios irrelevantes. |
| Fecha de publicación del anuncio | 🔎 | `createTime` existe en el esquema del anuncio | Verificar que `search` lo devuelva para anuncios de terceros. |
| Cambios de precio (5/15/30/60 min) | ✅ (cálculo propio) | Comparación de snapshots almacenados | El sistema solo "ve" cambios entre muestreos. |
| Aparición/desaparición de anuncios | ✅ (cálculo propio) | Diff de `advNo` entre snapshots | |
| Posición de mis anuncios | ✅ | Mis anuncios (`ads/listWithPagination`) vs. ranking de `search` | Posición *estimada*: Binance puede ordenar con criterios propios además del precio. |
| Concentración de la oferta | ✅ (cálculo propio) | HHI / cuota top-N por `surplusAmount` | |
| **Volumen realmente ejecutado del mercado** | ⛔ | No existe fuente oficial | Proxy *inferido*: caída de `surplusAmount` entre snapshots sin cambio de precio + `monthOrderCount`. Siempre etiquetado como inferido y no verificable. |
| Mis operaciones ejecutadas | ✅ | `GET /sapi/v1/c2c/agent/orderMatch/listUserOrderHistory`, `POST .../listOrders`, `.../getUserOrderDetail` | Incluye comisión maker/taker → contabilidad real. |
| Disputas / apelaciones propias | ✅ | `POST /sapi/v1/c2c/agent/complaint/query-complaints` | Para la estimación de pérdidas por disputas. |
| Referencia externa TRM (COP/USD) | 🔎 | Datos Abiertos Colombia (Banco de la República / Superfinanciera), dataset `32sa-8pi3` en `datos.gov.co` | Fuente pública oficial; verificar disponibilidad desde el servidor. |

### 2.2 Gestión de anuncios

| Función | Estado | Endpoint oficial | Notas |
|---|---|---|---|
| Listar mis anuncios | ✅ | `POST /sapi/v1/c2c/agent/ads/listWithPagination` | Solo lectura. |
| Detalle de un anuncio propio | ✅ | `POST /sapi/v1/c2c/agent/ads/getDetailByNo?advNo=…` | Necesario para "verificar estado actual antes de cambiar". |
| Crear anuncio | ✅ 🔎 | `POST /sapi/v1/c2c/agent/ads/post` | Requiere permiso de comerciante. Devuelve `advNo`. |
| Modificar precio / cantidad / límites | ✅ 🔎 | `POST /sapi/v1/c2c/agent/ads/update` | **Actualización de objeto completo**: enviar solo `advNo`+`price` produce error `-9000`. Flujo obligatorio: leer detalle → fusionar cambios → enviar objeto completo. |
| Pausar / reactivar / cerrar | ✅ 🔎 | `POST /sapi/v1/c2c/agent/ads/updateStatus` (1=online, 3=offline, 4=cerrado) | Operación por lotes con `failList`. |
| Precio flotante (ratio sobre referencia) | ✅ 🔎 | `priceType=2`, `priceFloatingRatio` | Alternativa a modificar el precio con frecuencia: menos llamadas de escritura. |
| Métodos de pago del usuario | ✅ | `GET /sapi/v1/c2c/agent/ads/getPayMethodByUserId` | En anuncios de VENTA se usa `payId`; en COMPRA el `identifier`. `payId` nunca se muestra al usuario. |
| Límite de frecuencia de modificaciones | 🔎 | No documentado | Se aplicará un límite propio conservador y se medirá. |
| Idempotencia nativa | ⛔ | La API no ofrece clave de idempotencia | La implementamos nosotros (ver §6). |
| Política de uso automatizado | 🔎 | La skill oficial exige confirmación humana en *su* flujo conversacional | Es una regla de diseño de la skill, no de la API. Aun así, **debes confirmar con tu gestor de comerciante Binance** que el uso automatizado de estos endpoints está permitido para tu cuenta antes del Modo 3. |

### 2.3 Operaciones que el sistema nunca hará

| Acción | Estado | Motivo |
|---|---|---|
| Marcar orden como pagada | ⛔ | No hay endpoint y está prohibido por diseño. |
| Liberar USDT / confirmar recepción de pago | ⛔ | No hay endpoint. La liberación es **siempre manual**, tras verificar el pago en tu banco. |
| Iniciar/cancelar apelaciones automáticamente | ⛔ | Fuera del alcance; acciones irreversibles. |
| Usar endpoints no documentados, scraping con sesión del navegador, eludir CAPTCHA o límites | ⛔ | Prohibido por tus requisitos y por las condiciones de Binance. |
| Pedir/almacenar contraseña, 2FA, semillas o claves privadas | ⛔ | Solo API key + secret con permisos mínimos, en variables de entorno. |

---

## 3. Accesos que necesitamos de ti

| # | Acceso | Para qué | Fase |
|---|---|---|---|
| 1 | Nada (endpoints públicos) | Monitor básico del mercado | 2 |
| 2 | **API key de Binance — solo "Enable Reading"**, con **restricción por IP** | Búsqueda autenticada profunda, mis anuncios, mis órdenes, comisiones | 2–8 |
| 3 | Un **servidor con IP fija** (VPS) en una región no restringida por Binance | Lista blanca de IP de la API key y operación 24/7 | 2+ |
| 4 | Bot de **Telegram** (token de @BotFather) + tu `chat_id` | Notificaciones | 6 |
| 5 | Tabla de **costos reales**: comisiones bancarias por banco/método (Bancolombia, Nequi, Daviplata, etc.), 4x1000 (GMF) si aplica, costos operativos | Módulo de rentabilidad | 4 |
| 6 | **Segunda API key, con permiso de gestión de anuncios**, también restringida por IP, **sin permiso de retiro** | Ejecución real | 9 (no antes) |
| 7 | Confirmación de Binance (gestor de comerciante / soporte) sobre límites de frecuencia y uso automatizado de la Agent SAPI | Habilitar Modo 3 | 9 |

**Nunca habilitar** en ninguna API key: retiros, transferencias universales, trading de margen/futuros.

---

## 4. Por qué no usamos el endpoint "friendly" de la web

`p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search` es el endpoint que usa la página web. Funciona sin autenticación y es lo que usan la mayoría de bots, pero:

- No está documentado como API para integraciones; puede cambiar o bloquearse sin aviso.
- Tus requisitos excluyen endpoints no oficiales.

Desde abril de 2026 Binance publica endpoints **documentados** equivalentes (`/bapi/c2c/v1/public/c2c/agent/*` sin autenticación y `/sapi/v1/c2c/agent/*` con autenticación), por lo que no hace falta recurrir al endpoint web. El conector queda aislado detrás de una interfaz, de modo que cambiar de fuente no afecta a la lógica de negocio.

---

## 5. Limitaciones del mercado P2P que condicionan el análisis

1. **No es un libro de órdenes centralizado.** Un anuncio con 10.000 USDT no significa que haya 10.000 USDT de demanda real: es *dinero anunciado*. Cada indicador del sistema se clasificará como:
   - **Observado**: dato devuelto por Binance (precio, cantidad anunciada, límites).
   - **Inferido**: derivado por el sistema (p. ej. "posible ejecución" cuando `surplusAmount` baja sin cambio de precio).
   - **No verificable**: hipótesis que no puede contrastarse (p. ej. el flujo real de dinero).
2. **Muestreo discreto.** Lo que ocurra entre dos consultas no se ve. La frecuencia de muestreo se ajustará al límite de peso de la API (los endpoints SAPI comparten el presupuesto de peso por IP de Binance).
3. **El orden de la lista no es solo por precio.** Binance puede priorizar anuncios por otros criterios; la "posición" es siempre una estimación.
4. **Filtros por monto.** Un anuncio con mínimo de 5.000.000 COP no compite por operaciones de 200.000 COP. El análisis se hará por *segmento de monto* (`transAmount`) y por método de pago.
5. **Precios en COP sin decimales relevantes.** El incremento mínimo de precio y la escala (`priceScale`) se obtendrán de `getReferencePrice`.

---

## 6. Requisitos de seguridad que la arquitectura garantiza

- **Modo por defecto: OBSERVACIÓN.** El Modo AUTOMÁTICO solo puede activarse si se cumplen simultáneamente: bandera explícita en configuración, API key de escritura presente, verificación de integración aprobada y límites de riesgo configurados. Si falta cualquiera, el sistema arranca en un modo inferior.
- **Idempotencia propia.** Cada acción tiene una clave determinista (`advNo` + tipo de acción + valores objetivo + ventana de tiempo). Antes de ejecutar: (1) se consulta el registro de auditoría por esa clave; (2) se relee el anuncio con `getDetailByNo`; (3) si el anuncio ya tiene el valor objetivo, se registra "sin cambios" y no se llama a `update`. Para `post` (crear) se comprueba antes en `listWithPagination` que no exista ya un anuncio equivalente.
- **Las 7 comprobaciones previas** de tu §7 se implementan como un "pipeline" de validadores; cualquiera que falle bloquea la acción y queda registrada con su motivo.
- **Interruptor de emergencia (kill-switch):** archivo/flag que detiene toda escritura de inmediato.
- **Secretos:** solo variables de entorno o gestor de secretos; un filtro de logs enmascara la API key (primeros 5 + últimos 4 caracteres) y elimina `signature`, `secret` y `payId`.
- **Auditoría inmutable:** cada decisión guarda datos de entrada, cálculo de rentabilidad, regla aplicada, acción solicitada y resultado real.

---

## 7. Stack tecnológico recomendado

| Componente | Elección | Justificación |
|---|---|---|
| Lenguaje | **Python 3.12+** | Ecosistema maduro para análisis de datos y estadística; fácil mantenimiento. |
| HTTP | `httpx` | Cliente moderno con *timeouts*, reintentos y transporte simulable para pruebas. |
| Modelos/validación | `pydantic` v2 + `pydantic-settings` | Validación estricta de datos de Binance y configuración por entorno. |
| Base de datos | **SQLite** (Fases 2–8) → **PostgreSQL** (producción, opcional) vía SQLAlchemy | SQLite es suficiente para un solo mercado y cero coste; migración sencilla. |
| Planificador | Bucle `asyncio` propio con recuperación tras reinicio | Pocas dependencias, control total del ritmo de consultas. |
| Panel web | **FastAPI** + HTML/JS ligero instalable como **PWA** en Android | Sin app nativa; funciona en teléfono y tableta. |
| Notificaciones | **Telegram Bot API** (correo como alternativa) | Gratis, inmediato, compatible con Android. |
| Pruebas | `pytest` + transportes HTTP simulados | Sin llamadas reales a Binance en pruebas automáticas. |
| Despliegue | VPS Linux (≈ 5–7 USD/mes) con IP fija + `systemd` o Docker | Necesario para la lista blanca de IP. **Evitar regiones bloqueadas por Binance** (p. ej. IPs de EE. UU. reciben 451/403 en `api.binance.com`). |

---

## 8. Cómo cerrar la verificación de la Fase 1 (tu acción)

Desde tu PC o VPS (no desde este entorno, que no tiene salida a Binance):

```bash
git clone <repo> && cd BINANCE-P2P
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # Rellenar BINANCE_API_KEY y BINANCE_API_SECRET (key de SOLO LECTURA)
jmcambios-verify              # Solo lectura. Nunca llama a endpoints de escritura.
```

El verificador comprueba, uno por uno, los endpoints públicos y autenticados de lectura, informa del resultado (OK / sin permiso / error), y escribe un informe en `reports/verificacion_<fecha>.json`. **Comparte conmigo ese informe** (no contiene secretos) para marcar cada 🔎 como ✅ o ⛔.

---

## 9. Plan de implementación por fases

| Fase | Entregable | Criterio para pasar a la siguiente |
|---|---|---|
| **1** | Este diagnóstico, arquitectura, estructura del proyecto, verificador de integración, pruebas | Informe de `jmcambios-verify` ejecutado por ti con endpoints de lectura en ✅ |
| 2 | Conector de mercado (público + autenticado), normalizador, monitor periódico USDT/COP compra y venta, filtros | Monitor corriendo ≥ 24 h sin errores no controlados |
| 3 | Almacenamiento de snapshots, estadísticas de liquidez (5/15/30/60 min), concentración, altas/bajas de anuncios | Estadísticas reproducibles sobre datos reales |
| 4 | Analizador de competencia + calculadora de rentabilidad (realizada / estimada / potencial) con tus costos reales | Cuadre del beneficio con tu historial real de órdenes |
| 5 | Detector de presión (observado/inferido/no verificable, confianza 0–100) + motor de precios con 3 escenarios | Revisión manual de recomendaciones durante varios días |
| 6 | Panel web PWA + notificaciones Telegram | Uso real desde tu teléfono |
| 7 | Backtesting sobre snapshots históricos (solo lectura) | Métricas de la estrategia frente a tu operación real |
| 8 | Simulación en tiempo real (*paper trading*) en Modo Recomendación | ≥ 2 semanas con resultados coherentes |
| 9 | Ejecutor real con API de escritura, idempotencia, 7 validaciones, kill-switch | Pruebas en anuncio de bajo monto + aprobación explícita tuya |
| 10 | Supervisión, ajuste de parámetros, mejoras | Continuo |

---

## 10. Riesgos principales

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Binance cambia o restringe la Agent SAPI | Alto | Conector aislado tras interfaz; degradación automática a Modo Observación. |
| Límites de frecuencia no documentados | Medio | Límite propio conservador, retroceso exponencial, medición de cabeceras de peso usado. |
| Interpretación errónea de liquidez anunciada como demanda real | Medio | Clasificación observado/inferido/no verificable en todo el sistema y en el panel. |
| Fraude de terceros (pagos falsos, triangulación) | Alto | El sistema nunca libera fondos; alertas por contrapartes y exposición. |
| Fuga de credenciales | Alto | Permisos mínimos, IP whitelist, sin retiros, redacción en logs, `.env` fuera de git. |
| Región del servidor bloqueada por Binance | Medio | Elegir VPS fuera de jurisdicciones restringidas y verificar con `jmcambios-verify`. |
