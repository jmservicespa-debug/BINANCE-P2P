"""Cómo trabajan los mejores comerciantes verificados (estudio sobre la base histórica).

Se muestrean ciclos guardados por el monitor y, en cada uno, se mira qué anuncios
tenía cada comerciante: puesto, distancia al mejor precio, montos, métodos y, si
anunciaba en los dos lados a la vez, su DIFERENCIA PROPIA entre venta y compra
(lo más parecido a su margen bruto).

Procedencia:
- OBSERVADO: precios, límites, métodos, presencia, órdenes en 30 días (las publica Binance).
- CÁLCULO: puesto, distancia, diferencia propia, cambios de precio por hora.
- INFERIDO: margen neto "con tus costos" (sus costos reales no se conocen) y que la
  diferencia propia sea su margen (puede operar en otros mercados o fuera de Binance).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

from jmcambios.domain import Side
from jmcambios.storage.history import HistoryStore

COT = timezone(timedelta(hours=-5), "COT")
MAX_SAMPLES = 240
MIN_PRESENCE = 0.10  # aparecer en al menos el 10 % de los ciclos muestreados
ACTIVE_RANK = 20  # para el patrón: puesto mediano ≤ 20 en compra y en venta (si no, el anuncio casi no se llena)


@dataclass
class _Acc:
    nickname: str = ""
    month_orders: int = 0
    finish_rate: float | None = None
    present: dict[str, int] = field(default_factory=lambda: {"BID": 0, "ASK": 0})
    ranks: dict[str, list[int]] = field(default_factory=lambda: {"BID": [], "ASK": []})
    gaps: dict[str, list[float]] = field(default_factory=lambda: {"BID": [], "ASK": []})
    own_spread: list[float] = field(default_factory=list)
    own_spread_pct: list[float] = field(default_factory=list)
    both_prices: list[tuple[float, float]] = field(default_factory=list)  # (compra, venta)
    hours: Counter = field(default_factory=Counter)
    mins: list[float] = field(default_factory=list)
    maxs: list[float] = field(default_factory=list)
    methods: Counter = field(default_factory=Counter)
    any_present: int = 0


@dataclass(frozen=True)
class MerchantProfile:
    user_id: str
    nickname: str
    month_orders: int
    finish_rate: float | None
    sides: str  # "compra y venta" / "solo compra" / "solo venta"
    presence: float  # 0..1 de los ciclos muestreados
    rank_buy: float | None  # puesto mediano entre verificados (anuncio de compra)
    rank_sell: float | None
    gap_buy: float | None  # COP por debajo del mejor comprador (0 = es el mejor)
    gap_sell: float | None  # COP por encima del mejor vendedor
    own_spread: float | None  # COP: su venta − su compra, cuando tiene los dos anuncios
    own_spread_pct: float | None
    both_prices: tuple[float, float] | None  # (compra, venta) medianas cuando anuncia en los dos lados
    min_fiat: float | None
    max_fiat: float | None
    methods: tuple[str, ...]
    active_hours: tuple[int, ...]  # horas Colombia en que suele estar
    reprices_per_hour: float | None


@dataclass
class MerchantStudy:
    since_ts: int
    until_ts: int
    samples: int
    merchants: list[MerchantProfile] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def two_sided(self) -> list[MerchantProfile]:
        return [m for m in self.merchants if m.own_spread is not None]


def _sampled_cycles(store: HistoryStore, venue: str, market: str, since: int, until: int, limit: int):
    rows = store.query(
        """SELECT cycle_ts, MAX(CASE WHEN side='ASK' THEN taken_ts END) AS ask_ts,
                  MAX(CASE WHEN side='BID' THEN taken_ts END) AS bid_ts
           FROM snapshots WHERE venue=? AND market=? AND cycle_ts BETWEEN ? AND ?
           GROUP BY cycle_ts HAVING ask_ts IS NOT NULL AND bid_ts IS NOT NULL ORDER BY cycle_ts""",
        (venue, market, since, until),
    )
    step = max(1, -(-len(rows) // limit))
    return rows[::step]


def _reprices(store: HistoryStore, venue: str, market: str, since: int, until: int, users: set[str]) -> dict[str, int]:
    """Cambios de precio por usuario en la ventana (filas consecutivas del mismo anuncio con precio distinto)."""
    if not users:
        return {}
    marks = ",".join("?" * len(users))
    rows = store.query(
        f"SELECT user_id, ad_id, price, first_ts FROM ad_states WHERE venue=? AND market=? AND user_id IN ({marks})"
        " AND last_ts>=? AND first_ts<=? ORDER BY ad_id, first_ts",
        (venue, market, *users, since, until),
    )
    out: dict[str, int] = defaultdict(int)
    prev: dict[str, float] = {}
    for r in rows:
        p = prev.get(r["ad_id"])
        if p is not None and p != r["price"] and r["first_ts"] >= since:
            out[r["user_id"]] += 1
        prev[r["ad_id"]] = r["price"]
    return out


def study(store: HistoryStore, venue: str, market: str, *, days: float = 3, now_ts: int | None = None,
          top: int = 10, merchants_only: bool = True, max_samples: int = MAX_SAMPLES) -> MerchantStudy:
    until = now_ts if now_ts is not None else (store.latest_ts(venue, market) or int(datetime.now(UTC).timestamp()))
    since = until - int(days * 86400)
    cycles = _sampled_cycles(store, venue, market, since, until, max_samples)
    out = MerchantStudy(since_ts=since, until_ts=until, samples=len(cycles))
    if len(cycles) < 10:
        out.notes.append("historial insuficiente: deja el monitor corriendo al menos un día")
        return out
    acc: dict[str, _Acc] = defaultdict(_Acc)
    hour_samples: Counter = Counter()
    for c in cycles:
        hour = datetime.fromtimestamp(c["cycle_ts"], UTC).astimezone(COT).hour
        hour_samples[hour] += 1
        mine_now: dict[str, dict[str, float]] = defaultdict(dict)
        for side, ts in (("ASK", c["ask_ts"]), ("BID", c["bid_ts"])):
            ads = list(store.ads_at(venue, market, Side(side), ts).values())
            if merchants_only:
                ads = [a for a in ads if (a["user_type"] or "").lower() == "merchant"]
            if not ads:
                continue
            ads.sort(key=lambda a: a["price"], reverse=(side == "BID"))
            best = ads[0]["price"]
            seen: set[str] = set()
            for rank, a in enumerate(ads, 1):
                uid = a["user_id"] or ""
                if uid in seen:  # varios anuncios del mismo lado: cuenta el mejor
                    continue
                seen.add(uid)
                m = acc[uid]
                m.nickname = a["nickname"] or uid[:8]
                m.month_orders = max(m.month_orders, a["month_orders"] or 0)
                m.finish_rate = a["finish_rate"] if a["finish_rate"] is not None else m.finish_rate
                m.present[side] += 1
                m.ranks[side].append(rank)
                m.gaps[side].append(abs(a["price"] - best))
                m.mins.append(a["min_fiat"])
                m.maxs.append(a["max_fiat"])
                m.methods.update((a["methods"] or "").split(","))
                mine_now[uid][side] = a["price"]
        for uid, sides in mine_now.items():
            m = acc[uid]
            m.any_present += 1
            m.hours[hour] += 1
            if "ASK" in sides and "BID" in sides:
                spread = sides["ASK"] - sides["BID"]
                m.own_spread.append(spread)
                m.own_spread_pct.append(spread / ((sides["ASK"] + sides["BID"]) / 2) * 100)
                m.both_prices.append((sides["BID"], sides["ASK"]))

    n = len(cycles)
    candidates = [(uid, m) for uid, m in acc.items() if m.any_present / n >= MIN_PRESENCE]
    candidates.sort(key=lambda kv: (-kv[1].month_orders, -kv[1].any_present))
    chosen = candidates[:top]
    hours_window = (cycles[-1]["cycle_ts"] - cycles[0]["cycle_ts"] + 60) / 3600  # tiempo con datos, no la ventana pedida
    reprices = _reprices(store, venue, market, since, until, {uid for uid, _ in chosen})
    med = lambda xs: float(median(xs)) if xs else None  # noqa: E731
    for uid, m in chosen:
        both = m.present["BID"] > 0 and m.present["ASK"] > 0 and len(m.own_spread) >= 3
        sides = "compra y venta" if both else ("solo compra" if m.present["BID"] >= m.present["ASK"] else "solo venta")
        online_h = hours_window * m.any_present / n
        active = tuple(sorted(h for h, k in m.hours.items() if hour_samples[h] and k / hour_samples[h] >= 0.5))
        out.merchants.append(MerchantProfile(
            user_id=uid, nickname=m.nickname, month_orders=m.month_orders, finish_rate=m.finish_rate, sides=sides,
            presence=m.any_present / n, rank_buy=med(m.ranks["BID"]), rank_sell=med(m.ranks["ASK"]),
            gap_buy=med(m.gaps["BID"]), gap_sell=med(m.gaps["ASK"]),
            own_spread=med(m.own_spread) if both else None, own_spread_pct=med(m.own_spread_pct) if both else None,
            both_prices=_median_pair(m.both_prices) if both else None,
            min_fiat=med(m.mins), max_fiat=med(m.maxs),
            methods=tuple(k for k, _ in m.methods.most_common(3) if k),
            active_hours=active,
            reprices_per_hour=(reprices.get(uid, 0) / online_h) if online_h > 0.5 else None,
        ))
    if n < 60:
        out.notes.append(f"solo {n} ciclos muestreados: resultados preliminares")
    return out


def _median_pair(pairs: list[tuple[float, float]]) -> tuple[float, float]:
    """El par (compra, venta) de un mismo momento cuya diferencia es la mediana: precios coherentes entre sí."""
    ordered = sorted(pairs, key=lambda p: p[1] - p[0])
    return ordered[len(ordered) // 2]


def is_active_both(m: MerchantProfile) -> bool:
    return (m.own_spread is not None and m.rank_buy is not None and m.rank_sell is not None
            and m.rank_buy <= ACTIVE_RANK and m.rank_sell <= ACTIVE_RANK)


def summarize(st: MerchantStudy) -> dict:
    """Patrón de los que compran y venden CERCA DE LOS PRIMEROS PUESTOS en los dos lados.

    Un anuncio en el puesto #150 casi nunca se llena: su "diferencia propia" no es margen y se excluye.
    """
    two = [m for m in st.two_sided if is_active_both(m)]
    if not two:
        return {}
    med = lambda xs: float(median(xs)) if xs else None  # noqa: E731
    return {
        "two_sided": len(two),
        "own_spread": med([m.own_spread for m in two]),
        "own_spread_pct": med([m.own_spread_pct for m in two]),
        "rank_buy": med([m.rank_buy for m in two if m.rank_buy is not None]),
        "gap_buy": med([m.gap_buy for m in two if m.gap_buy is not None]),
        "gap_sell": med([m.gap_sell for m in two if m.gap_sell is not None]),
        "rank_sell": med([m.rank_sell for m in two if m.rank_sell is not None]),
        "min_fiat": med([m.min_fiat for m in two if m.min_fiat]),
        "max_fiat": med([m.max_fiat for m in two if m.max_fiat]),
        "reprices_per_hour": med([m.reprices_per_hour for m in two if m.reprices_per_hour is not None]),
        "presence": med([m.presence for m in two]),
        "excluded": len(st.two_sided) - len(two),
        "active_rank": ACTIVE_RANK,
    }


def net_margin_with_costs(buy: float, sell: float, costs) -> Decimal:
    """Margen neto del ciclo si TÚ operaras con sus precios (sus costos reales no se conocen)."""
    from jmcambios.pricing.engine import cycle_margin

    return cycle_margin(Decimal(str(buy)), Decimal(str(sell)), costs)
