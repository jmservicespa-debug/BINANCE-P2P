"""Análisis de cruces de precio (mejor venta < mejor compra).

Un cruce solo es aprovechable si YO puedo: pagarle al vendedor con un método que
tengo (al menor 4x1000 posible), recibir del comprador en un método que tengo, y
mover una cantidad que encaje en los límites de ambos anuncios.

La comisión de tomador (taker) es un parámetro por lado. Valores por defecto
observados en las órdenes reales del usuario (2026-10-19): ~0,047 % al comprar y
~0,162 % al vender, cobrada en USDT.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

from jmcambios.domain import Ad

# Costo del 4x1000 por método con el que YO pago (informado por el usuario, verificado en extractos).
DEFAULT_MY_METHODS: dict[str, Decimal] = {
    "DaviviendaSA": Decimal("0"),
    "Daviplata": Decimal("0"),
    "BancolombiaSA": Decimal("0.004"),
    "Nequi": Decimal("0.004"),
}


def parse_my_methods(text: str | None) -> dict[str, Decimal]:
    """`"DaviviendaSA:0,Nequi:0.004"` → {método: tasa 4x1000}. Vacío → valores por defecto."""
    if not text or not text.strip():
        return dict(DEFAULT_MY_METHODS)
    out: dict[str, Decimal] = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        name, _, rate = part.partition(":")
        out[name.strip()] = Decimal(rate.strip() or "0.004")
    return out


@dataclass(frozen=True)
class CrossOpportunity:
    buy_ad: Ad  # anuncio de venta donde compro
    sell_ad: Ad  # anuncio de compra donde vendo
    pay_method: str  # con qué le pago al vendedor
    receive_method: str  # por dónde me paga el comprador
    gmf_rate: Decimal
    min_qty: Decimal
    max_qty: Decimal
    gross_per_unit: Decimal
    net_per_unit: Decimal

    @property
    def net_pct(self) -> Decimal:
        return self.net_per_unit / self.buy_ad.price * 100

    @property
    def net_total_max(self) -> Decimal:
        return self.net_per_unit * self.max_qty


@dataclass
class CrossReport:
    crossed: bool
    gross_spread: Decimal | None = None  # mejor compra − mejor venta (positivo si hay cruce)
    pairs_checked: int = 0
    best: CrossOpportunity | None = None  # la de mayor ganancia neta total
    executable_profitable: int = 0
    rejected: dict[str, int] = field(default_factory=dict)

    @property
    def executable(self) -> bool:
        return self.best is not None and self.best.net_per_unit > 0


def analyze(
    asks: list[Ad],
    bids: list[Ad],
    my_methods: dict[str, Decimal] | None = None,
    *,
    taker_fee_buy: Decimal = Decimal("0.00047"),
    taker_fee_sell: Decimal = Decimal("0.00162"),
    max_pairs: int = 400,
) -> CrossReport:
    methods = my_methods if my_methods is not None else DEFAULT_MY_METHODS
    if not asks or not bids:
        return CrossReport(crossed=False)
    asks_sorted = sorted(asks, key=lambda a: a.price)
    bids_sorted = sorted(bids, key=lambda b: b.price, reverse=True)
    best_ask, best_bid = asks_sorted[0].price, bids_sorted[0].price
    report = CrossReport(crossed=best_ask < best_bid, gross_spread=best_bid - best_ask)
    if not report.crossed:
        return report

    rejected: Counter[str] = Counter()
    for a in asks_sorted:
        if a.price >= best_bid:
            break
        for b in bids_sorted:
            if b.price <= a.price:
                break
            report.pairs_checked += 1
            if report.pairs_checked > max_pairs:
                break
            pay_options = [(methods[m], m) for m in a.payment_methods if m in methods]
            if not pay_options:
                rejected["no puedo pagarle al vendedor con mis métodos"] += 1
                continue
            receive = next((m for m in b.payment_methods if m in methods), None)
            if receive is None:
                rejected["el comprador no paga a ninguno de mis métodos"] += 1
                continue
            lo = max(a.min_fiat / a.price, b.min_fiat / b.price)
            hi = min(a.max_fiat_effective / a.price, b.max_fiat_effective / b.price)
            if lo > hi:
                rejected["montos incompatibles entre los dos anuncios"] += 1
                continue
            gmf, pay = min(pay_options)
            gross = b.price - a.price
            fees = a.price * gmf + a.price * taker_fee_buy + b.price * taker_fee_sell
            net = gross - fees
            opp = CrossOpportunity(a, b, pay, receive, gmf, lo, hi, gross, net)
            if net <= 0:
                rejected["el 4x1000/comisiones se comen el margen"] += 1
            else:
                report.executable_profitable += 1
            if report.best is None or opp.net_total_max > report.best.net_total_max:
                report.best = opp
        if report.pairs_checked > max_pairs:
            break
    report.rejected = dict(rejected)
    return report
