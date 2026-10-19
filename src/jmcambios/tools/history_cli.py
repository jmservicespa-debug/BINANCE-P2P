"""CLI de la base histórica — FASE 3.

  jmcambios-history importar     # carga data/snapshots/*.jsonl.gz en la base (se puede repetir)
  jmcambios-history estado       # qué hay guardado
  jmcambios-history cambios      # cambios de liquidez en 5/15/30/60 min (último dato)
  jmcambios-history perfil       # promedios por hora del día, hábil vs fin de semana
  jmcambios-history cruces       # episodios de cruce de precios y si eran aprovechables
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from jmcambios.analysis.crossing import parse_my_methods
from jmcambios.analysis.liquidity import cross_episodes, hourly_profile, window_changes
from jmcambios.config import Settings
from jmcambios.domain import Side
from jmcambios.monitor.report import BOGOTA, money
from jmcambios.storage.history import HistoryStore
from jmcambios.storage.importer import import_directory

VENUE = "binance_p2p"


def _num(value: float | int | None, decimals: int = 2, signed: bool = False) -> str:
    if value is None:
        return "—"
    text = money(Decimal(str(value)), decimals)
    return f"+{text}" if signed and value > 0 else text


def _when(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC).astimezone(BOGOTA).strftime("%Y-%m-%d %H:%M")


def cmd_importar(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    directory = Path(args.data_dir)
    if not directory.exists():
        print(f"No existe {directory.resolve()}: ejecuta primero jmcambios-monitor.")
        return 1
    print("Importando… puede tardar unos minutos (no cierres la ventana).", flush=True)
    r = import_directory(
        store, directory, parse_my_methods(settings.my_pay_methods), progress=lambda m: print("  " + m, flush=True)
    )
    print(f"Archivos: {r.files} · registros leídos: {r.records} · nuevos: {r.inserted} · ya existían: {r.skipped}")
    print(f"Ciclos con análisis de cruce: {r.cycles} · líneas dañadas ignoradas: {r.bad_lines}")
    return 0


def cmd_estado(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    market = f"{settings.asset}/{settings.fiat}"
    c = store.counts()
    rng = store.query("SELECT MIN(taken_ts) a, MAX(taken_ts) b FROM snapshots WHERE venue=? AND market=?", (VENUE, market))[0]
    print(f"Base: {store.path.resolve()}")
    print(f"Snapshots: {c['snapshots']} · ciclos: {c['cycles']} · estados de anuncios: {c['ad_states']}")
    if rng["a"]:
        hours = (rng["b"] - rng["a"]) / 3600
        print(f"Desde {_when(rng['a'])} hasta {_when(rng['b'])} (hora Colombia) · {hours:.1f} h de datos")
    return 0


def cmd_cambios(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    market = f"{settings.asset}/{settings.fiat}"
    changes = window_changes(store, VENUE, market)
    if not any(changes.values()):
        print("Aún no hay datos suficientes (se necesitan al menos dos ciclos guardados).")
        return 1
    titles = {Side.ASK: "Anuncios de VENTA (donde compras USDT)", Side.BID: "Anuncios de COMPRA (donde vendes USDT)"}
    for side in (Side.ASK, Side.BID):
        rows = changes[side]
        if not rows:
            continue
        print(f"\n{titles[side]} — hasta {_when(rows[0].to_ts)} (hora Colombia)")
        print(f"  {'Ventana':<8}{'Mejor':>10}{'Mediana':>10}{'Anuncios':>10}{'Liquidez USDT':>16}{'Nuevos':>8}{'Retirados':>10}{'Cambian precio':>15}{'Posible ejecución*':>20}")
        for w in rows:
            print(
                f"  {str(w.minutes) + ' min':<8}{_num(w.best_price_delta, signed=True):>10}{_num(w.median_delta, signed=True):>10}"
                f"{_num(w.ads_count_delta, 0, signed=True):>10}{_num(w.announced_qty_delta, 0, signed=True):>16}"
                f"{w.ads_appeared:>8}{w.ads_disappeared:>10}{w.repriced:>15}{_num(w.qty_reduced_same_price, 0):>20}"
            )
            for n in w.notes:
                print(f"           nota: {n}")
    print("\n[Binance] diferencias observadas entre snapshots.")
    print("* INFERIDO: USDT que bajaron en anuncios sin cambio de precio. Puede ser una venta real o el anunciante")
    print("  reduciendo su anuncio; Binance no publica el volumen ejecutado de terceros.")
    return 0


def cmd_perfil(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    market = f"{settings.asset}/{settings.fiat}"
    since = int(datetime.now(UTC).timestamp()) - args.days * 86400 if args.days else None
    rows = hourly_profile(store, VENUE, market, since)
    if not rows:
        print("Aún no hay ciclos guardados.")
        return 1
    current = None
    for r in rows:
        if r.day_type != current:
            current = r.day_type
            label = "Días hábiles" if current == "hábil" else "Fin de semana"
            print(f"\n{label} (hora Colombia) — promedios [cálculo]")
            print(f"  {'Hora':<6}{'Ciclos':>7}{'Dif. prom':>11}{'Dif. mín':>10}{'% cruce':>9}{'% aprov.':>10}{'Venta prom':>12}{'Compra prom':>13}{'Anunc. V/C':>12}")
        print(
            f"  {r.hour:02d}:00{r.cycles:>7}{_num(r.avg_spread):>11}{_num(r.min_spread):>10}{_num(r.crossed_pct, 0):>8}%"
            f"{_num(r.executable_pct, 0):>9}%{_num(r.avg_ask_best):>12}{_num(r.avg_bid_best):>13}"
            f"{_num(r.avg_ask_ads, 0) + '/' + _num(r.avg_bid_ads, 0):>12}"
        )
    print("\nDif. = mejor venta − mejor compra (negativo = cruce). '% aprov.' = cruces aprovechables con tus métodos de pago.")
    print("Pocos ciclos en una hora = resultado poco fiable. Los festivos todavía se cuentan como días hábiles.")
    return 0


def cmd_cruces(store: HistoryStore, args: argparse.Namespace, settings: Settings) -> int:
    market = f"{settings.asset}/{settings.fiat}"
    episodes = cross_episodes(store, VENUE, market)
    total = store.query("SELECT COUNT(*) n FROM cycles WHERE venue=? AND market=?", (VENUE, market))[0]["n"]
    if not episodes:
        print(f"Sin cruces de precio en {total} ciclos guardados.")
        return 0
    crossed = sum(e.cycles for e in episodes)
    useful = [e for e in episodes if e.executable_cycles]
    print(f"Ciclos guardados: {total} · con cruce: {crossed} ({100 * crossed / max(total, 1):.1f}%)")
    print(f"Episodios de cruce: {len(episodes)} · aprovechables con tus métodos: {len(useful)}")
    print(f"\n  {'Inicio (Colombia)':<18}{'Duración':>10}{'Ciclos':>8}{'Aprov.':>8}{'Neto COP/USDT':>15}{'Neto %':>9}{'Hasta USDT':>12}")
    for e in episodes[-args.limit:]:
        print(
            f"  {_when(e.start_ts):<18}{e.minutes:>8.0f} m{e.cycles:>8}{e.executable_cycles:>8}"
            f"{_num(e.best_net_per_unit):>15}{_num(e.best_net_pct, 3):>9}{_num(e.best_max_qty, 0):>12}"
        )
    print("\nNeto = después del 4x1000 del método con que pagarías; comisión taker observada ≈0,05% compra / 0,16% venta.")
    print("Un cruce visto en un ciclo pudo desaparecer en segundos: duración mínima real = intervalo del monitor.")
    return 0


COMMANDS = {
    "importar": cmd_importar,
    "estado": cmd_estado,
    "cambios": cmd_cambios,
    "perfil": cmd_perfil,
    "cruces": cmd_cruces,
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Base histórica del mercado P2P (Fase 3)")
    p.add_argument("comando", choices=list(COMMANDS))
    p.add_argument("--db", default="data/history.db")
    p.add_argument("--data-dir", default="data/snapshots", help="Carpeta de snapshots (para importar)")
    p.add_argument("--days", type=int, default=None, help="perfil: solo los últimos N días")
    p.add_argument("--limit", type=int, default=20, help="cruces: cuántos episodios mostrar")
    args = p.parse_args(argv)
    settings = Settings()
    with HistoryStore(args.db) as store:
        return COMMANDS[args.comando](store, args, settings)


if __name__ == "__main__":
    sys.exit(main())
