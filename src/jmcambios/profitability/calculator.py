"""Calculadora de rentabilidad real (módulo 7).

Método: costo promedio ponderado del inventario del activo, en orden cronológico.
- COMPRA: entra (cantidad − comisión) al inventario; cuesta (total fiat + 4x1000).
- VENTA: sale (cantidad + comisión) del inventario; se recibe el total fiat.
  Solo la parte de la venta cubierta por inventario de costo CONOCIDO genera
  beneficio realizado. Lo vendido sin compra registrada (comprado antes de la
  ventana, en otra moneda o fuera de Binance) se informa aparte, nunca se inventa.

Tipos de beneficio:
- REALIZADO: ciclos cerrados con costo conocido.
- ESTIMADO: inventario restante valorado al precio de mercado que se indique.
- POTENCIAL: lo calcula el motor de precios (Fase 5); aquí no se incluye.

Supuesto a verificar con el extracto de Binance: la comisión P2P se cobra en el activo.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from jmcambios.domain.account import Order, OrderSide
from jmcambios.profitability.costs import CostConfig

COT = timezone(timedelta(hours=-5))
ZERO = Decimal("0")


@dataclass
class DayResult:
    day: date
    buys: int = 0
    sells: int = 0
    bought_fiat: Decimal = ZERO
    sold_fiat: Decimal = ZERO
    realized: Decimal = ZERO


@dataclass
class ProfitReport:
    fiat: str
    asset: str
    start: datetime | None
    end: datetime | None
    gmf_mode: str
    # Compras (OBSERVADO salvo el 4x1000)
    buys: int = 0
    bought_qty_gross: Decimal = ZERO
    bought_qty_net: Decimal = ZERO
    bought_fiat: Decimal = ZERO
    gmf: Decimal = ZERO  # ESTIMADO
    buy_commission_qty: Decimal = ZERO
    # Ventas
    sells: int = 0
    sold_qty: Decimal = ZERO
    sold_fiat: Decimal = ZERO
    sell_commission_qty: Decimal = ZERO
    # Resultado
    realized: Decimal = ZERO  # beneficio REALIZADO bruto de costos operativos
    realized_qty: Decimal = ZERO  # USDT vendidos con costo conocido
    realized_proceeds: Decimal = ZERO
    realized_cost: Decimal = ZERO
    unmatched_sold_qty: Decimal = ZERO  # vendido sin compra registrada
    unmatched_sold_fiat: Decimal = ZERO
    operating_costs: Decimal = ZERO
    inventory_qty: Decimal = ZERO
    inventory_cost: Decimal = ZERO
    commissions_missing: int = 0  # órdenes sin comisión informada
    not_completed: int = 0
    by_day: list[DayResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------- derivados
    @property
    def net_realized(self) -> Decimal:
        return self.realized - self.operating_costs

    @property
    def effective_buy_price(self) -> Decimal | None:
        """Precio efectivo de adquisición: (fiat pagado + 4x1000) / activo neto recibido."""
        return (self.bought_fiat + self.gmf) / self.bought_qty_net if self.bought_qty_net else None

    @property
    def effective_sell_price(self) -> Decimal | None:
        """Precio efectivo de venta: fiat recibido / activo entregado (incluye comisión)."""
        out = self.sold_qty + self.sell_commission_qty
        return self.sold_fiat / out if out else None

    @property
    def gross_margin_per_unit(self) -> Decimal | None:
        if not self.realized_qty:
            return None
        return (self.realized_proceeds - self.realized_cost) / self.realized_qty

    @property
    def inventory_avg_cost(self) -> Decimal | None:
        return self.inventory_cost / self.inventory_qty if self.inventory_qty > 0 else None

    @property
    def hours(self) -> Decimal | None:
        if not self.start or not self.end or self.end <= self.start:
            return None
        return Decimal(str((self.end - self.start).total_seconds() / 3600))

    def roc_pct(self, capital: Decimal | None) -> Decimal | None:
        return self.net_realized / capital * 100 if capital else None

    def turnover(self, capital: Decimal | None) -> Decimal | None:
        """Rotación = capital transaccionado en compras / capital operativo del periodo."""
        return self.bought_fiat / capital if capital else None

    def profit_per_hour(self) -> Decimal | None:
        h = self.hours
        return self.net_realized / h if h else None

    def opportunity_cost(self, capital: Decimal | None, annual_rate: Decimal | None) -> Decimal | None:
        h = self.hours
        if not capital or annual_rate is None or not h:
            return None
        return capital * annual_rate * h / Decimal(24 * 365)

    def estimated_inventory_value(self, market_bid: Decimal | None, sell_commission_rate: Decimal = ZERO) -> Decimal | None:
        """Beneficio ESTIMADO si el inventario se vendiera hoy al mejor precio de compra del mercado."""
        if market_bid is None or self.inventory_qty <= 0:
            return None
        proceeds = self.inventory_qty / (1 + sell_commission_rate) * market_bid
        return proceeds - self.inventory_cost


def calculate(
    orders: list[Order],
    cfg: CostConfig,
    *,
    fiat: str,
    asset: str = "USDT",
    start: datetime | None = None,
    end: datetime | None = None,
    gmf_mode: str = "estimado",
) -> ProfitReport:
    rep = ProfitReport(fiat=fiat, asset=asset, start=start, end=end, gmf_mode=gmf_mode)
    days: dict[date, DayResult] = defaultdict(lambda: DayResult(day=date.min))
    inv_qty, inv_cost = ZERO, ZERO

    for o in sorted(orders, key=lambda x: (x.created_at, x.order_id)):
        if o.fiat != fiat or o.asset != asset:
            continue
        if start and o.created_at < start:
            continue
        if end and o.created_at >= end:
            continue
        if not o.completed:
            rep.not_completed += 1
            continue
        comm = o.commission if o.commission is not None else ZERO
        if o.commission is None:
            rep.commissions_missing += 1
        d = o.created_at.astimezone(COT).date()
        day = days[d]
        day.day = d
        rep.operating_costs += cfg.cost_per_order

        if o.side is OrderSide.BUY:
            gmf = o.total_fiat * cfg.gmf_rate(o, gmf_mode)
            net_qty = o.qty - comm
            rep.buys += 1
            rep.bought_qty_gross += o.qty
            rep.bought_qty_net += net_qty
            rep.bought_fiat += o.total_fiat
            rep.gmf += gmf
            rep.buy_commission_qty += comm
            inv_qty += net_qty
            inv_cost += o.total_fiat + gmf
            day.buys += 1
            day.bought_fiat += o.total_fiat
        else:
            out_qty = o.qty + comm
            rep.sells += 1
            rep.sold_qty += o.qty
            rep.sold_fiat += o.total_fiat
            rep.sell_commission_qty += comm
            day.sells += 1
            day.sold_fiat += o.total_fiat
            covered = min(out_qty, inv_qty) if inv_qty > 0 else ZERO
            if covered > 0:
                avg = inv_cost / inv_qty
                cost = avg * covered
                proceeds = o.total_fiat * covered / out_qty
                profit = proceeds - cost
                rep.realized += profit
                rep.realized_qty += covered
                rep.realized_proceeds += proceeds
                rep.realized_cost += cost
                day.realized += profit
                inv_qty -= covered
                inv_cost -= cost
            if covered < out_qty:
                missing = out_qty - covered
                rep.unmatched_sold_qty += missing
                rep.unmatched_sold_fiat += o.total_fiat * missing / out_qty

    rep.inventory_qty, rep.inventory_cost = inv_qty, inv_cost
    rep.by_day = [days[k] for k in sorted(days)]
    if rep.unmatched_sold_qty > 0:
        rep.warnings.append(
            f"{rep.unmatched_sold_qty:.2f} {asset} vendidos en {fiat} no tienen compra registrada en el periodo "
            "(comprados antes, en otra moneda o fuera de Binance): no se cuentan como beneficio realizado."
        )
    if rep.commissions_missing:
        rep.warnings.append(
            f"{rep.commissions_missing} órdenes sin comisión informada por Binance: se tomaron como 0."
        )
    if rep.inventory_qty > 0 and rep.buys and not rep.sells:
        rep.warnings.append(f"Solo hubo compras en {fiat}: el inventario sigue abierto; no hay ciclo cerrado.")
    return rep
