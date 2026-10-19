"""Analizador de competencia (módulo 4).

Ubica cada anuncio propio frente al libro actual del mismo lado y calcula los
precios límite rentables. La posición es una ESTIMACIÓN: Binance ordena también
por criterios propios, no solo por precio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median

from jmcambios.domain import Ad, Side
from jmcambios.domain.account import MyAd, OrderSide

ZERO = Decimal("0")
NEAR_BAND = Decimal("0.005")  # ±0,5 % alrededor de mi precio


def market_side_for(ad: MyAd) -> Side:
    """Mi anuncio de COMPRA compite con quienes compran (BID); el de VENTA con quienes venden (ASK)."""
    return Side.BID if ad.side is OrderSide.BUY else Side.ASK


def _better(side: Side, price: Decimal, mine: Decimal) -> bool:
    return price > mine if side is Side.BID else price < mine


@dataclass(frozen=True)
class Competitor:
    nickname: str
    price: Decimal
    qty: Decimal
    month_orders: int | None
    finish_rate: Decimal | None
    is_merchant: bool
    compatible: bool  # comparte método de pago y sus límites se cruzan con los míos


@dataclass
class AdPosition:
    ad: MyAd
    side: Side
    total_competitors: int
    estimated_rank: int  # 1 = primero
    better_count: int
    tied_count: int
    best_price: Decimal | None
    gap_to_best: Decimal | None  # cuánto me separa del primero (positivo = estoy peor)
    gap_to_best_pct: Decimal | None
    median_price: Decimal | None
    qty_ahead: Decimal  # liquidez anunciada que está por delante de mí
    compatible_ahead: int  # competidores por delante que de verdad atienden a mis mismos clientes
    near_count: int  # anuncios a ±0,5 % de mi precio
    near_qty: Decimal
    ahead: list[Competitor] = field(default_factory=list)  # los 5 más cercanos por delante
    top_active: list[Competitor] = field(default_factory=list)  # más órdenes en 30 días cerca de mí


def _compatible(mine: MyAd, other: Ad) -> bool:
    shares_method = bool(set(mine.payment_methods) & set(other.payment_methods))
    overlap = max(mine.min_fiat, other.min_fiat) <= min(mine.max_fiat, other.max_fiat_effective)
    return shares_method and overlap


def _competitor(mine: MyAd, a: Ad) -> Competitor:
    return Competitor(
        nickname=a.advertiser.nickname or a.advertiser.user_id[:8],
        price=a.price,
        qty=a.available_qty,
        month_orders=a.advertiser.month_orders,
        finish_rate=a.advertiser.month_finish_rate,
        is_merchant=a.advertiser.is_merchant,
        compatible=_compatible(mine, a),
    )


def position(mine: MyAd, market_ads: list[Ad], my_user_ids: set[str] | None = None) -> AdPosition:
    side = market_side_for(mine)
    my_user_ids = my_user_ids or set()
    others = [a for a in market_ads if a.ad_id != mine.ad_id and a.advertiser.user_id not in my_user_ids]
    better = [a for a in others if _better(side, a.price, mine.price)]
    tied = [a for a in others if a.price == mine.price]
    prices = [a.price for a in others]
    best = (max(prices) if side is Side.BID else min(prices)) if prices else None
    gap = None
    if best is not None:
        gap = (best - mine.price) if side is Side.BID else (mine.price - best)
    near = [a for a in others if abs(a.price - mine.price) <= mine.price * NEAR_BAND]
    better_sorted = sorted(better, key=lambda a: a.price, reverse=(side is Side.ASK))  # el más cercano a mí primero
    active = sorted(
        (a for a in near if a.advertiser.month_orders is not None),
        key=lambda a: a.advertiser.month_orders or 0,
        reverse=True,
    )
    return AdPosition(
        ad=mine,
        side=side,
        total_competitors=len(others),
        estimated_rank=len(better) + 1,
        better_count=len(better),
        tied_count=len(tied),
        best_price=best,
        gap_to_best=gap,
        gap_to_best_pct=(gap / best * 100) if gap is not None and best else None,
        median_price=Decimal(median(prices)) if prices else None,
        qty_ahead=sum((a.available_qty for a in better), ZERO),
        compatible_ahead=sum(1 for a in better if _compatible(mine, a)),
        near_count=len(near),
        near_qty=sum((a.available_qty for a in near), ZERO),
        ahead=[_competitor(mine, a) for a in better_sorted[:5]],
        top_active=[_competitor(mine, a) for a in active[:5]],
    )


# --------------------------------------------------------------------- precios límite
def max_profitable_buy_price(
    sell_price: Decimal, *, gmf: Decimal, buy_commission: Decimal, sell_commission: Decimal, min_margin: Decimal
) -> Decimal:
    """Precio máximo al que comprar para ganar al menos `min_margin` (fracción del precio de venta).

    Comprar 1 unidad a P_b cuesta P_b·(1+gmf) y deja (1−c_b) unidades; vender q unidades
    consume q·(1+c_s) del inventario. Margen por unidad vendida ≥ m·P_s ⇒
    P_b ≤ P_s·(1−m)·(1−c_b) / ((1+c_s)·(1+gmf)).
    """
    return sell_price * (1 - min_margin) * (1 - buy_commission) / ((1 + sell_commission) * (1 + gmf))


def min_profitable_sell_price(cost_per_unit: Decimal, *, sell_commission: Decimal, min_margin: Decimal) -> Decimal:
    """Precio mínimo de venta dado el costo efectivo por unidad en inventario: P_s ≥ C·(1+c_s)/(1−m)."""
    return cost_per_unit * (1 + sell_commission) / (1 - min_margin)
