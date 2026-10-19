"""CLI del monitor de mercado — FASE 2 (solo lectura).

Ejemplos:
  jmcambios-monitor --once
  jmcambios-monitor --interval 60
  jmcambios-monitor --pay BancolombiaSA,Nequi --amount 1000000 --min-finish-rate 95
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from jmcambios.analysis.crossing import parse_my_methods, taker_fees_from_orders
from jmcambios.analysis.filters import AdFilter
from jmcambios.config import Settings
from jmcambios.connectors.binance.client import BinanceP2PClient
from jmcambios.connectors.binance.market import BinanceMarketSource
from jmcambios.logging_utils import setup_logging
from jmcambios.monitor.recorder import SnapshotRecorder
from jmcambios.monitor.report import render
from jmcambios.monitor.service import Monitor
from jmcambios.storage.history import HistoryStore

MIN_INTERVAL_S = 20


def _csv(value: str | None) -> frozenset[str]:
    return frozenset(v.strip() for v in (value or "").split(",") if v.strip())


def _decimal(value: str | None, name: str) -> Decimal | None:
    if value is None:
        return None
    text = value.strip().replace(" ", "")
    if "," in text:  # formato colombiano: 1.000.000,50
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", text):  # 1.000.000
        text = text.replace(".", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise SystemExit(f"{name} inválido: {value}") from exc


def build_filter(args: argparse.Namespace) -> AdFilter:
    finish = _decimal(args.min_finish_rate, "--min-finish-rate")
    return AdFilter(
        payment_methods=_csv(args.pay),
        amount_fiat=_decimal(args.amount, "--amount"),
        min_finish_rate=(finish / 100 if finish is not None and finish > 1 else finish),
        min_month_orders=args.min_orders,
        merchants_only=args.merchants_only,
        exclude_user_ids=_csv(args.exclude_user),
    )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Monitor del mercado Binance P2P USDT/COP (solo lectura)")
    p.add_argument("--once", action="store_true", help="Un solo ciclo y salir")
    p.add_argument("--cycles", type=int, default=None, help="Número de ciclos y salir")
    p.add_argument("--interval", type=float, default=60, help=f"Segundos entre ciclos (mínimo {MIN_INTERVAL_S})")
    p.add_argument("--pay", help="Métodos de pago compatibles, separados por coma (p. ej. BancolombiaSA,Nequi)")
    p.add_argument("--amount", help="Monto típico por operación en COP (filtra por límites del anuncio)")
    p.add_argument("--min-finish-rate", help="Tasa mínima de finalización 30 días, en %% (p. ej. 95)")
    p.add_argument("--min-orders", type=int, help="Órdenes mínimas del anunciante en 30 días")
    p.add_argument("--merchants-only", action="store_true", help="Solo comerciantes verificados")
    p.add_argument("--exclude-user", help="userNo a excluir (p. ej. el mío), separados por coma")
    p.add_argument("--data-dir", default="data/snapshots", help="Carpeta de snapshots")
    p.add_argument("--no-record", action="store_true", help="No guardar snapshots ni base histórica")
    p.add_argument("--db", default="data/history.db", help="Base histórica SQLite (Fase 3)")
    p.add_argument("--brief", action="store_true", help="Salida resumida")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.interval < MIN_INTERVAL_S:
        print(f"--interval mínimo es {MIN_INTERVAL_S} s para respetar los límites de Binance.")
        return 2

    settings = Settings()
    secrets = [s.get_secret_value() for s in (settings.api_key, settings.api_secret) if s]
    setup_logging(logging.WARNING, secrets)
    ad_filter = build_filter(args)
    recorder = None if args.no_record else SnapshotRecorder(Path(args.data_dir))
    store = None if args.no_record else HistoryStore(args.db)
    fees = taker_fees_from_orders(store.load_orders(), settings.fiat) if store else {}

    if not settings.has_read_credentials:
        print("Aviso: sin API key → solo 20 anuncios por lado (lista pública). Ejecuta set_keys para ver el libro completo.\n")

    def show(result) -> None:
        print(render(result, ad_filter, detail=not args.brief), flush=True)
        print()

    cycles = 1 if args.once else args.cycles
    with BinanceP2PClient(settings, allow_write=False) as client:
        monitor = Monitor(
            BinanceMarketSource(client, settings),
            ad_filter=ad_filter,
            recorder=recorder,
            store=store,
            my_methods=parse_my_methods(settings.my_pay_methods),
            fees=fees,
            interval_s=args.interval,
            clock=lambda: datetime.now(UTC),
            on_cycle=show,
        )
        try:
            monitor.run(max_cycles=cycles)
        except KeyboardInterrupt:
            print("\nMonitor detenido por el usuario.")
    if store is not None:
        store.close()
    if recorder is not None:
        print(f"Snapshots guardados en: {Path(args.data_dir).resolve()}")
        print(f"Base histórica: {Path(args.db).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
