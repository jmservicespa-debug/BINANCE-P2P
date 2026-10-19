"""Monitor periódico del mercado P2P (solo lectura)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from jmcambios.analysis import crossing, pressure
from jmcambios.analysis.crossing import CrossReport
from jmcambios.analysis.pressure import PressureReport
from jmcambios.analysis.filters import AdFilter
from jmcambios.analysis.market_stats import SideStats, Spread, spread, summarize
from jmcambios.connectors.binance.market import MarketDataError, MarketSource
from jmcambios.domain import MarketSnapshot, Side
from jmcambios.monitor.recorder import SnapshotRecorder
from jmcambios.storage.history import HistoryStore

log = logging.getLogger(__name__)


@dataclass
class CycleResult:
    started_at: datetime
    snapshots: dict[Side, MarketSnapshot] = field(default_factory=dict)
    stats: dict[Side, SideStats] = field(default_factory=dict)
    filtered_stats: dict[Side, SideStats] = field(default_factory=dict)
    excluded: dict[Side, dict[str, int]] = field(default_factory=dict)
    spread: Spread | None = None
    filtered_spread: Spread | None = None
    cross: CrossReport | None = None
    pressure: PressureReport | None = None
    errors: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class Monitor:
    def __init__(
        self,
        source: MarketSource,
        *,
        ad_filter: AdFilter | None = None,
        recorder: SnapshotRecorder | None = None,
        store: HistoryStore | None = None,
        my_methods: dict[str, Decimal] | None = None,
        fees: dict[str, Decimal] | None = None,
        interval_s: float = 60.0,
        max_backoff_s: float = 900.0,
        clock: Callable[[], datetime],
        sleep: Callable[[float], None] = time.sleep,
        on_cycle: Callable[[CycleResult], None] | None = None,
    ) -> None:
        self._source = source
        self._filter = ad_filter or AdFilter()
        self._recorder = recorder
        self._store = store
        self._my_methods = my_methods
        self._fees = fees or {}
        self._interval = interval_s
        self._max_backoff = max_backoff_s
        self._clock = clock
        self._sleep = sleep
        self._on_cycle = on_cycle
        self.consecutive_failures = 0

    def run_cycle(self) -> CycleResult:
        result = CycleResult(started_at=self._clock())
        for side in (Side.ASK, Side.BID):
            try:
                snap = self._source.fetch(side)
            except MarketDataError as exc:
                result.errors.append(str(exc))
                continue
            stats = summarize(side, snap.ads)
            result.snapshots[side] = snap
            result.stats[side] = stats
            if self._filter.active:
                kept, excluded = self._filter.apply(snap.ads)
                result.filtered_stats[side] = summarize(side, kept)
                result.excluded[side] = excluded
            if not snap.complete:
                result.alerts.append(f"{side.label_es}: snapshot incompleto — " + "; ".join(snap.notes))
            if snap.rejected:
                result.alerts.append(f"{side.label_es}: {len(snap.rejected)} anuncios rechazados por datos incoherentes")
            if self._recorder is not None:
                try:
                    self._recorder.write(snap, stats)
                except OSError as exc:
                    result.errors.append(f"no se pudo guardar el snapshot: {exc}")

        if Side.ASK in result.stats and Side.BID in result.stats:
            result.spread = spread(result.stats[Side.ASK], result.stats[Side.BID])
            result.cross = crossing.analyze(
                result.snapshots[Side.ASK].ads, result.snapshots[Side.BID].ads, self._my_methods, **self._fees
            )
        self._store_cycle(result)
        self._measure_pressure(result)
        if result.filtered_stats.get(Side.ASK) and result.filtered_stats.get(Side.BID):
            result.filtered_spread = spread(result.filtered_stats[Side.ASK], result.filtered_stats[Side.BID])

        if any("AUTH_ERROR" in e for e in result.errors):
            result.alerts.append(
                "Binance rechazó la API key. Causa más común: cambió tu IP pública (p. ej. tras un corte de internet). "
                "Revisa tu IP actual y actualízala en Binance → Gestión de API."
            )
        self.consecutive_failures = self.consecutive_failures + 1 if result.errors else 0
        if self.consecutive_failures >= 3:
            result.alerts.append(f"{self.consecutive_failures} ciclos seguidos con errores; esperando más entre intentos")
        return result

    def _store_cycle(self, result: CycleResult) -> None:
        if self._store is None or not result.snapshots:
            return
        cycle_ts = int(result.started_at.timestamp())
        try:
            for side, snap in result.snapshots.items():
                self._store.record_snapshot(snap, result.stats[side], cycle_ts)
            if result.spread is not None:
                any_snap = next(iter(result.snapshots.values()))
                self._store.record_cycle(
                    any_snap.venue, f"{any_snap.asset}/{any_snap.fiat}", cycle_ts, result.spread,
                    result.stats[Side.ASK].best_price, result.stats[Side.BID].best_price, result.cross,
                )
        except Exception as exc:  # la base no debe tumbar el monitor
            log.exception("error guardando en la base histórica")
            result.errors.append(f"no se pudo guardar en la base histórica: {type(exc).__name__}: {exc}")

    def _measure_pressure(self, result: CycleResult) -> None:
        if self._store is None or not result.snapshots:
            return
        snap = next(iter(result.snapshots.values()))
        try:
            result.pressure = pressure.analyze(self._store, snap.venue, f"{snap.asset}/{snap.fiat}")
        except Exception:  # un fallo de análisis no debe tumbar el monitor
            log.exception("error calculando la presión del mercado")

    def next_delay(self) -> float:
        if self.consecutive_failures == 0:
            return self._interval
        return min(self._interval * (2 ** min(self.consecutive_failures, 6)), self._max_backoff)

    def run(self, max_cycles: int | None = None) -> None:
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            started = time.monotonic()
            try:
                result = self.run_cycle()
            except Exception as exc:  # el monitor debe sobrevivir a fallos inesperados
                log.exception("fallo inesperado en el ciclo")
                result = CycleResult(started_at=self._clock(), errors=[f"fallo inesperado: {type(exc).__name__}: {exc}"])
                self.consecutive_failures += 1
            if self._on_cycle:
                self._on_cycle(result)
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            self._sleep(max(0.0, self.next_delay() - (time.monotonic() - started)))
