"""Montos por orden: quién compite de verdad con un anuncio según sus límites.

En Binance el cliente busca con un monto y solo ve los anuncios cuyo rango lo
incluye. Dos anuncios compiten en la medida en que sus rangos se cruzan. El cruce
se mide en escala logarítmica: de 500 mil a 1 M pesa lo mismo que de 5 M a 10 M,
porque así se reparten los montos de los clientes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from jmcambios.domain import Ad, Side

MIN_OVERLAP = 0.5  # un competidor directo cubre al menos la mitad de tu rango

# Tramos de monto (COP) para ver dónde hay menos competencia.
TRANCHES: tuple[tuple[str, Decimal, Decimal | None], ...] = (
    ("< 500 mil", Decimal("0"), Decimal("500000")),
    ("500 mil – 2 M", Decimal("500000"), Decimal("2000000")),
    ("2 – 5 M", Decimal("2000000"), Decimal("5000000")),
    ("5 – 10 M", Decimal("5000000"), Decimal("10000000")),
    ("> 10 M", Decimal("10000000"), None),
)


def overlap_fraction(lo: Decimal, hi: Decimal, other_lo: Decimal, other_hi: Decimal) -> float:
    """Parte de [lo, hi] que también cubre [other_lo, other_hi] (0..1, escala logarítmica)."""
    a, b = max(lo, other_lo), min(hi, other_hi)
    if a > b:
        return 0.0
    lo_f, hi_f = float(max(lo, Decimal(1))), float(max(hi, Decimal(1)))
    if hi_f <= lo_f * 1.0001:  # rango de un solo monto
        return 1.0
    a_f, b_f = float(max(a, Decimal(1))), float(max(b, Decimal(1)))
    return max(0.0, min(1.0, (math.log(b_f) - math.log(a_f)) / (math.log(hi_f) - math.log(lo_f))))


def competes(lo: Decimal, hi: Decimal, ad: Ad, min_overlap: float = MIN_OVERLAP) -> bool:
    return overlap_fraction(lo, hi, ad.min_fiat, ad.max_fiat_effective) >= min_overlap


def _better(side: Side, price: Decimal, mine: Decimal) -> bool:
    return price > mine if side is Side.BID else price < mine


@dataclass(frozen=True)
class TrancheView:
    label: str
    lo: Decimal
    hi: Decimal | None
    ads: int
    best_price: Decimal | None
    qty: Decimal  # liquidez anunciada que atiende el tramo
    my_rank: int | None  # puesto con mi precio en este tramo (None si no hay precio)


def tranche_views(side: Side, ads: list[Ad], methods: tuple[str, ...] | None = None,
                  my_price: Decimal | None = None) -> list[TrancheView]:
    """Competencia por tramo: anuncios que aceptan algún monto del tramo (y comparten método, si se da)."""
    out = []
    for label, lo, hi in TRANCHES:
        top = hi if hi is not None else Decimal("1e12")
        pool = [a for a in ads if a.min_fiat < top and a.max_fiat_effective > lo  # tocar solo el borde no cuenta
                and (not methods or set(methods) & set(a.payment_methods))]
        prices = [a.price for a in pool]
        best = (max(prices) if side is Side.BID else min(prices)) if prices else None
        rank = (sum(1 for a in pool if _better(side, a.price, my_price)) + 1) if my_price is not None else None
        out.append(TrancheView(label, lo, hi, len(pool), best, sum((a.available_qty for a in pool), Decimal(0)), rank))
    return out
