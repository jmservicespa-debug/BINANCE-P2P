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
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from jmcambios.analysis.crossing import CrossReport
from jmcambios.analysis.market_stats import SideStats, Spread
from jmcambios.domain import MarketSnapshot, Side
from jmcambios.domain.account import Order, OrderSide

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
    top1_share REAL, top3_share REAL, top5_share REAL, hhi REAL, top5_price REAL,
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

-- Órdenes propias (Fase 4). Importes como TEXT: contabilidad exacta con Decimal.
CREATE TABLE IF NOT EXISTS orders (
    venue TEXT NOT NULL, order_id TEXT NOT NULL,
    side TEXT NOT NULL, asset TEXT NOT NULL, fiat TEXT NOT NULL,
    qty TEXT NOT NULL, unit_price TEXT NOT NULL, total_fiat TEXT NOT NULL,
    status TEXT NOT NULL, created_ts INTEGER NOT NULL,
    role TEXT, commission TEXT, commission_rate TEXT,
    pay_method TEXT, counterparty TEXT, ad_id TEXT,
    synced_ts INTEGER NOT NULL,
    PRIMARY KEY (venue, order_id)
);
CREATE INDEX IF NOT EXISTS ix_orders_time ON orders (fiat, created_ts);

-- Alertas (Fase 6): todas quedan registradas, se hayan enviado o no.
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL, key TEXT NOT NULL, severity TEXT NOT NULL,
    title TEXT NOT NULL, body TEXT NOT NULL,
    sent_to TEXT, suppressed INTEGER NOT NULL DEFAULT 0, errors TEXT
);
CREATE INDEX IF NOT EXISTS ix_alerts_key ON alerts (key, ts);
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
        self._migrate()

    def _migrate(self) -> None:
        """Columnas añadidas después de crear bases existentes."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(snapshots)")}
        if "top5_price" not in cols:
            with self.conn:
                self.conn.execute("ALTER TABLE snapshots ADD COLUMN top5_price REAL")

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
                   announced_fiat, depth_05, depth_1, depth_2, top1_share, top3_share, top5_share, hhi, top5_price)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snap.venue, market, snap.side.value, ts, cycle_ts, snap.source, int(snap.complete),
                    snap.reported_total, stats.ads_count, stats.merchants_count, _f(stats.best_price),
                    _f(stats.median_price), _f(stats.vwap), _f(stats.announced_qty), _f(stats.announced_fiat),
                    _f(stats.depth_qty.get("0.5%")), _f(stats.depth_qty.get("1%")), _f(stats.depth_qty.get("2%")),
                    _f(stats.top1_share), _f(stats.top3_share), _f(stats.top5_share), _f(stats.hhi),
                    _f(stats.top5_avg_price),
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

    def upsert_orders(self, orders: Iterable[Order], synced_ts: int) -> tuple[int, int]:
        """Inserta o actualiza órdenes (el estado puede cambiar). Devuelve (nuevas, actualizadas)."""
        new = updated = 0
        with self._tx() as c:
            for o in orders:
                exists = c.execute(
                    "SELECT 1 FROM orders WHERE venue=? AND order_id=?", (o.venue, o.order_id)
                ).fetchone()
                c.execute(
                    """INSERT OR REPLACE INTO orders (venue, order_id, side, asset, fiat, qty, unit_price, total_fiat,
                       status, created_ts, role, commission, commission_rate, pay_method, counterparty, ad_id, synced_ts)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        o.venue, o.order_id, o.side.value, o.asset, o.fiat, str(o.qty), str(o.unit_price),
                        str(o.total_fiat), o.status, _ts(o.created_at), o.role,
                        None if o.commission is None else str(o.commission),
                        None if o.commission_rate is None else str(o.commission_rate),
                        o.pay_method, o.counterparty, o.ad_id, synced_ts,
                    ),
                )
                if exists:
                    updated += 1
                else:
                    new += 1
        return new, updated

    def load_orders(
        self, *, fiat: str | None = None, asset: str | None = None, since_ts: int = 0, until_ts: int | None = None
    ) -> list[Order]:
        sql = "SELECT * FROM orders WHERE created_ts >= ?"
        params: list[Any] = [since_ts]
        if until_ts is not None:
            sql += " AND created_ts < ?"
            params.append(until_ts)
        if fiat:
            sql += " AND fiat = ?"
            params.append(fiat)
        if asset:
            sql += " AND asset = ?"
            params.append(asset)
        rows = self.conn.execute(sql + " ORDER BY created_ts, order_id", params).fetchall()
        return [
            Order(
                venue=r["venue"], order_id=r["order_id"], side=OrderSide(r["side"]), asset=r["asset"], fiat=r["fiat"],
                qty=Decimal(r["qty"]), unit_price=Decimal(r["unit_price"]), total_fiat=Decimal(r["total_fiat"]),
                status=r["status"], created_at=datetime.fromtimestamp(r["created_ts"], UTC), role=r["role"],
                commission=None if r["commission"] is None else Decimal(r["commission"]),
                commission_rate=None if r["commission_rate"] is None else Decimal(r["commission_rate"]),
                pay_method=r["pay_method"], counterparty=r["counterparty"], ad_id=r["ad_id"],
            )
            for r in rows
        ]

    def record_alert(self, ts: int, key: str, severity: str, title: str, body: str,
                     sent_to: list[str], suppressed: bool, errors: list[str]) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO alerts (ts, key, severity, title, body, sent_to, suppressed, errors) VALUES (?,?,?,?,?,?,?,?)",
                (ts, key, severity, title, body, ",".join(sent_to), int(suppressed), "; ".join(errors) or None),
            )

    def last_alert_ts(self, key: str) -> int | None:
        row = self.conn.execute(
            "SELECT MAX(ts) AS t FROM alerts WHERE key=? AND suppressed=0", (key,)
        ).fetchone()
        return row["t"] if row and row["t"] is not None else None

    def recent_alerts(self, limit: int = 30) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM alerts WHERE suppressed=0 ORDER BY ts DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()

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
        return {t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("snapshots", "cycles", "ad_states", "orders", "alerts")}
