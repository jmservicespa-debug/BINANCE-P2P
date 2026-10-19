from datetime import UTC, datetime, timedelta

import pytest

from jmcambios.analysis import crossing
from jmcambios.analysis.liquidity import cross_episodes, hourly_profile, window_change, window_changes
from jmcambios.analysis.market_stats import spread, summarize
from jmcambios.domain import MarketSnapshot, Side
from jmcambios.monitor.recorder import SnapshotRecorder
from jmcambios.storage.history import HistoryStore
from jmcambios.storage.importer import import_directory
from tests.fixtures import make_ad

T0 = datetime(2026, 10, 19, 13, 0, tzinfo=UTC)  # lunes 08:00 Colombia
VENUE, MARKET = "binance_p2p", "USDT/COP"


def snap(side, ads, at, complete=True):
    return MarketSnapshot(venue=VENUE, asset="USDT", fiat="COP", side=side, taken_at=at, ads=ads,
                          source="sapi.ads_search", reported_total=len(ads), complete=complete)


def ask(ad_id, price, qty, user="s1", methods=("DaviviendaSA",)):
    return make_ad(ad_id, price, qty, side=Side.ASK, user=user, methods=methods)


def bid(ad_id, price, qty, user="b1", methods=("Nequi",)):
    return make_ad(ad_id, price, qty, side=Side.BID, user=user, methods=methods)


def record(store, minute, asks, bids, complete=True):
    at = T0 + timedelta(minutes=minute)
    cycle_ts = int(at.timestamp())
    sa, sb = snap(Side.ASK, asks, at, complete), snap(Side.BID, bids, at + timedelta(seconds=1), complete)
    st_a, st_b = summarize(Side.ASK, asks), summarize(Side.BID, bids)
    store.record_snapshot(sa, st_a, cycle_ts)
    store.record_snapshot(sb, st_b, cycle_ts)
    store.record_cycle(VENUE, MARKET, cycle_ts, spread(st_a, st_b), st_a.best_price, st_b.best_price,
                       crossing.analyze(asks, bids))
    return cycle_ts


@pytest.fixture
def store():
    s = HistoryStore(":memory:")
    yield s
    s.close()


def test_ad_states_only_store_changes(store):
    for m in range(5):
        record(store, m, [ask("A1", "3170", "100"), ask("A2", "3175", "50")], [bid("B1", "3160", "200")])
    assert store.counts()["ad_states"] == 3  # sin cambios: se extiende last_ts
    record(store, 5, [ask("A1", "3168", "100"), ask("A2", "3175", "50")], [bid("B1", "3160", "200")])
    assert store.counts()["ad_states"] == 4  # A1 cambió de precio
    open_a1 = store.query("SELECT price FROM ad_states WHERE ad_id='A1' AND open=1")
    assert [r["price"] for r in open_a1] == [3168.0]


def test_disappeared_ads_closed_only_on_complete_snapshot(store):
    record(store, 0, [ask("A1", "3170", "100"), ask("A2", "3175", "50")], [bid("B1", "3160", "200")])
    record(store, 1, [ask("A1", "3170", "100")], [bid("B1", "3160", "200")], complete=False)
    assert store.query("SELECT open FROM ad_states WHERE ad_id='A2'")[0]["open"] == 1
    record(store, 2, [ask("A1", "3170", "100")], [bid("B1", "3160", "200")])
    assert store.query("SELECT open FROM ad_states WHERE ad_id='A2'")[0]["open"] == 0


def test_duplicate_snapshot_ignored(store):
    record(store, 0, [ask("A1", "3170", "100")], [bid("B1", "3160", "200")])
    record(store, 0, [ask("A1", "3170", "100")], [bid("B1", "3160", "200")])
    assert store.counts()["snapshots"] == 2


def test_window_change_flows(store):
    record(store, 0, [ask("A1", "3170", "100"), ask("A2", "3175", "50"), ask("A3", "3180", "70")], [bid("B1", "3160", "200")])
    # 5 min después: A1 bajó cantidad sin cambiar precio (¿venta?), A2 cambió precio, A3 se fue, A4 nuevo
    record(store, 5, [ask("A1", "3170", "60"), ask("A2", "3172", "50"), ask("A4", "3165", "30")], [bid("B1", "3160", "200")])
    now = int((T0 + timedelta(minutes=5)).timestamp())
    w = window_change(store, VENUE, MARKET, Side.ASK, now, 5)
    assert w.best_price_delta == pytest.approx(-5.0)  # 3170 → 3165
    assert w.ads_appeared == 1 and w.ads_disappeared == 1 and w.repriced == 1
    assert w.qty_appeared == pytest.approx(30) and w.qty_disappeared == pytest.approx(70)
    assert w.ads_reduced_same_price == 1 and w.qty_reduced_same_price == pytest.approx(40)
    assert w.announced_qty_delta == pytest.approx(140 - 220)


def test_window_changes_all_windows(store):
    for m in range(0, 61, 5):
        record(store, m, [ask("A1", str(3170 - m // 5), "100")], [bid("B1", "3160", "200")])
    res = window_changes(store, VENUE, MARKET)
    assert [w.minutes for w in res[Side.ASK]] == [5, 15, 30, 60]
    assert res[Side.ASK][-1].best_price_delta == pytest.approx(-12)


def test_window_change_none_without_history(store):
    record(store, 0, [ask("A1", "3170", "100")], [bid("B1", "3160", "200")])
    assert window_change(store, VENUE, MARKET, Side.ASK, int(T0.timestamp()), 5) is None


def test_hourly_profile_and_day_type(store):
    record(store, 0, [ask("A1", "3170", "100")], [bid("B1", "3160", "200")])  # lunes 08:00 COT
    record(store, 1, [ask("A1", "3150", "100")], [bid("B1", "3160", "200")])  # cruce aprovechable
    sunday = T0 - timedelta(days=1)
    st_a, st_b = summarize(Side.ASK, [ask("A9", "3171", "1")]), summarize(Side.BID, [bid("B9", "3160", "1")])
    ts = int(sunday.timestamp())
    store.record_cycle(VENUE, MARKET, ts, spread(st_a, st_b), st_a.best_price, st_b.best_price, None)
    rows = hourly_profile(store, VENUE, MARKET)
    by = {(r.day_type, r.hour): r for r in rows}
    weekday = by[("hábil", 8)]
    assert weekday.cycles == 2 and weekday.crossed_pct == pytest.approx(50) and weekday.executable_pct == pytest.approx(50)
    assert weekday.avg_spread == pytest.approx(0)  # (10 + −10) / 2
    assert by[("fin de semana", 8)].cycles == 1


def test_cross_episodes(store):
    record(store, 0, [ask("A1", "3170", "100")], [bid("B1", "3160", "200")])
    record(store, 1, [ask("A1", "3150", "100")], [bid("B1", "3160", "200")])
    record(store, 2, [ask("A1", "3152", "100")], [bid("B1", "3160", "200")])
    record(store, 30, [ask("A1", "3155", "100", methods=("Efecty",))], [bid("B1", "3160", "200")])
    eps = cross_episodes(store, VENUE, MARKET)
    assert len(eps) == 2
    assert eps[0].cycles == 2 and eps[0].executable_cycles == 2 and eps[0].best_net_per_unit == pytest.approx(10)
    assert eps[0].minutes == pytest.approx(1)
    assert eps[1].executable_cycles == 0


def test_import_jsonl_roundtrip_and_idempotent(tmp_path):
    rec = SnapshotRecorder(tmp_path / "snaps")
    for m in range(3):
        at = T0 + timedelta(minutes=m)
        asks = [ask("A1", str(3150 + m * 10), "100")]
        bids = [bid("B1", "3160", "200")]
        rec.write(snap(Side.ASK, asks, at), summarize(Side.ASK, asks))
        rec.write(snap(Side.BID, bids, at + timedelta(seconds=2)), summarize(Side.BID, bids))
    with HistoryStore(tmp_path / "h.db") as store:
        r1 = import_directory(store, tmp_path / "snaps")
        assert r1.inserted == 6 and r1.cycles == 3 and r1.bad_lines == 0
        r2 = import_directory(store, tmp_path / "snaps")
        assert r2.inserted == 0 and r2.skipped == 6
        cycles = store.query("SELECT crossed, executable, spread FROM cycles ORDER BY cycle_ts")
        assert [c["crossed"] for c in cycles] == [1, 0, 0]
        assert [c["executable"] for c in cycles] == [1, 0, 0]
        # BID se empareja con el ASK de su ciclo
        assert store.query("SELECT COUNT(DISTINCT cycle_ts) n FROM snapshots")[0]["n"] == 3


def test_old_snapshot_does_not_rewrite_ad_history(store):
    record(store, 10, [ask("A1", "3170", "100")], [bid("B1", "3160", "200")])
    record(store, 0, [ask("A1", "3100", "1")], [bid("B1", "3160", "200")])  # llega tarde (importación)
    rows = store.query("SELECT price FROM ad_states WHERE ad_id='A1'")
    assert [r["price"] for r in rows] == [3170.0]
    assert store.counts()["snapshots"] == 4
