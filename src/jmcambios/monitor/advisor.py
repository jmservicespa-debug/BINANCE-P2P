"""Asesor del monitor (Fase 6): después de cada ciclo calcula escenarios, revisa
mis anuncios, dispara alertas y deja `estado.json` para el panel.

Solo lectura: nunca modifica anuncios ni órdenes.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
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
from jmcambios.profitability import daily
from jmcambios.profitability.costs import CostConfig
from jmcambios.analysis.amounts import tranche_views
from jmcambios.monitor.report import money
from jmcambios.pricing.engine import tranche_opportunities
from jmcambios.pricing.engine import DEFAULT_LIMITS, AdProfile, Costs, PricePlan, build_costs, plan, profile_for

log = logging.getLogger(__name__)


@dataclass
class AdvisorOutput:
    plan: PricePlan | None = None
    positions: list[AdPosition] = field(default_factory=list)
    deliveries: list[Delivery] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    today: daily.TodaySummary | None = None
    opportunities: tuple | None = None  # (lista por tramo, índice sugerido)
    exempt: daily.ExemptUsage | None = None


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
        merchants_only: bool = True,
        fetch_orders: Callable[[], list[Order]] | None = None,
        orders_every: int = 15,
        daily_goal: Decimal | None = None,
        exempt_cap: Decimal | None = None,
        exempt_accounts: tuple[str, ...] | None = None,
        merchant_start: datetime | None = None,
        summary_hours: tuple[int, ...] = (),
    ) -> None:
        self._summary_hours = summary_hours
        self._merchants_only = merchants_only
        self._fetch_orders = fetch_orders
        self._orders_every = max(1, orders_every)
        self._goal = daily_goal
        self._cap = exempt_cap
        self._cost_cfg = CostConfig(gmf_by_account=gmf_by_account)
        self._exempt_accounts = exempt_accounts or daily.exempt_accounts(self._cost_cfg, None)
        self._start = merchant_start
        self._cap_exceeded = False
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
        self._profiles: dict[str, AdProfile] = {}
        self._my_users: set[str] = set()

    def _build_costs(self) -> Costs:
        costs = build_costs(self._orders, self.my_ads, self._fiat, self._gmf, self._default_gmf, self._min_margin)
        # Pasado el tope exento, cada peso pagado vuelve a pagar 4x1000.
        return replace(costs, gmf=costs.gmf_worst) if self._cap_exceeded else costs

    def _refresh_orders(self, out: AdvisorOutput) -> None:
        if self._fetch_orders is None or (self._cycle - 1) % self._orders_every:
            return
        try:
            self._orders = self._fetch_orders()
            self.costs = self._build_costs()
        except MarketDataError as exc:
            out.notes.append(f"no se pudieron actualizar tus órdenes: {exc}")

    def _opportunities(self, snaps, my_users: set[str]):
        """Margen por tramo de montos estando de primero (misma competencia que los escenarios)."""
        side_ads = {}
        for side in (Side.BID, Side.ASK):
            ads = [a for a in snaps[side].ads if a.advertiser.user_id not in my_users]
            if self._merchants_only:
                ads = [a for a in ads if a.advertiser.is_merchant] or ads
            side_ads[side] = ads
        methods = self._profiles["buy"].methods if self._profiles else tuple(self._gmf)
        return tranche_opportunities(tranche_views(Side.BID, side_ads[Side.BID], methods),
                                     tranche_views(Side.ASK, side_ads[Side.ASK], methods), self.costs)

    def _summary(self, result: CycleResult, out: AdvisorOutput, now_ts: int):
        """Resumen a las horas configuradas (hora Colombia), una vez por hora y día."""
        local = datetime.fromtimestamp(now_ts, UTC).astimezone(daily.COT)
        if local.hour not in self._summary_hours:
            return None
        lines = [f"{local:%Y-%m-%d %H:%M} hora Colombia"]
        snaps = result.snapshots
        if Side.ASK in snaps and Side.BID in snaps:
            asks = [a.price for a in snaps[Side.ASK].ads if a.advertiser.is_merchant]
            bids = [a.price for a in snaps[Side.BID].ads if a.advertiser.is_merchant]
            if asks and bids:
                lines.append(f"Verificados: venden desde {money(min(asks))} · compran hasta {money(max(bids))}"
                             f" · diferencia {money(min(asks) - max(bids))} COP")
        if out.opportunities is not None and out.opportunities[1] is not None:
            o = out.opportunities[0][out.opportunities[1]]
            lines.append(f"Mejor tramo: {o.label} → {money(o.margin * 100, 2)} % libre siendo #1"
                         + (" ✔ alcanza tu margen" if o.meets_min else f" (tu mínimo: {money(self.costs.min_margin * 100, 2)} %)"))
        if result.pressure is not None and result.pressure.windows:
            lines.append(f"Presión: {result.pressure.label} ({result.pressure.score:+.0f}, confianza {result.pressure.confidence})")
        if out.today is not None:
            lines.append(f"Hoy: {money(out.today.realized, 0)} de {money(out.today.goal, 0)} COP"
                         f" · {out.today.buys} compras / {out.today.sells} ventas")
        if out.exempt is not None:
            lines.append(f"Tope exento: {money(out.exempt.ratio * 100, 0)} % usado · quedan {money(out.exempt.remaining, 0)} COP")
        return rules.summary_alert(f"resumen:{local:%Y-%m-%d}:{local.hour}", lines)

    def _operation(self, out: AdvisorOutput, now_ts: int) -> None:
        now = datetime.fromtimestamp(now_ts, UTC)
        if self._cap is not None:
            out.exempt = daily.exempt_usage(self._orders, fiat=self._fiat, now=now, cap=self._cap,
                                            accounts=self._exempt_accounts)
            if out.exempt.exceeded != self._cap_exceeded:
                self._cap_exceeded = out.exempt.exceeded
                self.costs = self._build_costs()
        if self._goal is not None:
            out.today = daily.today_summary(self._orders, self._cost_cfg, fiat=self._fiat, asset="USDT", now=now,
                                            start=self._start, goal=self._goal)

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
        self._refresh_orders(out)
        self._operation(out, now_ts)
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
                costs=self.costs, pressure=result.pressure, exclude_users=my_users, merchants_only=self._merchants_only,
            )
            self._profiles = {
                "buy": profile_for(buy_ad, self._gmf, DEFAULT_LIMITS),
                "sell": profile_for(sell_ad, self._gmf, DEFAULT_LIMITS),
            }
            self._my_users = my_users
            out.positions = [
                position(a, snaps[Side.BID if a.side is OrderSide.BUY else Side.ASK].ads, my_users, self._merchants_only)
                for a in self.my_ads
            ]
            out.opportunities = self._opportunities(snaps, my_users)

        failing = bool(result.errors)
        alerts = [a for a in (rules.cross_alert(result.cross, self._cross_min), rules.pressure_alert(result.pressure)) if a]
        alerts += rules.error_alerts(result.errors, consecutive_failures, recovered=self._was_failing and not failing)
        if self.mode is not Mode.OBSERVATION:
            alerts += rules.my_ad_alerts(out.positions, out.plan)
        alerts += [a for a in (rules.exempt_alert(out.exempt), rules.goal_alert(out.today)) if a]
        if out.opportunities is not None and self.mode is not Mode.OBSERVATION:  # sugiere precios
            alerts += [a for a in (rules.opportunity_alert(*out.opportunities),) if a]
        summary = self._summary(result, out, now_ts)
        if summary is not None:
            alerts.append(summary)
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
        for side, key in ((Side.ASK, "ask"), (Side.BID, "bid")):
            snap = result.snapshots.get(side)
            prices = [a.price for a in snap.ads if a.advertiser.is_merchant] if snap else []
            if prices and key in market:
                market[key]["verified_best"] = _f(min(prices) if side is Side.ASK else max(prices))
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
            # Para que el panel recalcule escenarios con otro margen sin tocar Binance.
            "profiles": {k: {"methods": list(p.methods), "min_fiat": _f(p.min_fiat), "max_fiat": _f(p.max_fiat)}
                         for k, p in self._profiles.items()},
            "my_users": sorted(self._my_users),
            "merchants_only": self._merchants_only,
            "costs": {"maker_buy": _f(self.costs.maker_buy), "maker_sell": _f(self.costs.maker_sell),
                      "gmf": _f(self.costs.gmf), "gmf_worst": _f(self.costs.gmf_worst), "min_margin": _f(self.costs.min_margin)},
            "my_ads": my_ads, "errors": result.errors, "alerts": result.alerts + out.notes,
            "today": None if out.today is None else {
                "day": out.today.day.isoformat(), "goal": _f(out.today.goal), "realized": _f(out.today.realized),
                "progress": _f(out.today.progress), "buys": out.today.buys, "sells": out.today.sells,
                "bought_fiat": _f(out.today.bought_fiat), "sold_fiat": _f(out.today.sold_fiat),
                "inventory_qty": _f(out.today.inventory_qty), "inventory_avg_cost": _f(out.today.inventory_avg_cost),
                "inventory_since": int(out.today.inventory_since.timestamp()) if out.today.inventory_since else None,
                "warnings": out.today.warnings,
            },
            "exempt": None if out.exempt is None else {
                "month": out.exempt.month, "cap": _f(out.exempt.cap), "used": _f(out.exempt.used),
                "remaining": _f(out.exempt.remaining), "ratio": _f(out.exempt.ratio), "orders": out.exempt.orders,
                "accounts": list(out.exempt.accounts), "exceeded": out.exempt.exceeded,
            },
        }

    def write_state(self, result: CycleResult, out: AdvisorOutput, now_ts: int) -> None:
        path = self._state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state(result, out, now_ts), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)  # el panel nunca lee un archivo a medio escribir
