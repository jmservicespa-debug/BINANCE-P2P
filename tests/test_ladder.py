import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from jmcambios.alerts import rules
from jmcambios.analysis import ladder
from jmcambios.config import Mode
from jmcambios.dashboard import server as panel
from jmcambios.domain.account import Order, OrderSide
from jmcambios.monitor.advisor import Advisor
from jmcambios.pricing.engine import Costs
from jmcambios.storage.history import HistoryStore
from tests.test_phase6 import METHODS, _setup_ads, cycle, my_ad

D = Decimal
T = 1_800_000_000  # instante base (segundos)
COSTS = Costs(D("0.002"), D("0.002"), D("0"), D("0.004"), D("0.01"))
RULES = ladder.LadderRules(fast_s=20 * 60, slow_s=60 * 60, step=D("0.001"))


def row(ts, side, price, online=1, rank=3, ad_id=None):
    return {"ts": ts, "ad_id": ad_id or f"ad-{side}", "side": side, "price": price, "online": online, "rank": rank,
            "total": 40, "min_fiat": 100000.0, "max_fiat": 500000.0, "available": 200.0}


def order(i, side, price, ts, status="COMPLETED", role="MAKER", qty="100"):
    q, p = D(qty), D(price)
    return Order(venue="binance_p2p", order_id=f"o{i}", side=side, asset="USDT", fiat="COP", qty=q, unit_price=p,
                 total_fiat=q * p, status=status, created_at=datetime.fromtimestamp(ts, UTC), role=role)


def log_both():
    # Compra a 3130 desde T; venta a 3165 desde T. La compra cambia a 3128 en T+1800.
    out = []
    for k in range(0, 13):
        ts = T + k * 300
        out.append(row(ts, "BUY", 3130.0 if ts < T + 1800 else 3128.0, rank=2 if ts < T + 1800 else 6))
        out.append(row(ts, "SELL", 3165.0))
    return out


def test_fills_wait_rank_and_pair_margin():
    orders = [order(1, OrderSide.BUY, "3130", T + 600), order(2, OrderSide.BUY, "3130", T + 900),
              order(3, OrderSide.BUY, "3128", T + 3000), order(4, OrderSide.BUY, "3128", T + 3100, status="CANCELLED"),
              order(5, OrderSide.SELL, "3170", T + 3200, role="TAKER")]
    fs = ladder.fills(orders, log_both(), COSTS)
    assert [f.order_id for f in fs] == ["o1", "o2", "o3"]  # sin canceladas ni órdenes en anuncios ajenos
    assert [f.wait_s for f in fs] == [600, 300, 1200]  # desde el inicio, la orden anterior y el cambio de precio
    assert fs[0].rank == 2 and fs[2].rank == 6 and fs[0].min_fiat == 100000.0
    assert fs[0].pair_margin == pytest.approx(D(1) - D("3130") * D("1.002") / (D("3165") * D("0.998")), abs=D("1e-9"))
    groups = ladder.by_rank(fs)
    assert [(g["rank"], g["orders"], g["median_wait_s"]) for g in groups] == [("#2–3", 2, 450), ("#4–8", 1, 1200)]


def test_fill_before_any_log_has_no_wait():
    fs = ladder.fills([order(1, OrderSide.BUY, "3130", T - 60)], log_both(), COSTS)
    assert fs[0].wait_s is None and fs[0].rank is None


def test_suggest_up_down_and_hold():
    log = log_both()
    # Compra: se llenó 4 min después de bajar a 3128 → subir margen (comprar más barato).
    steps = ladder.suggest(log, ladder.fills([order(1, OrderSide.BUY, "3128", T + 2040)], log, COSTS),
                           T + 2400, COSTS, RULES)
    buy, sell = steps
    assert buy.action == "subir" and buy.suggested == D("3124.87") and buy.last_wait_s == 240
    assert buy.margin_after > buy.margin_now
    # Venta: en línea desde T sin órdenes → 40 min: mantener; a los 61 min: bajar (vender más barato).
    assert sell.action == "mantener" and sell.suggested is None and "primera orden" in sell.reason
    later = ladder.suggest(log, [], T + 3660, COSTS, RULES)
    assert later[1].action == "bajar" and later[1].suggested == D("3161.84") and later[1].margin_after < later[1].margin_now
    assert later[1].below_min and buy.below_min  # el par de ejemplo está bajo el 1 % en los dos casos
    assert not ladder.suggest(log, [], T + 3660, Costs(D("0"), D("0"), D("0"), D("0"), D("0.005")), RULES)[1].below_min
    assert "debajo de tu margen mínimo" in rules.ladder_alert(later[1]).body
    # Compra a 3128 desde T+1800 sin órdenes: 31 min → mantener.
    assert later[0].action == "mantener"


def test_suggest_skips_offline_and_alert_text():
    log = [row(T, "BUY", 3130.0, online=0)]
    assert ladder.suggest(log, [], T + 7200, COSTS, RULES) == []
    step = ladder.suggest([row(T, "SELL", 3165.0)], [], T + 4000, COSTS, RULES)[0]
    a = rules.ladder_alert(step)
    assert a.key == f"escalera:SELL:bajar:{T}" and "venta" in a.title and "3.165,00 → 3.161,84" in a.body
    assert rules.ladder_alert(ladder.suggest([row(T, "SELL", 3165.0)], [], T + 60, COSTS, RULES)[0]) is None


def test_advisor_logs_my_ads_and_writes_ladder(tmp_path):
    store = HistoryStore(":memory:")
    state = tmp_path / "estado.json"
    adv = Advisor(orders=[], fiat="COP", gmf_by_account=METHODS, mode=Mode.RECOMMENDATION, ads_every=2,
                  fetch_my_ads=lambda: [my_ad(OrderSide.BUY, "3140", ad_id="b1"), my_ad(OrderSide.SELL, "3210", ad_id="s1")],
                  state_path=state, store=store, ladder_rules=RULES)
    asks, bids, _ = _setup_ads()
    for i in range(3):
        out = adv.process(cycle(asks, bids), 0, T + i * 60)
    log = store.my_ad_log("COP", 0)
    assert len(log) == 4 and {r["ts"] for r in log} == {T, T + 120}  # solo cuando se leen los anuncios
    assert all(r["rank"] for r in log)
    assert [s.action for s in out.ladder] == ["mantener", "mantener"]
    s = json.loads(state.read_text(encoding="utf-8"))
    assert s["ladder"][0]["side"] == "BUY" and s["ladder_rules"] == {"fast_min": 20, "slow_min": 60, "step_pct": 0.1}


def test_panel_bitacora(tmp_path):
    db = tmp_path / "h.db"
    now = T + 3600
    with HistoryStore(db) as st:
        for r in log_both():
            st.record_my_ads(r["ts"], "COP", [r])
        st.upsert_orders([order(1, OrderSide.BUY, "3130", T + 600), order(2, OrderSide.SELL, "3165", T + 1500)], now)
    state = tmp_path / "e.json"
    state.write_text(json.dumps({"generated_ts": now, "costs": {"maker_buy": 0.002, "maker_sell": 0.002, "gmf": 0,
                                                                "gmf_worst": 0.004, "min_margin": 0.01}}), encoding="utf-8")
    data = panel.PanelData(db, state, venue="binance_p2p", market="USDT/COP", fiat="COP", asset="USDT",
                           cost_config=panel.cost_config(METHODS))
    out = data.bitacora(7, now)
    assert out["logged"] and [f["side"] for f in out["fills"]] == ["SELL", "BUY"]  # la más reciente primero
    assert out["fills"][1]["wait_s"] == 600 and out["fills"][0]["pair_margin"] is not None
    assert {(g["side"], g["orders"]) for g in out["by_rank"]} == {("BUY", 1), ("SELL", 1)}


def test_summary_includes_bitacora_and_ladder(tmp_path):
    from jmcambios.alerts.channels import MemoryChannel
    from jmcambios.alerts.manager import AlertManager

    store = HistoryStore(":memory:")
    for r in log_both():
        store.record_my_ads(r["ts"], "COP", [r])
    chan = MemoryChannel()
    hour = datetime.fromtimestamp(T + 2400, UTC).astimezone(ladder_tz()).hour
    adv = Advisor(orders=[order(1, OrderSide.BUY, "3128", T + 2040)], fiat="COP", gmf_by_account=METHODS,
                  mode=Mode.RECOMMENDATION, alerts=AlertManager([chan], store), store=store, ladder_rules=RULES,
                  summary_hours=(hour,))
    asks, bids, _ = _setup_ads()
    adv.process(cycle(asks, bids), 0, T + 2400)
    body = next(b for t, b in chan.sent if "Resumen" in t or "resumen" in t.lower())
    assert "Bitácora: 1 órdenes por tus anuncios · espera mediana 4 min" in body
    assert "Escalera compra: subir → 3.124,87" in body
    assert any("Escalera: sube el margen de tu anuncio de compra" in t for t, _ in chan.sent)


def ladder_tz():
    from jmcambios.profitability.daily import COT

    return COT
