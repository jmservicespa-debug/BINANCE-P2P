"""Base de datos histórica (módulo 3) sobre SQLite.

Diseño para que semanas de datos quepan en un PC:
- `snapshots`: una fila por lado y ciclo con las estadísticas calculadas.
- `cycles`: una fila por ciclo con el diferencial y el análisis de cruce.
- `ad_states`: cada anuncio se guarda SOLO cuando cambia (precio, cantidad,
  límites o métodos). Mientras no cambia se extiende `last_ts`. Así se puede
  reconstruir qué anuncios existían en cualquier momento sin guardar 600 filas
  por minuto.

Los importes se guardan como REAL: la base es para análisis; los cálculos
contables exactos (Fase 4) usan Decimal en memoria.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from jmcambios.analysis.crossing import CrossReport
from jmcambios.analysis.market_stats import SideStats, Spread
from jmcambios.domain import Ad, MarketSnapshot, Side

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    venue TEXT NOT NULL, market TEXT NOT NULL, side TEXT NOT NULL,
    taken_ts INTEGER NOT NULL, cycle_ts INTEGER NOT NULL,
    source TEXT, complete INTEGER, reported_total INTEGER,
    ads_count INTEGER, merchants_count INTEGER,
    best_price REAL, median_price REAL, vwap REAL,
    announced_qty REAL, announced_fiat REAL,
    depth_05 REAL, depth_1 REAL, depth_2 REAL,
    top1_share REAL, top3_share REAL, top5_share REAL, hhi REAL,
    UNIQUE (venue, market, side, taken_ts)
);
CREATE INDEX IF NOT EXISTS ix_snap_cycle ON snapshots (venue, market, cycle_ts);

CREATE TABLE IF NOT EXISTS cycles (
    venue TEXT NOT NULL, market TEXT NOT NULL, cycle_ts INTEGER NOT NULL,
    ask_best REAL, bid_best REAL, spread REAL, spread_pct REAL,
    crossed INTEGER, executable INTEGER,
    best_net_per_unit REAL, best_net_pct REAL, best_max_qty REAL,
    best_pay_method TEXT, best_receive_method TEXT,
    PRIMARY KEY (venue, market, cycle_ts)
);

CREATE TABLE IF NOT EXISTS ad_states (
    id INTEGER PRIMARY KEY,
    venue TEXT NOT NULL, market TEXT NOT NULL, side TEXT NOT NULL, ad_id TEXT NOT NULL,
    user_id TEXT, nickname TEXT, user_type TEXT, month_orders INTEGER, finish_rate REAL,
    price REAL, qty REAL, min_fiat REAL, max_fiat REAL, methods TEXT,
    first_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL, open INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_states_open ON ad_states (venue, market, side, open);
CREATE INDEX IF NOT EXISTS ix_states_time ON ad_states (venue, market, side, first_ts, last_ts);
"""


def _f(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def _ad_key(price: float, qty: float, lo: float, hi: float, methods: str) -> tuple:
    return (round(price, 6), round(qty, 6), round(lo, 2), round(hi, 2), methods)


class HistoryStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> HistoryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self.conn:
            yield self.conn

    # ------------------------------------------------------------------ escritura
    def record_snapshot(self, snap: MarketSnapshot, stats: SideStats, cycle_ts: int) -> bool:
        """Guarda un snapshot. Devuelve False si ya existía (importación idempotente)."""
        market = f"{snap.asset}/{snap.fiat}"
        ts = _ts(snap.taken_at)
        with self._tx() as c:
            cur = c.execute(
                """INSERT OR IGNORE INTO snapshots (venue, market, side, taken_ts, cycle_ts, source, complete,
                   reported_total, ads_count, merchants_count, best_price, median_price, vwap, announced_qty,
                   announced_fiat, depth_05, depth_1, depth_2, top1_share, top3_share, top5_share, hhi)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snap.venue, market, snap.side.value, ts, cycle_ts, snap.source, int(snap.complete),
                    snap.reported_total, stats.ads_count, stats.merchants_count, _f(stats.best_price),
                    _f(stats.median_price), _f(stats.vwap), _f(stats.announced_qty), _f(stats.announced_fiat),
                    _f(stats.depth_qty.get("0.5%")), _f(stats.depth_qty.get("1%")), _f(stats.depth_qty.get("2%")),
                    _f(stats.top1_share), _f(stats.top3_share), _f(stats.top5_share), _f(stats.hhi),
                ),
            )
            if cur.rowcount == 0:
                return False
            newest = c.execute(
                "SELECT MAX(last_ts) FROM ad_states WHERE venue=? AND market=? AND side=?",
                (snap.venue, market, snap.side.value),
            ).fetchone()[0]
            # Un snapshot más viejo que lo ya registrado no puede reescribir la historia de anuncios.
            if newest is None or ts > newest:
                self._update_states(c, snap, market, ts)
        return True

    def _update_states(self, c: sqlite3.Connection, snap: MarketSnapshot, market: str, ts: int) -> None:
        open_rows = c.execute(
            "SELECT id, ad_id, price, qty, min_fiat, max_fiat, methods FROM ad_states "
            "WHERE venue=? AND market=? AND side=? AND open=1",
            (snap.venue, market, snap.side.value),
        ).fetchall()
        current = {r["ad_id"]: r for r in open_rows}
        seen: set[str] = set()
        for ad in snap.ads:
            seen.add(ad.ad_id)
            methods = ",".join(ad.payment_methods)
            key = _ad_key(float(ad.price), float(ad.available_qty), float(ad.min_fiat), float(ad.max_fiat), methods)
            row = current.get(ad.ad_id)
            if row is not None and _ad_key(row["price"], row["qty"], row["min_fiat"], row["max_fiat"], row["methods"]) == key:
                c.execute("UPDATE ad_states SET last_ts=? WHERE id=?", (ts, row["id"]))
                continue
            if row is not None:
                c.execute("UPDATE ad_states SET open=0 WHERE id=?", (row["id"],))
            a = ad.advertiser
            c.execute(
                """INSERT INTO ad_states (venue, market, side, ad_id, user_id, nickname, user_type, month_orders,
                   finish_rate, price, qty, min_fiat, max_fiat, methods, first_ts, last_ts, open)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (
                    snap.venue, market, snap.side.value, ad.ad_id, a.user_id, a.nickname, a.user_type,
                    a.month_orders, _f(a.month_finish_rate), float(ad.price), float(ad.available_qty),
                    float(ad.min_fiat), float(ad.max_fiat), methods, ts, ts,
                ),
            )
        # Solo un snapshot completo prueba que un anuncio ya no está publicado.
        if snap.complete:
            gone = [current[k]["id"] for k in current.keys() - seen]
            c.executemany("UPDATE ad_states SET open=0 WHERE id=?", [(i,) for i in gone])

    def record_cycle(
        self, venue: str, market: str, cycle_ts: int, spread: Spread | None,
        ask_best: Decimal | None, bid_best: Decimal | None, cross: CrossReport | None,
    ) -> None:
        best = cross.best if cross else None
        with self._tx() as c:
            c.execute(
                """INSERT OR REPLACE INTO cycles (venue, market, cycle_ts, ask_best, bid_best, spread, spread_pct,
                   crossed, executable, best_net_per_unit, best_net_pct, best_max_qty, best_pay_method,
                   best_receive_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    venue, market, cycle_ts, _f(ask_best), _f(bid_best),
                    _f(spread.absolute) if spread else None, _f(spread.pct) if spread else None,
                    int(bool(cross and cross.crossed)), int(bool(cross and cross.executable)),
                    _f(best.net_per_unit) if best else None, _f(best.net_pct) if best else None,
                    _f(best.max_qty) if best else None,
                    best.pay_method if best else None, best.receive_method if best else None,
                ),
            )

    # ------------------------------------------------------------------ lectura
    def snapshot_at(self, venue: str, market: str, side: Side, ts: int) -> sqlite3.Row | None:
        """Último snapshot tomado en o antes de `ts`."""
        return self.conn.execute(
            "SELECT * FROM snapshots WHERE venue=? AND market=? AND side=? AND taken_ts<=? "
            "ORDER BY taken_ts DESC LIMIT 1",
            (venue, market, side.value, ts),
        ).fetchone()

    def latest_ts(self, venue: str, market: str) -> int | None:
        row = self.conn.execute(
            "SELECT MAX(taken_ts) AS t FROM snapshots WHERE venue=? AND market=?", (venue, market)
        ).fetchone()
        return row["t"] if row and row["t"] is not None else None

    def ads_at(self, venue: str, market: str, side: Side, ts: int) -> dict[str, sqlite3.Row]:
        """Anuncios vigentes en el instante `ts` (uno por ad_id)."""
        rows = self.conn.execute(
            "SELECT * FROM ad_states WHERE venue=? AND market=? AND side=? AND first_ts<=? AND last_ts>=?",
            (venue, market, side.value, ts, ts),
        ).fetchall()
        return {r["ad_id"]: r for r in rows}

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def counts(self) -> dict[str, int]:
        return {t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("snapshots", "cycles", "ad_states")}
