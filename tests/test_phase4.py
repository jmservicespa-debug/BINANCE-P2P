import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from jmcambios.analysis.competition import max_profitable_buy_price, min_profitable_sell_price, position
from jmcambios.config import Settings
from jmcambios.connectors.binance.account import BinanceAccount
from jmcambios.connectors.binance.client import BinanceP2PClient
from jmcambios.domain import Side
from jmcambios.domain.account import MyAd, Order, OrderSide
from jmcambios.normalizer.binance_account import my_ad_from_detail, order_from_history
from jmcambios.profitability.calculator import calculate
from jmcambios.profitability.costs import CostConfig, fraction, method_identifier
from jmcambios.storage.history import HistoryStore
from tests.fixtures import make_ad

T0 = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
D = Decimal


def order(i, side, qty, price, *, fiat="COP", minutes=0, commission="0", method="Davivienda", status="COMPLETED", role="MAKER"):
    qty, price = D(qty), D(price)
    return Order(
        venue="binance_p2p", order_id=f"o{i}", side=OrderSide(side), asset="USDT", fiat=fiat, qty=qty,
        unit_price=price, total_fiat=qty * price, status=status, created_at=T0 + timedelta(minutes=minutes),
        role=role, commission=None if commission is None else D(commission), pay_method=method,
    )


CFG = CostConfig()


# ---------------------------------------------------------------- normalizador
def test_order_from_history_taker_and_maker():
    item = {
        "orderNumber": "2201", "advNo": "A1", "tradeType": "BUY", "asset": "USDT", "fiat": "COP",
        "amount": "100", "totalPrice": "316000", "unitPrice": "3160", "orderStatus": "COMPLETED",
        "createTime": 1760000000000, "advertisementRole": "TAKER", "takerCommission": "0.05",
        "takerCommissionRate": "0.0005", "payMethodName": "Nequi", "counterPartNickName": "x",
    }
    o = order_from_history(item)
    assert o.side is OrderSide.BUY and o.commission == D("0.05") and o.role == "TAKER" and o.completed
    item.update(advertisementRole="MAKER", commission="0.16", commissionRate="0.0016")
    assert order_from_history(item).commission == D("0.16")
    item.pop("commission")
    assert order_from_history(item).commission is None


def test_order_status_numeric_and_missing_unit_price():
    o = order_from_history({"orderNumber": "1", "tradeType": "SELL", "asset": "USDT", "fiat": "COP", "amount": "2",
                            "totalPrice": "6400", "orderStatus": 6, "createTime": "1760000000000"})
    assert o.status == "CANCELLED" and not o.completed and o.unit_price == D("3200")


def test_my_ad_from_detail():
    ad = my_ad_from_detail({"advNo": "99", "tradeType": "SELL", "asset": "USDT", "fiatUnit": "COP", "price": "3170",
                            "priceType": 1, "surplusAmount": "500", "minSingleTransAmount": "50000",
                            "maxSingleTransAmount": "2000000", "advStatus": 1, "commissionRate": "0.0016",
                            "tradeMethods": [{"identifier": "Nequi"}, {"identifier": "DaviviendaSA"}]})
    assert ad.side is OrderSide.SELL and ad.online and ad.payment_methods == ("Nequi", "DaviviendaSA")


# ---------------------------------------------------------------- costos
def test_method_identifier_and_gmf():
    assert method_identifier("Davivienda") == "DaviviendaSA"
    assert method_identifier("DaviPlata") == "Daviplata"
    assert method_identifier("Bancolombia S.A.") == "BancolombiaSA"
    assert method_identifier("Transferencia Bre-B") == "BreBKeys"
    assert CFG.gmf_rate(order(1, "BUY", 1, 1, method="Nequi")) == D("0.004")
    assert CFG.gmf_rate(order(1, "BUY", 1, 1, method="Daviplata")) == 0
    assert CFG.gmf_rate(order(1, "BUY", 1, 1, method="Efecty")) == D("0.004")  # cuenta desconocida → por defecto
    assert CFG.gmf_rate(order(1, "SELL", 1, 1, method="Nequi")) == 0  # recibir no paga 4x1000
    assert CFG.gmf_rate(order(1, "BUY", 1, 1, method="Nequi"), "minimo") == 0


def test_fraction():
    assert fraction(D("0.0016")) == D("0.0016")
    assert fraction(D("0.16")) == D("0.0016")


# ---------------------------------------------------------------- rentabilidad
def test_simple_cycle_exempt_account():
    orders = [order(1, "BUY", "1000", "3150"), order(2, "SELL", "1000", "3170", minutes=60)]
    r = calculate(orders, CFG, fiat="COP")
    assert r.realized == D("20000") and r.realized_qty == D("1000")
    assert r.gross_margin_per_unit == D("20") and r.inventory_qty == 0
    assert r.effective_buy_price == D("3150") and r.effective_sell_price == D("3170")
    assert not r.warnings


def test_cycle_with_gmf_and_commissions():
    orders = [
        order(1, "BUY", "1000", "3150", method="Nequi", commission="1"),  # entran 999 USDT; costo 3.150.000 + 12.600
        order(2, "SELL", "998", "3170", minutes=10, commission="1"),  # salen 999 USDT
    ]
    r = calculate(orders, CFG, fiat="COP")
    assert r.gmf == D("12600")
    cost = D("3150000") + D("12600")
    assert r.realized == D("998") * D("3170") - cost
    assert r.inventory_qty == 0
    assert r.effective_buy_price == cost / D("999")


def test_average_cost_and_open_inventory():
    orders = [
        order(1, "BUY", "100", "3100"), order(2, "BUY", "100", "3200", minutes=1),
        order(3, "SELL", "50", "3300", minutes=2),
    ]
    r = calculate(orders, CFG, fiat="COP")
    assert r.realized == D("50") * (D("3300") - D("3150"))
    assert r.inventory_qty == D("150") and r.inventory_avg_cost == D("3150")
    assert r.estimated_inventory_value(D("3160")) == D("150") * D("10")


def test_unmatched_sales_not_counted_as_profit():
    r = calculate([order(1, "SELL", "100", "3170")], CFG, fiat="COP")
    assert r.realized == 0 and r.unmatched_sold_qty == D("100") and r.warnings


def test_filters_fiat_status_and_period():
    orders = [
        order(1, "BUY", "100", "3100"),
        order(2, "SELL", "100", "40", fiat="VES", minutes=1),
        order(3, "SELL", "100", "3200", minutes=2, status="CANCELLED"),
        order(4, "SELL", "100", "3200", minutes=600),
    ]
    r = calculate(orders, CFG, fiat="COP", start=T0, end=T0 + timedelta(hours=5))
    assert r.buys == 1 and r.sells == 0 and r.not_completed == 1


def test_gmf_range_and_metrics():
    orders = [order(1, "BUY", "1000", "3150", method="Nequi"), order(2, "SELL", "1000", "3170", minutes=120)]
    cfg = CostConfig(capital=D("10000000"), cost_per_order=D("500"), opportunity_rate_annual=D("0.10"))
    est = calculate(orders, cfg, fiat="COP", start=T0, end=T0 + timedelta(hours=10))
    best = calculate(orders, cfg, fiat="COP", gmf_mode="minimo", start=T0, end=T0 + timedelta(hours=10))
    assert best.realized - est.realized == D("12600")
    assert est.net_realized == est.realized - 1000
    assert est.roc_pct(cfg.capital) == est.net_realized / D("10000000") * 100
    assert est.turnover(cfg.capital) == D("0.315")
    assert est.profit_per_hour() == pytest.approx(est.net_realized / 10)
    assert est.opportunity_cost(cfg.capital, cfg.opportunity_rate_annual) == pytest.approx(
        D("10000000") * D("0.10") * 10 / (24 * 365))


def test_missing_commission_warned():
    r = calculate([order(1, "BUY", "10", "3000", commission=None)], CFG, fiat="COP")
    assert r.commissions_missing == 1 and any("sin comisión" in w for w in r.warnings)


# ---------------------------------------------------------------- competencia
def my(side, price, methods=("Nequi",), lo="50000", hi="2000000"):
    return MyAd(venue="binance_p2p", ad_id="MINE", side=OrderSide(side), asset="USDT", fiat="COP", price=D(price),
                price_type=1, floating_ratio=None, available_qty=D("500"), min_fiat=D(lo), max_fiat=D(hi),
                payment_methods=tuple(methods), status=1, commission_rate=D("0.0016"))


def test_position_sell_ad_against_asks():
    asks = [
        make_ad("a1", "3160", "100", user="u1", methods=("Nequi",)),
        make_ad("a2", "3165", "200", user="u2", methods=("Efecty",)),
        make_ad("a3", "3170", "50", user="u3"),
        make_ad("a4", "3180", "70", user="u4"),
        make_ad("MINE", "3170", "500", user="me"),
    ]
    p = position(my("SELL", "3170"), asks, my_user_ids={"me"})
    assert p.side is Side.ASK and p.total_competitors == 4
    assert p.better_count == 2 and p.estimated_rank == 3 and p.tied_count == 1
    assert p.best_price == D("3160") and p.gap_to_best == D("10")
    assert p.compatible_ahead == 1 and p.qty_ahead == D("300")
    assert [c.price for c in p.ahead] == [D("3165"), D("3160")]  # el más cercano primero


def test_position_buy_ad_against_bids():
    bids = [make_ad("b1", "3155", "100", side=Side.BID, user="u1"), make_ad("b2", "3150", "100", side=Side.BID, user="u2")]
    p = position(my("BUY", "3152"), bids)
    assert p.side is Side.BID and p.estimated_rank == 2 and p.gap_to_best == D("3")


def test_price_limits_are_consistent():
    p_buy = max_profitable_buy_price(D("3170"), gmf=D("0.004"), buy_commission=D("0.0016"),
                                     sell_commission=D("0.0016"), min_margin=D("0.003"))
    # comprar a ese precio y vender a 3170 deja exactamente 0,3 %
    cost_net = p_buy * (1 + D("0.004")) / (1 - D("0.0016"))
    margin = D("3170") - (1 + D("0.0016")) * cost_net
    assert margin / D("3170") == pytest.approx(D("0.003"))
    p_sell = min_profitable_sell_price(cost_net, sell_commission=D("0.0016"), min_margin=D("0.003"))
    assert p_sell == pytest.approx(D("3170"))


# ---------------------------------------------------------------- cuenta y base
def test_fetch_orders_windows_pagination_and_store(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        q = dict(httpx.QueryParams(request.url.query))
        calls.append(q)
        if request.url.path.endswith("listUserOrderHistory"):
            page = int(q["page"])
            n = 150 if int(q["endTimestamp"]) > int(T0.timestamp() * 1000) - 1 else 0
            start = (page - 1) * 100
            rows = [{"orderNumber": f"N{i}", "tradeType": "BUY", "asset": "USDT", "fiat": "COP", "amount": "1",
                     "totalPrice": "3160", "unitPrice": "3160", "orderStatus": "COMPLETED",
                     "createTime": int(T0.timestamp() * 1000), "advertisementRole": "MAKER"}
                    for i in range(start, min(start + 100, n))]
            return httpx.Response(200, json={"code": "000000", "success": True, "data": rows, "total": n})
        return httpx.Response(404)

    s = Settings(_env_file=None, BINANCE_API_KEY="k" * 10, BINANCE_API_SECRET="s" * 10)
    with BinanceP2PClient(s, transport=httpx.MockTransport(handler)) as client:
        acct = BinanceAccount(client, clock=lambda: T0 + timedelta(seconds=1))
        fetched = acct.fetch_orders(T0 - timedelta(days=65))
    assert len(fetched.orders) == 150
    windows = {(c["startTimestamp"], c["endTimestamp"]) for c in calls}
    assert len(windows) == 3  # 65 días → 3 ventanas de máx. 30 días
    for start, end in windows:
        assert int(end) - int(start) <= 30 * 86400 * 1000
    with HistoryStore(tmp_path / "h.db") as store:
        assert store.upsert_orders(fetched.orders, 0) == (150, 0)
        assert store.upsert_orders(fetched.orders, 1) == (0, 150)
        loaded = store.load_orders(fiat="COP")
        assert len(loaded) == 150 and loaded[0].total_fiat == D("3160")


def test_business_cli_rentabilidad_and_costos(tmp_path, capsys, monkeypatch):
    from jmcambios.tools import business_cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BINANCE_API_KEY", "")
    db = tmp_path / "h.db"
    now = datetime.now(UTC)
    orders = [
        Order("binance_p2p", "o1", OrderSide.BUY, "USDT", "COP", D("1000"), D("3150"), D("3150000"), "COMPLETED",
              now - timedelta(hours=5), "TAKER", D("0.5"), D("0.0005"), "Nequi"),
        Order("binance_p2p", "o2", OrderSide.SELL, "USDT", "COP", D("999"), D("3175"), D("3171825"), "COMPLETED",
              now - timedelta(hours=1), "MAKER", D("0.5"), D("0.0005"), "Davivienda"),
    ]
    with HistoryStore(db) as store:
        store.upsert_orders(orders, 0)
    assert business_cli.main(["rentabilidad", "--db", str(db), "--capital", "10.000.000", "--dias", "1"]) == 0
    assert business_cli.main(["costos", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "beneficio REALIZADO" in out and "rango según 4x1000" in out and "rotación" in out
    assert "TAKER" in out and "MAKER" in out


def test_fetch_orders_when_binance_caps_page_size_at_50():
    def handler(request: httpx.Request):
        q = dict(httpx.QueryParams(request.url.query))
        page, total = int(q["page"]), 120
        start = (page - 1) * 50  # Binance ignora rows=100 y entrega 50
        rows = [{"orderNumber": f"N{i}", "tradeType": "SELL", "asset": "USDT", "fiat": "VES", "amount": "1",
                 "totalPrice": "40", "orderStatus": "COMPLETED", "createTime": int(T0.timestamp() * 1000),
                 "advertisementRole": "TAKER"} for i in range(start, min(start + 50, total))]
        return httpx.Response(200, json={"code": "000000", "success": True, "data": rows, "total": total})

    s = Settings(_env_file=None, BINANCE_API_KEY="k" * 10, BINANCE_API_SECRET="s" * 10)
    with BinanceP2PClient(s, transport=httpx.MockTransport(handler)) as client:
        fetched = BinanceAccount(client, clock=lambda: T0 + timedelta(seconds=1)).fetch_orders(T0 - timedelta(days=10))
    assert len(fetched.orders) == 120 and fetched.requests == 3


def test_observed_fee_prefers_fiat_then_falls_back():
    from jmcambios.analysis.crossing import taker_fees_from_orders
    from jmcambios.profitability.costs import observed_fee

    ves = [order(f"v{i}", OrderSide.SELL, "100", "40", fiat="VES", commission="0.142", role="TAKER") for i in range(5)]
    cop = [order(f"c{i}", OrderSide.SELL, "100", "3800", commission="0.2", role="TAKER") for i in range(5)]
    # Con datos COP suficientes usa COP; si no, todas las monedas.
    fee = observed_fee(ves + cop, role="TAKER", side=OrderSide.SELL, fiat="COP")
    assert fee.rate == Decimal("0.002") and fee.scope == "COP" and fee.orders == 5
    fee = observed_fee(ves + cop[:2], role="TAKER", side=OrderSide.SELL, fiat="COP")
    assert fee.scope == "todas las monedas" and fee.orders == 7
    assert observed_fee(ves, role="TAKER", side=OrderSide.BUY, fiat="COP") is None
    assert taker_fees_from_orders(ves, "COP") == {"taker_fee_sell": Decimal("0.00142")}
