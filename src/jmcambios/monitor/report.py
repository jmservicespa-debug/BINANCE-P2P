"""Presentación en consola de cada ciclo del monitor (formato colombiano)."""

from __future__ import annotations

from datetime import timedelta, timezone
from decimal import Decimal

from jmcambios.analysis.crossing import CrossReport
from jmcambios.analysis.filters import AdFilter
from jmcambios.analysis.market_stats import SideStats, Spread
from jmcambios.domain import Side
from jmcambios.monitor.service import CycleResult

# Colombia no tiene horario de verano: UTC-5 fijo (evita depender de tzdata en Windows).
BOGOTA = timezone(timedelta(hours=-5), "COT")


def money(value: Decimal | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(value: Decimal | None) -> str:
    return "—" if value is None else f"{money(value * 100, 1)}%"


def _side_block(title: str, s: SideStats, *, detail: bool) -> list[str]:
    lines = [
        f"  {title}",
        f"    [Binance] anuncios: {s.ads_count} · comerciantes: {s.merchants_count}",
        f"    [cálculo] mejor: {money(s.best_price)} · mediana: {money(s.median_price)} · "
        f"prom. ponderado: {money(s.vwap)} · rango: {money(s.min_price)} – {money(s.max_price)}",
        f"    [cálculo] liquidez ANUNCIADA: {money(s.announced_qty)} USDT (≈ {money(s.announced_fiat, 0)} COP) · "
        f"volumen ejecutado: no disponible",
    ]
    if s.depth_qty:
        depth = " · ".join(f"a {k.replace('.', ',')}: {money(v)}" for k, v in s.depth_qty.items())
        lines.append(f"    [cálculo] USDT anunciados cerca del mejor precio → {depth}")
    if s.top1_share is not None:
        lines.append(
            f"    [cálculo] concentración: top1 {pct(s.top1_share)} · top3 {pct(s.top3_share)} · "
            f"top5 {pct(s.top5_share)} · HHI {s.hhi}"
        )
    if detail and s.top_merchants:
        lines.append("    Principales comerciantes por liquidez anunciada:")
        for m in s.top_merchants[:5]:
            lines.append(f"      - {m.nickname or m.user_id[:8]}: {money(m.qty)} USDT ({pct(m.share)}) · mejor {money(m.best_price)} · {m.ads} anuncio(s)")
    if detail and s.by_method:
        top = list(s.by_method.items())[:6]
        lines.append("    Métodos de pago (anuncios · mejor precio): " + " · ".join(f"{k} {v.ads}·{money(v.best_price)}" for k, v in top))
    return lines


def _spread_line(label: str, sp: Spread | None) -> str:
    if sp is None:
        return f"  {label}: —"
    return f"  {label}: {money(sp.absolute)} COP ({money(sp.pct, 3)}%) · punto medio {money(sp.mid)}"


def _cross_lines(cross: CrossReport | None) -> list[str]:
    if cross is None or not cross.crossed:
        return []
    head = (
        f"  ◆ CRUCE DE PRECIOS [cálculo]: el mejor anuncio de venta está {money(cross.gross_spread)} COP "
        f"por debajo del mejor de compra"
    )
    lines = [head]
    best = cross.best
    if cross.executable and best is not None:
        lines.append(
            f"    ✔ Aprovechable con tus métodos: comprar a {money(best.buy_ad.price)} pagando por {best.pay_method} "
            f"(4x1000 {money(best.gmf_rate * 100, 1)}%) y vender a {money(best.sell_ad.price)} cobrando por {best.receive_method}"
        )
        lines.append(
            f"      neto ≈ {money(best.net_per_unit)} COP/USDT ({money(best.net_pct, 3)}%) · cantidad posible "
            f"{money(best.min_qty)}–{money(best.max_qty)} USDT · hasta ≈ {money(best.net_total_max, 0)} COP "
            f"(incluye la comisión taker observada en tus órdenes; el anuncio puede desaparecer antes de completar)"
        )
    else:
        reasons = ", ".join(f"{k} ({v})" for k, v in sorted(cross.rejected.items(), key=lambda kv: -kv[1])) or "sin pares"
        lines.append(f"    ✘ No aprovechable con tus métodos de pago: {reasons}")
    return lines


TITLES = {
    Side.ASK: "COMPRAR USDT — anuncios de venta (compiten con MIS anuncios de venta)",
    Side.BID: "VENDER USDT — anuncios de compra (compiten con MIS anuncios de compra)",
}


def render(result: CycleResult, ad_filter: AdFilter, *, detail: bool = True) -> str:
    ts = result.started_at.astimezone(BOGOTA)
    any_snap = next(iter(result.snapshots.values()), None)
    header = f"=== {ts:%Y-%m-%d %H:%M:%S} (hora Colombia) · USDT/COP"
    if any_snap:
        header += f" · {any_snap.venue} · fuente {any_snap.source}"
    lines = [header + " ==="]
    for side in (Side.ASK, Side.BID):
        if side in result.stats:
            lines += _side_block(TITLES[side], result.stats[side], detail=detail)
    lines.append(_spread_line("Diferencial entre mejores precios [cálculo]", result.spread))
    lines += _cross_lines(result.cross)

    if ad_filter.active:
        lines.append(f"  --- Con mis filtros ({ad_filter.describe()}) ---")
        for side in (Side.ASK, Side.BID):
            if side in result.filtered_stats:
                excluded = result.excluded.get(side) or {}
                lines += _side_block(TITLES[side], result.filtered_stats[side], detail=False)
                if excluded:
                    lines.append("    excluidos: " + ", ".join(f"{k} {v}" for k, v in excluded.items()))
        lines.append(_spread_line("Diferencial con filtros [cálculo]", result.filtered_spread))

    for alert in result.alerts:
        lines.append(f"  ⚠ {alert}")
    for err in result.errors:
        lines.append(f"  ✘ ERROR: {err}")
    return "\n".join(lines)
