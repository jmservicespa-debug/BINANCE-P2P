"""CLI de negocio — FASES 4 y 5: órdenes, rentabilidad, competencia y precios.

  jmcambios-negocio sincronizar            # descarga tu historial de órdenes (últimos 6 meses) a la base
  jmcambios-negocio costos                 # comisiones reales cobradas por Binance (maker/taker)
  jmcambios-negocio rentabilidad           # beneficio realizado/estimado, precios efectivos, rotación
  jmcambios-negocio competencia            # posición de tus anuncios y precios límite rentables
  jmcambios-negocio presion                # presión del mercado (alcista/bajista) con confianza — FASE 5
  jmcambios-negocio recomendar             # 3 escenarios de precio para tus anuncios — FASE 5

Solo lectura: nada de esto modifica anuncios ni órdenes.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from jmcambios.analysis.competition import (
    AdPosition,
    max_profitable_buy_price,
    min_profitable_sell_price,
    position,
)
from jmcambios.analysis import pressure
from jmcambios.analysis.crossing import parse_my_methods
from jmcambios.analysis.liquidity import hourly_profile
from jmcambios.analysis.pressure import PressureReport
from jmcambios.config import Mode, Settings, effective_mode
from jmcambios.connectors.binance.account import BinanceAccount
from jmcambios.connectors.binance.client import BinanceP2PClient
from jmcambios.connectors.binance.market import BinanceMarketSource, MarketDataError
from jmcambios.domain import Side
from jmcambios.domain.account import MyAd, OrderSide
from jmcambios.logging_utils import setup_logging
from jmcambios.monitor.report import BOGOTA, money, pct
from jmcambios.profitability.calculator import ProfitReport, calculate
from jmcambios.pricing.engine import DEFAULT_LIMITS, AdProfile, Costs, SidePrice, daily_goal, maker_fees, profile_for
from jmcambios.pricing.engine import plan as pricing_plan
from jmcambios.profitability.costs import CostConfig, fraction
from jmcambios.storage.history import HistoryStore

COT_DAY = timedelta(days=1)


def pct3(value: Decimal | None) -> str:
    return "—" if value is None else f"{money(value * 100, 3)}%"


def _dec(text: str | None, name: str) -> Decimal | None:
    if text is None:
        return None
    t = text.strip().replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        return Decimal(t)
    except InvalidOperation as exc:
        raise SystemExit(f"{name} inválido: {text}") from exc


def _date(text: str | None) -> datetime | None:
    if not text:
        return None
    d = datetime.strptime(text, "%Y-%m-%d")
    return d.replace(tzinfo=BOGOTA).astimezone(UTC)


def _client(settings: Settings) -> BinanceP2PClient:
    if not settings.has_read_credentials:
        raise SystemExit("Falta la API key de solo lectura. Ejecuta: python -m jmcambios.tools.set_keys")
    return BinanceP2PClient(settings, allow_write=False)


def _cfg(settings: Settings, args: argparse.Namespace) -> CostConfig:
    capital = _dec(getattr(args, "capital", None), "--capital")
    rate = _dec(getattr(args, "tasa_oportunidad", None), "--tasa-oportunidad")
    return CostConfig(
        gmf_by_account=parse_my_methods(settings.my_pay_methods),
        cost_per_order=_dec(getattr(args, "costo_orden", None), "--costo-orden") or Decimal("0"),
        capital=capital,
        opportunity_rate_annual=(rate / 100 if rate is not None and rate > 1 else rate),
    )


# ------------------------------------------------------------------------ comandos
def cmd_sincronizar(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    since = datetime.now(UTC) - timedelta(days=args.dias)
    print(f"Descargando órdenes desde {since.astimezone(BOGOTA):%Y-%m-%d} (máx. 6 meses)…", flush=True)
    with _client(settings) as client:
        try:
            fetched = BinanceAccount(client).fetch_orders(since, on_progress=lambda m: print("  " + m, flush=True))
        except MarketDataError as exc:
            print(f"✘ {exc}")
            if "AUTH_ERROR" in str(exc):
                print("  Revisa si cambió tu IP pública y actualízala en Binance → Gestión de API.")
            return 1
    new, updated = store.upsert_orders(fetched.orders, int(datetime.now(UTC).timestamp()))
    by_fiat: dict[str, int] = defaultdict(int)
    for o in fetched.orders:
        by_fiat[o.fiat] += 1
    print(f"\nÓrdenes descargadas: {len(fetched.orders)} · nuevas: {new} · actualizadas: {updated} · ilegibles: {fetched.rejected}")
    print("Por moneda: " + ", ".join(f"{k} {v}" for k, v in sorted(by_fiat.items(), key=lambda kv: -kv[1])))
    print(f"Consultas a Binance: {fetched.requests}")
    return 0


def cmd_costos(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    orders = [o for o in store.load_orders(fiat=args.fiat or None) if o.completed]
    if not orders:
        print("No hay órdenes guardadas. Ejecuta primero: jmcambios-negocio sincronizar")
        return 1
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for o in orders:
        groups[(o.role or "¿?", o.side.value)].append(o)
    scope = args.fiat or "todas las monedas"
    print(f"Comisiones cobradas por Binance en órdenes completadas ({scope}) [Binance]\n")
    print(f"  {'Rol':<7}{'Lado':<6}{'Órdenes':>9}{'Con comisión':>14}{'Tasa prom.':>12}{'Comisión/cantidad':>19}")
    for (role, side), items in sorted(groups.items()):
        with_c = [o for o in items if o.commission is not None]
        rates = [fraction(o.commission_rate) for o in with_c if o.commission_rate is not None]
        avg_rate = sum(rates) / len(rates) if rates else None
        qty = sum((o.qty for o in with_c), Decimal(0))
        comm = sum((o.commission for o in with_c), Decimal(0))
        eff = comm / qty if qty else None
        print(
            f"  {role:<7}{side:<6}{len(items):>9}{len(with_c):>14}{pct3(avg_rate):>12}{pct3(eff):>19}"
        )
    print("\nRol: MAKER = la orden entró por tu anuncio; TAKER = tomaste el anuncio de otro.")
    print("'Comisión/cantidad' es lo realmente cobrado (comisión ÷ cantidad); 'Tasa prom.' es la tasa que informa Binance.")
    return 0


def _print_report(
    rep: ProfitReport, cfg: CostConfig, market_bid: Decimal | None, worst: ProfitReport, best: ProfitReport
) -> None:
    f = rep.fiat
    start = rep.start.astimezone(BOGOTA).strftime("%Y-%m-%d") if rep.start else "inicio"
    end = (rep.end.astimezone(BOGOTA) - timedelta(seconds=1)).strftime("%Y-%m-%d") if rep.end else "hoy"
    print(f"Rentabilidad {rep.asset}/{f} · {start} → {end} (hora Colombia)\n")
    print("  COMPRAS [Binance]")
    print(f"    órdenes: {rep.buys} · {money(rep.bought_qty_gross)} {rep.asset} · pagado {money(rep.bought_fiat, 0)} {f}")
    print(f"    comisión: {money(rep.buy_commission_qty, 4)} {rep.asset} · 4x1000 [estimado]: {money(rep.gmf, 0)} {f}")
    print(f"    precio efectivo de adquisición [cálculo]: {money(rep.effective_buy_price)} {f}/{rep.asset}")
    print("  VENTAS [Binance]")
    print(f"    órdenes: {rep.sells} · {money(rep.sold_qty)} {rep.asset} · recibido {money(rep.sold_fiat, 0)} {f}")
    print(f"    comisión: {money(rep.sell_commission_qty, 4)} {rep.asset}")
    print(f"    precio efectivo de venta [cálculo]: {money(rep.effective_sell_price)} {f}/{rep.asset}")
    print("  RESULTADO [cálculo]")
    print(f"    {rep.asset} vendidos con costo conocido: {money(rep.realized_qty)}")
    print(f"    margen bruto por {rep.asset}: {money(rep.gross_margin_per_unit)} {f}")
    print(f"    beneficio REALIZADO: {money(rep.realized, 0)} {f}"
          f"   (rango según 4x1000: {money(worst.realized, 0)} a {money(best.realized, 0)})")
    if rep.operating_costs:
        print(f"    costos operativos: −{money(rep.operating_costs, 0)} {f} → beneficio neto {money(rep.net_realized, 0)} {f}")
    if cfg.capital:
        print(f"    capital: {money(cfg.capital, 0)} {f} · rentabilidad sobre capital: {money(rep.roc_pct(cfg.capital), 3)}%"
              f" · rotación: {money(rep.turnover(cfg.capital), 2)} veces")
    print(f"    beneficio por hora: {money(rep.profit_per_hour(), 0)} {f}/h")
    opp = rep.opportunity_cost(cfg.capital, cfg.opportunity_rate_annual)
    if opp is not None:
        print(f"    costo de oportunidad del capital (indicador aparte): {money(opp, 0)} {f}")
    print("  INVENTARIO ABIERTO")
    print(f"    {money(rep.inventory_qty)} {rep.asset} · costo promedio {money(rep.inventory_avg_cost)} {f}")
    est = rep.estimated_inventory_value(market_bid)
    if est is not None:
        print(f"    beneficio ESTIMADO si se vendiera hoy a {money(market_bid)} [estimación]: {money(est, 0)} {f}")
    if rep.not_completed:
        print(f"  Órdenes no completadas (canceladas/en curso) excluidas: {rep.not_completed}")
    for w in rep.warnings:
        print(f"  ⚠ {w}")
    if rep.by_day:
        print("\n  Por día (hora Colombia)")
        print(f"    {'Día':<12}{'Compras':>8}{'Ventas':>8}{'Comprado ' + f:>18}{'Vendido ' + f:>18}{'Realizado':>14}")
        for d in rep.by_day[-31:]:
            print(f"    {d.day.isoformat():<12}{d.buys:>8}{d.sells:>8}{money(d.bought_fiat, 0):>18}"
                  f"{money(d.sold_fiat, 0):>18}{money(d.realized, 0):>14}")
    print("\nREALIZADO = ciclos cerrados con costo conocido. ESTIMADO = inventario a precio de mercado.")
    print("POTENCIAL = lo calculará el motor de precios (Fase 5). La comisión se toma en unidades del activo.")


def _latest_market_bid(store: HistoryStore, settings: Settings) -> Decimal | None:
    ts = store.latest_ts("binance_p2p", f"{settings.asset}/{settings.fiat}")
    if ts is None:
        return None
    row = store.snapshot_at("binance_p2p", f"{settings.asset}/{settings.fiat}", Side.BID, ts)
    return Decimal(str(row["best_price"])) if row and row["best_price"] is not None else None


def cmd_rentabilidad(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    fiat = args.fiat or settings.fiat
    cfg = _cfg(settings, args)
    start = _date(args.desde) or (datetime.now(UTC) - timedelta(days=args.dias))
    end = (_date(args.hasta) + COT_DAY) if args.hasta else datetime.now(UTC)
    orders = store.load_orders(fiat=fiat, asset=settings.asset)
    if not orders:
        print(f"No hay órdenes en {fiat}. Ejecuta primero: jmcambios-negocio sincronizar")
        return 1
    kw = dict(fiat=fiat, asset=settings.asset, start=start, end=end)
    rep = calculate(orders, cfg, **kw)
    worst = calculate(orders, cfg, gmf_mode="maximo", **kw)  # todo pagado con 4x1000
    best = calculate(orders, cfg, gmf_mode="minimo", **kw)  # todo pagado desde cuentas exentas
    _print_report(rep, cfg, _latest_market_bid(store, settings) if fiat == settings.fiat else None, worst, best)
    return 0


def _print_position(p: AdPosition) -> None:
    a = p.ad
    kind = "COMPRA" if a.side is OrderSide.BUY else "VENTA"
    state = {1: "en línea", 3: "fuera de línea", 4: "cerrado"}.get(a.status or 0, f"estado {a.status}")
    print(f"\n  Mi anuncio de {kind} {a.ad_id[-6:]} · {state} · precio {money(a.price)} · disponible {money(a.available_qty)} {a.asset}")
    print(f"    límites {money(a.min_fiat, 0)}–{money(a.max_fiat, 0)} {a.fiat} · métodos: {', '.join(a.payment_methods)}")
    print(f"    posición estimada: #{p.estimated_rank} de {p.total_competitors + 1}"
          f" · por delante: {p.better_count} anuncios ({money(p.qty_ahead, 0)} {a.asset}), {p.compatible_ahead} compatibles contigo"
          + (f" · empatados: {p.tied_count}" if p.tied_count else ""))
    print(f"    mejor precio del lado: {money(p.best_price)} · distancia: {money(p.gap_to_best)} ({money(p.gap_to_best_pct, 3)}%)"
          f" · mediana: {money(p.median_price)}")
    print(f"    competidores a ±0,5% de tu precio: {p.near_count} ({money(p.near_qty, 0)} {a.asset})")
    if p.gap_to_best is not None and p.gap_to_best < 0:
        what = "vendes más barato" if a.side is OrderSide.SELL else "pagas más caro"
        print(f"    ⚠ {what} que el mejor anuncio del mercado por {money(-p.gap_to_best)} {a.fiat}/{a.asset}: "
              f"estarías regalando margen. Para quedar de primero basta igualar o mejorar por poco el {money(p.best_price)}.")
    if p.ahead:
        print("    Justo por delante de ti:")
        for c in p.ahead:
            tag = "compatible" if c.compatible else "otro segmento"
            print(f"      - {c.nickname}: {money(c.price)} · {money(c.qty, 0)} {a.asset} · {c.month_orders or '—'} órdenes/30d"
                  f" · {pct(c.finish_rate)} · {tag}")
    if p.top_active:
        print("    Más activos cerca de tu precio (órdenes en 30 días):")
        for c in p.top_active:
            print(f"      - {c.nickname}: {c.month_orders} órdenes · {money(c.price)} · {money(c.qty, 0)} {a.asset}")


def _maker_fees(store: HistoryStore, my_ads: list[MyAd], settings: Settings) -> dict[OrderSide, tuple[Decimal, str]]:
    return maker_fees(store.load_orders(), my_ads, settings.fiat)


def cmd_competencia(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    min_margin = (_dec(args.margen_min, "--margen-min") or settings.min_margin_pct) / 100
    cfg = _cfg(settings, args)
    with _client(settings) as client:
        try:
            my_ads = [a for a in BinanceAccount(client).fetch_my_ads() if a.fiat == settings.fiat and a.asset == settings.asset]
            source = BinanceMarketSource(client, settings)
            books = {side: source.fetch(side) for side in (Side.ASK, Side.BID)}
        except MarketDataError as exc:
            print(f"✘ {exc}")
            return 1
    best_ask = min((a.price for a in books[Side.ASK].ads), default=None)
    best_bid = max((a.price for a in books[Side.BID].ads), default=None)
    print(f"Competencia {settings.asset}/{settings.fiat} · {datetime.now(UTC).astimezone(BOGOTA):%Y-%m-%d %H:%M} (hora Colombia)")
    print("  Competencia: " + ("solo comerciantes verificados (JMC_SOLO_VERIFICADOS=true)" if settings.merchants_only
                                  else "todos los anunciantes (JMC_SOLO_VERIFICADOS=false)"))
    print(f"  Mercado [Binance]: mejor venta {money(best_ask)} · mejor compra {money(best_bid)}")
    if not my_ads:
        print(f"\n  No tienes anuncios en {settings.fiat}. Puedes crear uno con los precios límite de abajo.")
    my_ids = {a.ad_id for a in my_ads}
    my_users = {ad.advertiser.user_id for snap in books.values() for ad in snap.ads if ad.ad_id in my_ids}
    for ad in my_ads:
        _print_position(position(ad, books[Side.BID if ad.side is OrderSide.BUY else Side.ASK].ads, my_users,
                                 settings.merchants_only))

    # Precios límite [cálculo]: comisión maker OBSERVADA por lado; si no hay, la tasa de tus anuncios.
    fee_src = _maker_fees(store, my_ads, settings)
    maker_buy, maker_sell = fee_src[OrderSide.BUY][0], fee_src[OrderSide.SELL][0]
    sell_ref = next((a.price for a in my_ads if a.side is OrderSide.SELL and a.online), best_ask)
    gmf_low = min(cfg.gmf_by_account.values(), default=Decimal("0"))
    gmf_high = max([*cfg.gmf_by_account.values(), cfg.default_gmf])
    print(f"\n  PRECIOS LÍMITE [cálculo] · margen mínimo {money(min_margin * 100, 2)}%")
    print(f"    comisión maker al comprar {pct3(maker_buy)} ({fee_src[OrderSide.BUY][1]})"
          f" · al vender {pct3(maker_sell)} ({fee_src[OrderSide.SELL][1]})")
    if sell_ref is not None:
        for label, g in (("pagando desde cuenta exenta", gmf_low), ("pagando con 4x1000", gmf_high)):
            p = max_profitable_buy_price(sell_ref, gmf=g, buy_commission=maker_buy, sell_commission=maker_sell, min_margin=min_margin)
            print(f"    Comprar como máximo a {money(p)} si vendes a {money(sell_ref)} ({label}, 4x1000 {pct3(g)})")
    orders = store.load_orders(fiat=settings.fiat, asset=settings.asset)
    rep = calculate(orders, cfg, fiat=settings.fiat, asset=settings.asset, start=datetime.now(UTC) - timedelta(days=30))
    bases = []
    if rep.inventory_avg_cost is not None:
        bases.append(("costo promedio de tus USDT comprados en COP (30 días)", rep.inventory_avg_cost))
    if best_bid is not None:
        for label, g in (("cuenta exenta", gmf_low), ("con 4x1000", gmf_high)):
            # Reponer comprando con mi anuncio al mejor precio de compra actual.
            bases.append((f"reponer hoy al mejor precio de compra, {label}", best_bid * (1 + g) / (1 - maker_buy)))
    for basis, cost in bases:
        p = min_profitable_sell_price(cost, sell_commission=maker_sell, min_margin=min_margin)
        print(f"    Vender como mínimo a {money(p)} ({basis}: costo {money(cost)})")
    fees_cycle = maker_buy + maker_sell
    print(f"    Costos de un ciclo compra+venta: comisión ≈ {pct3(fees_cycle)} + 4x1000 {pct3(gmf_low)}–{pct3(gmf_high)}"
          f" → diferencia mínima entre compra y venta ≈ {pct3(fees_cycle + min_margin + gmf_low)}–{pct3(fees_cycle + min_margin + gmf_high)}")
    print("\n  Posición = estimación por precio; Binance también ordena por otros criterios.")
    return 0


# ------------------------------------------------------------------ Fase 5
VENUE = "binance_p2p"
DEFAULT_GOAL = Decimal("127000")  # ≈ 40 USD/día
MIN_HOUR_CYCLES = 10


def _print_pressure(rep: PressureReport) -> None:
    age = f" · datos de hace {rep.data_age_s // 60} min" if rep.data_age_s is not None else ""
    print(f"  PRESIÓN DEL MERCADO [cálculo]: {rep.label} · puntaje {rep.score:+.0f} (−100 a +100)"
          f" · confianza {rep.confidence}/100{age}")
    if rep.windows:
        print(f"    ventanas analizadas: {', '.join(f'{m} min' for m in rep.windows)}")
    for side, act in rep.sides.items():
        who = "Vendedores (anuncios de venta)" if side is Side.ASK else "Compradores (anuncios de compra)"
        qty = f"{fmt_signed(act.announced_qty_pct, 1)} %" if act.announced_qty_pct is not None else "—"
        dp = fmt_signed(act.best_price_delta) if act.best_price_delta is not None else "—"
        print(f"    {who}, últimos {act.window_min} min: mejor precio {dp} COP [observado] · liquidez {qty} [observado]"
              f" · nuevos {act.ads_appeared} / retirados {act.ads_disappeared} / cambiaron precio {act.repriced} [observado]"
              f" · posibles ejecuciones {money(Decimal(str(act.possible_executed_qty)), 0)} USDT [inferido]")
    strongest = sorted((s for s in rep.signals if abs(s.direction) > 0.05), key=lambda s: -abs(s.direction) * s.weight)[:5]
    if strongest:
        print("    Señales más fuertes:")
        for sg in strongest:
            arrow = "↑" if sg.direction > 0 else "↓"
            print(f"      {arrow} {sg.name} ({sg.window_min} min): {sg.detail} [{sg.provenance}]")
    for u in rep.unverifiable:
        print(f"    · {u} [no verificable]")
    for n in rep.notes:
        print(f"    ⚠ {n}")


def cmd_presion(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    rep = pressure.analyze(store, VENUE, f"{settings.asset}/{settings.fiat}", int(datetime.now(UTC).timestamp()))
    print(f"Presión {settings.asset}/{settings.fiat} · {datetime.now(UTC).astimezone(BOGOTA):%Y-%m-%d %H:%M} (hora Colombia)\n")
    _print_pressure(rep)
    print("\n  Alcista = el precio del USDT tiende a subir (conviene comprar antes); bajista = tiende a bajar (conviene vender antes).")
    print("  Es una lectura de corto plazo, no una predicción garantizada.")
    return 0


def fmt_signed(x: float, decimals: int = 2) -> str:
    return ("+" if x >= 0 else "−") + money(Decimal(str(abs(x))), decimals)


def _print_best_hours(store: HistoryStore, market: str) -> None:
    """Horas (Colombia) con mayor diferencial promedio en el historial, para el tipo de día de hoy."""
    today = "fin de semana" if datetime.now(UTC).astimezone(BOGOTA).weekday() >= 5 else "hábil"
    rows = [r for r in hourly_profile(store, VENUE, market) if r.day_type == today and r.cycles >= MIN_HOUR_CYCLES
            and r.avg_spread is not None]
    if not rows:
        return
    top = sorted(rows, key=lambda r: -r.avg_spread)[:3]
    print(f"\n  Horas con mayor diferencial en días tipo '{today}' [historial]: "
          + " · ".join(f"{r.hour:02d}h {money(Decimal(str(r.avg_spread)))} COP" for r in top)
          + "  → mejores momentos para tener los dos anuncios activos")


def _profile(ad: MyAd | None, methods: dict[str, Decimal]) -> AdProfile:
    return profile_for(ad, methods, DEFAULT_LIMITS)


def _side_line(sp: SidePrice, asset: str) -> str:
    kind = "Comprar" if sp.side is OrderSide.BUY else "Vender "
    extra = f" (competitivo {money(sp.competitive_price)}, movido para proteger el margen)" if sp.adjusted else ""
    comp = (f"#{sp.rank_compatible} de {sp.compatible_total} compatibles" if sp.rank_compatible <= sp.compatible_total
            else f"detrás de los {sp.compatible_total} compatibles")
    return (f"{kind} a {money(sp.price)} → puesto ≈ #{sp.rank} · {comp}"
            f" · {money(sp.qty_ahead, 0)} {asset} por delante{extra}")


def cmd_recomendar(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    mode, _ = effective_mode(settings)
    min_margin = (_dec(args.margen_min, "--margen-min") or settings.min_margin_pct) / 100
    cfg = _cfg(settings, args)
    goal = _dec(args.meta, "--meta") or DEFAULT_GOAL
    market = f"{settings.asset}/{settings.fiat}"
    with _client(settings) as client:
        try:
            my_ads = [a for a in BinanceAccount(client).fetch_my_ads() if a.fiat == settings.fiat and a.asset == settings.asset]
            source = BinanceMarketSource(client, settings)
            books = {side: source.fetch(side) for side in (Side.ASK, Side.BID)}
        except MarketDataError as exc:
            print(f"✘ {exc}")
            return 1
    now = datetime.now(UTC)
    my_ids = {a.ad_id for a in my_ads}
    my_users = {ad.advertiser.user_id for snap in books.values() for ad in snap.ads if ad.ad_id in my_ids}
    fees = _maker_fees(store, my_ads, settings)
    gmf_low = min(cfg.gmf_by_account.values(), default=Decimal("0"))
    gmf_high = max([*cfg.gmf_by_account.values(), cfg.default_gmf])
    costs = Costs(maker_buy=fees[OrderSide.BUY][0], maker_sell=fees[OrderSide.SELL][0],
                  gmf=gmf_low, gmf_worst=gmf_high, min_margin=min_margin)
    my_buy = next((a for a in my_ads if a.side is OrderSide.BUY), None)
    my_sell = next((a for a in my_ads if a.side is OrderSide.SELL), None)
    press = pressure.analyze(store, VENUE, market, int(now.timestamp()))
    pp = pricing_plan(
        books[Side.ASK].ads, books[Side.BID].ads,
        buy_profile=_profile(my_buy, cfg.gmf_by_account), sell_profile=_profile(my_sell, cfg.gmf_by_account),
        costs=costs, pressure=press, exclude_users=my_users, merchants_only=settings.merchants_only,
    )

    print(f"Escenarios de precio {market} · {now.astimezone(BOGOTA):%Y-%m-%d %H:%M} (hora Colombia)")
    print("  Competencia: " + ("solo comerciantes verificados (JMC_SOLO_VERIFICADOS=true)" if settings.merchants_only
                                  else "todos los anunciantes (JMC_SOLO_VERIFICADOS=false)"))
    print(f"  Mercado [Binance]: mejor venta {money(pp.best_ask)} · mejor compra {money(pp.best_bid)}")
    print(f"  Costos [cálculo]: comisión maker compra {pct3(costs.maker_buy)} · venta {pct3(costs.maker_sell)}"
          f" · 4x1000 {pct3(gmf_low)} (cuenta exenta) / {pct3(gmf_high)} · margen mínimo {money(min_margin * 100, 2)}%")
    for side, snap in books.items():
        if not snap.complete:
            pp.warnings.append(f"{side.label_es}: libro incompleto — los puestos pueden estar subestimados")
    print()
    _print_pressure(press)

    print(f"\n  ESCENARIOS [cálculo] · se paga desde la cuenta exenta; entre paréntesis, margen pagando con 4x1000")
    names = {"conservador": "CONSERVADOR (más margen, menos órdenes)",
             "equilibrado": "EQUILIBRADO",
             "agresivo": "AGRESIVO (primer puesto, menos margen)"}
    for sc in pp.scenarios:
        qty, rot = daily_goal(sc.net_per_unit, goal, sc.buy.price, cfg.capital)
        print(f"\n    {names[sc.name]} · objetivo: puesto #{sc.target_rank} entre compatibles"
              f" con margen ≥ {pct3(sc.target_margin)}")
        print(f"      {_side_line(sc.buy, settings.asset)}")
        print(f"      {_side_line(sc.sell, settings.asset)}")
        print(f"      margen neto del ciclo: {pct3(sc.margin)} ({pct3(sc.margin_worst)})"
              f" · ganancia ≈ {money(sc.net_per_unit)} {settings.fiat} por {settings.asset} vendido")
        meta = f"      para la meta de {money(goal, 0)} {settings.fiat}/día: rotar ≈ {money(qty, 0)} {settings.asset}/día"
        if rot is not None:
            meta += f" = {money(rot, 1)} veces tu capital"
        print(meta)

    rep = calculate(store.load_orders(fiat=settings.fiat, asset=settings.asset), cfg,
                    fiat=settings.fiat, asset=settings.asset, start=now - timedelta(days=30))
    if rep.inventory_qty > 0 and rep.inventory_avg_cost is not None:
        floor = min_profitable_sell_price(rep.inventory_avg_cost, sell_commission=costs.maker_sell, min_margin=min_margin)
        print(f"\n  Inventario según tus órdenes COP de 30 días: {money(rep.inventory_qty)} {settings.asset}"
              f" a costo {money(rep.inventory_avg_cost)} → venderlo con ganancia exige ≥ {money(floor)}"
              " (si esos USDT ya salieron por otra vía, ignóralo)")
    if any(sc.margin_worst < 0 for sc in pp.scenarios):
        pp.warnings.append("pagando desde Bancolombia/Nequi algún escenario PIERDE dinero: paga desde Davivienda/Daviplata")
    if pp.scenarios and pp.scenarios[-1].buy.adjusted and pp.scenarios[-1].sell.adjusted:
        pp.warnings.append("con el margen mínimo no se puede estar de primero en compra y venta a la vez: "
                           "el diferencial del mercado es menor que tus costos + margen")
    _print_best_hours(store, market)
    for wmsg in pp.warnings:
        print(f"  ⚠ {wmsg}")

    if mode is Mode.OBSERVATION:
        print("\n  Modo OBSERVACIÓN: solo se muestran escenarios. Para recibir recomendaciones pon JMC_MODE=RECOMMENDATION en .env")
    else:
        bal = next(sc for sc in pp.scenarios if sc.name == "equilibrado")
        why = {"comprar": "presión alcista con confianza suficiente: prioriza COMPRAR (se cede margen en la venta)",
               "vender": "presión bajista con confianza suficiente: prioriza VENDER (se cede margen en la compra)",
               "equilibrado": "sin señal clara de presión: margen repartido entre compra y venta"}[pp.priority]
        print(f"\n  RECOMENDACIÓN [modo {mode.value}] · escenario equilibrado · {why}")
        for mine, target in ((my_buy, bal.buy), (my_sell, bal.sell)):
            kind = "COMPRA" if target.side is OrderSide.BUY else "VENTA"
            if mine is None:
                print(f"    Anuncio de {kind}: no tienes; podrías crearlo a {money(target.price)}")
            elif mine.price == target.price:
                print(f"    Anuncio de {kind} {mine.ad_id[-6:]}: ya está en {money(mine.price)}, sin cambios")
            else:
                print(f"    Anuncio de {kind} {mine.ad_id[-6:]}: cambiar {money(mine.price)} → {money(target.price)}")
        print("    Nada se modifica en Binance: tú decides y lo cambias en la app.")
    print("\n  Puesto = estimación por precio; Binance también ordena por otros criterios. Sin garantía de ejecución.")
    return 0


COMMANDS = {
    "sincronizar": cmd_sincronizar,
    "costos": cmd_costos,
    "rentabilidad": cmd_rentabilidad,
    "competencia": cmd_competencia,
    "presion": cmd_presion,
    "recomendar": cmd_recomendar,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Órdenes, rentabilidad, competencia y precios (Fases 4–5, solo lectura)")
    p.add_argument("comando", choices=list(COMMANDS))
    p.add_argument("--db", default="data/history.db")
    p.add_argument("--dias", type=int, default=30, help="Días hacia atrás (sincronizar: hasta 180)")
    p.add_argument("--desde", help="rentabilidad: fecha inicial AAAA-MM-DD (hora Colombia)")
    p.add_argument("--hasta", help="rentabilidad: fecha final AAAA-MM-DD, incluida")
    p.add_argument("--fiat", help="Moneda (por defecto la de JMC_FIAT; costos: todas)")
    p.add_argument("--capital", help="Capital operativo, p. ej. 10.000.000")
    p.add_argument("--costo-orden", help="Costo operativo atribuible por orden completada")
    p.add_argument("--tasa-oportunidad", help="Costo de oportunidad anual en %%, p. ej. 10")
    p.add_argument("--margen-min", help="competencia/recomendar: margen mínimo en %%, p. ej. 1 (por defecto JMC_MARGEN_MIN)")
    p.add_argument("--meta", help="recomendar: meta de ganancia diaria en COP (por defecto 127.000)")
    args = p.parse_args(argv)
    if args.comando == "sincronizar" and args.dias == 30:
        args.dias = 180
    settings = Settings()
    secrets = [s.get_secret_value() for s in (settings.api_key, settings.api_secret) if s]
    setup_logging(logging.WARNING, secrets)
    with HistoryStore(args.db) as store:
        return COMMANDS[args.comando](store, args, settings)


if __name__ == "__main__":
    sys.exit(main())
