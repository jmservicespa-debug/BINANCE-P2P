from decimal import Decimal

from jmcambios.analysis.crossing import DEFAULT_MY_METHODS, analyze, parse_my_methods
from jmcambios.domain import Side
from tests.fixtures import make_ad


def ask(i, price, methods, lo="10000", hi="10000000", qty="1000"):
    return make_ad(f"a{i}", price, qty, side=Side.ASK, methods=methods, lo=lo, hi=hi, user=f"s{i}")


def bid(i, price, methods, lo="10000", hi="10000000", qty="1000"):
    return make_ad(f"b{i}", price, qty, side=Side.BID, methods=methods, lo=lo, hi=hi, user=f"b{i}")


def test_parse_my_methods():
    assert parse_my_methods(None) == DEFAULT_MY_METHODS
    assert parse_my_methods("DaviviendaSA:0, Nequi:0.004") == {"DaviviendaSA": Decimal("0"), "Nequi": Decimal("0.004")}


def test_no_cross():
    r = analyze([ask(1, "3170", ("Nequi",))], [bid(1, "3160", ("Nequi",))])
    assert not r.crossed and not r.executable and r.gross_spread == Decimal("-10")


def test_cross_profitable_paying_with_exempt_account():
    r = analyze([ask(1, "3155.59", ("Nequi", "DaviviendaSA"))], [bid(1, "3160", ("BancolombiaSA",))])
    assert r.crossed and r.executable
    assert r.best.pay_method == "DaviviendaSA" and r.best.gmf_rate == 0
    assert r.best.receive_method == "BancolombiaSA"
    assert r.best.net_per_unit == Decimal("4.41")


def test_cross_eaten_by_gmf():
    r = analyze([ask(1, "3155.59", ("Nequi",))], [bid(1, "3160", ("Nequi",))])
    assert r.crossed and not r.executable
    # 4,41 − 3155,59 × 0,004 = −8,2124
    assert r.best.net_per_unit == Decimal("4.41") - Decimal("3155.59") * Decimal("0.004")
    assert r.rejected == {"el 4x1000/comisiones se comen el margen": 1}


def test_cross_without_my_methods():
    r = analyze([ask(1, "3150", ("Efecty",))], [bid(1, "3160", ("Nequi",))])
    assert not r.executable and "no puedo pagarle al vendedor con mis métodos" in r.rejected


def test_cross_incompatible_amounts():
    r = analyze(
        [ask(1, "3150", ("DaviviendaSA",), lo="10000", hi="500000")],
        [bid(1, "3160", ("Nequi",), lo="5000000", hi="9000000")],
    )
    assert not r.executable and r.rejected == {"montos incompatibles entre los dos anuncios": 1}


def test_quantity_range_respects_both_ads_and_available_qty():
    r = analyze(
        [ask(1, "3150", ("DaviviendaSA",), lo="315000", hi="31500000", qty="500")],  # 100–500 USDT (disponible 500)
        [bid(1, "3160", ("Nequi",), lo="632000", hi="3160000")],  # 200–1000 USDT
    )
    assert r.best.min_qty == Decimal("200") and r.best.max_qty == Decimal("500")
    assert r.best.net_total_max == Decimal("10") * 500


def test_taker_fee_parameter():
    r = analyze([ask(1, "3150", ("DaviviendaSA",))], [bid(1, "3160", ("Nequi",))], taker_fee_rate=Decimal("0.001"))
    assert r.best.net_per_unit == Decimal("10") - Decimal("6310") * Decimal("0.001")


def test_picks_best_total_among_pairs():
    asks = [ask(1, "3150", ("DaviviendaSA",), qty="10"), ask(2, "3152", ("DaviviendaSA",), qty="1000")]
    bids = [bid(1, "3160", ("Nequi",))]
    r = analyze(asks, bids)
    assert r.best.buy_ad.ad_id == "a2"  # 8 × 1000 > 10 × 10
    assert r.executable_profitable == 2
