"""Asesor del monitor (Fase 6): después de cada ciclo calcula escenarios, revisa
mis anuncios, dispara alertas y deja `estado.json` para el panel.

Solo lectura: nunca modifica anuncios ni órdenes.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from jmcambios.alerts import rules
from jmcambios.alerts.manager import AlertManager, Delivery
from jmcambios.analysis.competition import AdPosition, position
from jmcambios.analysis.pressure import PressureReport
from jmcambios.config import Mode
from jmcambios.connectors.binance.market import MarketDataError
from jmcambios.domain import Side
from jmcambios.domain.account import MyAd, Order, OrderSide
from jmcambios.monitor.service import CycleResult
from jmcambios.pricing.engine import DEFAULT_LIMITS, Costs, PricePlan, build_costs, plan, profile_for

log = logging.getLogger(__name__)


@dataclass
class AdvisorOutput:
    plan: PricePlan | None = None
    positions: list[AdPosition] = field(default_factory=list)
    deliveries: list[Delivery] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _f(v: Decimal | None) -> float | None:
    return None if v is None else float(v)


class Advisor:
    def __init__(
        self,
        *,
        orders: list[Order],
        fiat: str,
        gmf_by_account: dict[str, Decimal],
        default_gmf: Decimal = Decimal("0.004"),
        min_margin: Decimal = Decimal("0.003"),
        mode: Mode = Mode.OBSERVATION,
        fetch_my_ads: Callable[[], list[MyAd]] | None = None,
        ads_every: int = 5,
        alerts: AlertManager | None = None,
        state_path: Path | None = None,
        cross_min_total: Decimal = rules.CROSS_MIN_TOTAL,
    ) -> None:
        self._cross_min = cross_min_total
        self._orders = orders
        self._fiat = fiat
        self._gmf = gmf_by_account
        self._default_gmf = default_gmf
        self._min_margin = min_margin
        self.mode = mode
        self._fetch_my_ads = fetch_my_ads
        self._ads_every = max(1, ads_every)
        self._alerts = alerts
        self._state_path = state_path
        self._cycle = 0
        self.my_ads: list[MyAd] = []
        self.costs: Costs = self._build_costs()
        self._was_failing = False

    def _build_costs(self) -> Costs:
        return build_costs(self._orders, self.my_ads, self._fiat, self._gmf, self._default_gmf, self._min_margin)

    def _refresh_my_ads(self, out: AdvisorOutput) -> None:
        if self._fetch_my_ads is None or (self._cycle - 1) % self._ads_every:  # ciclo 1 y luego cada N
            return
        try:
            self.my_ads = [a for a in self._fetch_my_ads() if a.fiat == self._fiat]
            self.costs = self._build_costs()
        except MarketDataError as exc:
            out.notes.append(f"no se pudieron leer tus anuncios: {exc}")

    def process(self, result: CycleResult, consecutive_failures: int, now_ts: int) -> AdvisorOutput:
        self._cycle += 1
        out = AdvisorOutput()
        self._refresh_my_ads(out)
        snaps = result.snapshots
        if Side.ASK in snaps and Side.BID in snaps:
            my_ids = {a.ad_id for a in self.my_ads}
            my_users = {ad.advertiser.user_id for s in snaps.values() for ad in s.ads if ad.ad_id in my_ids}
            buy_ad = next((a for a in self.my_ads if a.side is OrderSide.BUY), None)
            sell_ad = next((a for a in self.my_ads if a.side is OrderSide.SELL), None)
            out.plan = plan(
                snaps[Side.ASK].ads, snaps[Side.BID].ads,
                buy_profile=profile_for(buy_ad, self._gmf, DEFAULT_LIMITS),
                sell_profile=profile_for(sell_ad, self._gmf, DEFAULT_LIMITS),
                costs=self.costs, pressure=result.pressure, exclude_users=my_users,
            )
            out.positions = [
                position(a, snaps[Side.BID if a.side is OrderSide.BUY else Side.ASK].ads, my_users) for a in self.my_ads
            ]

        failing = bool(result.errors)
        alerts = [a for a in (rules.cross_alert(result.cross, self._cross_min), rules.pressure_alert(result.pressure)) if a]
        alerts += rules.error_alerts(result.errors, consecutive_failures, recovered=self._was_failing and not failing)
        if self.mode is not Mode.OBSERVATION:
            alerts += rules.my_ad_alerts(out.positions, out.plan)
        if consecutive_failures >= rules.FAILURES_ALERT or any("AUTH_ERROR" in e for e in result.errors):
            self._was_failing = True
        elif not failing:
            self._was_failing = False
        if self._alerts is not None:
            out.deliveries = [self._alerts.notify(a, now_ts) for a in alerts]
        if self._state_path is not None:
            try:
                self.write_state(result, out, now_ts)
            except OSError as exc:
                out.notes.append(f"no se pudo guardar el estado del panel: {exc}")
        return out

    # ------------------------------------------------------------------ estado para el panel
    def state(self, result: CycleResult, out: AdvisorOutput, now_ts: int) -> dict[str, Any]:
        market: dict[str, Any] = {"asset": None, "fiat": self._fiat}
        for side, key in ((Side.ASK, "ask"), (Side.BID, "bid")):
            st = result.stats.get(side)
            snap = result.snapshots.get(side)
            if snap is not None:
                market["asset"] = snap.asset
            if st is None:
                continue
            market[key] = {
                "best": _f(st.best_price), "median": _f(st.median_price), "ads": st.ads_count,
                "merchants": st.merchants_count, "qty": _f(st.announced_qty),
                "depth_1": _f(st.depth_qty.get("1%")), "top1_share": _f(st.top1_share),
                "complete": snap.complete if snap else None,
            }
        if result.spread is not None:
            market["spread"] = _f(result.spread.absolute)
            market["spread_pct"] = _f(result.spread.pct)
        cross = None
        if result.cross is not None and result.cross.crossed:
            b = result.cross.best
            cross = {
                "gross": _f(result.cross.gross_spread), "executable": result.cross.executable,
                "net": _f(b.net_per_unit) if b else None, "net_pct": _f(b.net_pct) if b else None,
                "max_qty": _f(b.max_qty) if b else None, "pay": b.pay_method if b else None,
                "receive": b.receive_method if b else None, "rejected": result.cross.rejected,
            }
        pr: PressureReport | None = result.pressure
        pressure = None
        if pr is not None:
            top = sorted((s for s in pr.signals if abs(s.direction) > 0.05), key=lambda s: -abs(s.direction) * s.weight)[:5]
            pressure = {
                "score": pr.score, "confidence": pr.confidence, "label": pr.label, "windows": pr.windows,
                "signals": [{"name": s.name, "window": s.window_min, "up": s.direction > 0, "detail": s.detail,
                             "provenance": s.provenance} for s in top],
                "notes": pr.notes, "unverifiable": pr.unverifiable,
            }
        scenarios = []
        if out.plan is not None:
            for sc in out.plan.scenarios:
                scenarios.append({
                    "name": sc.name, "target_margin": _f(sc.target_margin), "margin": _f(sc.margin),
                    "margin_worst": _f(sc.margin_worst), "net_per_unit": _f(sc.net_per_unit),
                    **{k: {"price": _f(sp.price), "rank": sp.rank, "rank_compatible": sp.rank_compatible,
                           "compatible_total": sp.compatible_total, "adjusted": sp.adjusted}
                       for k, sp in (("buy", sc.buy), ("sell", sc.sell))},
                })
        bal = next((s for s in (out.plan.scenarios if out.plan else []) if s.name == "equilibrado"), None)
        my_ads = []
        for p in out.positions:
            a = p.ad
            target = (bal.buy if a.side is OrderSide.BUY else bal.sell) if bal else None
            my_ads.append({
                "id": a.ad_id[-6:], "side": a.side.value, "price": _f(a.price), "online": a.online,
                "available": _f(a.available_qty), "rank": p.estimated_rank, "total": p.total_competitors + 1,
                "gap": _f(p.gap_to_best), "suggested": _f(target.price) if target and self.mode is not Mode.OBSERVATION else None,
            })
        return {
            "generated_ts": now_ts, "cycle_ts": int(result.started_at.timestamp()), "mode": self.mode.value,
            "market": market, "cross": cross, "pressure": pressure,
            "plan": {"priority": out.plan.priority, "warnings": out.plan.warnings, "scenarios": scenarios} if out.plan else None,
            "costs": {"maker_buy": _f(self.costs.maker_buy), "maker_sell": _f(self.costs.maker_sell),
                      "gmf": _f(self.costs.gmf), "gmf_worst": _f(self.costs.gmf_worst), "min_margin": _f(self.costs.min_margin)},
            "my_ads": my_ads, "errors": result.errors, "alerts": result.alerts + out.notes,
        }

    def write_state(self, result: CycleResult, out: AdvisorOutput, now_ts: int) -> None:
        path = self._state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state(result, out, now_ts), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)  # el panel nunca lee un archivo a medio escribir
