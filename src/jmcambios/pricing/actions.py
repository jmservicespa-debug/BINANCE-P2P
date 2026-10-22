"""Qué hacer ahora con cada anuncio: subir, bajar o mantener el precio (solo sugerencia; el precio lo cambia la persona).

Orden de prioridad por anuncio en línea:
1. Regala margen: está más allá del siguiente competidor → acercarse a él (sigue de primero ganando más).
2. Lejos del escenario equilibrado (más de la tolerancia) → ir al precio equilibrado.
3. Si no, mantener. La escalera (cuánto tardan en llenarse las órdenes) se muestra como nota, no mueve el precio,
   para no pelear con el equilibrado ciclo a ciclo.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from jmcambios.analysis.competition import AdPosition
from jmcambios.domain.account import OrderSide
from jmcambios.pricing.engine import PricePlan

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

    @property
    def delta(self) -> Decimal | None:
        return None if self.to is None else self.to - self.price


def _money(v: Decimal) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ad_actions(positions: list[AdPosition], plan: PricePlan | None, ladder_steps=(),
               tolerance: Decimal = TOLERANCE) -> list[AdAction]:
    bal = next((s for s in plan.scenarios if s.name == "equilibrado"), None) if plan else None
    notes = {getattr(st, "side", None): st for st in ladder_steps}
    out = []
    for p in sorted(positions, key=lambda x: x.ad.side is not OrderSide.BUY):
        ad = p.ad
        buying = ad.side is OrderSide.BUY
        base = dict(side=ad.side.value, ad_id=ad.ad_id[-6:], online=ad.online, price=ad.price,
                    rank=p.estimated_rank, total=p.total_competitors + 1)
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
        if bal is None:
            out.append(AdAction(**base, move="mantener", to=None, note=note, reason="Sin escenario calculado todavía."))
            continue
        target = (bal.buy if buying else bal.sell).price
        diff = target - ad.price
        if abs(diff) < tolerance:
            out.append(AdAction(**base, move="mantener", to=None, note=note,
                                reason=f"Estás en el precio del equilibrado (≈ #{(bal.buy if buying else bal.sell).rank_compatible} entre compatibles)."))
            continue
        move = "subir" if diff > 0 else "bajar"
        behind = (diff > 0) if buying else (diff < 0)  # compra más baja / venta más alta que lo sugerido = quedaste atrás
        sp = bal.buy if buying else bal.sell
        reason = (f"Quedaste atrás (puesto #{p.estimated_rank}): con {_money(target)} vuelves a ≈ #{sp.rank_compatible} entre compatibles."
                  if behind else
                  f"Ganas menos de lo necesario: con {_money(target)} sigues ≈ #{sp.rank_compatible} y recuperas margen "
                  f"(margen del ciclo {_money(bal.margin * 100)} %).")
        out.append(AdAction(**base, move=move, to=target, reason=reason, note=note))
    return out


def console_line(a: AdAction) -> str:
    kind = "COMPRA" if a.side == "BUY" else "VENTA"
    if a.move in ("subir", "bajar"):
        arrow = "⬆ SUBE" if a.move == "subir" else "⬇ BAJA"
        d = a.delta
        return f"  ➜ {kind}: {arrow} tu precio a {_money(a.to)} (ahora {_money(a.price)}, {'+' if d > 0 else ''}{_money(d)}) · {a.reason}"
    if a.move == "mantener":
        return f"  ✓ {kind}: mantén {_money(a.price)} · {a.reason}"
    return f"  · {kind}: fuera de línea"
