"""Bitácora de órdenes y escalera de margen (prueba real).

Bitácora: cada orden que entra por MIS anuncios queda con lo que tenía el anuncio
en ese momento (precio, puesto, montos) y cuánto TARDÓ en llenarse: tiempo desde
el último cambio de precio, la última vez que el anuncio se puso en línea o la
orden anterior del mismo lado (lo más reciente).

Escalera: si el anuncio se llena rápido, el mercado aguanta más margen → subir un
escalón; si lleva mucho tiempo quieto → bajar uno. Cada lado se mide por separado.

Procedencia:
- OBSERVADO: órdenes y anuncios propios (API de Binance).
- CÁLCULO: tiempos, puesto, margen del par compra/venta con tus costos.
- El registro de anuncios se toma cada vez que el monitor los lee (cada ~5 min):
  un cambio de precio puede detectarse hasta ese tiempo tarde.

Solo sugiere. Nunca cambia precios ni toca órdenes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from jmcambios.domain.account import Order

TICK = Decimal("0.01")
CANCELLED = ("CANCELLED", "CANCELLED_BY_SYSTEM", "6", "7")
RANK_BUCKETS = ((1, 1, "#1"), (2, 3, "#2–3"), (4, 8, "#4–8"), (9, 20, "#9–20"), (21, 10**9, "#21 o más"))


@dataclass(frozen=True)
class LadderRules:
    fast_s: int = 20 * 60  # se llenó en menos de esto → subir margen
    slow_s: int = 60 * 60  # quieto más que esto → bajar margen
    step: Decimal = Decimal("0.001")  # 0,1 punto de margen ≈ 0,1 % del precio


@dataclass(frozen=True)
class Fill:
    order_id: str
    side: str  # BUY / SELL desde mi punto de vista (= lado de mi anuncio)
    ts: int
    price: Decimal
    qty: Decimal
    total_fiat: Decimal
    status: str
    wait_s: int | None  # None = no hay registro del anuncio antes de la orden
    rank: int | None
    total: int | None
    min_fiat: float | None
    max_fiat: float | None
    pair_margin: Decimal | None  # margen del ciclo con mi anuncio del otro lado en ese momento


@dataclass(frozen=True)
class Step:
    side: str
    action: str  # subir / mantener / bajar
    reason: str
    price: Decimal
    suggested: Decimal | None
    waiting_s: int
    last_wait_s: int | None
    margin_now: Decimal | None
    margin_after: Decimal | None
    since_ts: int  # desde cuándo cuenta la espera (sirve de clave de la alerta)
    below_min: bool = False  # el precio sugerido deja el par por debajo de tu margen mínimo


def _resets(rows: list[dict]) -> list[int]:
    """Momentos en que el anuncio "vuelve a empezar": primer registro, cambio de precio o vuelta a en línea."""
    out, prev = [], None
    for r in rows:
        if prev is None or r["price"] != prev["price"] or (r["online"] and not prev["online"]):
            out.append(r["ts"])
        prev = r
    return out


def _last_before(rows: list[dict], ts: int) -> dict | None:
    found = None
    for r in rows:
        if r["ts"] > ts:
            break
        found = r
    return found


def _by_side(log: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(log, key=lambda r: r["ts"]):
        out[r["side"]].append(r)
    return out


def _pair_margin(buy: Decimal | float | None, sell: Decimal | float | None, costs) -> Decimal | None:
    if buy is None or sell is None or costs is None:
        return None
    from jmcambios.pricing.engine import cycle_margin

    return cycle_margin(Decimal(str(buy)), Decimal(str(sell)), costs)


def is_mine(o: Order, my_ad_ids: set[str]) -> bool:
    return (o.role or "").upper() == "MAKER" or (o.ad_id is not None and o.ad_id in my_ad_ids)


def fills(orders: list[Order], log: list[dict], costs=None, *, since_ts: int = 0) -> list[Fill]:
    """Órdenes que entraron por mis anuncios (sin las canceladas), con el contexto del anuncio."""
    sides = _by_side(log)
    resets = {s: _resets(rows) for s, rows in sides.items()}
    ad_ids = {r["ad_id"] for r in log}
    mine = sorted((o for o in orders if is_mine(o, ad_ids) and o.status.upper() not in CANCELLED),
                  key=lambda o: o.created_at)
    last_fill: dict[str, int] = {}
    out = []
    for o in mine:
        side, ts = o.side.value, int(o.created_at.timestamp())
        rows = sides.get(side, [])
        starts = [t for t in resets.get(side, []) if t <= ts]
        anchor = max(starts[-1:] + ([last_fill[side]] if side in last_fill else []), default=None)
        last_fill[side] = ts
        if ts < since_ts:
            continue
        here = _last_before(rows, ts)
        other = _last_before(sides.get("SELL" if side == "BUY" else "BUY", []), ts)
        other_price = other["price"] if other and other["online"] else None
        buy, sell = (o.unit_price, other_price) if side == "BUY" else (other_price, o.unit_price)
        out.append(Fill(
            order_id=o.order_id, side=side, ts=ts, price=o.unit_price, qty=o.qty, total_fiat=o.total_fiat,
            status=o.status, wait_s=None if anchor is None else ts - anchor,
            rank=here["rank"] if here else None, total=here["total"] if here else None,
            min_fiat=here["min_fiat"] if here else None, max_fiat=here["max_fiat"] if here else None,
            pair_margin=_pair_margin(buy, sell, costs),
        ))
    return out


def suggest(log: list[dict], all_fills: list[Fill], now_ts: int, costs=None,
            rules: LadderRules = LadderRules()) -> list[Step]:
    """Un escalón por lado para los anuncios en línea."""
    sides = _by_side(log)
    out = []
    for side in ("BUY", "SELL"):
        rows = sides.get(side, [])
        if not rows or not rows[-1]["online"]:
            continue
        cur = rows[-1]
        price = Decimal(str(cur["price"]))
        reset = _resets(rows)[-1]
        side_fills = [f for f in all_fills if f.side == side]
        after = [f for f in side_fills if f.ts >= reset]
        since = max([reset] + [f.ts for f in side_fills])
        waiting = max(0, now_ts - since)
        last_wait = after[-1].wait_s if after else None
        other = sides.get("SELL" if side == "BUY" else "BUY", [])
        other_price = other[-1]["price"] if other and other[-1]["online"] else None

        def margin(p: Decimal) -> Decimal | None:
            return _pair_margin(p, other_price, costs) if side == "BUY" else _pair_margin(other_price, p, costs)

        up = Decimal(1) - rules.step if side == "BUY" else Decimal(1) + rules.step  # más margen
        down = Decimal(1) + rules.step if side == "BUY" else Decimal(1) - rules.step
        if waiting >= rules.slow_s:
            action, new = "bajar", (price * down).quantize(TICK)
            reason = f"lleva {duration(waiting)} sin órdenes"
        elif last_wait is not None and last_wait < rules.fast_s:
            action, new = "subir", (price * up).quantize(TICK)
            reason = f"la última orden se llenó en {duration(last_wait)}"
        else:
            action, new = "mantener", None
            reason = (f"la última orden tardó {duration(last_wait)}" if last_wait is not None
                      else f"esperando la primera orden a este precio ({duration(waiting)})")
        after_m = margin(new) if new is not None else None
        out.append(Step(side=side, action=action, reason=reason, price=price, suggested=new, waiting_s=waiting,
                        last_wait_s=last_wait, margin_now=margin(price), margin_after=after_m, since_ts=since,
                        below_min=after_m is not None and after_m < costs.min_margin))
    return out


def by_rank(all_fills: list[Fill]) -> list[dict]:
    """Resumen de la bitácora por lado y puesto: cuántas órdenes, cuánto tardaron, con qué margen."""
    groups: dict[tuple[str, str], list[Fill]] = defaultdict(list)
    for f in all_fills:
        if f.rank is None:
            label = "sin registro"
        else:
            label = next(name for lo, hi, name in RANK_BUCKETS if lo <= f.rank <= hi)
        groups[(f.side, label)].append(f)
    order = {name: i for i, (_, _, name) in enumerate(RANK_BUCKETS)}
    out = []
    for (side, label), fs in sorted(groups.items(), key=lambda kv: (kv[0][0], order.get(kv[0][1], 99))):
        waits = [f.wait_s for f in fs if f.wait_s is not None]
        margins = [f.pair_margin for f in fs if f.pair_margin is not None]
        out.append({
            "side": side, "rank": label, "orders": len(fs), "fiat": float(sum(f.total_fiat for f in fs)),
            "median_wait_s": int(median(waits)) if waits else None,
            "median_margin": float(median(margins)) if margins else None,
        })
    return out


def duration(s: int | None) -> str:
    if s is None:
        return "—"
    if s < 3600:
        return f"{max(1, round(s / 60))} min"
    return f"{s // 3600} h {round(s % 3600 / 60):02d} min"
