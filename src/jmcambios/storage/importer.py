"""Importa los snapshots JSONL.gz de la Fase 2 a la base histórica (idempotente)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from jmcambios.analysis import crossing
from jmcambios.analysis.market_stats import spread, summarize
from jmcambios.domain import Ad, Advertiser, MarketSnapshot, RejectedAd, Side
from jmcambios.monitor.recorder import read_records
from jmcambios.storage.history import HistoryStore

PAIR_WINDOW_S = 30  # ASK y BID del mismo ciclo se toman con segundos de diferencia


def _dec(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def snapshot_from_record(rec: dict) -> MarketSnapshot:
    asset, fiat = rec["market"].split("/")
    side = Side(rec["side"])
    ads = [
        Ad(
            venue=rec["venue"],
            ad_id=a["id"],
            side=side,
            asset=asset,
            fiat=fiat,
            price=Decimal(a["p"]),
            available_qty=Decimal(a["q"]),
            min_fiat=Decimal(a["min"]),
            max_fiat=Decimal(a["max"]),
            payment_methods=tuple(a.get("pm") or ()),
            advertiser=Advertiser(
                user_id=a["u"], nickname=a.get("n") or "", user_type=a.get("ut"),
                month_orders=a.get("mo"), month_finish_rate=_dec(a.get("fr")),
            ),
            classify=a.get("c"),
        )
        for a in rec.get("ads", [])
    ]
    return MarketSnapshot(
        venue=rec["venue"],
        asset=asset,
        fiat=fiat,
        side=side,
        taken_at=datetime.fromisoformat(rec["taken_at"]),
        ads=ads,
        source=rec.get("source", ""),
        reported_total=rec.get("reported_total"),
        complete=bool(rec.get("complete", True)),
        rejected=[RejectedAd(**r) for r in rec.get("rejected", [])],
        notes=list(rec.get("notes", [])),
    )


@dataclass
class ImportResult:
    files: int = 0
    records: int = 0
    inserted: int = 0
    skipped: int = 0
    cycles: int = 0
    bad_lines: int = 0


def import_directory(
    store: HistoryStore,
    directory: Path,
    my_methods: dict[str, Decimal] | None = None,
    progress: Callable[[str], None] | None = None,
    fees: dict[str, Decimal] | None = None,
) -> ImportResult:
    result = ImportResult()
    fees = fees or {}
    paths = sorted(directory.rglob("*.jsonl.gz"))
    for n, path in enumerate(paths, 1):
        result.files += 1
        if progress:
            progress(f"[{n}/{len(paths)}] {path.name} …")
        try:
            records = read_records(path)
        except (OSError, EOFError, ValueError):
            # Archivo truncado (p. ej. apagado brusco): se importan las líneas legibles.
            records = _read_tolerant(path, result)
        pending_ask: tuple[int, MarketSnapshot] | None = None
        for rec in records:
            result.records += 1
            try:
                snap = snapshot_from_record(rec)
            except (KeyError, ValueError, TypeError):
                result.bad_lines += 1
                continue
            ts = int(snap.taken_at.timestamp())
            if snap.side is Side.ASK:
                cycle_ts = ts
                pending_ask = (ts, snap)
            elif pending_ask and 0 <= ts - pending_ask[0] <= PAIR_WINDOW_S:
                cycle_ts = pending_ask[0]
            else:
                cycle_ts = ts
            stats = summarize(snap.side, snap.ads)
            if store.record_snapshot(snap, stats, cycle_ts):
                result.inserted += 1
            else:
                result.skipped += 1
            if snap.side is Side.BID and pending_ask and cycle_ts == pending_ask[0]:
                ask_snap = pending_ask[1]
                ask_stats = summarize(Side.ASK, ask_snap.ads)
                cross = crossing.analyze(ask_snap.ads, snap.ads, my_methods, **fees)
                store.record_cycle(
                    snap.venue, f"{snap.asset}/{snap.fiat}", cycle_ts, spread(ask_stats, stats),
                    ask_stats.best_price, stats.best_price, cross,
                )
                result.cycles += 1
                pending_ask = None
    return result


def _read_tolerant(path: Path, result: ImportResult) -> list[dict]:
    import gzip
    import json

    out: list[dict] = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    result.bad_lines += 1
    except (OSError, EOFError):
        pass
    return out
