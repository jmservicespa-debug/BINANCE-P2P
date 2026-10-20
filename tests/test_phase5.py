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


def test_scenarios_are_monotonic():
    # Libro de compra muy plano arriba: sin la regla, el conservador compraría más caro que el equilibrado.
    asks = [ask("a0", "3149")] + [ask(f"a{i}", str(3155 + i)) for i in range(1, 10)]
    bids = [bid(f"b{i}", p) for i, p in enumerate(["3160", "3150", "3140", "3136", "3136", "3136", "3136", "3135.46"])]
    cons, bal, agg = plan(asks, bids, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS).scenarios
    assert cons.buy.price <= bal.buy.price <= agg.buy.price
    assert cons.sell.price >= bal.sell.price >= agg.sell.price
    assert cons.margin >= bal.margin >= agg.margin >= COSTS.min_margin


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
    assert "solo comerciantes verificados" in out and "Solo verificados [Binance]" in out and "Mercado completo" in out
    assert business_cli.main(["recomendar", "--db", str(db), "--competencia", "todos"]) == 0
    assert "todos los anunciantes" in capsys.readouterr().out
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


def test_pressure_ignores_single_outlier_ad(store):
    # Un comprador aparece 30 COP por encima de todos: el mejor precio salta, el promedio de 5 apenas.
    bids = [bid(f"B{i}", str(3160 - i)) for i in range(6)]
    asks = [ask(f"A{i}", str(3170 + i)) for i in range(6)]
    for m in range(0, 31, 5):
        extra = [bid("RARO", "3190", qty="110")] if m == 30 else []
        record(store, m, asks, bids + extra)
    rep = pressure.analyze(store, VENUE, MARKET)
    names = {s.name for s in rep.signals}
    assert "precio de los 5 mejores compradores" in names and "mejor precio de compradores" not in names
    assert rep.score < 40  # sin el promedio de 5 habría sido "fuerte alcista"


def test_old_database_gets_top5_column(tmp_path):
    import sqlite3

    db = tmp_path / "vieja.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE snapshots (id INTEGER PRIMARY KEY, venue TEXT NOT NULL, market TEXT NOT NULL, side TEXT NOT NULL,"
                " taken_ts INTEGER NOT NULL, cycle_ts INTEGER NOT NULL, source TEXT, complete INTEGER, reported_total INTEGER,"
                " ads_count INTEGER, merchants_count INTEGER, best_price REAL, median_price REAL, vwap REAL, announced_qty REAL,"
                " announced_fiat REAL, depth_05 REAL, depth_1 REAL, depth_2 REAL, top1_share REAL, top3_share REAL,"
                " top5_share REAL, hhi REAL, UNIQUE (venue, market, side, taken_ts))")
    con.execute("INSERT INTO snapshots (venue, market, side, taken_ts, cycle_ts, best_price) VALUES ('v','m','ASK',1,1,3150)")
    con.commit()
    con.close()
    with HistoryStore(db) as s:
        rows = s.query("SELECT best_price, top5_price FROM snapshots")
        assert [(r["best_price"], r["top5_price"]) for r in rows] == [(3150.0, None)]
        record(s, 0, [ask("A1", "3170")], [bid("B1", "3160")])
        assert s.query("SELECT top5_price FROM snapshots WHERE side='ASK' AND venue='binance_p2p'")[0][0] == 3170.0


def test_plan_merchants_only():
    from tests.fixtures import make_ad as mk

    asks = [mk("u1", "3150", "500", side=Side.ASK, user="x1", user_type="user", methods=("DaviviendaSA",), lo="100000", hi="5000000")]
    asks += [ask(f"a{i}", str(3200 + i)) for i in range(5)]
    bids = [mk("u2", "3190", "500", side=Side.BID, user="x2", user_type="user", methods=("DaviviendaSA",), lo="100000", hi="5000000")]
    bids += [bid(f"b{i}", str(3150 - i)) for i in range(5)]
    allp = plan(asks, bids, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS)
    mer = plan(asks, bids, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS, merchants_only=True)
    assert allp.best_ask == D("3150") and mer.best_ask == D("3200") and mer.merchants_only
    assert mer.scenarios[-1].buy.price == D("3150.01") and mer.scenarios[-1].buy.rank == 1
    only_users = plan(asks[:1], bids[:1], buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS, merchants_only=True)
    assert not only_users.merchants_only and any("verificados" in w for w in only_users.warnings)


def test_position_merchants_only():
    from jmcambios.analysis.competition import position
    from tests.fixtures import make_ad as mk

    mine = MyAd(venue=VENUE, ad_id="mio", side=OrderSide.BUY, asset="USDT", fiat="COP", price=D("3150"), price_type=1,
                floating_ratio=None, available_qty=D("100"), min_fiat=D("200000"), max_fiat=D("3000000"),
                payment_methods=("DaviviendaSA",), status=1)
    book = [mk("u", "3170", "10", side=Side.BID, user="x", user_type="user"), bid("b1", "3155"), bid("b2", "3140")]
    assert position(mine, book).estimated_rank == 3
    assert position(mine, book, merchants_only=True).estimated_rank == 2


def test_competencia_cli_uses_verified_prices(tmp_path, capsys, monkeypatch):
    from jmcambios.tools import business_cli
    from tests.fixtures import make_ad as mk

    class SourceWithOutlier(_FakeSource):
        def fetch(self, side):
            snap = super().fetch(side)
            if side is Side.BID:  # comprador NO verificado muy por encima del resto
                snap.ads.append(mk("raro", "3185.55", "110", side=Side.BID, user="x", user_type="user",
                                   methods=("Nequi",), lo="300000", hi="400000"))
            return snap

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(business_cli, "_client", lambda settings: nullcontext())
    monkeypatch.setattr(business_cli, "BinanceAccount", _FakeAccount)
    monkeypatch.setattr(business_cli, "BinanceMarketSource", SourceWithOutlier)
    db = str(tmp_path / "h.db")
    assert business_cli.main(["competencia", "--db", db, "--margen-min", "1"]) == 0
    out = capsys.readouterr().out
    assert "Mercado completo [Binance]: mejor venta 3.155,00 · mejor compra 3.185,55" in out
    assert "Solo verificados [Binance]: mejor venta 3.155,00 · mejor compra 3.160,00" in out
    # Reponer = mejor compra ÷ (1 − comisión 0,2 %): 3.160 → 3.166,33; el atípico daría 3.191,93.
    assert "costo 3.166,33" in out and "costo 3.191,93" not in out
    assert business_cli.main(["competencia", "--db", db, "--competencia", "todos"]) == 0
    assert "costo 3.191,93" in capsys.readouterr().out


def test_recomendar_with_limits_and_competencia_tranches(tmp_path, capsys, monkeypatch):
    from jmcambios.tools import business_cli

    assert business_cli._dec("500.000", "x") == D("500000") and business_cli._dec("0.3", "x") == D("0.3")
    assert business_cli._parse_limits("500.000-2.000.000") == (D("500000"), D("2000000"))
    with pytest.raises(SystemExit):
        business_cli._parse_limits("2.000.000-500.000")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(business_cli, "_client", lambda settings: nullcontext())
    monkeypatch.setattr(business_cli, "BinanceAccount", _FakeAccount)
    monkeypatch.setattr(business_cli, "BinanceMarketSource", _FakeSource)
    db = str(tmp_path / "h.db")
    assert business_cli.main(["recomendar", "--db", db, "--limites", "500.000-2.000.000"]) == 0
    assert "compra 500.000–2.000.000 · venta 500.000–2.000.000 COP" in capsys.readouterr().out
    assert business_cli.main(["competencia", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "COMPETENCIA POR MONTO" in out and "500 mil – 2 M" in out and "Tu puesto" in out
