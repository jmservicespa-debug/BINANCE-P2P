"""Cambios de liquidez y perfiles horarios (módulo 5, primera parte).

Todo se calcula sobre la base histórica. Cada resultado indica su procedencia:
- OBSERVADO: comparación directa de datos publicados por Binance.
- INFERIDO: interpretación (p. ej. una cantidad que baja sin cambio de precio
  puede ser una venta ejecutada… o el anunciante que la redujo a mano).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jmcambios.domain import Side
from jmcambios.storage.history import HistoryStore

WINDOWS_MIN = (5, 15, 30, 60)
COT_OFFSET_S = -5 * 3600  # Colombia, UTC-5 sin horario de verano


@dataclass
class WindowChange:
    side: Side
    minutes: int
    from_ts: int
    to_ts: int
    # OBSERVADO (diferencias entre dos snapshots)
    best_price_delta: float | None = None
    median_delta: float | None = None
    vwap_delta: float | None = None
    ads_count_delta: int | None = None
    announced_qty_delta: float | None = None
    depth_1_delta: float | None = None
    ads_appeared: int = 0
    ads_disappeared: int = 0
    repriced: int = 0
    qty_appeared: float = 0.0
    qty_disappeared: float = 0.0
    # INFERIDO
    qty_reduced_same_price: float = 0.0  # posible ejecución (no verificable)
    ads_reduced_same_price: int = 0
    notes: list[str] = field(default_factory=list)


def _delta(a, b):
    return None if a is None or b is None else b - a


def window_change(store: HistoryStore, venue: str, market: str, side: Side, now_ts: int, minutes: int) -> WindowChange | None:
    end = store.snapshot_at(venue, market, side, now_ts)
    start = store.snapshot_at(venue, market, side, now_ts - minutes * 60)
    if end is None or start is None or start["taken_ts"] >= end["taken_ts"]:
        return None
    wc = WindowChange(side=side, minutes=minutes, from_ts=start["taken_ts"], to_ts=end["taken_ts"])
    gap = (now_ts - minutes * 60) - start["taken_ts"]
    if gap > 180:
        wc.notes.append(f"sin datos exactos: se compara con un snapshot {gap // 60} min más antiguo")
    wc.best_price_delta = _delta(start["best_price"], end["best_price"])
    wc.median_delta = _delta(start["median_price"], end["median_price"])
    wc.vwap_delta = _delta(start["vwap"], end["vwap"])
    wc.ads_count_delta = _delta(start["ads_count"], end["ads_count"])
    wc.announced_qty_delta = _delta(start["announced_qty"], end["announced_qty"])
    wc.depth_1_delta = _delta(start["depth_1"], end["depth_1"])

    before = store.ads_at(venue, market, side, start["taken_ts"])
    after = store.ads_at(venue, market, side, end["taken_ts"])
    for ad_id in after.keys() - before.keys():
        wc.ads_appeared += 1
        wc.qty_appeared += after[ad_id]["qty"] or 0
    for ad_id in before.keys() - after.keys():
        wc.ads_disappeared += 1
        wc.qty_disappeared += before[ad_id]["qty"] or 0
    for ad_id in before.keys() & after.keys():
        b, a = before[ad_id], after[ad_id]
        if a["price"] != b["price"]:
            wc.repriced += 1
        elif (a["qty"] or 0) < (b["qty"] or 0):
            wc.ads_reduced_same_price += 1
            wc.qty_reduced_same_price += (b["qty"] or 0) - (a["qty"] or 0)
    if not start["complete"] or not end["complete"]:
        wc.notes.append("algún snapshot estaba incompleto: altas/bajas pueden estar sobreestimadas")
    return wc


def window_changes(store: HistoryStore, venue: str, market: str, now_ts: int | None = None) -> dict[Side, list[WindowChange]]:
    now_ts = now_ts if now_ts is not None else store.latest_ts(venue, market)
    out: dict[Side, list[WindowChange]] = {Side.ASK: [], Side.BID: []}
    if now_ts is None:
        return out
    for side in (Side.ASK, Side.BID):
        for m in WINDOWS_MIN:
            wc = window_change(store, venue, market, side, now_ts, m)
            if wc is not None:
                out[side].append(wc)
    return out


@dataclass
class HourProfile:
    day_type: str  # "hábil" / "fin de semana"
    hour: int  # 0..23 hora Colombia
    cycles: int
    avg_spread: float | None
    min_spread: float | None
    crossed_pct: float
    executable_pct: float
    avg_ask_best: float | None
    avg_bid_best: float | None
    avg_ask_ads: float | None
    avg_bid_ads: float | None
    avg_ask_qty: float | None
    avg_bid_qty: float | None


def hourly_profile(store: HistoryStore, venue: str, market: str, since_ts: int | None = None) -> list[HourProfile]:
    """Promedios por hora del día (Colombia) y tipo de día. Los festivos aún no se distinguen."""
    rows = store.query(
        f"""
        WITH c AS (
            SELECT cycle_ts, spread, crossed, executable,
                   CAST(strftime('%H', cycle_ts + ({COT_OFFSET_S}), 'unixepoch') AS INTEGER) AS hour,
                   CASE WHEN strftime('%w', cycle_ts + ({COT_OFFSET_S}), 'unixepoch') IN ('0','6')
                        THEN 'fin de semana' ELSE 'hábil' END AS day_type
            FROM cycles WHERE venue=? AND market=? AND cycle_ts >= ?
        )
        SELECT c.day_type, c.hour, COUNT(*) AS n,
               AVG(c.spread) AS avg_spread, MIN(c.spread) AS min_spread,
               100.0 * AVG(c.crossed) AS crossed_pct, 100.0 * AVG(c.executable) AS executable_pct,
               AVG(a.best_price) AS ask_best, AVG(b.best_price) AS bid_best,
               AVG(a.ads_count) AS ask_ads, AVG(b.ads_count) AS bid_ads,
               AVG(a.announced_qty) AS ask_qty, AVG(b.announced_qty) AS bid_qty
        FROM c
        LEFT JOIN snapshots a ON a.venue=? AND a.market=? AND a.side='ASK' AND a.cycle_ts=c.cycle_ts
        LEFT JOIN snapshots b ON b.venue=? AND b.market=? AND b.side='BID' AND b.cycle_ts=c.cycle_ts
        GROUP BY c.day_type, c.hour
        ORDER BY c.day_type, c.hour
        """,
        (venue, market, since_ts or 0, venue, market, venue, market),
    )
    return [
        HourProfile(
            day_type=r["day_type"], hour=r["hour"], cycles=r["n"], avg_spread=r["avg_spread"],
            min_spread=r["min_spread"], crossed_pct=r["crossed_pct"] or 0.0, executable_pct=r["executable_pct"] or 0.0,
            avg_ask_best=r["ask_best"], avg_bid_best=r["bid_best"], avg_ask_ads=r["ask_ads"],
            avg_bid_ads=r["bid_ads"], avg_ask_qty=r["ask_qty"], avg_bid_qty=r["bid_qty"],
        )
        for r in rows
    ]


@dataclass
class CrossEpisode:
    start_ts: int
    end_ts: int
    cycles: int
    executable_cycles: int
    best_net_per_unit: float | None
    best_net_pct: float | None
    best_max_qty: float | None

    @property
    def minutes(self) -> float:
        return (self.end_ts - self.start_ts) / 60


def cross_episodes(store: HistoryStore, venue: str, market: str, max_gap_s: int = 180) -> list[CrossEpisode]:
    """Agrupa ciclos consecutivos con cruce en episodios (cuánto dura cada cruce)."""
    rows = store.query(
        "SELECT cycle_ts, executable, best_net_per_unit, best_net_pct, best_max_qty FROM cycles "
        "WHERE venue=? AND market=? AND crossed=1 ORDER BY cycle_ts",
        (venue, market),
    )
    episodes: list[CrossEpisode] = []
    for r in rows:
        ep = episodes[-1] if episodes else None
        if ep is None or r["cycle_ts"] - ep.end_ts > max_gap_s:
            ep = CrossEpisode(r["cycle_ts"], r["cycle_ts"], 0, 0, None, None, None)
            episodes.append(ep)
        ep.end_ts = r["cycle_ts"]
        ep.cycles += 1
        if r["executable"]:
            ep.executable_cycles += 1
            if ep.best_net_per_unit is None or (r["best_net_per_unit"] or 0) > ep.best_net_per_unit:
                ep.best_net_per_unit = r["best_net_per_unit"]
                ep.best_net_pct = r["best_net_pct"]
                ep.best_max_qty = r["best_max_qty"]
    return episodes
