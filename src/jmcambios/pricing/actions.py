"""Qué hacer ahora con cada anuncio: subir, bajar o mantener el precio (solo sugerencia; el precio lo cambia la persona).

Orden de prioridad por anuncio en línea:
1. Regala margen: está más allá del siguiente competidor → acercarse a él (sigue de primero ganando más).
2. Regala en órdenes chicas: entre quienes atienden una orden de tu MÍNIMO con tus métodos, quedas primero por más
   de la tolerancia → acercarte al siguiente de ese grupo (ahí entran las órdenes chicas).
3. Lejos del escenario objetivo ("tu puesto" si lo elegiste; si no, el equilibrado) → ir a ese precio, sin pasar
   el tope del punto 2.
4. Si no, mantener. La escalera (cuánto tardan en llenarse las órdenes) se muestra como nota, no mueve el precio,
   para no pelear con el equilibrado ciclo a ciclo.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from jmcambios.analysis.competition import AdPosition
from jmcambios.domain import Ad
from jmcambios.domain.account import MyAd, OrderSide
from jmcambios.pricing.engine import CUSTOM, PricePlan

TOLERANCE = Decimal("1")  # COP de diferencia con lo sugerido antes de pedir un cambio
STEP = Decimal("0.01")


@dataclass(frozen=True)
class AdAction:
    side: str  # "BUY" (tu anuncio de compra) / "SELL" (tu anuncio de venta)
    ad_id: str
    online: bool
    price: Decimal
    move: str  # "subir" / "bajar" / "mantener" / "fuera de línea"
    to: Decimal | None
    reason: str
    rank: int | None = None
    total: int | None = None
    note: str = ""
    small_rank: int | None = None  # puesto entre quienes atienden una orden de tu mínimo con tus métodos
    small_total: int | None = None

    @property
    def delta(self) -> Decimal | None:
        return None if self.to is None else self.to - self.price


def _money(v: Decimal) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def best_at_min(ad: MyAd, book: list[Ad], exclude_users: set[str] = frozenset()) -> Decimal | None:
    """Mejor precio de quienes atienden una orden del monto MÍNIMO de mi anuncio con alguno de mis métodos
    (lo que ve un cliente que quiere hacer una orden chica)."""
    mine = set(ad.payment_methods)
    pool = [a.price for a in book if a.advertiser.user_id not in exclude_users and a.accepts_amount(ad.min_fiat)
            and mine & set(a.payment_methods)]
    if not pool:
        return None
    return max(pool) if ad.side is OrderSide.BUY else min(pool)


def rank_at_min(ad: MyAd, book: list[Ad], exclude_users: set[str] = frozenset()) -> tuple[int, int] | None:
    """(puesto, total) entre quienes atienden una orden del monto MÍNIMO de mi anuncio con alguno de mis métodos:
    lo que ve un cliente que filtra por ese monto y por mis bancos."""
    mine = set(ad.payment_methods)
    pool = [a for a in book if a.ad_id != ad.ad_id and a.advertiser.user_id not in exclude_users
            and a.accepts_amount(ad.min_fiat) and mine & set(a.payment_methods)]
    better = [a for a in pool if (a.price > ad.price if ad.side is OrderSide.BUY else a.price < ad.price)]
    return len(better) + 1, len(pool) + 1


def ad_actions(positions: list[AdPosition], plan: PricePlan | None, ladder_steps=(),
               tolerance: Decimal = TOLERANCE, books: dict[str, list[Ad]] | None = None,
               exclude_users: set[str] = frozenset()) -> list[AdAction]:
    scen = plan.scenarios if plan else []
    bal = next((s for s in scen if s.name == CUSTOM), None) or next((s for s in scen if s.name == "equilibrado"), None)
    label = "tu puesto" if bal is not None and bal.name == CUSTOM else "equilibrado"
    notes = {getattr(st, "side", None): st for st in ladder_steps}
    out = []
    for p in sorted(positions, key=lambda x: x.ad.side is not OrderSide.BUY):
        ad = p.ad
        buying = ad.side is OrderSide.BUY
        rs = rank_at_min(ad, books.get(ad.side.value, []), exclude_users) if books else None
        base = dict(side=ad.side.value, ad_id=ad.ad_id[-6:], online=ad.online, price=ad.price,
                    rank=p.estimated_rank, total=p.total_competitors + 1,
                    small_rank=rs[0] if rs else None, small_total=rs[1] if rs else None)
        if not ad.online:
            out.append(AdAction(**base, move="fuera de línea", to=None, reason="El anuncio está fuera de línea."))
            continue
        st = notes.get(ad.side.value)
        note = f"Escalera: {st.reason}" if st is not None and getattr(st, "reason", "") else ""
        # 1. Regala margen: está mejor que el siguiente por más de la tolerancia.
        if p.gap_to_best is not None and p.gap_to_best <= -tolerance and p.best_price is not None:
            to = p.best_price + STEP if buying else p.best_price - STEP
            out.append(AdAction(**base, move="bajar" if buying else "subir", to=to, note=note,
                                reason=f"Regalas {_money(-p.gap_to_best)} COP: con {_money(to)} sigues de primero ganando más."))
            continue
        # 2. Órdenes chicas: tope para no regalar donde entran las órdenes de tu mínimo.
        small = best_at_min(ad, books.get(ad.side.value, []), exclude_users) if books else None
        cap = None if small is None else (small + STEP if buying else small - STEP)
        if cap is not None and ((ad.price - cap >= tolerance) if buying else (cap - ad.price >= tolerance)):
            out.append(AdAction(**base, move="bajar" if buying else "subir", to=cap, note=note,
                                reason=f"En órdenes de tu mínimo ({_money(ad.min_fiat)} COP) quedas primero por "
                                       f"{_money(abs(ad.price - cap))} COP: con {_money(cap)} sigues de primero en esas órdenes."))
            continue
        if bal is None:
            out.append(AdAction(**base, move="mantener", to=None, note=note, reason="Sin escenario calculado todavía."))
            continue
        target = (bal.buy if buying else bal.sell).price
        capped = cap is not None and (target > cap if buying else target < cap)
        if capped:
            target = cap  # más allá no ganas órdenes chicas: solo regalas margen
        diff = target - ad.price
        if abs(diff) < tolerance:
            out.append(AdAction(**base, move="mantener", to=None, note=note,
                                reason=f"Estás en el precio de {label} (≈ #{(bal.buy if buying else bal.sell).rank_compatible} entre compatibles)."))
            continue
        move = "subir" if diff > 0 else "bajar"
        behind = (diff > 0) if buying else (diff < 0)  # compra más baja / venta más alta que lo sugerido = quedaste atrás
        sp = bal.buy if buying else bal.sell
        reason = (f"Con {_money(target)} quedas primero en órdenes de tu mínimo ({_money(ad.min_fiat)} COP); "
                  f"más arriba solo regalarías margen." if capped and behind else
                  f"Quedaste atrás (puesto #{p.estimated_rank}): con {_money(target)} vuelves a ≈ #{sp.rank_compatible} entre compatibles."
                  if behind else
                  f"Ganas menos de lo necesario: con {_money(target)} sigues ≈ #{sp.rank_compatible} y recuperas margen "
                  f"(margen del ciclo {_money(bal.margin * 100)} %).")
        out.append(AdAction(**base, move=move, to=target, reason=reason, note=note))
    return out


def _where(a: AdAction) -> str:
    if a.small_rank is None:
        return ""
    return f" · #{a.small_rank} de {a.small_total} en órdenes de tu mínimo con tus métodos (#{a.rank} en todo el mercado)"


def console_line(a: AdAction) -> str:
    kind = "COMPRA" if a.side == "BUY" else "VENTA"
    if a.move in ("subir", "bajar"):
        arrow = "⬆ SUBE" if a.move == "subir" else "⬇ BAJA"
        d = a.delta
        return f"  ➜ {kind}: {arrow} tu precio a {_money(a.to)} (ahora {_money(a.price)}, {'+' if d > 0 else ''}{_money(d)}){_where(a)} · {a.reason}"
    if a.move == "mantener":
        return f"  ✓ {kind}: mantén {_money(a.price)}{_where(a)} · {a.reason}"
    if a.small_rank is not None:
        return f"  · {kind}: fuera de línea · si lo activas a {_money(a.price)} quedarías #{a.small_rank} de {a.small_total} en órdenes de tu mínimo (#{a.rank} en todo el mercado)"
    return f"  · {kind}: fuera de línea"
