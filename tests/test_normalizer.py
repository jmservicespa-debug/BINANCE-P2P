from decimal import Decimal

import pytest

from jmcambios.domain import Side
from jmcambios.normalizer import binance_p2p as norm
from tests.fixtures import search_item


def test_query_side_mapping():
    assert norm.side_for_query("BUY") is Side.ASK
    assert norm.side_for_query("SELL") is Side.BID
    assert norm.query_for_side(Side.ASK) == "BUY"
    assert norm.query_for_side(Side.BID) == "SELL"


def test_from_sapi_search_full():
    ad = norm.from_sapi_search(search_item("A1", "3905.50", "1200.5", methods=("Nequi", "Nequi", "BancolombiaSA")),
                               "BUY", "USDT", "COP")
    assert ad.side is Side.ASK and ad.ad_id == "A1"
    assert ad.price == Decimal("3905.50") and ad.available_qty == Decimal("1200.5")
    assert ad.payment_methods == ("Nequi", "BancolombiaSA")
    assert ad.advertiser.is_merchant and ad.advertiser.month_finish_rate == Decimal("0.98")
    assert ad.available_fiat == Decimal("3905.50") * Decimal("1200.5")


def test_finish_rate_in_percent_is_normalized():
    ad = norm.from_sapi_search(search_item("A1", "4000", "10", finish="97.5"), "BUY", "USDT", "COP")
    assert ad.advertiser.month_finish_rate == Decimal("0.975")


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"price": "0"}, "precio no positivo"),
        ({"price": "abc"}, "precio no numérico"),
        ({"qty": "-1"}, "cantidad negativa"),
        ({"lo": "900", "hi": "100"}, "límites incoherentes"),
        ({"methods": ()}, "sin métodos de pago"),
    ],
)
def test_invalid_ads_rejected(kwargs, reason):
    base = {"adv_no": "X", "price": "4000", "qty": "10"}
    base.update(kwargs)
    item = search_item(base.pop("adv_no"), base.pop("price"), base.pop("qty"), **base)
    with pytest.raises(norm.InvalidAd, match=reason):
        norm.from_sapi_search(item, "BUY", "USDT", "COP")


def test_wrong_fiat_rejected():
    item = search_item("A1", "4000", "10")
    item["adv"]["fiatUnit"] = "VES"
    with pytest.raises(norm.InvalidAd):
        norm.from_sapi_search(item, "BUY", "USDT", "COP")


def test_normalize_many_collects_rejections():
    items = [search_item("A1", "4000", "10"), search_item("A2", "0", "10"), "basura"]
    ads, rejected = norm.normalize_many(items, norm.from_sapi_search, "BUY", "USDT", "COP")
    assert [a.ad_id for a in ads] == ["A1"]
    assert {r.ad_id for r in rejected} == {"A2", None}


def test_reported_side():
    assert norm.reported_side(search_item("A", "1", "1", trade_type="SELL")) is Side.ASK
    assert norm.reported_side(search_item("A", "1", "1", trade_type="BUY")) is Side.BID
    assert norm.reported_side({"adv": {}}) is None


def test_from_public_ad_list():
    item = {
        "adNo": "P1", "asset": "USDT", "fiat": "COP", "price": "3910", "tradableAmount": "55.5",
        "minTransAmount": "20000", "maxTransAmount": "2000000", "payTimeLimit": 15,
        "tradeMethods": [{"identifier": "Nequi"}], "advertiser": {"userNo": "u9", "nickName": "N9"},
    }
    ad = norm.from_public_ad_list(item, "SELL", "USDT", "COP")
    assert ad.side is Side.BID and ad.available_qty == Decimal("55.5") and ad.payment_methods == ("Nequi",)


def test_max_fiat_effective_capped_by_available():
    ad = norm.from_sapi_search(search_item("A1", "4000", "10", hi="5000000"), "BUY", "USDT", "COP")
    assert ad.max_fiat_effective == Decimal("40000")
    assert not ad.accepts_amount(Decimal("50000"))
