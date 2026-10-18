"""Cliente HTTP para Binance P2P (API pública agent + C2C Agent SAPI).

Por diseño, un cliente creado con `allow_write=False` (el valor por defecto)
rechaza cualquier endpoint de escritura antes de tocar la red.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from jmcambios.config import Settings
from jmcambios.connectors.binance.endpoints import Base, BodyKind, Endpoint
from jmcambios.connectors.binance.signing import encode_query, signed_query

log = logging.getLogger(__name__)

USER_AGENT = "jmcambios-p2p/0.1.0"
SUCCESS_CODE = "000000"
WEIGHT_HEADERS = ("x-sapi-used-ip-weight-1m", "x-sapi-used-uid-weight-1m", "x-mbx-used-weight-1m")


class WriteNotAllowedError(RuntimeError):
    """Se intentó llamar a un endpoint de escritura con un cliente de solo lectura."""


class MissingCredentialsError(RuntimeError):
    pass


class Outcome(str, Enum):
    OK = "OK"
    AUTH_ERROR = "AUTH_ERROR"  # key/firma/timestamp inválidos
    PERMISSION_DENIED = "PERMISSION_DENIED"  # sin permiso (p. ej. no comerciante)
    GEO_OR_IP_BLOCKED = "GEO_OR_IP_BLOCKED"  # 451, o 403 por región/IP
    RATE_LIMITED = "RATE_LIMITED"
    API_ERROR = "API_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"


@dataclass
class ApiResult:
    endpoint: str
    outcome: Outcome
    http_status: int | None = None
    code: str | None = None
    message: str | None = None
    data: Any = None
    total: int | None = None
    weight_headers: dict[str, str] = field(default_factory=dict)
    latency_ms: float | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.OK


_AUTH_CODES = {"-2014", "-2015", "-1021", "-1022", "-1102"}


def classify(status: int, payload: Any) -> tuple[Outcome, str | None, str | None]:
    code = msg = None
    if isinstance(payload, dict):
        raw_code = payload.get("code")
        code = None if raw_code is None else str(raw_code)
        msg = payload.get("message") or payload.get("msg")
        if 200 <= status < 300 and (payload.get("success") is True or code in (None, SUCCESS_CODE)):
            return Outcome.OK, code, msg
    if status == 451:
        return Outcome.GEO_OR_IP_BLOCKED, code, msg
    if status in (418, 429):
        return Outcome.RATE_LIMITED, code, msg
    if code in _AUTH_CODES:
        return Outcome.AUTH_ERROR, code, msg
    text = f"{code or ''} {msg or ''}".lower()
    if "permission" in text or "merchant" in text or (status == 403 and isinstance(payload, dict)):
        return Outcome.PERMISSION_DENIED, code, msg
    if status == 403:
        return Outcome.GEO_OR_IP_BLOCKED, code, msg
    if status == 401:
        return Outcome.AUTH_ERROR, code, msg
    return Outcome.API_ERROR, code, msg


class BinanceP2PClient:
    def __init__(
        self,
        settings: Settings,
        *,
        allow_write: bool = False,
        transport: httpx.BaseTransport | None = None,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._settings = settings
        self._allow_write = allow_write
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._http = httpx.Client(
            timeout=settings.http_timeout_s,
            transport=transport,
            headers={"User-Agent": USER_AGENT},
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BinanceP2PClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _credentials(self, endpoint: Endpoint) -> tuple[str, str]:
        s = self._settings
        if endpoint.write:
            key, secret = s.trade_api_key, s.trade_api_secret
        else:
            key, secret = s.api_key, s.api_secret
        if not key or not secret or not key.get_secret_value() or not secret.get_secret_value():
            raise MissingCredentialsError(f"faltan credenciales para {endpoint.name}")
        return key.get_secret_value(), secret.get_secret_value()

    def call(
        self,
        endpoint: Endpoint,
        params: Mapping[str, object] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> ApiResult:
        if endpoint.write and not self._allow_write:
            raise WriteNotAllowedError(f"{endpoint.name} es de escritura; cliente en solo lectura")

        params = dict(params or {})
        base = self._settings.public_base_url if endpoint.base is Base.PUBLIC else self._settings.sapi_base_url
        headers: dict[str, str] = {}

        if endpoint.signed:
            api_key, secret = self._credentials(endpoint)
            query = signed_query(params, secret, self._clock_ms(), self._settings.recv_window_ms)
            headers["X-MBX-APIKEY"] = api_key
        else:
            query = encode_query(params)

        url = f"{base}{endpoint.path}" + (f"?{query}" if query else "")
        json_body = None
        if endpoint.body is BodyKind.JSON:
            json_body = dict(body or {})

        started = time.perf_counter()
        try:
            response = self._http.request(endpoint.method, url, headers=headers, json=json_body)
        except httpx.HTTPError as exc:
            log.warning("binance request failed", extra={"fields": {"endpoint": endpoint.name, "error": type(exc).__name__}})
            return ApiResult(endpoint.name, Outcome.NETWORK_ERROR, message=type(exc).__name__)
        latency = (time.perf_counter() - started) * 1000

        try:
            payload = response.json()
        except ValueError:
            payload = None
        outcome, code, msg = classify(response.status_code, payload)
        weights = {h: response.headers[h] for h in WEIGHT_HEADERS if h in response.headers}
        data = payload.get("data") if isinstance(payload, dict) else None
        total = payload.get("total") if isinstance(payload, dict) else None

        log.info(
            "binance request",
            extra={"fields": {"endpoint": endpoint.name, "status": response.status_code, "outcome": outcome.value, "code": code, **weights}},
        )
        return ApiResult(
            endpoint=endpoint.name,
            outcome=outcome,
            http_status=response.status_code,
            code=code,
            message=msg,
            data=data,
            total=total if isinstance(total, int) else None,
            weight_headers=weights,
            latency_ms=round(latency, 1),
        )
