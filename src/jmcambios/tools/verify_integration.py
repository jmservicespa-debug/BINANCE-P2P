"""Verificador de integración Binance P2P — FASE 1 (solo lectura).

Ejecuta, uno por uno, los endpoints de LECTURA documentados y produce un informe
JSON sin datos personales ni secretos: solo resultado, códigos, número de
elementos y nombres de campos del esquema devuelto.

Nunca llama a endpoints de escritura: el cliente se crea con allow_write=False.

Uso:  jmcambios-verify [--out reports/] [--skip-auth]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from jmcambios import __version__
from jmcambios.config import Settings
from jmcambios.connectors.binance import endpoints as ep
from jmcambios.connectors.binance.client import ApiResult, BinanceP2PClient, Outcome
from jmcambios.logging_utils import mask_key, setup_logging

TRM_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"


@dataclass
class Check:
    name: str
    endpoint: str
    requires_auth: bool
    outcome: str
    http_status: int | None = None
    code: str | None = None
    message: str | None = None
    items: int | None = None
    total: int | None = None
    schema_keys: list[str] = field(default_factory=list)
    findings: dict[str, Any] = field(default_factory=dict)
    latency_ms: float | None = None
    weight_headers: dict[str, str] = field(default_factory=dict)


def _items(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "data", "rows", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def _keys(obj: Any) -> list[str]:
    return sorted(obj.keys()) if isinstance(obj, dict) else []


def _to_check(name: str, result: ApiResult, requires_auth: bool, schema_of: Callable[[Any], Any] | None = None) -> Check:
    items = _items(result.data)
    sample = items[0] if items else result.data
    if schema_of and sample is not None:
        sample = schema_of(sample)
    return Check(
        name=name,
        endpoint=result.endpoint,
        requires_auth=requires_auth,
        outcome=result.outcome.value,
        http_status=result.http_status,
        code=result.code,
        # Mensaje de error de la API (sin datos personales); en éxito no se guarda.
        message=None if result.ok else result.message,
        items=len(items) if result.ok else None,
        total=result.total,
        schema_keys=_keys(sample) if result.ok else [],
        latency_ms=result.latency_ms,
        weight_headers=result.weight_headers,
    )


def reference_price_variants(asset: str, fiat: str, trade_type: str) -> list[dict[str, Any]]:
    """Variantes del cuerpo de getReferencePrice.

    La forma documentada devolvió -31002 "illegal parameter" en la primera
    verificación real (2026-10-18); se prueban variantes para identificar la válida.
    """
    numeric = "0" if trade_type == "BUY" else "1"
    return [
        {"assets": [asset], "fiatCurrency": fiat, "tradeType": trade_type},
        {"assets": [asset], "fiatCurrency": fiat, "tradeType": trade_type, "payType": "BANK"},
        {"assets": [asset], "fiatCurrency": fiat, "tradeType": numeric},
        {"asset": asset, "fiatCurrency": fiat, "tradeType": trade_type},
        {"assets": [asset], "fiat": fiat, "tradeType": trade_type},
    ]


def _reference_price_check(client: BinanceP2PClient, asset: str, fiat: str, trade_type: str) -> Check:
    tried: list[dict[str, Any]] = []
    first_failure: ApiResult | None = None
    for body in reference_price_variants(asset, fiat, trade_type):
        r = client.call(ep.REFERENCE_PRICE, body=body)
        tried.append({"body_keys": sorted(body), "tradeType": body.get("tradeType"), "outcome": r.outcome.value, "code": r.code})
        if r.ok:
            c = _to_check(f"Precio de referencia {trade_type}", r, True)
            first = (_items(r.data) or [{}])[0]
            if isinstance(first, dict):
                c.findings = {k: first.get(k) for k in ("referencePrice", "priceScale", "currencyScale", "assetScale")}
            c.findings["working_body"] = body
            c.findings["variants_tried"] = tried
            return c
        first_failure = first_failure or r
        if r.outcome is not Outcome.API_ERROR:
            break  # error de autenticación/red: no tiene sentido probar más variantes
    c = _to_check(f"Precio de referencia {trade_type}", first_failure, True)
    c.findings["variants_tried"] = tried
    return c


DAY_MS = 86_400_000


def _count_by_fiat(data: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in _items(data):
        if isinstance(row, dict):
            fiat = str(row.get("fiat") or "?")
            counts[fiat] = counts.get(fiat, 0) + 1
    return counts


def _six_month_history_check(client: BinanceP2PClient, now_ms: int) -> Check:
    """Totales de órdenes por ventanas de 30 días (solo conteos, sin datos de las órdenes)."""
    windows: list[dict[str, Any]] = []
    last: ApiResult | None = None
    for i in range(6):
        end = now_ms - i * 30 * DAY_MS
        start = end - 30 * DAY_MS + 1
        last = client.call(ep.ORDER_HISTORY, {"startTimestamp": start, "endTimestamp": end, "page": 1, "rows": 100})
        windows.append({
            "window": f"-{(i + 1) * 30}d..-{i * 30}d",
            "outcome": last.outcome.value,
            "total": last.total,
            "by_fiat_first_page": _count_by_fiat(last.data) if last.ok else {},
        })
        if not last.ok:
            break
    c = _to_check("Historial de órdenes (6 meses, por ventanas)", last, True)
    c.findings["windows"] = windows
    return c


def run_checks(
    settings: Settings,
    client: BinanceP2PClient,
    *,
    skip_auth: bool = False,
    now_ms: int | None = None,
) -> list[Check]:
    now_ms = now_ms if now_ms is not None else int(datetime.now(UTC).timestamp() * 1000)
    asset, fiat = settings.asset, settings.fiat
    checks: list[Check] = []

    # --- Públicos ---
    for trade_type in ("BUY", "SELL"):
        r = client.call(ep.PUBLIC_QUOTE_PRICE, {"fiat": fiat, "asset": asset, "tradeType": trade_type})
        checks.append(_to_check(f"Cotización pública {trade_type}", r, False))
    r = client.call(ep.PUBLIC_TRADE_METHODS, {"fiat": fiat})
    c = _to_check("Métodos de pago públicos (COP)", r, False)
    if r.ok:
        # Identificadores públicos del sistema, no datos personales.
        c.findings["identifiers"] = sorted({str(i.get("identifier")) for i in _items(r.data) if isinstance(i, dict)})
    checks.append(c)
    for trade_type in ("BUY", "SELL"):
        r = client.call(ep.PUBLIC_AD_LIST, {"fiat": fiat, "asset": asset, "tradeType": trade_type, "limit": 20})
        checks.append(_to_check(f"Lista pública de anuncios {trade_type}", r, False))

    if skip_auth or not settings.has_read_credentials:
        reason = "omitido por --skip-auth" if skip_auth else "sin BINANCE_API_KEY/BINANCE_API_SECRET"
        checks.append(Check("Endpoints autenticados", "sapi.*", True, "SKIPPED", message=reason))
        return checks

    # --- Autenticados (lectura) ---
    for trade_type in ("BUY", "SELL"):
        checks.append(_reference_price_check(client, asset, fiat, trade_type))

        r = client.call(ep.ADS_SEARCH, body={"fiat": fiat, "asset": asset, "tradeType": trade_type, "page": 1, "rows": 20})
        c = _to_check(f"Búsqueda autenticada de anuncios {trade_type}", r, True, schema_of=lambda s: s.get("adv", s) if isinstance(s, dict) else s)
        if r.ok:
            first = (_items(r.data) or [{}])[0]
            adv = first.get("adv", {}) if isinstance(first, dict) else {}
            advertiser = first.get("advertiser", {}) if isinstance(first, dict) else {}
            c.findings = {
                "advertiser_keys": _keys(advertiser),
                "has_createTime": isinstance(adv, dict) and adv.get("createTime") is not None,
                "has_surplusAmount": isinstance(adv, dict) and "surplusAmount" in adv,
                "total_reported": r.total,
            }
        checks.append(c)

    r = client.call(ep.ADS_SEARCH, body={"fiat": fiat, "asset": asset, "tradeType": "BUY", "page": 2, "rows": 20})
    c = _to_check("Paginación de búsqueda (página 2)", r, True, schema_of=lambda s: s.get("adv", s) if isinstance(s, dict) else s)
    checks.append(c)

    r = client.call(ep.MY_ADS, body={"page": 1, "rows": 20})
    checks.append(_to_check("Mis anuncios", r, True))

    r = client.call(ep.ADS_CATEGORY)
    c = _to_check("Categorías de anuncio disponibles", r, True)
    if r.ok and isinstance(r.data, dict):
        c.findings["advClassifies"] = r.data.get("advClassifies")
    checks.append(c)

    r = client.call(ep.MY_PAY_METHODS)
    c = _to_check("Mis métodos de pago (solo conteo)", r, True)
    c.schema_keys = [k for k in c.schema_keys if k != "payId"]
    checks.append(c)

    r = client.call(ep.ALL_TRADE_METHODS)
    checks.append(_to_check("Métodos de pago del sistema", r, True))

    r = client.call(ep.ORDER_HISTORY, {"page": 1, "rows": 5})
    checks.append(_to_check("Historial de órdenes (30 días)", r, True))

    # Diagnóstico: comparar con el endpoint C2C clásico y ampliar a 6 meses.
    for trade_type in ("BUY", "SELL"):
        r = client.call(ep.ORDER_HISTORY_LEGACY, {"tradeType": trade_type, "page": 1, "rows": 100})
        c = _to_check(f"Historial C2C clásico {trade_type} (30 días)", r, True)
        if r.ok:
            c.findings["orders_by_fiat"] = _count_by_fiat(r.data)
        checks.append(c)
    checks.append(_six_month_history_check(client, now_ms))

    r = client.call(ep.LIST_ORDERS, body={"page": 1, "rows": 5})
    checks.append(_to_check("Listado de órdenes", r, True))

    r = client.call(ep.QUERY_COMPLAINTS, body={"page": 1, "rows": 5})
    checks.append(_to_check("Apelaciones / disputas", r, True))

    return checks


def check_trm(transport: httpx.BaseTransport | None = None, timeout: float = 15.0) -> Check:
    try:
        with httpx.Client(timeout=timeout, transport=transport) as http:
            resp = http.get(TRM_URL, params={"$limit": 1, "$order": "vigenciadesde DESC"})
        rows = resp.json() if resp.status_code == 200 else []
        ok = resp.status_code == 200 and isinstance(rows, list) and len(rows) > 0
        check = Check("TRM oficial (datos.gov.co)", "datos.gov.co/32sa-8pi3", False, "OK" if ok else "API_ERROR", http_status=resp.status_code)
        if ok:
            check.findings = {k: rows[0].get(k) for k in ("valor", "vigenciadesde", "vigenciahasta")}
            check.schema_keys = _keys(rows[0])
        return check
    except (httpx.HTTPError, ValueError) as exc:
        return Check("TRM oficial (datos.gov.co)", "datos.gov.co/32sa-8pi3", False, Outcome.NETWORK_ERROR.value, message=type(exc).__name__)


def summarize(checks: list[Check]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for c in checks:
        counts[c.outcome] = counts.get(c.outcome, 0) + 1
    public_ok = all(c.outcome == "OK" for c in checks if not c.requires_auth and c.endpoint.startswith("public."))
    auth = [c for c in checks if c.requires_auth and c.outcome != "SKIPPED"]
    return {
        "counts": counts,
        "public_market_ok": public_ok,
        "authenticated_read_ok": bool(auth) and all(c.outcome == "OK" for c in auth),
        "phase1_read_verification_passed": public_ok and bool(auth) and all(c.outcome == "OK" for c in auth),
    }


def build_report(settings: Settings, checks: list[Check]) -> dict[str, Any]:
    return {
        "tool": "jmcambios-verify",
        "version": __version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "market": f"{settings.asset}/{settings.fiat}",
        "api_key": mask_key(settings.api_key.get_secret_value()) if settings.api_key else None,
        "write_endpoints_called": False,
        "summary": summarize(checks),
        "checks": [asdict(c) for c in checks],
    }


def _print_table(checks: list[Check]) -> None:
    print(f"\n{'Resultado':<20} {'HTTP':<5} {'Elem.':<6} Comprobación")
    print("-" * 78)
    for c in checks:
        items = "" if c.items is None else str(c.items)
        http = "" if c.http_status is None else str(c.http_status)
        line = f"{c.outcome:<20} {http:<5} {items:<6} {c.name}"
        if c.message and c.outcome != "OK":
            line += f"  — {c.message}"
        print(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verificador de integración Binance P2P (solo lectura)")
    parser.add_argument("--out", default="reports", help="Directorio del informe JSON")
    parser.add_argument("--skip-auth", action="store_true", help="Solo endpoints públicos")
    args = parser.parse_args(argv)

    settings = Settings()
    secrets = [s.get_secret_value() for s in (settings.api_key, settings.api_secret) if s]
    setup_logging(logging.WARNING, secrets)

    with BinanceP2PClient(settings, allow_write=False) as client:
        checks = run_checks(settings, client, skip_auth=args.skip_auth)
    checks.append(check_trm(timeout=settings.http_timeout_s))

    report = build_report(settings, checks)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"verificacion_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    _print_table(checks)
    s = report["summary"]
    print(f"\nMercado público OK: {s['public_market_ok']} · Lectura autenticada OK: {s['authenticated_read_ok']}")
    if any(c.outcome == "AUTH_ERROR" for c in checks):
        print("Aviso: Binance rechazó la API key. Revisa (1) que tu IP pública actual sea la registrada en la key,")
        print("       (2) que la key esté bien guardada (python -m jmcambios.tools.set_keys) y (3) el permiso Enable Reading.")
    print(f"Informe: {path}  (no contiene secretos; compártelo para cerrar la Fase 1)")
    return 0 if s["public_market_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
