"""Datos de prueba con la forma real observada en la verificación del 2026-10-18."""

from decimal import Decimal

from jmcambios.domain import Ad, Advertiser, Side


def search_item(adv_no, price, qty, *, user="u1", nick="Nick1", methods=("BancolombiaSA",), lo="50000", hi="5000000",
                trade_type="SELL", user_type="merchant", orders=500, finish="0.98"):
    return {
        "adv": {
            "advNo": adv_no,
            "asset": "USDT",
            "classify": "mass",
            "fiatUnit": "COP",
            "maxSingleTransAmount": hi,
            "minSingleTransAmount": lo,
            "payTimeLimit": 15,
            "price": price,
            "surplusAmount": qty,
            "takerAdditionalKycRequired": 0,
            "tradableQuantity": qty,
            "tradeMethods": [{"identifier": m, "tradeMethodName": m} for m in methods],
            "tradeType": trade_type,
        },
        "advertiser": {
            "monthFinishRate": finish,
            "monthOrderCount": orders,
            "nickName": nick,
            "tagIconUrls": [],
            "userNo": user,
            "userType": user_type,
        },
    }


def make_ad(ad_id, price, qty, *, side=Side.ASK, user="u1", nick="Nick1", methods=("BancolombiaSA",),
            lo="50000", hi="5000000", user_type="merchant", orders=500, finish="0.98"):
    return Ad(
        venue="binance_p2p",
        ad_id=ad_id,
        side=side,
        asset="USDT",
        fiat="COP",
        price=Decimal(price),
        available_qty=Decimal(qty),
        min_fiat=Decimal(lo),
        max_fiat=Decimal(hi),
        payment_methods=tuple(methods),
        advertiser=Advertiser(user_id=user, nickname=nick, user_type=user_type, month_orders=orders,
                              month_finish_rate=Decimal(finish) if finish is not None else None),
    )
