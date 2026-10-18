"""Estadísticas de un snapshot de mercado (cálculos del sistema sobre datos observados).

Todas las cantidades son LIQUIDEZ ANUNCIADA. El volumen realmente ejecutado del
mercado no es observable con las fuentes disponibles y nunca se presenta como tal.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import median

from jmcambios.domain import Ad, Side

DEPTH_BANDS = (Decimal("0.005"), Decimal("0.01"), Decimal("0.02"))


@dataclass(frozen=True)
class MerchantShare:
    user_id: str
    nickname: str
    ads: int
    qty: Decimal
    share: Decimal  # 0..1 de la liquidez anunciada del lado
    best_price: Decimal


@dataclass(frozen=True)
class MethodStats:
    ads: int
    qty: Decimal
    best_price: Decimal


@dataclass
class SideStats:
    side: Side
    ads_count: int
    merchants_count: int
    best_price: Decimal | None = None  # ASK: el más bajo; BID: el más alto
    worst_price: Decimal | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    median_price: Decimal | None = None
    mean_price: Decimal | None = None
    vwap: Decimal | None = None  # ponderado por cantidad anunciada
    announced_qty: Decimal = Decimal(0)
    announced_fiat: Decimal = Decimal(0)
    depth_qty: dict[str, Decimal] = field(default_factory=dict)  # "0.5%" -> qty dentro de la banda
    top_merchants: list[MerchantShare] = field(default_factory=list)
    top1_share: Decimal | None = None
    top3_share: Decimal | None = None
    top5_share: Decimal | None = None
    hhi: Decimal | None = None  # 0..10000
    by_method: dict[str, MethodStats] = field(default_factory=dict)


def _best(side: Side, prices: list[Decimal]) -> Decimal:
    return min(prices) if side is Side.ASK else max(prices)


def _within(side: Side, price: Decimal, best: Decimal, band: Decimal) -> bool:
    if side is Side.ASK:
        return price <= best * (1 + band)
    return price >= best * (1 - band)


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places))


def summarize(side: Side, ads: list[Ad], top_n: int = 10) -> SideStats:
    merchants = {a.advertiser.user_id for a in ads}
    stats = SideStats(side=side, ads_count=len(ads), merchants_count=len(merchants))
    if not ads:
        return stats

    prices = [a.price for a in ads]
    best = _best(side, prices)
    stats.best_price = best
    stats.worst_price = max(prices) if side is Side.ASK else min(prices)
    stats.min_price, stats.max_price = min(prices), max(prices)
    stats.median_price = Decimal(median(prices))
    stats.mean_price = _q(sum(prices) / len(prices))
    stats.announced_qty = sum((a.available_qty for a in ads), Decimal(0))
    stats.announced_fiat = _q(sum((a.available_fiat for a in ads), Decimal(0)), "1")
    if stats.announced_qty > 0:
        stats.vwap = _q(sum((a.price * a.available_qty for a in ads), Decimal(0)) / stats.announced_qty)

    for band in DEPTH_BANDS:
        label = f"{band * 100:g}%"
        stats.depth_qty[label] = sum((a.available_qty for a in ads if _within(side, a.price, best, band)), Decimal(0))

    per_user: dict[str, list[Ad]] = defaultdict(list)
    for a in ads:
        per_user[a.advertiser.user_id].append(a)
    total_qty = stats.announced_qty
    shares = []
    for user_id, user_ads in per_user.items():
        qty = sum((a.available_qty for a in user_ads), Decimal(0))
        share = qty / total_qty if total_qty > 0 else Decimal(0)
        shares.append(
            MerchantShare(
                user_id=user_id,
                nickname=user_ads[0].advertiser.nickname,
                ads=len(user_ads),
                qty=qty,
                share=share,
                best_price=_best(side, [a.price for a in user_ads]),
            )
        )
    shares.sort(key=lambda m: m.qty, reverse=True)
    stats.top_merchants = shares[:top_n]
    if total_qty > 0:
        stats.top1_share = sum((m.share for m in shares[:1]), Decimal(0))
        stats.top3_share = sum((m.share for m in shares[:3]), Decimal(0))
        stats.top5_share = sum((m.share for m in shares[:5]), Decimal(0))
        stats.hhi = _q(sum((m.share * m.share for m in shares), Decimal(0)) * 10000, "1")

    methods: dict[str, list[Ad]] = defaultdict(list)
    for a in ads:
        for m in a.payment_methods:
            methods[m].append(a)
    stats.by_method = {
        m: MethodStats(
            ads=len(m_ads),
            qty=sum((a.available_qty for a in m_ads), Decimal(0)),
            best_price=_best(side, [a.price for a in m_ads]),
        )
        for m, m_ads in sorted(methods.items(), key=lambda kv: -len(kv[1]))
    }
    return stats


@dataclass(frozen=True)
class Spread:
    absolute: Decimal  # best ASK − best BID
    pct: Decimal  # sobre el punto medio, en %
    mid: Decimal

    @property
    def inverted(self) -> bool:
        """Spread negativo: anomalía (posible mapeo de lados erróneo o datos incoherentes)."""
        return self.absolute < 0


def spread(ask: SideStats, bid: SideStats) -> Spread | None:
    if ask.best_price is None or bid.best_price is None:
        return None
    mid = (ask.best_price + bid.best_price) / 2
    absolute = ask.best_price - bid.best_price
    return Spread(absolute=absolute, pct=_q(absolute / mid * 100, "0.001"), mid=_q(mid))
