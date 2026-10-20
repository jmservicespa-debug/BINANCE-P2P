from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from jmcambios.analysis import merchants
from jmcambios.analysis.market_stats import summarize
from jmcambios.domain import MarketSnapshot, Side
from jmcambios.pricing.engine import Costs
from jmcambios.storage.history import HistoryStore
from tests.fixtures import make_ad

T0 = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)  # 08:00 Colombia
VENUE, MARKET = "binance_p2p", "USDT/COP"
D = Decimal


def record(store, minute, asks, bids):
    at = T0 + timedelta(minutes=minute)
    ts = int(at.timestamp())
    for side, ads in ((Side.ASK, asks), (Side.BID, bids)):
        snap = MarketSnapshot(venue=VENUE, asset="USDT", fiat="COP", side=side, taken_at=at, ads=ads,
                              source="t", reported_total=len(ads), complete=True)
        store.record_snapshot(snap, summarize(side, ads), ts)


def book(minute):
    # "Grande": compra y venta, 4.800 órdenes; cambia la compra cada 30 min. "Vendedor": solo vende.
    big_bid = "3135" if (minute // 30) % 2 == 0 else "3134"
    asks = [make_ad("g-a", "3155", "5000", user="grande", nick="Grande", orders=4800, lo="200000", hi="3000000"),
            make_ad("v-a", "3152", "2000", user="vend", nick="Vendedor", orders=900, lo="50000", hi="500000"),
            make_ad("x-a", "3140", "100", user="nover", nick="NoVer", user_type="user", orders=5000)]
    bids = [make_ad("g-b", big_bid, "8000", side=Side.BID, user="grande", nick="Grande", orders=4800,
                    lo="200000", hi="3000000"),
            make_ad("o-b", "3136", "1000", side=Side.BID, user="otro", nick="Otro", orders=300)]
    return asks, bids


@pytest.fixture
def store():
    s = HistoryStore(":memory:")
    for m in range(0, 120):
        record(s, m, *book(m))
    yield s
    s.close()


def test_study_profiles_top_merchants(store):
    st = merchants.study(store, VENUE, MARKET, days=1, now_ts=int((T0 + timedelta(minutes=119)).timestamp()))
    assert st.samples == 120 and st.notes == []
    names = [m.nickname for m in st.merchants]
    assert names[0] == "Grande" and "NoVer" not in names  # ordenado por órdenes; no verificados fuera
    g = st.merchants[0]
    assert g.sides == "compra y venta" and g.presence == 1.0
    assert g.own_spread == pytest.approx(20.5) and g.both_prices in ((3134.0, 3155.0), (3135.0, 3155.0))
    assert g.rank_buy == 2 and g.rank_sell == 2 and g.gap_sell == pytest.approx(3)
    assert g.min_fiat == 200000 and g.max_fiat == 3000000 and g.active_hours == (8, 9)
    assert g.reprices_per_hour == pytest.approx(1.5, abs=0.6)  # 3 cambios en ~2 h
    v = next(m for m in st.merchants if m.nickname == "Vendedor")
    assert v.sides == "solo venta" and v.own_spread is None and v.rank_sell == 1
    s = merchants.summarize(st)
    assert s["two_sided"] == 1 and s["own_spread"] == pytest.approx(20.5) and s["excluded"] == 0
    costs = Costs(D("0.00181"), D("0.00008"), D("0"), D("0.004"), D("0.01"))
    net = merchants.net_margin_with_costs(3135, 3155, costs)
    assert D("0.004") < net < D("0.005")


def test_study_all_includes_unverified(store):
    st = merchants.study(store, VENUE, MARKET, days=1, merchants_only=False,
                         now_ts=int((T0 + timedelta(minutes=119)).timestamp()))
    assert st.merchants[0].nickname == "NoVer"


def test_study_without_history():
    s = HistoryStore(":memory:")
    st = merchants.study(s, VENUE, MARKET, days=1, now_ts=int(T0.timestamp()))
    assert not st.merchants and st.notes


def test_comerciantes_cli(store, tmp_path, capsys, monkeypatch):
    from jmcambios.tools import business_cli

    db = tmp_path / "h.db"
    with HistoryStore(db) as s:
        for m in range(0, 120):
            record(s, m, *book(m))
    monkeypatch.chdir(tmp_path)
    assert business_cli.main(["comerciantes", "--db", str(db), "--top", "5"]) == 0
    out = capsys.readouterr().out
    assert "1. Grande · 4800 órdenes/30d" in out and "SU DIFERENCIA PROPIA" in out and "PATRÓN de los 1" in out
    assert "activo 8–10 h" in out and "NoVer" not in out


def test_panel_comerciantes_api(tmp_path):
    import json

    from jmcambios.dashboard import server as panel

    db = tmp_path / "h.db"
    with HistoryStore(db) as s:
        for m in range(0, 120):
            record(s, m, *book(m))
    state = tmp_path / "e.json"
    state.write_text(json.dumps({"generated_ts": int(datetime.now(UTC).timestamp()), "merchants_only": True,
                                 "costs": {"maker_buy": 0.00181, "maker_sell": 0.00008, "gmf": 0, "gmf_worst": 0.004,
                                           "min_margin": 0.01}}), encoding="utf-8")
    data = panel.PanelData(db, state, venue=VENUE, market=MARKET, fiat="COP", asset="USDT",
                           cost_config=panel.cost_config({"Nequi": D("0.004")}))
    out = data.comerciantes(int(datetime.now(UTC).timestamp()))
    # Los datos son de "hoy 13:00 UTC" o antes: el estudio usa el último dato guardado.
    assert out["merchants"][0]["nickname"] == "Grande" and out["pattern"]["two_sided"] == 1
    assert 0.004 < out["merchants"][0]["net_with_my_costs"] < 0.005
    assert data.comerciantes(int(datetime.now(UTC).timestamp())) is out  # caché



def test_pattern_excludes_inactive_side():
    from jmcambios.analysis.merchants import MerchantProfile, MerchantStudy, summarize

    def mp(name, spread, rb, rs):
        return MerchantProfile(name, name, 100, None, "compra y venta", 1.0, rb, rs, 0, 0, spread, spread / 31.5,
                               (3135.0, 3135.0 + spread), 1e5, 1e6, (), (), 1.0)
    st = MerchantStudy(0, 1, 100, [mp("a", 38, 10, 9), mp("b", 32, 15, 7), mp("c", 187, 45, 152)])
    s = summarize(st)
    assert s["two_sided"] == 2 and s["excluded"] == 1 and s["own_spread"] == pytest.approx(35)


def test_plan_leaders_scenario():
    from jmcambios.pricing.engine import LEADERS, AdProfile, plan

    asks = [make_ad(f"a{i}", str(3150 + i * 2), "1000", user=f"s{i}") for i in range(15)]
    bids = [make_ad(f"b{i}", str(3140 - i * 2), "1000", side=Side.BID, user=f"b{i}") for i in range(15)]
    prof = AdProfile(("BancolombiaSA",), D("200000"), D("3000000"))
    costs = Costs(D("0.00181"), D("0.00008"), D("0"), D("0.004"), D("0.01"))
    pp = plan(asks, bids, buy_profile=prof, sell_profile=prof, costs=costs, leader_ranks=(10, 9))
    lead = pp.scenarios[-1]
    assert lead.name == LEADERS and len(pp.scenarios) == 4
    assert lead.buy.price == D("3122.01") and lead.sell.price == D("3165.99")  # supera al 10º comprador y al 9º vendedor
    assert lead.buy.rank == 10 and lead.sell.rank == 9 and not lead.buy.adjusted
    assert lead.margin > D("0.01")
    assert len(plan(asks, bids, buy_profile=prof, sell_profile=prof, costs=costs).scenarios) == 3


def test_panel_escenarios_include_leaders(tmp_path):
    import json

    from jmcambios.dashboard import server as panel

    db = tmp_path / "h.db"
    with HistoryStore(db) as s:
        for m in range(0, 120):
            record(s, m, *book(m))
    state = tmp_path / "e.json"
    state.write_text(json.dumps({"generated_ts": int(datetime.now(UTC).timestamp()), "merchants_only": True,
                                 "costs": {"maker_buy": 0.00181, "maker_sell": 0.00008, "gmf": 0, "gmf_worst": 0.004,
                                           "min_margin": 0.01}}), encoding="utf-8")
    data = panel.PanelData(db, state, venue=VENUE, market=MARKET, fiat="COP", asset="USDT",
                           cost_config=panel.cost_config({"BancolombiaSA": D("0.004")}))
    out = data.escenarios(D("1"), int(datetime.now(UTC).timestamp()))
    assert out["leader_ranks"] == [2, 2] and out["scenarios"][-1]["name"] == "como los mejores"
