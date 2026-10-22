"""Mejor precio REAL: el primer precio del libro con plata suficiente detrás (filtro anti-carnada).

Algunos anuncios se ponen arriba del todo con muy poca plata (o casi sin USDT) para mover la referencia de
"mejor precio" y que los demás los persigan; en la práctica no atienden una operación normal. Recorriendo el
libro desde el mejor precio y sumando la plata disponible de cada anuncio, el mejor precio real es aquel en el
que lo acumulado llega a `min_liquidity` COP: hasta ahí sí se podría mover ese monto. Los anuncios que quedan
por delante con poca plata se marcan como posible carnada (es una estimación: no se ve si de verdad operan).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from jmcambios.domain import Ad, Side

MIN_LIQUIDITY = Decimal("2000000")  # COP acumulados que debe haber hasta el precio para considerarlo real
MIN_GAP = Decimal("0.002")  # menos de 0,2 % entre el primero y el real = mercado normal, no carnada
ZERO = Decimal("0")


@dataclass(frozen=True)
class RealBest:
    best: Decimal | None  # primer precio del libro (el que muestra Binance)
    price: Decimal | None  # mejor precio real (None = todo el libro junto no llega al monto)
    min_liquidity: Decimal
    bait: list[Ad] = field(default_factory=list)  # anuncios por delante del precio real, con poca plata

    @property
    def bait_fiat(self) -> Decimal:
        return sum((a.available_fiat for a in self.bait), ZERO)

    @property
    def distorted(self) -> bool:
        """Hay anuncios con poca plata arriba Y quedan lejos (≥ 0,2 %) del precio real: posible carnada."""
        if not self.bait or self.price is None or self.best is None:
            return False
        return abs(self.best - self.price) >= self.price * MIN_GAP


def real_best(side: Side, ads: list[Ad], *, min_liquidity: Decimal = MIN_LIQUIDITY,
              exclude_users: set[str] = frozenset()) -> RealBest:
    """`side` = lado del libro: ASK (vendedores, el mejor es el más barato) o BID (compradores, el más caro)."""
    pool = sorted((a for a in ads if a.advertiser.user_id not in exclude_users),
                  key=lambda a: a.price, reverse=(side is Side.BID))
    if not pool:
        return RealBest(None, None, min_liquidity)
    acc = ZERO
    for i, a in enumerate(pool):
        acc += a.available_fiat
        if acc >= min_liquidity:
            return RealBest(pool[0].price, a.price, min_liquidity, [b for b in pool[:i] if b.price != a.price])
    return RealBest(pool[0].price, None, min_liquidity)


def describe(r: RealBest, money) -> str:
    """Una línea para consola y panel."""
    if r.price is None:
        return f"todo el libro junto no suma {money(r.min_liquidity, 0)} COP: no hay precio real confiable"
    if not r.bait:
        return f"{money(r.price)} (el primero ya tiene plata detrás)"
    if not r.distorted:
        return f"{money(r.price)} (casi igual al primero, {money(r.best)}: sin carnada)"
    n = len(r.bait)
    return (f"{money(r.price)} · {n} anuncio{'s' if n != 1 else ''} por delante con solo {money(r.bait_fiat, 0)} COP "
            f"en total (posible carnada, desde {money(r.best)})")
