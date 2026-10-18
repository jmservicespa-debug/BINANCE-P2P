import json
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest

from jmcambios.config import Settings
from jmcambios.connectors.binance import endpoints as ep
from jmcambios.connectors.binance.client import (
    BinanceP2PClient,
    MissingCredentialsError,
    Outcome,
    WriteNotAllowedError,
    classify,
)
from jmcambios.connectors.binance.signing import sign


def settings(**env) -> Settings:
    base = {"BINANCE_API_KEY": "readkey123456", "BINANCE_API_SECRET": "readsecret"}
    base.update(env)
    return Settings(_env_file=None, **base)


def client_with(handler, **env) -> BinanceP2PClient:
    return BinanceP2PClient(settings(**env), transport=httpx.MockTransport(handler), clock_ms=lambda: 1700000000000)


def test_write_endpoints_blocked_before_network():
    def handler(request):  # pragma: no cover - no debe ejecutarse
        raise AssertionError("no debe llegar a la red")

    with client_with(handler) as c:
        for endpoint in (ep.AD_POST, ep.AD_UPDATE, ep.AD_UPDATE_STATUS):
            with pytest.raises(WriteNotAllowedError):
                c.call(endpoint, body={"advNo": "1"})


def test_write_endpoints_catalogued_as_write():
    writes = {e.name for e in ep.ALL_ENDPOINTS if e.write}
    assert writes == {"sapi.ad_post", "sapi.ad_update", "sapi.ad_update_status"}


def test_signed_request_has_valid_signature_and_api_key_header():
    seen = {}

    def handler(request: httpx.Request):
        seen["request"] = request
        return httpx.Response(200, json={"code": "000000", "data": [{"a": 1}], "total": 7, "success": True},
                              headers={"x-sapi-used-ip-weight-1m": "3"})

    with client_with(handler) as c:
        r = c.call(ep.MY_ADS, body={"page": 1, "rows": 20})

    req = seen["request"]
    assert req.method == "POST"
    assert req.headers["X-MBX-APIKEY"] == "readkey123456"
    assert json.loads(req.content) == {"page": 1, "rows": 20}
    raw_query = urlsplit(str(req.url)).query
    unsigned, signature = raw_query.rsplit("&signature=", 1)
    assert unsigned == "recvWindow=10000&timestamp=1700000000000"
    assert signature == sign(unsigned, "readsecret")
    assert r.ok and r.total == 7 and r.weight_headers == {"x-sapi-used-ip-weight-1m": "3"}


def test_public_request_is_unsigned():
    seen = {}

    def handler(request: httpx.Request):
        seen["request"] = request
        return httpx.Response(200, json={"code": "000000", "data": {"price": "4000"}, "success": True})

    with client_with(handler) as c:
        r = c.call(ep.PUBLIC_QUOTE_PRICE, {"fiat": "COP", "asset": "USDT", "tradeType": "BUY"})

    req = seen["request"]
    assert str(req.url).startswith("https://www.binance.com/bapi/c2c/v1/public/c2c/agent/quote-price")
    assert "X-MBX-APIKEY" not in req.headers
    params = dict(parse_qsl(urlsplit(str(req.url)).query))
    assert params == {"fiat": "COP", "asset": "USDT", "tradeType": "BUY"}
    assert r.ok


def test_missing_credentials_raise():
    with BinanceP2PClient(Settings(_env_file=None, BINANCE_API_KEY="", BINANCE_API_SECRET=""),
                          transport=httpx.MockTransport(lambda r: httpx.Response(200))) as c:
        with pytest.raises(MissingCredentialsError):
            c.call(ep.MY_ADS)


def test_network_error_is_reported_not_raised():
    def handler(request):
        raise httpx.ConnectError("boom")

    with client_with(handler) as c:
        r = c.call(ep.PUBLIC_TRADE_METHODS, {"fiat": "COP"})
    assert r.outcome is Outcome.NETWORK_ERROR


@pytest.mark.parametrize(
    "status,payload,expected",
    [
        (200, {"code": "000000", "success": True}, Outcome.OK),
        (400, {"code": -2015, "msg": "Invalid API-key, IP, or permissions for action."}, Outcome.AUTH_ERROR),
        (400, {"code": -1022, "msg": "Signature invalid"}, Outcome.AUTH_ERROR),
        (200, {"code": "000002", "message": "Permission denied", "success": False}, Outcome.PERMISSION_DENIED),
        (451, None, Outcome.GEO_OR_IP_BLOCKED),
        (403, None, Outcome.GEO_OR_IP_BLOCKED),
        (429, {"code": -1003}, Outcome.RATE_LIMITED),
        (500, None, Outcome.API_ERROR),
    ],
)
def test_classify(status, payload, expected):
    assert classify(status, payload)[0] is expected
