"""Modelos de la cuenta propia: órdenes ejecutadas y anuncios propios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class OrderSide(str, Enum):
    """Desde MI punto de vista: BUY = compré el activo (pagué fiat); SELL = vendí el activo."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class Order:
    venue: str
    order_id: str
    side: OrderSide
    asset: str
    fiat: str
    qty: Decimal  # cantidad del activo de la orden
    unit_price: Decimal
    total_fiat: Decimal
    status: str  # COMPLETED, CANCELLED, ...
    created_at: datetime
    role: str | None = None  # MAKER (mi anuncio) / TAKER (anuncio ajeno)
    commission: Decimal | None = None  # en unidades del activo; None = Binance no la informó
    commission_rate: Decimal | None = None
    pay_method: str | None = None  # método de la orden (cuenta de la contraparte o la mía según el lado)
    counterparty: str | None = None
    ad_id: str | None = None

    @property
    def completed(self) -> bool:
        return self.status.upper() in ("COMPLETED", "4")


@dataclass(frozen=True)
class MyAd:
    venue: str
    ad_id: str
    side: OrderSide  # BUY = mi anuncio compra el activo
    asset: str
    fiat: str
    price: Decimal
    price_type: int | None  # 1 fijo, 2 flotante
    floating_ratio: Decimal | None
    available_qty: Decimal
    min_fiat: Decimal
    max_fiat: Decimal
    payment_methods: tuple[str, ...]
    status: int | None  # 1 en línea, 3 fuera de línea, 4 cerrado
    commission_rate: Decimal | None = None

    @property
    def online(self) -> bool:
        return self.status == 1
