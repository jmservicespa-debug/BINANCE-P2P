from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from jmcambios.analysis import pressure
from jmcambios.analysis.market_stats import summarize
from jmcambios.analysis.pressure import INFERRED, OBSERVED, PressureReport
from jmcambios.domain import MarketSnapshot, Side
from jmcambios.domain.account import MyAd, OrderSide
from jmcambios.pricing.engine import (
    AdProfile,
    Costs,
    competitive_price,
    concession_from_pressure,
    cycle_margin,
    daily_goal,
    plan,
)
from jmcambios.storage.history import HistoryStore
from tests.fixtures import make_ad

T0 = datetime(2026, 10, 19, 13, 0, tzinfo=UTC)
VENUE, MARKET = "binance_p2p", "USDT/COP"
D = Decimal


def ask(ad_id, price, qty="1000", user=None, methods=("DaviviendaSA",), lo="100000", hi="5000000"):
    return make_ad(ad_id, price, qty, side=Side.ASK, user=user or ad_id, methods=methods, lo=lo, hi=hi)


def bid(ad_id, price, qty="1000", user=None, methods=("DaviviendaSA",), lo="100000", hi="5000000"):
    return make_ad(ad_id, price, qty, side=Side.BID, user=user or ad_id, methods=methods, lo=lo, hi=hi)


def record(store, minute, asks, bids):
    at = T0 + timedelta(minutes=minute)
    ts = int(at.timestamp())
    for side, ads in ((Side.ASK, asks), (Side.BID, bids)):
        snap = MarketSnapshot(venue=VENUE, asset="USDT", fiat="COP", side=side, taken_at=at, ads=ads,
                              source="sapi.ads_search", reported_total=len(ads), complete=True)
        store.record_snapshot(snap, summarize(side, ads), ts)
    return ts


@pytest.fixture
def store():
    s = HistoryStore(":memory:")
    yield s
    s.close()


# ------------------------------------------------------------------ presión
def test_pressure_without_history(store):
    rep = pressure.analyze(store, VENUE, MARKET)
    assert rep.label == "sin datos" and rep.confidence == 0
    assert any("Binance no lo publica" in u for u in rep.unverifiable)


def test_pressure_rising_market_is_bullish(store):
    # Ambos lados suben de precio y la oferta se reduce: presión alcista clara.
    for m in range(0, 61, 5):
        record(store, m, [ask("A1", str(3160 + m // 5), qty=str(1000 - 10 * m))], [bid("B1", str(3150 + m // 5))])
    rep = pressure.analyze(store, VENUE, MARKET)
    assert rep.windows == [5, 15, 30, 60]
    assert rep.score > 40 and rep.direction == 1 and rep.label.startswith("fuerte alcista")
    assert rep.confidence >= 80
    assert {s.provenance for s in rep.signals} <= {OBSERVED, INFERRED}
    assert rep.sides[Side.ASK].best_price_delta == pytest.approx(12)


def test_pressure_falling_market_is_bearish(store):
    for m in range(0, 31, 5):
        record(store, m, [ask("A1", str(3170 - m))], [bid("B1", str(3160 - m), qty=str(1000 - 20 * m))])
    rep = pressure.analyze(store, VENUE, MARKET)
    assert rep.direction == -1 and "bajista" in rep.label


def test_pressure_flat_market_is_neutral(store):
    for m in range(0, 31, 5):
        record(store, m, [ask("A1", "3170")], [bid("B1", "3160")])
    rep = pressure.analyze(store, VENUE, MARKET)
    assert rep.score == 0 and rep.label == "neutral" and rep.direction == 0


def test_pressure_stale_data_caps_confidence(store):
    for m in range(0, 61, 5):
        record(store, m, [ask("A1", str(3160 + m // 5))], [bid("B1", str(3150 + m // 5))])
    latest = store.latest_ts(VENUE, MARKET)
    rep = pressure.analyze(store, VENUE, MARKET, now_ts=latest + 3600)
    assert rep.confidence <= 20 and any("monitor" in n for n in rep.notes)


def test_pressure_only_inferred_signals_capped(store):
    # Mismo precio y misma liquidez total, pero el ASK pierde cantidad sin moverse (posibles compras).
    record(store, 0, [ask("A1", "3170", "1000"), ask("A2", "3180", "1000")], [bid("B1", "3160", "1000")])
    record(store, 5, [ask("A1", "3170", "950"), ask("A2", "3180", "1050")], [bid("B1", "3160", "1000")])
    rep = pressure.analyze(store, VENUE, MARKET)
    assert rep.score > 0
    assert rep.confidence <= 50 and any("inferidas" in n for n in rep.notes)


# ------------------------------------------------------------------ motor de precios
COSTS = Costs(maker_buy=D("0.00181"), maker_sell=D("0.00008"), gmf=D("0"), gmf_worst=D("0.004"), min_margin=D("0.003"))
PROFILE = AdProfile(("DaviviendaSA", "Daviplata"), D("200000"), D("3000000"))


def test_cycle_margin_matches_price_limit_formula():
    from jmcambios.analysis.competition import max_profitable_buy_price

    b = max_profitable_buy_price(D("3155"), gmf=D("0"), buy_commission=COSTS.maker_buy,
                                 sell_commission=COSTS.maker_sell, min_margin=COSTS.min_margin)
    assert cycle_margin(b, D("3155"), COSTS) == pytest.approx(D("0.003"), abs=D("1e-12"))


def test_competitive_price_uses_compatible_ads_only():
    bids = [bid("x", "3170", methods=("Efecty",)), bid("b1", "3160"), bid("b2", "3158"), bid("b3", "3150")]
    assert competitive_price(Side.BID, bids, PROFILE, 1) == D("3160.01")  # ignora a Efecty
    assert competitive_price(Side.BID, bids, PROFILE, 3) == D("3150.01")
    assert competitive_price(Side.BID, bids, PROFILE, 8) == D("3150.01")  # menos competidores que el objetivo
    asks = [ask("a1", "3200"), ask("a2", "3210")]
    assert competitive_price(Side.ASK, asks, PROFILE, 1) == D("3199.99")


def test_plan_wide_spread_needs_no_adjustment():
    asks = [ask(f"a{i}", str(3200 + i)) for i in range(10)]
    bids = [bid(f"b{i}", str(3150 - i)) for i in range(10)]
    pp = plan(asks, bids, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS)
    assert [s.name for s in pp.scenarios] == ["conservador", "equilibrado", "agresivo"]
    agg = pp.scenarios[-1]
    assert agg.buy.price == D("3150.01") and agg.sell.price == D("3199.99")
    assert agg.buy.rank == 1 and agg.sell.rank == 1 and not agg.buy.adjusted and not agg.sell.adjusted
    cons = pp.scenarios[0]
    assert cons.buy.price < agg.buy.price and cons.sell.price > agg.sell.price
    assert cons.margin > agg.margin >= COSTS.min_margin
    assert agg.net_per_unit == agg.sell.price * agg.margin
    assert not pp.warnings


def test_plan_crossed_market_protects_margin():
    asks = [ask(f"a{i}", str(3155 + i)) for i in range(10)]
    bids = [bid(f"b{i}", str(3160 - i)) for i in range(10)]
    pp = plan(asks, bids, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS)
    assert any("mercado cruzado" in w for w in pp.warnings)
    for sc in pp.scenarios:
        assert sc.margin >= COSTS.min_margin
        assert sc.buy.adjusted and sc.sell.adjusted
        assert sc.buy.price < sc.buy.competitive_price and sc.sell.price > sc.sell.competitive_price
        assert sc.margin_worst < sc.margin


def _pressure(score, confidence):
    return PressureReport(score=score, confidence=confidence, label="")


def test_concession_follows_pressure_only_with_confidence():
    assert concession_from_pressure(None) == (D("0.5"), "equilibrado")
    assert concession_from_pressure(_pressure(60, 30)) == (D("0.5"), "equilibrado")
    assert concession_from_pressure(_pressure(60, 70)) == (D("0.25"), "comprar")
    assert concession_from_pressure(_pressure(-60, 70)) == (D("0.75"), "vender")
    assert concession_from_pressure(_pressure(5, 90)) == (D("0.5"), "equilibrado")


def test_bullish_pressure_keeps_buy_price_more_competitive():
    asks = [ask(f"a{i}", str(3155 + i)) for i in range(10)]
    bids = [bid(f"b{i}", str(3160 - i)) for i in range(10)]
    kw = dict(buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS)
    up = plan(asks, bids, pressure=_pressure(60, 80), **kw).scenarios[1]
    down = plan(asks, bids, pressure=_pressure(-60, 80), **kw).scenarios[1]
    assert up.buy.price > down.buy.price and up.sell.price > down.sell.price


def test_plan_excludes_my_own_ads_and_handles_empty_book():
    asks = [ask("mine", "3100", user="me"), ask("a1", "3200")]
    bids = [bid("b1", "3150")]
    pp = plan(asks, bids, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS, exclude_users={"me"})
    assert pp.best_ask == D("3200")
    empty = plan([], bids, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS)
    assert not empty.scenarios and empty.warnings


def test_daily_goal():
    qty, rot = daily_goal(D("10"), D("127000"), D("3150"), D("10000000"))
    assert qty == D("12700") and rot == D("12700") * 3150 / D("10000000")
    assert daily_goal(D("0"), D("127000"), D("3150"), None)[0] == D("Infinity")


# ------------------------------------------------------------------ CLI
class _FakeAccount:
    def __init__(self, client):
        pass

    def fetch_my_ads(self):
        return [MyAd(venue=VENUE, ad_id="473152", side=OrderSide.BUY, asset="USDT", fiat="COP", price=D("3150"),
                     price_type=1, floating_ratio=None, available_qty=D("550"), min_fiat=D("200000"),
                     max_fiat=D("3000000"), payment_methods=("Daviplata", "DaviviendaSA"), status=3,
                     commission_rate=D("0.002"))]


class _FakeSource:
    def __init__(self, client, settings):
        pass

    def fetch(self, side):
        ads = [ask(f"a{i}", str(3155 + i)) for i in range(10)] if side is Side.ASK else [bid(f"b{i}", str(3160 - i)) for i in range(10)]
        return MarketSnapshot(venue=VENUE, asset="USDT", fiat="COP", side=side, taken_at=T0, ads=ads,
                              source="test", reported_total=len(ads), complete=True)


@pytest.mark.parametrize("mode", ["OBSERVATION", "RECOMMENDATION"])
def test_recomendar_cli(tmp_path, capsys, monkeypatch, mode):
    from jmcambios.tools import business_cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JMC_MODE", mode)
    monkeypatch.setattr(business_cli, "_client", lambda settings: nullcontext())
    monkeypatch.setattr(business_cli, "BinanceAccount", _FakeAccount)
    monkeypatch.setattr(business_cli, "BinanceMarketSource", _FakeSource)
    db = tmp_path / "h.db"
    assert business_cli.main(["recomendar", "--db", str(db), "--capital", "10.000.000"]) == 0
    out = capsys.readouterr().out
    assert "CONSERVADOR" in out and "EQUILIBRADO" in out and "AGRESIVO" in out
    assert "mercado cruzado" in out and "veces tu capital" in out
    if mode == "OBSERVATION":
        assert "Modo OBSERVACIÓN" in out and "RECOMENDACIÓN" not in out
    else:
        assert "RECOMENDACIÓN [modo RECOMMENDATION]" in out and "cambiar 3.150,00 →" in out
        assert "Nada se modifica en Binance" in out


def test_presion_cli(tmp_path, capsys, monkeypatch):
    from jmcambios.tools import business_cli

    monkeypatch.chdir(tmp_path)
    db = tmp_path / "h.db"
    with HistoryStore(db) as s:
        for m in range(0, 16, 5):
            record(s, m, [ask("A1", str(3160 + m))], [bid("B1", str(3150 + m))])
    assert business_cli.main(["presion", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "PRESIÓN DEL MERCADO" in out and "[observado]" in out and "[no verificable]" in out
