"""Costos aplicables a cada orden (módulo 7).

Procedencia de cada costo:
- Comisión de Binance: OBSERVADA en la orden (en unidades del activo).
- 4x1000 (GMF): ESTIMADO. Binance no informa desde qué cuenta pagaste; se
  supone la cuenta de la misma entidad que el método de la orden cuando la
  tienes configurada, y si no, la tasa por defecto. Por eso el informe muestra
  también el rango mínimo/máximo posible.
- Costos operativos por orden: parámetro del usuario.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from jmcambios.analysis.crossing import DEFAULT_MY_METHODS
from jmcambios.domain.account import Order, OrderSide

# Nombre visible del método (payMethodName) → identificador de Binance.
_NAME_TO_ID = (
    ("daviplata", "Daviplata"),
    ("davivienda", "DaviviendaSA"),
    ("bancolombia", "BancolombiaSA"),
    ("nequi", "Nequi"),
    ("bre-b", "BreBKeys"),
    ("breb", "BreBKeys"),
    ("bogota", "BancodeBogota"),
    ("bbva", "BBVABank"),
    ("colpatria", "ScotiabankColpatria"),
    ("falabella", "BancoFalabella"),
    ("popular", "BancoPopular"),
    ("itau", "BancoItauColombia"),
    ("movii", "Movii"),
    ("powwi", "Powwi"),
    ("efecty", "Efecty"),
)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.lower().replace(" ", "")


def method_identifier(name: str | None) -> str | None:
    if not name:
        return None
    n = _norm(name)
    for needle, ident in _NAME_TO_ID:
        if needle.replace(" ", "") in n:
            return ident
    return name


def fraction(rate: Decimal | None) -> Decimal | None:
    """Binance a veces expresa tasas como fracción (0.0016) y a veces en % (0.16)."""
    if rate is None:
        return None
    return rate / 100 if rate > Decimal("0.05") else rate


@dataclass(frozen=True)
class CostConfig:
    gmf_by_account: dict[str, Decimal] = field(default_factory=lambda: dict(DEFAULT_MY_METHODS))
    default_gmf: Decimal = Decimal("0.004")
    cost_per_order: Decimal = Decimal("0")  # costos operativos atribuibles por orden completada (fiat)
    capital: Decimal | None = None  # capital operativo disponible (fiat)
    opportunity_rate_annual: Decimal | None = None  # p. ej. 0.10 = 10 % anual (indicador separado)

    def gmf_rate(self, order: Order, mode: str = "estimado") -> Decimal:
        """4x1000 sobre una COMPRA (pago en fiat). Las ventas no pagan 4x1000 al recibir."""
        if order.side is not OrderSide.BUY:
            return Decimal("0")
        if mode == "minimo":
            return min(self.gmf_by_account.values(), default=Decimal("0"))
        if mode == "maximo":
            return max([*self.gmf_by_account.values(), self.default_gmf])
        ident = method_identifier(order.pay_method)
        return self.gmf_by_account.get(ident or "", self.default_gmf)
