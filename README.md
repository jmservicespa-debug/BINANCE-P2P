# JM Cambios — Agente Binance P2P USDT/COP

Sistema de observación, análisis y posicionamiento estratégico de anuncios Binance P2P para el mercado USDT/COP.

**Estado actual: FASE 6 (panel para el celular y alertas por Telegram).** Ver:
- [`docs/FASE1_VIABILIDAD.md`](docs/FASE1_VIABILIDAD.md) — diagnóstico técnico: qué está confirmado, qué falta verificar y qué no es posible.
- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) — módulos y flujo.
- [`PROJECT_STATE.md`](PROJECT_STATE.md) — estado del proyecto entre sesiones.

> El sistema arranca siempre en **Modo OBSERVACIÓN**. No puede modificar anuncios en esta fase: el cliente rechaza los endpoints de escritura antes de tocar la red. Nunca marca órdenes como pagadas ni libera USDT.

## Requisitos
- Python 3.12 o superior
- Git
- (Para lectura autenticada) API key de Binance con **solo "Enable Reading"** y **restricción por IP**

## Instalación

```bash
git clone https://github.com/jmservicespa-debug/BINANCE-P2P.git
cd BINANCE-P2P
git checkout claude/binance-p2p-trading-agent-madi2s
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # Windows: copy .env.example .env
```

Guarda la key de **solo lectura** con el asistente (pide las claves sin mostrarlas y las escribe en `.env`):

```bash
python -m jmcambios.tools.set_keys
```

Las variables `BINANCE_TRADE_*` deben quedar vacías.

## Verificación de integración (cierre de la Fase 1)

```bash
jmcambios-verify               # endpoints públicos + autenticados de lectura
jmcambios-verify --skip-auth   # solo endpoints públicos (sin API key)
```

Muestra una tabla con el resultado de cada endpoint y guarda `reports/verificacion_<fecha>.json`. El informe **no contiene secretos ni datos personales** (solo resultados, códigos y nombres de campos). Compártelo para actualizar la matriz de viabilidad.

Resultados posibles: `OK`, `AUTH_ERROR` (key/firma/hora), `PERMISSION_DENIED` (p. ej. falta permiso de comerciante), `GEO_OR_IP_BLOCKED` (región o IP no permitida), `RATE_LIMITED`, `API_ERROR`, `NETWORK_ERROR`.

## Monitor del mercado (Fase 2)

Solo lee datos; no modifica anuncios. Con API key recorre el libro completo; sin ella usa la lista pública (20 anuncios por lado).

```bash
jmcambios-monitor --once                      # un ciclo y salir
jmcambios-monitor                             # cada 60 s hasta Ctrl+C
jmcambios-monitor --interval 120 --brief      # cada 2 min, salida resumida
jmcambios-monitor --pay BancolombiaSA,Nequi --amount 1.000.000 --min-finish-rate 95 --merchants-only
```

| Opción | Uso |
|---|---|
| `--pay` | Métodos de pago compatibles (identificadores de Binance: `BancolombiaSA`, `Nequi`, `DaviviendaSA`, `Daviplata`, `BreBKeys`…) |
| `--amount` | Monto típico por operación en COP: descarta anuncios cuyos límites no lo admiten |
| `--min-finish-rate` / `--min-orders` / `--merchants-only` | Calidad mínima del anunciante |
| `--exclude-user` | Excluir usuarios (p. ej. tu propio `userNo`) |
| `--no-record` | No guardar snapshots |

Cada ciclo se guarda en `data/snapshots/binance_p2p/usdt_cop/AAAA-MM-DD.jsonl.gz` (base para la Fase 3).
En pantalla, `[Binance]` = dato observado y `[cálculo]` = cálculo del sistema. La liquidez mostrada es **anunciada**, no volumen ejecutado.

## Base histórica (Fase 3)

El monitor guarda cada ciclo también en `data/history.db` (SQLite). Los anuncios se guardan solo cuando cambian, para que semanas de datos quepan en el PC.

```bash
jmcambios-history importar   # carga los snapshots .jsonl.gz anteriores (repetible, no duplica)
jmcambios-history estado     # cuántos datos hay y desde cuándo
jmcambios-history cambios    # cambios de precio y liquidez en 5/15/30/60 min
jmcambios-history perfil     # promedios por hora del día: días hábiles vs fin de semana
jmcambios-history cruces     # episodios de cruce de precios y si eran aprovechables
```

Importa los datos viejos **antes** de volver a arrancar el monitor, para que el historial de anuncios quede en orden.

**Cruces de precio:** cuando el mejor anuncio de venta está por debajo del mejor de compra, el monitor indica si es aprovechable con tus métodos de pago (`JMC_MY_PAY_METHODS` en `.env`, con el 4x1000 de cada cuenta), qué cantidad encaja en los límites de ambos anuncios y el margen neto. La comisión del tomador se asume 0 % hasta verificarla con órdenes reales.

## Negocio: órdenes, rentabilidad y competencia (Fase 4)

Requiere la API key de solo lectura de tu **cuenta oficial**.

```bash
jmcambios-negocio sincronizar                     # descarga tus órdenes de los últimos 6 meses a data/history.db
jmcambios-negocio costos                          # comisiones reales cobradas por Binance (maker/taker)
jmcambios-negocio rentabilidad --capital 10.000.000 --dias 30
jmcambios-negocio rentabilidad --desde 2026-10-01 --hasta 2026-10-15 --costo-orden 500 --tasa-oportunidad 10
jmcambios-negocio competencia --margen-min 0,3    # posición de tus anuncios y precios límite rentables
```

- **Beneficio realizado**: ciclos cerrados con costo conocido (costo promedio ponderado). Lo vendido sin compra registrada en el periodo se informa aparte y no se cuenta como ganancia.
- **4x1000**: Binance no informa desde qué cuenta pagaste; se estima con la cuenta de la misma entidad del método de pago (`JMC_MY_PAY_METHODS`) y se muestra el rango mínimo–máximo.
- **Estimado**: inventario abierto valorado al mejor precio de compra del mercado. **Potencial**: llegará con el motor de precios (Fase 5).

## Precios: presión del mercado y 3 escenarios (Fase 5)

```bash
jmcambios-negocio presion                                  # presión alcista/bajista con confianza (usa data/history.db; no necesita API)
jmcambios-negocio recomendar --capital 10.000.000          # 3 escenarios para tus anuncios (lee mercado y anuncios en vivo)
jmcambios-negocio recomendar --margen-min 0,3 --meta 127.000
```

- **Presión** (−100 a +100) y **confianza** (0–100). Cada señal indica si es **observada** (precio/liquidez publicados), **inferida** (cantidad que baja sin cambio de precio → posible ejecución) o **no verificable** (volumen ejecutado real). Con datos de más de 10 min la confianza se limita a 20.
- **Escenarios**: conservador (puesto #8 entre compatibles, margen mín. + 0,30 pp), equilibrado (#3, + 0,15 pp), agresivo (#1, margen mínimo). Si el mercado no da el margen, el precio se mueve para protegerlo; la presión (solo con confianza ≥ 50) decide de qué lado se cede.
- En `JMC_MODE=OBSERVATION` se muestran solo los escenarios; en `RECOMMENDATION` además el cambio sugerido para cada anuncio. **Nunca se modifica nada en Binance.**
- El monitor muestra una línea de presión en cada ciclo.

## Panel y alertas (Fase 6)

```bash
jmcambios-alertas configurar                       # conecta tu bot de Telegram (guiado, una sola vez)
jmcambios-alertas probar                           # mensaje de prueba
jmcambios-monitor --interval 60 --brief --panel    # monitor + panel + alertas en una sola ventana
jmcambios-panel                                    # solo el panel (si el monitor corre en otra ventana)
```

- **Panel**: página de solo lectura para el celular (misma red Wi-Fi) con tres pestañas: Mercado (precios, gráfico, presión), Precios (3 escenarios y tus anuncios) y Resultados (rentabilidad y alertas). El enlace lleva una clave (`JMC_DASHBOARD_TOKEN`, se crea sola). No abras el puerto a internet.
- **Alertas** (Telegram y/o correo): cruce aprovechable, presión fuerte (|puntaje| ≥ 40 y confianza ≥ 60), API key rechazada (IP), 3+ ciclos con errores, recuperación, inicio/parada del monitor y —en modo RECOMMENDATION— tus anuncios en línea que regalan margen, quedan por debajo del margen objetivo o se quedan atrás. Cada asunto se repite como máximo cada 10–60 min. Todas quedan registradas en la base.
- En la pestaña **Precios** eliges la ganancia libre que buscas (0,5 / 1 / 1,5 / 2 % u otro valor) y los 3 escenarios y los precios sugeridos se recalculan con el último libro guardado. Solo cambia la vista; las alertas usan `JMC_MARGEN_MIN`.
- También en **Precios**: botones **Solo verificados / Todos** para calcular las estrategias contra comerciantes verificados o contra todos. En comandos: `jmcambios-negocio recomendar --competencia todos` (o `verificados`).
- El bot **solo envía**: el sistema no lee ni ejecuta nada que llegue por Telegram.

## Pruebas

```bash
pytest -q
```

Las pruebas no hacen llamadas de red: usan transportes HTTP simulados.

## Estructura

```
src/jmcambios/
  config.py                       configuración (.env) y modo efectivo
  logging_utils.py                logs JSON con redacción de secretos
  connectors/binance/endpoints.py catálogo de endpoints oficiales
  connectors/binance/signing.py   firma HMAC-SHA256 SAPI C2C
  connectors/binance/client.py    cliente HTTP (solo lectura por defecto)
  tools/verify_integration.py     verificador de Fase 1 (CLI jmcambios-verify)
  tools/set_keys.py               asistente para guardar la API key en .env
  tools/monitor_cli.py            monitor de mercado (CLI jmcambios-monitor)
  domain/                         modelos independientes del exchange (Ad, MarketSnapshot, Side)
  normalizer/binance_p2p.py       validación y normalización de anuncios
  connectors/binance/market.py    fuente de mercado Binance (paginación, respaldo público)
  analysis/market_stats.py        estadísticas por lado, profundidad, concentración, spread
  analysis/filters.py             filtros de relevancia (método, monto, calidad)
  monitor/                        servicio periódico, registro gzip y salida en consola
  analysis/crossing.py            cruces de precio: ¿aprovechables con mis métodos y montos?
  analysis/liquidity.py           cambios 5/15/30/60 min, perfil horario, episodios de cruce
  storage/history.py              base histórica SQLite (anuncios solo cuando cambian)
  storage/importer.py             importación de snapshots .jsonl.gz
  tools/history_cli.py            consultas del historial (CLI jmcambios-history)
  domain/account.py               órdenes y anuncios propios
  normalizer/binance_account.py   normalización de órdenes y anuncios propios
  connectors/binance/account.py   historial de órdenes (ventanas de 30 días) y mis anuncios
  profitability/                  costos (comisión, 4x1000 estimado) y rentabilidad real
  analysis/competition.py         posición de mis anuncios y precios límite rentables
  tools/business_cli.py           CLI jmcambios-negocio
tests/                            pruebas unitarias
docs/                             diagnóstico y arquitectura
```
