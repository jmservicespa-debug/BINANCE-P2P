"""Validador y normalizador de anuncios Binance P2P (módulo 2).

Convierte las respuestas de `ads/search` (SAPI) y `ad-list` (público) en `Ad`.
Un anuncio con datos incoherentes se rechaza con su motivo; nunca se "repara"
inventando valores.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from jmcambios.domain import Ad, Advertiser, RejectedAd, Side

VENUE = "binance_p2p"


class InvalidAd(ValueError):
    pass


def side_for_query(query_trade_type: str) -> Side:
    """En Binance, buscar tradeType=BUY devuelve anuncios de quien VENDE (ASK)."""
    return Side.ASK if query_trade_type.upper() == "BUY" else Side.BID


def query_for_side(side: Side) -> str:
    return "BUY" if side is Side.ASK else "SELL"


def _dec(value: Any, name: str, *, required: bool = True) -> Decimal | None:
    if value is None or value == "":
        if required:
            raise InvalidAd(f"falta {name}")
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise InvalidAd(f"{name} no numérico") from exc
    if not result.is_finite():
        raise InvalidAd(f"{name} no finito")
    return result


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _methods(raw: Any) -> tuple[str, ...]:
    out: list[str] = []
    for m in raw or []:
        ident = m.get("identifier") or m.get("tradeMethodName") if isinstance(m, dict) else m
        if ident:
            out.append(str(ident))
    return tuple(dict.fromkeys(out))


def _finish_rate(value: Any) -> Decimal | None:
    rate = _dec(value, "monthFinishRate", required=False)
    if rate is None:
        return None
    # Binance la entrega como fracción (0.98); por si llega en porcentaje (98).
    return rate / 100 if rate > 1 else rate


def _advertiser(raw: Any) -> Advertiser:
    raw = raw if isinstance(raw, dict) else {}
    user_id = raw.get("userNo") or raw.get("userId") or raw.get("merchantNo")
    if not user_id:
        raise InvalidAd("anunciante sin identificador")
    return Advertiser(
        user_id=str(user_id),
        nickname=str(raw.get("nickName") or raw.get("nickname") or ""),
        user_type=raw.get("userType"),
        month_orders=_int(raw.get("monthOrderCount")),
        month_finish_rate=_finish_rate(raw.get("monthFinishRate")),
    )


def _build(
    *,
    ad_id: Any,
    side: Side,
    asset: str,
    fiat: str,
    price: Any,
    qty: Any,
    min_fiat: Any,
    max_fiat: Any,
    methods: Any,
    advertiser: Any,
    classify: Any = None,
    pay_time: Any = None,
) -> Ad:
    if not ad_id:
        raise InvalidAd("anuncio sin número")
    p = _dec(price, "precio")
    q = _dec(qty, "cantidad disponible")
    lo = _dec(min_fiat, "límite mínimo")
    hi = _dec(max_fiat, "límite máximo")
    assert p is not None and q is not None and lo is not None and hi is not None
    if p <= 0:
        raise InvalidAd("precio no positivo")
    if q < 0:
        raise InvalidAd("cantidad negativa")
    if lo < 0 or hi <= 0 or lo > hi:
        raise InvalidAd("límites incoherentes")
    pm = _methods(methods)
    if not pm:
        raise InvalidAd("sin métodos de pago")
    return Ad(
        venue=VENUE,
        ad_id=str(ad_id),
        side=side,
        asset=asset,
        fiat=fiat,
        price=p,
        available_qty=q,
        min_fiat=lo,
        max_fiat=hi,
        payment_methods=pm,
        advertiser=_advertiser(advertiser),
        classify=classify,
        pay_time_limit_min=_int(pay_time),
    )


def from_sapi_search(item: Any, query_trade_type: str, asset: str, fiat: str) -> Ad:
    """Elemento de `POST /sapi/v1/c2c/agent/ads/search` → Ad."""
    if not isinstance(item, dict):
        raise InvalidAd("elemento no es un objeto")
    adv = item.get("adv") or {}
    if (adv.get("asset") or asset) != asset or (adv.get("fiatUnit") or fiat) != fiat:
        raise InvalidAd("activo o moneda distinta a la consultada")
    side = side_for_query(query_trade_type)
    qty = adv.get("surplusAmount") if adv.get("surplusAmount") is not None else adv.get("tradableQuantity")
    return _build(
        ad_id=adv.get("advNo"),
        side=side,
        asset=asset,
        fiat=fiat,
        price=adv.get("price"),
        qty=qty,
        min_fiat=adv.get("minSingleTransAmount"),
        max_fiat=adv.get("maxSingleTransAmount"),
        methods=adv.get("tradeMethods"),
        advertiser=item.get("advertiser"),
        classify=adv.get("classify"),
        pay_time=adv.get("payTimeLimit"),
    )


def from_public_ad_list(item: Any, query_trade_type: str, asset: str, fiat: str) -> Ad:
    """Elemento de `GET /bapi/c2c/v1/public/c2c/agent/ad-list` → Ad."""
    if not isinstance(item, dict):
        raise InvalidAd("elemento no es un objeto")
    if (item.get("asset") or asset) != asset or (item.get("fiat") or fiat) != fiat:
        raise InvalidAd("activo o moneda distinta a la consultada")
    return _build(
        ad_id=item.get("adNo"),
        side=side_for_query(query_trade_type),
        asset=asset,
        fiat=fiat,
        price=item.get("price"),
        qty=item.get("tradableAmount"),
        min_fiat=item.get("minTransAmount"),
        max_fiat=item.get("maxTransAmount"),
        methods=item.get("tradeMethods"),
        advertiser=item.get("advertiser"),
        pay_time=item.get("payTimeLimit"),
    )


def reported_side(item: Any) -> Side | None:
    """Lado que declara el propio anuncio (`adv.tradeType`: SELL = el anunciante vende)."""
    adv = item.get("adv") if isinstance(item, dict) else None
    reported = (adv or {}).get("tradeType")
    if not reported:
        return None
    return Side.ASK if str(reported).upper() == "SELL" else Side.BID


def normalize_many(items: list[Any], parser, query_trade_type: str, asset: str, fiat: str) -> tuple[list[Ad], list[RejectedAd]]:
    ads: list[Ad] = []
    rejected: list[RejectedAd] = []
    for item in items:
        try:
            ads.append(parser(item, query_trade_type, asset, fiat))
        except InvalidAd as exc:
            ad_id = None
            if isinstance(item, dict):
                ad_id = (item.get("adv") or {}).get("advNo") or item.get("adNo")
            rejected.append(RejectedAd(ad_id=ad_id, reason=str(exc)))
    return ads, rejected
