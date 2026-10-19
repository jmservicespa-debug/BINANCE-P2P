"""Resumen del día y control del tope exento de 4x1000 (Fase 6, ampliación).

- Ganancia de HOY (hora Colombia) frente a la meta diaria: beneficio REALIZADO
  con costo promedio, contando el inventario comprado desde `start`.
- Inventario parado: USDT comprados y aún sin vender, y desde cuándo.
- Tope exento: suma de lo PAGADO este mes en compras P2P por métodos de las
  cuentas exentas. Es una ESTIMACIÓN: Binance no dice desde qué cuenta pagaste
  (se supone la de la misma entidad) y no ve otros débitos de esas cuentas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from jmcambios.domain.account import Order, OrderSide
from jmcambios.profitability.calculator import calculate
from jmcambios.profitability.costs import CostConfig, method_identifier

COT = timezone(timedelta(hours=-5), "COT")
ZERO = Decimal(0)
DUST = Decimal("0.5")  # USDT: por debajo se considera inventario vacío


@dataclass
class TodaySummary:
    day: date
    goal: Decimal
    realized: Decimal = ZERO
    buys: int = 0
    sells: int = 0
    bought_fiat: Decimal = ZERO
    sold_fiat: Decimal = ZERO
    inventory_qty: Decimal = ZERO
    inventory_avg_cost: Decimal | None = None
    inventory_since: datetime | None = None  # desde cuándo hay inventario sin vender
    warnings: list[str] = field(default_factory=list)

    @property
    def progress(self) -> Decimal:
        return self.realized / self.goal if self.goal else ZERO


def _start_of_day(now: datetime) -> datetime:
    local = now.astimezone(COT)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def today_summary(orders: list[Order], cfg: CostConfig, *, fiat: str, asset: str, now: datetime,
                  start: datetime | None, goal: Decimal) -> TodaySummary:
    begin = start or (now - timedelta(days=30))
    rep = calculate(orders, cfg, fiat=fiat, asset=asset, start=begin, end=now)
    today = now.astimezone(COT).date()
    out = TodaySummary(day=today, goal=goal, inventory_qty=rep.inventory_qty, inventory_avg_cost=rep.inventory_avg_cost)
    for d in rep.by_day:
        if d.day == today:
            out.realized, out.buys, out.sells = d.realized, d.buys, d.sells
            out.bought_fiat, out.sold_fiat = d.bought_fiat, d.sold_fiat
    # Desde cuándo el inventario no vuelve a cero (aprox. por cantidades).
    qty = ZERO
    for o in sorted(orders, key=lambda x: (x.created_at, x.order_id)):
        if o.fiat != fiat or o.asset != asset or not o.completed or o.created_at < begin or o.created_at >= now:
            continue
        comm = o.commission or ZERO
        before = qty
        qty = qty + (o.qty - comm) if o.side is OrderSide.BUY else max(ZERO, qty - o.qty - comm)
        if before <= DUST < qty:
            out.inventory_since = o.created_at
        elif qty <= DUST:
            out.inventory_since = None
    if rep.unmatched_sold_qty > 0:
        out.warnings.append("hay ventas sin compra registrada en el periodo: no cuentan como ganancia "
                            "(fija JMC_INICIO_COMERCIANTE con la fecha en que empezaste como comerciante COP)")
    return out


@dataclass
class ExemptUsage:
    month: str  # AAAA-MM (hora Colombia)
    cap: Decimal
    used: Decimal
    orders: int
    accounts: tuple[str, ...]

    @property
    def remaining(self) -> Decimal:
        return max(ZERO, self.cap - self.used)

    @property
    def ratio(self) -> Decimal:
        return self.used / self.cap if self.cap else ZERO

    @property
    def exceeded(self) -> bool:
        return self.used >= self.cap


def exempt_usage(orders: list[Order], *, fiat: str, now: datetime, cap: Decimal, accounts: tuple[str, ...]) -> ExemptUsage:
    local = now.astimezone(COT)
    month_start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used, n = ZERO, 0
    for o in orders:
        if (o.fiat == fiat and o.side is OrderSide.BUY and o.completed and month_start <= o.created_at <= now
                and method_identifier(o.pay_method) in accounts):
            used += o.total_fiat
            n += 1
    return ExemptUsage(month=f"{local:%Y-%m}", cap=cap, used=used, orders=n, accounts=accounts)


def exempt_accounts(cfg: CostConfig, explicit: str | None) -> tuple[str, ...]:
    """Cuentas que comparten el tope: las indicadas o, si no, las configuradas con 4x1000 = 0."""
    if explicit:
        return tuple(a.strip() for a in explicit.split(",") if a.strip())
    return tuple(k for k, v in cfg.gmf_by_account.items() if v == 0)
