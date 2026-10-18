# JM Cambios — Agente Binance P2P USDT/COP

Sistema de observación, análisis y posicionamiento estratégico de anuncios Binance P2P para el mercado USDT/COP.

**Estado actual: FASE 1 (viabilidad).** Ver:
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
tests/                            pruebas unitarias
docs/                             diagnóstico y arquitectura
```
