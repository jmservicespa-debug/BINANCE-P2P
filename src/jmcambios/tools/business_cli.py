"""CLI de negocio — FASE 4: órdenes, rentabilidad real y competencia.

  jmcambios-negocio sincronizar            # descarga tu historial de órdenes (últimos 6 meses) a la base
  jmcambios-negocio costos                 # comisiones reales cobradas por Binance (maker/taker)
  jmcambios-negocio rentabilidad           # beneficio realizado/estimado, precios efectivos, rotación
  jmcambios-negocio competencia            # posición de tus anuncios y precios límite rentables

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
from jmcambios.analysis.crossing import parse_my_methods
from jmcambios.config import Settings
from jmcambios.connectors.binance.account import BinanceAccount
from jmcambios.connectors.binance.client import BinanceP2PClient
from jmcambios.connectors.binance.market import BinanceMarketSource, MarketDataError
from jmcambios.domain import Side
from jmcambios.domain.account import OrderSide
from jmcambios.logging_utils import setup_logging
from jmcambios.monitor.report import BOGOTA, money, pct
from jmcambios.profitability.calculator import ProfitReport, calculate
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


def cmd_competencia(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    min_margin = (_dec(args.margen_min, "--margen-min") or Decimal("0.3")) / 100
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
    print(f"  Mercado [Binance]: mejor venta {money(best_ask)} · mejor compra {money(best_bid)}")
    if not my_ads:
        print(f"\n  No tienes anuncios en {settings.fiat}. Puedes crear uno con los precios límite de abajo.")
    my_ids = {a.ad_id for a in my_ads}
    my_users = {ad.advertiser.user_id for snap in books.values() for ad in snap.ads if ad.ad_id in my_ids}
    for ad in my_ads:
        _print_position(position(ad, books[Side.BID if ad.side is OrderSide.BUY else Side.ASK].ads, my_users))

    # Precios límite [cálculo]
    maker_rates = [fraction(a.commission_rate) for a in my_ads if a.commission_rate is not None]
    maker = max(maker_rates) if maker_rates else Decimal("0")
    sell_ref = next((a.price for a in my_ads if a.side is OrderSide.SELL and a.online), best_ask)
    gmf_low = min(cfg.gmf_by_account.values(), default=Decimal("0"))
    gmf_high = max([*cfg.gmf_by_account.values(), cfg.default_gmf])
    print(f"\n  PRECIOS LÍMITE [cálculo] · margen mínimo {money(min_margin * 100, 2)}% · comisión maker {pct3(maker)}"
          + ("" if maker_rates else " (sin dato: se usa 0)"))
    if sell_ref is not None:
        for label, g in (("pagando desde cuenta exenta", gmf_low), ("pagando con 4x1000", gmf_high)):
            p = max_profitable_buy_price(sell_ref, gmf=g, buy_commission=maker, sell_commission=maker, min_margin=min_margin)
            print(f"    Comprar como máximo a {money(p)} si vendes a {money(sell_ref)} ({label}, 4x1000 {pct3(g)})")
    orders = store.load_orders(fiat=settings.fiat, asset=settings.asset)
    rep = calculate(orders, cfg, fiat=settings.fiat, asset=settings.asset, start=datetime.now(UTC) - timedelta(days=30))
    bases = []
    if rep.inventory_avg_cost is not None:
        bases.append(("costo promedio de tus USDT comprados en COP (30 días)", rep.inventory_avg_cost))
    if best_bid is not None:
        for label, g in (("cuenta exenta", gmf_low), ("con 4x1000", gmf_high)):
            # Reponer comprando con mi anuncio al mejor precio de compra actual.
            bases.append((f"reponer hoy al mejor precio de compra, {label}", best_bid * (1 + g) / (1 - maker)))
    for basis, cost in bases:
        p = min_profitable_sell_price(cost, sell_commission=maker, min_margin=min_margin)
        print(f"    Vender como mínimo a {money(p)} ({basis}: costo {money(cost)})")
    print(f"    Costos de un ciclo compra+venta: comisión ≈ {pct3(2 * maker)} + 4x1000 {pct3(gmf_low)}–{pct3(gmf_high)}"
          f" → diferencia mínima entre compra y venta ≈ {pct3(2 * maker + min_margin + gmf_low)}–{pct3(2 * maker + min_margin + gmf_high)}")
    print("\n  Posición = estimación por precio; Binance también ordena por otros criterios.")
    return 0


COMMANDS = {
    "sincronizar": cmd_sincronizar,
    "costos": cmd_costos,
    "rentabilidad": cmd_rentabilidad,
    "competencia": cmd_competencia,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Órdenes, rentabilidad y competencia (Fase 4, solo lectura)")
    p.add_argument("comando", choices=list(COMMANDS))
    p.add_argument("--db", default="data/history.db")
    p.add_argument("--dias", type=int, default=30, help="Días hacia atrás (sincronizar: hasta 180)")
    p.add_argument("--desde", help="rentabilidad: fecha inicial AAAA-MM-DD (hora Colombia)")
    p.add_argument("--hasta", help="rentabilidad: fecha final AAAA-MM-DD, incluida")
    p.add_argument("--fiat", help="Moneda (por defecto la de JMC_FIAT; costos: todas)")
    p.add_argument("--capital", help="Capital operativo, p. ej. 10.000.000")
    p.add_argument("--costo-orden", help="Costo operativo atribuible por orden completada")
    p.add_argument("--tasa-oportunidad", help="Costo de oportunidad anual en %%, p. ej. 10")
    p.add_argument("--margen-min", help="competencia: margen mínimo en %%, p. ej. 0,3")
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
