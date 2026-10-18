from decimal import Decimal

from jmcambios.analysis.filters import AdFilter
from jmcambios.analysis.market_stats import spread, summarize
from jmcambios.domain import Side
from tests.fixtures import make_ad

ASKS = [
    make_ad("a1", "4000", "100", user="u1", nick="A", methods=("Nequi",)),
    make_ad("a2", "4010", "300", user="u2", nick="B", methods=("BancolombiaSA",)),
    make_ad("a3", "4100", "600", user="u2", nick="B", methods=("BancolombiaSA", "Nequi")),
]
BIDS = [
    make_ad("b1", "3980", "200", side=Side.BID, user="u3", nick="C"),
    make_ad("b2", "3950", "200", side=Side.BID, user="u4", nick="D"),
]


def test_ask_side_stats():
    s = summarize(Side.ASK, ASKS)
    assert s.ads_count == 3 and s.merchants_count == 2
    assert s.best_price == Decimal("4000") and s.worst_price == Decimal("4100")
    assert s.median_price == Decimal("4010")
    assert s.announced_qty == Decimal("1000")
    # VWAP = (4000*100 + 4010*300 + 4100*600) / 1000
    assert s.vwap == Decimal("4063.00")
    assert s.announced_fiat == Decimal("4063000")
    assert s.depth_qty["0.5%"] == Decimal("400")  # 4000*1.005 = 4020
    assert s.depth_qty["2%"] == Decimal("400")  # 4080 límite → a3 fuera
    assert s.top_merchants[0].nickname == "B" and s.top1_share == Decimal("0.9")
    assert s.hhi == Decimal("8200")  # 0.9² + 0.1² = 0.82
    assert s.by_method["Nequi"].ads == 2 and s.by_method["Nequi"].best_price == Decimal("4000")


def test_bid_best_is_highest():
    s = summarize(Side.BID, BIDS)
    assert s.best_price == Decimal("3980") and s.worst_price == Decimal("3950")
    assert s.depth_qty["0.5%"] == Decimal("200")  # límite 3980*0,995 = 3960,1 → b2 (3950) queda fuera
    assert s.depth_qty["2%"] == Decimal("400")

def test_empty_side():
    s = summarize(Side.ASK, [])
    assert s.ads_count == 0 and s.best_price is None and s.vwap is None


def test_spread():
    sp = spread(summarize(Side.ASK, ASKS), summarize(Side.BID, BIDS))
    assert sp.absolute == Decimal("20") and not sp.inverted
    assert sp.mid == Decimal("3990.00")
    assert sp.pct == Decimal("0.501")


def test_inverted_spread_flagged():
    asks = [make_ad("x", "3900", "1")]
    bids = [make_ad("y", "3950", "1", side=Side.BID)]
    assert spread(summarize(Side.ASK, asks), summarize(Side.BID, bids)).inverted


def test_filter_by_method_amount_and_quality():
    ads = [
        make_ad("1", "4000", "1000", methods=("Nequi",)),
        make_ad("2", "4000", "1000", methods=("Efecty",)),
        make_ad("3", "4000", "1000", lo="2000000", hi="9000000"),
        make_ad("4", "4000", "1000", user_type="user"),
        make_ad("5", "4000", "1000", finish="0.80"),
        make_ad("6", "4000", "1000", orders=3),
        make_ad("7", "4000", "1000", user="me"),
        make_ad("8", "4000", "10"),  # 10 USDT = 40.000 COP < monto
    ]
    f = AdFilter(
        payment_methods=frozenset({"Nequi", "BancolombiaSA"}),
        amount_fiat=Decimal("500000"),
        min_finish_rate=Decimal("0.95"),
        min_month_orders=50,
        merchants_only=True,
        exclude_user_ids=frozenset({"me"}),
    )
    kept, excluded = f.apply(ads)
    assert [a.ad_id for a in kept] == ["1"]
    assert excluded == {
        "método de pago no compatible": 1,
        "monto fuera de los límites": 2,
        "no es comerciante": 1,
        "tasa de finalización baja": 1,
        "pocas órdenes en 30 días": 1,
        "usuario excluido": 1,
    }
    assert "Nequi" in f.describe()


def test_inactive_filter():
    assert not AdFilter().active
    assert AdFilter().describe() == "sin filtros"
