"""Registro de snapshots en archivos diarios JSONL comprimidos (gzip).

Es el almacenamiento mínimo de la Fase 2; la Fase 3 lo cargará en la base de
datos histórica. Una línea por lado y ciclo. Cada archivo gzip admite que se
añadan miembros, así que un reinicio no corrompe lo ya escrito.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import asdict
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from jmcambios.analysis.market_stats import SideStats
from jmcambios.domain import MarketSnapshot

SCHEMA_VERSION = 1


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"no serializable: {type(obj).__name__}")


def snapshot_record(snapshot: MarketSnapshot, stats: SideStats) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "venue": snapshot.venue,
        "market": f"{snapshot.asset}/{snapshot.fiat}",
        "side": snapshot.side.value,
        "taken_at": snapshot.taken_at,
        "source": snapshot.source,
        "complete": snapshot.complete,
        "reported_total": snapshot.reported_total,
        "notes": snapshot.notes,
        "rejected": [asdict(r) for r in snapshot.rejected],
        # Anuncios en forma compacta (datos OBSERVADOS de Binance).
        "ads": [
            {
                "id": a.ad_id,
                "p": a.price,
                "q": a.available_qty,
                "min": a.min_fiat,
                "max": a.max_fiat,
                "pm": list(a.payment_methods),
                "u": a.advertiser.user_id,
                "n": a.advertiser.nickname,
                "ut": a.advertiser.user_type,
                "mo": a.advertiser.month_orders,
                "fr": a.advertiser.month_finish_rate,
                "c": a.classify,
            }
            for a in snapshot.ads
        ],
        # Cálculos del sistema sobre esos anuncios.
        "stats": {
            "ads_count": stats.ads_count,
            "merchants_count": stats.merchants_count,
            "best_price": stats.best_price,
            "median_price": stats.median_price,
            "vwap": stats.vwap,
            "announced_qty": stats.announced_qty,
            "announced_fiat": stats.announced_fiat,
            "depth_qty": stats.depth_qty,
            "top1_share": stats.top1_share,
            "top3_share": stats.top3_share,
            "top5_share": stats.top5_share,
            "hhi": stats.hhi,
        },
    }


class SnapshotRecorder:
    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def path_for(self, snapshot: MarketSnapshot) -> Path:
        market = f"{snapshot.asset}_{snapshot.fiat}".lower()
        return self._dir / snapshot.venue / market / f"{snapshot.taken_at:%Y-%m-%d}.jsonl.gz"

    def write(self, snapshot: MarketSnapshot, stats: SideStats) -> Path:
        path = self.path_for(snapshot)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(snapshot_record(snapshot, stats), default=_default, ensure_ascii=False, separators=(",", ":"))
        with gzip.open(path, "at", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return path


def read_records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
