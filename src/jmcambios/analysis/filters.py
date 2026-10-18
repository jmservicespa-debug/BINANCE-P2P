"""Filtros de relevancia: qué anuncios compiten realmente con mi estrategia."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

from jmcambios.domain import Ad


@dataclass(frozen=True)
class AdFilter:
    payment_methods: frozenset[str] = field(default_factory=frozenset)  # vacío = todos
    amount_fiat: Decimal | None = None  # monto típico de mis operaciones
    min_finish_rate: Decimal | None = None  # 0..1
    min_month_orders: int | None = None
    merchants_only: bool = False
    exclude_user_ids: frozenset[str] = field(default_factory=frozenset)  # p. ej. mi propio usuario

    @property
    def active(self) -> bool:
        return bool(
            self.payment_methods
            or self.amount_fiat is not None
            or self.min_finish_rate is not None
            or self.min_month_orders is not None
            or self.merchants_only
            or self.exclude_user_ids
        )

    def reason_to_exclude(self, ad: Ad) -> str | None:
        if ad.advertiser.user_id in self.exclude_user_ids:
            return "usuario excluido"
        if self.payment_methods and not self.payment_methods.intersection(ad.payment_methods):
            return "método de pago no compatible"
        if self.amount_fiat is not None and not ad.accepts_amount(self.amount_fiat):
            return "monto fuera de los límites"
        if self.merchants_only and not ad.advertiser.is_merchant:
            return "no es comerciante"
        if self.min_finish_rate is not None and (
            ad.advertiser.month_finish_rate is None or ad.advertiser.month_finish_rate < self.min_finish_rate
        ):
            return "tasa de finalización baja"
        if self.min_month_orders is not None and (
            ad.advertiser.month_orders is None or ad.advertiser.month_orders < self.min_month_orders
        ):
            return "pocas órdenes en 30 días"
        return None

    def apply(self, ads: list[Ad]) -> tuple[list[Ad], dict[str, int]]:
        kept: list[Ad] = []
        excluded: Counter[str] = Counter()
        for ad in ads:
            reason = self.reason_to_exclude(ad)
            if reason is None:
                kept.append(ad)
            else:
                excluded[reason] += 1
        return kept, dict(excluded)

    def describe(self) -> str:
        parts = []
        if self.payment_methods:
            parts.append("métodos: " + ", ".join(sorted(self.payment_methods)))
        if self.amount_fiat is not None:
            parts.append(f"monto: {self.amount_fiat:,.0f}".replace(",", "."))
        if self.merchants_only:
            parts.append("solo comerciantes")
        if self.min_finish_rate is not None:
            parts.append(f"finalización ≥ {self.min_finish_rate * 100:.0f}%")
        if self.min_month_orders is not None:
            parts.append(f"órdenes 30d ≥ {self.min_month_orders}")
        if self.exclude_user_ids:
            parts.append(f"{len(self.exclude_user_ids)} usuario(s) excluido(s)")
        return "; ".join(parts) or "sin filtros"
