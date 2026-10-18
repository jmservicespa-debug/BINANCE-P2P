import json

import httpx

from jmcambios.config import Settings
from jmcambios.connectors.binance.client import BinanceP2PClient
from jmcambios.tools import verify_integration as vi

AD = {"adv": {"advNo": "1", "price": "4000", "surplusAmount": "100", "createTime": 1},
      "advertiser": {"nickName": "PrivateNick", "monthFinishRate": 0.99}}


def fake_binance(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if "/public/" in path:
        if path.endswith("trade-methods"):
            return httpx.Response(200, json={"code": "000000", "success": True, "data": [{"identifier": "BancolombiaSA"}]})
        return httpx.Response(200, json={"code": "000000", "success": True, "data": [{"price": "4000"}]})
    assert request.method in ("GET", "POST")
    assert "/ads/post" not in path and "/ads/update" not in path, "endpoint de escritura llamado"
    if path.endswith("ads/search"):
        return httpx.Response(200, json={"code": "000000", "success": True, "data": [AD], "total": 150})
    if path.endswith("getPayMethodByUserId"):
        return httpx.Response(200, json={"code": "000000", "success": True,
                                         "data": [{"payId": 999, "identifier": "Nequi", "tradeMethodName": "Nequi"}]})
    if path.endswith("listWithPagination"):
        return httpx.Response(200, json={"code": "000002", "message": "Permission denied", "success": False})
    return httpx.Response(200, json={"code": "000000", "success": True, "data": []})


def make_client(**env):
    s = Settings(_env_file=None, BINANCE_API_KEY="readkey123456", BINANCE_API_SECRET="readsecret", **env)
    return s, BinanceP2PClient(s, transport=httpx.MockTransport(fake_binance))


def test_run_checks_full_flow_and_report_has_no_private_data():
    s, client = make_client()
    with client:
        checks = vi.run_checks(s, client)
    by_name = {c.name: c for c in checks}

    search = by_name["Búsqueda autenticada de anuncios BUY"]
    assert search.outcome == "OK" and search.findings["has_createTime"] is True
    assert search.findings["total_reported"] == 150
    assert by_name["Mis anuncios"].outcome == "PERMISSION_DENIED"
    assert "payId" not in by_name["Mis métodos de pago (solo conteo)"].schema_keys

    report = vi.build_report(s, checks)
    dumped = json.dumps(report)
    assert "PrivateNick" not in dumped and "999" not in dumped and "readsecret" not in dumped
    assert report["api_key"] == "readk...3456"
    assert report["write_endpoints_called"] is False
    assert report["summary"]["public_market_ok"] is True
    assert report["summary"]["authenticated_read_ok"] is False


def test_without_credentials_only_public_checks_run():
    s = Settings(_env_file=None, BINANCE_API_KEY="", BINANCE_API_SECRET="")
    with BinanceP2PClient(s, transport=httpx.MockTransport(fake_binance)) as client:
        checks = vi.run_checks(s, client)
    assert checks[-1].outcome == "SKIPPED"
    assert all(not c.requires_auth for c in checks[:-1])


def test_trm_check_parses_rows():
    def handler(request):
        return httpx.Response(200, json=[{"valor": "3900.12", "vigenciadesde": "2026-10-17T00:00:00.000"}])

    c = vi.check_trm(transport=httpx.MockTransport(handler))
    assert c.outcome == "OK" and c.findings["valor"] == "3900.12"


def test_trm_network_failure():
    def handler(request):
        raise httpx.ConnectError("x")

    assert vi.check_trm(transport=httpx.MockTransport(handler)).outcome == "NETWORK_ERROR"


def test_reference_price_tries_variants_until_one_works():
    calls = []

    def handler(request: httpx.Request):
        if request.url.path.endswith("getReferencePrice"):
            body = json.loads(request.content)
            calls.append(body)
            if body.get("tradeType") in ("0", "1"):
                return httpx.Response(200, json={"code": "000000", "success": True,
                                                 "data": [{"referencePrice": "3900", "priceScale": 2}]})
            return httpx.Response(400, json={"code": -31002, "msg": "illegal parameter"})
        return fake_binance(request)

    s = Settings(_env_file=None, BINANCE_API_KEY="readkey123456", BINANCE_API_SECRET="readsecret")
    with BinanceP2PClient(s, transport=httpx.MockTransport(handler)) as client:
        checks = vi.run_checks(s, client)
    ref = next(c for c in checks if c.name == "Precio de referencia BUY")
    assert ref.outcome == "OK"
    assert ref.findings["working_body"]["tradeType"] == "0"
    assert ref.findings["referencePrice"] == "3900"
    assert len(ref.findings["variants_tried"]) == 3


def test_reference_price_all_variants_fail_reports_first_error():
    def handler(request: httpx.Request):
        if request.url.path.endswith("getReferencePrice"):
            return httpx.Response(400, json={"code": -31002, "msg": "illegal parameter"})
        return fake_binance(request)

    s = Settings(_env_file=None, BINANCE_API_KEY="readkey123456", BINANCE_API_SECRET="readsecret")
    with BinanceP2PClient(s, transport=httpx.MockTransport(handler)) as client:
        checks = vi.run_checks(s, client)
    ref = next(c for c in checks if c.name == "Precio de referencia SELL")
    assert ref.outcome == "API_ERROR" and ref.code == "-31002"
    assert len(ref.findings["variants_tried"]) == len(vi.reference_price_variants("USDT", "COP", "SELL"))
