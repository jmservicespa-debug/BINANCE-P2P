"""Normalización de órdenes y anuncios propios de Binance P2P."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from jmcambios.domain.account import MyAd, Order, OrderSide
from jmcambios.normalizer.binance_p2p import VENUE, InvalidAd, _methods

ORDER_STATUS = {1: "UNPAID", 2: "PAID", 3: "APPEALING", 4: "COMPLETED", 6: "CANCELLED", 7: "CANCELLED_BY_SYSTEM"}


class InvalidOrder(ValueError):
    pass


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def _time(value: Any) -> datetime:
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        return datetime.fromtimestamp(int(value) / 1000, UTC)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    raise InvalidOrder("fecha de creación ilegible")


def _side(value: Any) -> OrderSide:
    v = str(value).upper()
    if v in ("BUY", "0"):
        return OrderSide.BUY
    if v in ("SELL", "1"):
        return OrderSide.SELL
    raise InvalidOrder(f"tipo de orden desconocido: {value}")


def order_from_history(item: Any) -> Order:
    """Elemento de listUserOrderHistory (agent o clásico) → Order."""
    if not isinstance(item, dict):
        raise InvalidOrder("elemento no es un objeto")
    order_id = item.get("orderNumber")
    qty = _dec(item.get("amount"))
    total = _dec(item.get("totalPrice"))
    price = _dec(item.get("unitPrice"))
    if not order_id or qty is None or total is None:
        raise InvalidOrder("orden incompleta")
    if price is None and qty:
        price = total / qty
    status = item.get("orderStatus")
    status = ORDER_STATUS.get(status, str(status)) if isinstance(status, int) else str(status or "")
    role = item.get("advertisementRole")
    # Comisión que pagué: como MAKER la de mi anuncio, como TAKER la de tomador.
    if role == "TAKER":
        commission, rate = _dec(item.get("takerCommission")), _dec(item.get("takerCommissionRate"))
    else:
        commission, rate = _dec(item.get("commission")), _dec(item.get("commissionRate"))
    return Order(
        venue=VENUE,
        order_id=str(order_id),
        side=_side(item.get("tradeType")),
        asset=str(item.get("asset") or ""),
        fiat=str(item.get("fiat") or ""),
        qty=qty,
        unit_price=price,
        total_fiat=total,
        status=status,
        created_at=_time(item.get("createTime")),
        role=role,
        commission=commission,
        commission_rate=rate,
        pay_method=item.get("payMethodName"),
        counterparty=item.get("counterPartNickName"),
        ad_id=item.get("advNo"),
    )


def my_ad_from_detail(item: Any) -> MyAd:
    """Elemento de ads/listWithPagination o getDetailByNo → MyAd."""
    if not isinstance(item, dict) or not item.get("advNo"):
        raise InvalidAd("anuncio propio sin número")
    price = _dec(item.get("price"))
    qty = _dec(item.get("surplusAmount"))
    if qty is None:
        qty = _dec(item.get("tradableQuantity"))
    lo, hi = _dec(item.get("minSingleTransAmount")), _dec(item.get("maxSingleTransAmount"))
    if price is None or qty is None or lo is None or hi is None:
        raise InvalidAd("anuncio propio incompleto")
    status = item.get("advStatus")
    price_type = item.get("priceType")
    return MyAd(
        venue=VENUE,
        ad_id=str(item["advNo"]),
        side=_side(item.get("tradeType")),
        asset=str(item.get("asset") or ""),
        fiat=str(item.get("fiatUnit") or ""),
        price=price,
        price_type=int(price_type) if price_type is not None else None,
        floating_ratio=_dec(item.get("priceFloatingRatio")),
        available_qty=qty,
        min_fiat=lo,
        max_fiat=hi,
        payment_methods=_methods(item.get("tradeMethods")),
        status=int(status) if status is not None else None,
        commission_rate=_dec(item.get("commissionRate")),
    )
