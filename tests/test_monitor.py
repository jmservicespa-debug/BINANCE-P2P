import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from jmcambios.analysis.filters import AdFilter
from jmcambios.config import Settings
from jmcambios.connectors.binance.client import BinanceP2PClient
from jmcambios.connectors.binance.market import BinanceMarketSource, MarketDataError
from jmcambios.domain import Side
from jmcambios.monitor.recorder import SnapshotRecorder, read_records
from jmcambios.monitor.report import money, render
from jmcambios.monitor.service import Monitor
from jmcambios.tools import monitor_cli
from tests.fixtures import search_item

NOW = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)


def book(trade_type: str, n: int):
    """Libro simulado: BUY → anuncios de venta (ASK) desde 4000; SELL → compra (BID) desde 3980."""
    if trade_type == "BUY":
        return [search_item(f"A{i}", str(4000 + i), "100", user=f"s{i % 7}", trade_type="SELL") for i in range(n)]
    return [search_item(f"B{i}", str(3980 - i), "100", user=f"b{i % 5}", trade_type="BUY") for i in range(n)]


def fake_exchange(total=45, fail_page=None, calls=None):
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        if calls is not None:
            calls.append(body)
        if fail_page and body["page"] == fail_page:
            return httpx.Response(500, json={"code": "-1", "msg": "boom"})
        full = book(body["tradeType"], total)
        start = (body["page"] - 1) * body["rows"]
        return httpx.Response(200, json={"code": "000000", "success": True,
                                         "data": full[start:start + body["rows"]], "total": total})
    return handler


def source(handler, **env):
    base = {"BINANCE_API_KEY": "k" * 10, "BINANCE_API_SECRET": "s" * 10}
    base.update(env)
    s = Settings(_env_file=None, **base)
    client = BinanceP2PClient(s, transport=httpx.MockTransport(handler))
    return BinanceMarketSource(client, s, clock=lambda: NOW)


def test_fetch_walks_all_pages():
    calls = []
    snap = source(fake_exchange(total=45, calls=calls)).fetch(Side.ASK)
    assert len(snap.ads) == 45 and snap.complete and snap.reported_total == 45
    assert [c["page"] for c in calls] == [1, 2, 3]
    assert all(c["tradeType"] == "BUY" for c in calls)
    assert not snap.notes


def test_fetch_bid_uses_sell_query():
    calls = []
    snap = source(fake_exchange(total=5, calls=calls)).fetch(Side.BID)
    assert calls[0]["tradeType"] == "SELL" and snap.side is Side.BID and len(snap.ads) == 5


def test_failure_on_later_page_marks_incomplete():
    snap = source(fake_exchange(total=45, fail_page=2)).fetch(Side.ASK)
    assert len(snap.ads) == 20 and not snap.complete
    assert "página 2" in snap.notes[0]


def test_failure_on_first_page_raises():
    try:
        source(fake_exchange(fail_page=1)).fetch(Side.ASK)
    except MarketDataError as exc:
        assert "API_ERROR" in str(exc)
    else:
        raise AssertionError("debía fallar")


def test_side_mismatch_noted():
    def handler(request):
        body = json.loads(request.content)
        items = [search_item("A1", "4000", "1", trade_type="BUY")]  # declara lo contrario
        return httpx.Response(200, json={"code": "000000", "success": True, "data": items, "total": 1})

    snap = source(handler).fetch(Side.ASK)
    assert any("lado distinto" in n for n in snap.notes)


def test_public_fallback_without_credentials():
    def handler(request: httpx.Request):
        assert request.url.path.endswith("/ad-list")
        item = {"adNo": "P1", "price": "4000", "tradableAmount": "10", "minTransAmount": "1",
                "maxTransAmount": "100000", "tradeMethods": [{"identifier": "Nequi"}],
                "advertiser": {"userNo": "u"}}
        return httpx.Response(200, json={"code": "000000", "success": True, "data": [item]})

    snap = source(handler, BINANCE_API_KEY="", BINANCE_API_SECRET="").fetch(Side.ASK)
    assert len(snap.ads) == 1 and not snap.complete and "sin API key" in snap.notes[0]


def test_monitor_cycle_records_and_renders(tmp_path):
    recorder = SnapshotRecorder(tmp_path)
    f = AdFilter(payment_methods=frozenset({"BancolombiaSA"}), amount_fiat=Decimal("100000"))
    mon = Monitor(source(fake_exchange(total=30)), ad_filter=f, recorder=recorder, clock=lambda: NOW)
    result = mon.run_cycle()

    assert result.ok and result.stats[Side.ASK].best_price == Decimal("4000")
    assert result.stats[Side.BID].best_price == Decimal("3980")
    assert result.spread.absolute == Decimal("20")
    assert Side.ASK in result.filtered_stats

    path = tmp_path / "binance_p2p" / "usdt_cop" / "2026-10-18.jsonl.gz"
    records = read_records(path)
    assert [r["side"] for r in records] == ["ASK", "BID"]
    assert len(records[0]["ads"]) == 30 and records[0]["stats"]["best_price"] == "4000"

    text = render(result, f)
    assert "COMPRAR USDT" in text and "VENDER USDT" in text
    assert "volumen ejecutado: no disponible" in text
    assert "10:00:00 (hora Colombia)" in text
    assert "Con mis filtros" in text


def test_monitor_survives_errors_and_backs_off():
    def handler(request):
        return httpx.Response(503, json={"code": "-1", "msg": "down"})

    sleeps = []
    results = []
    mon = Monitor(source(handler), interval_s=60, clock=lambda: NOW, sleep=sleeps.append, on_cycle=results.append)
    mon.run(max_cycles=4)
    assert len(results) == 4 and all(not r.ok for r in results)
    assert mon.consecutive_failures == 4
    assert sleeps[0] > 60 and sleeps[-1] > sleeps[0]
    assert any("ciclos seguidos" in a for a in results[-1].alerts)


def test_money_format_colombian():
    assert money(Decimal("1234567.891")) == "1.234.567,89"
    assert money(Decimal("4000"), 0) == "4.000"
    assert money(None) == "—"


def test_cli_amount_parsing():
    args = monitor_cli.parse_args(["--amount", "1.000.000", "--min-finish-rate", "95", "--pay", "Nequi, BancolombiaSA"])
    f = monitor_cli.build_filter(args)
    assert f.amount_fiat == Decimal("1000000")
    assert f.min_finish_rate == Decimal("0.95")
    assert f.payment_methods == frozenset({"Nequi", "BancolombiaSA"})
    assert monitor_cli.build_filter(monitor_cli.parse_args(["--amount", "1.500.000,50"])).amount_fiat == Decimal("1500000.50")


def test_cli_rejects_too_short_interval(capsys):
    assert monitor_cli.main(["--interval", "5"]) == 2


def test_monitor_writes_history_and_renders_cross(tmp_path):
    from jmcambios.storage.history import HistoryStore

    def handler(request):
        body = json.loads(request.content)
        if body["tradeType"] == "BUY":  # anuncios de venta: uno barato que cruza
            items = [search_item("A1", "3155.59", "500", methods=("DaviviendaSA",), trade_type="SELL")]
        else:
            items = [search_item("B1", "3160", "500", user="b1", methods=("Nequi",), trade_type="BUY")]
        return httpx.Response(200, json={"code": "000000", "success": True, "data": items, "total": 1})

    with HistoryStore(tmp_path / "h.db") as store:
        mon = Monitor(source(handler), store=store, clock=lambda: NOW)
        result = mon.run_cycle()
        assert result.ok and result.cross.crossed and result.cross.executable
        assert store.counts() == {"snapshots": 2, "cycles": 1, "ad_states": 2}
        row = store.query("SELECT crossed, executable, best_pay_method, best_net_per_unit FROM cycles")[0]
        assert row["crossed"] == 1 and row["executable"] == 1 and row["best_pay_method"] == "DaviviendaSA"
        assert row["best_net_per_unit"] == 4.41

    text = render(result, AdFilter())
    assert "CRUCE DE PRECIOS" in text and "Aprovechable" in text and "DaviviendaSA" in text
    assert "ANOMALÍA" not in text


def test_history_cli_end_to_end(tmp_path, capsys, monkeypatch):
    from jmcambios.tools import history_cli

    monkeypatch.chdir(tmp_path)
    rec = SnapshotRecorder(tmp_path / "data" / "snapshots")
    mon = Monitor(source(fake_exchange(total=30)), recorder=rec, clock=lambda: NOW)
    mon.run_cycle()
    assert history_cli.main(["importar"]) == 0
    assert history_cli.main(["estado"]) == 0
    assert history_cli.main(["perfil"]) == 0
    assert history_cli.main(["cruces"]) == 0
    out = capsys.readouterr().out
    assert "nuevos: 2" in out and "Snapshots: 2" in out and "Sin cruces" in out
