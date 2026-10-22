"""Capital de trabajo: cuántos pesos y USDT quedan según las órdenes completadas desde que se fijó el capital inicial.

Solo ve las órdenes de Binance: movimientos por fuera (retiros, traspasos entre bancos, 4x1000, comisiones del banco)
no aparecen y hay que corregirlos volviendo a fijar el capital.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal

from jmcambios.domain.account import Order, OrderSide

HEAVY = Decimal("0.65")  # más de 65 % del capital en un lado = cargado de ese lado
SPLIT = 3  # máximo por orden = lo disponible ÷ 3 (alcanza para al menos 3 órdenes)
ROUND = Decimal("10000")
LOW_COP = Decimal("100000")


@dataclass
class CapitalView:
    cop: Decimal
    usdt: Decimal
    price: Decimal | None  # COP por USDT usado para valorizar
    cop_share: Decimal | None  # parte del capital en pesos (0–1)
    status: str  # "pesos" / "usdt" / "equilibrado" / "sin precio"
    max_buy_order: Decimal  # COP por orden en tu anuncio de compra
    max_sell_order: Decimal  # COP por orden en tu anuncio de venta
    buys: int = 0
    sells: int = 0
    advice: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _down(v: Decimal) -> Decimal:
    """Redondea hacia abajo a decenas de miles (los límites de anuncio se escriben así)."""
    return (max(v, Decimal("0")) / ROUND).to_integral_value(ROUND_DOWN) * ROUND


def _fmt(v: Decimal, d: int = 0) -> str:
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def capital(cop0: Decimal, usdt0: Decimal, orders: list[Order], since_ts: int, price: Decimal | None) -> CapitalView:
    cop, usdt, buys, sells = cop0, usdt0, 0, 0
    for o in orders:
        if not o.completed or o.created_at.timestamp() < since_ts:
            continue
        fee = o.commission or Decimal("0")
        if o.side is OrderSide.BUY:  # compré USDT: pagué pesos
            cop -= o.total_fiat
            usdt += o.qty - fee
            buys += 1
        else:  # vendí USDT: recibí pesos
            cop += o.total_fiat
            usdt -= o.qty + fee
            sells += 1
    v = CapitalView(cop=cop, usdt=usdt, price=price, cop_share=None, status="sin precio",
                    max_buy_order=_down(cop / SPLIT),
                    max_sell_order=Decimal("0"), buys=buys, sells=sells)
    if cop < 0 or usdt < 0:
        v.warnings.append("Saldo negativo: revisa el capital inicial o si moviste plata por fuera de Binance.")
    if price is None or price <= 0:
        return v
    usdt_cop = max(usdt, Decimal("0")) * price
    total = max(cop, Decimal("0")) + usdt_cop
    v.max_sell_order = _down(usdt_cop / SPLIT)
    if total <= 0:
        v.status = "equilibrado"
        return v
    v.cop_share = max(cop, Decimal("0")) / total
    if v.cop_share > HEAVY:
        v.status = "pesos"
        v.advice.append(f"Estás cargado de pesos ({_fmt(v.cop_share * 100)} %): prioriza COMPRAR USDT. "
                        "Pon la compra más competitiva (agresivo) y la venta más tranquila (conservador).")
    elif v.cop_share < 1 - HEAVY:
        v.status = "usdt"
        v.advice.append(f"Estás cargado de USDT ({_fmt((1 - v.cop_share) * 100)} %): prioriza VENDER. "
                        "Pon la venta más competitiva (agresivo) y la compra más tranquila (conservador).")
    else:
        v.status = "equilibrado"
        v.advice.append("Balance sano entre pesos y USDT: usa el equilibrado en los dos lados.")
    v.advice.append(f"Máximo por orden para atender al menos {SPLIT} órdenes: compra {_fmt(v.max_buy_order)} COP · "
                    f"venta {_fmt(v.max_sell_order)} COP.")
    if cop < LOW_COP:
        v.advice.append("Te quedan pocos pesos: baja el máximo de tu anuncio de compra o ponlo fuera de línea.")
    if usdt_cop < LOW_COP:
        v.advice.append("Te quedan pocos USDT: baja el máximo de tu anuncio de venta o ponlo fuera de línea.")
    return v
