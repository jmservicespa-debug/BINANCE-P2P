"""Modelos de dominio independientes del exchange.

Toda la lógica de negocio (estadísticas, filtros, precios, decisiones) trabaja
sobre estos tipos. Cada adaptador de exchange convierte sus respuestas a ellos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Side(str, Enum):
    """Lado del anuncio según la intención del ANUNCIANTE.

    ASK: el anunciante VENDE el activo (USDT). Ahí compraría yo; compite con mis anuncios de venta.
    BID: el anunciante COMPRA el activo. Ahí vendería yo; compite con mis anuncios de compra.
    """

    ASK = "ASK"
    BID = "BID"

    @property
    def label_es(self) -> str:
        return "Anuncios de VENTA de USDT" if self is Side.ASK else "Anuncios de COMPRA de USDT"


@dataclass(frozen=True)
class Advertiser:
    user_id: str
    nickname: str
    user_type: str | None = None  # "merchant" / "user"
    month_orders: int | None = None
    month_finish_rate: Decimal | None = None  # 0..1

    @property
    def is_merchant(self) -> bool:
        return (self.user_type or "").lower() == "merchant"


@dataclass(frozen=True)
class Ad:
    venue: str
    ad_id: str
    side: Side
    asset: str
    fiat: str
    price: Decimal  # fiat por unidad de activo
    available_qty: Decimal  # activo anunciado disponible (liquidez ANUNCIADA, no ejecutada)
    min_fiat: Decimal  # mínimo por operación
    max_fiat: Decimal  # máximo por operación
    payment_methods: tuple[str, ...]
    advertiser: Advertiser
    classify: str | None = None
    pay_time_limit_min: int | None = None

    @property
    def available_fiat(self) -> Decimal:
        return self.price * self.available_qty

    @property
    def max_fiat_effective(self) -> Decimal:
        """El máximo real por operación nunca supera lo que queda disponible."""
        return min(self.max_fiat, self.available_fiat)

    def accepts_amount(self, amount_fiat: Decimal) -> bool:
        return self.min_fiat <= amount_fiat <= self.max_fiat_effective


@dataclass(frozen=True)
class RejectedAd:
    ad_id: str | None
    reason: str


@dataclass
class MarketSnapshot:
    venue: str
    asset: str
    fiat: str
    side: Side
    taken_at: datetime
    ads: list[Ad]
    source: str  # endpoint usado
    reported_total: int | None = None  # total de anuncios que informa el exchange
    complete: bool = True  # False si no se pudo recorrer todo el libro
    rejected: list[RejectedAd] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
