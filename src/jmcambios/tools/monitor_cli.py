"""CLI del monitor de mercado — FASES 2 y 6 (solo lectura).

Ejemplos:
  jmcambios-monitor --once
  jmcambios-monitor --interval 60
  jmcambios-monitor --interval 60 --brief --panel      # + panel para el celular y alertas
  jmcambios-monitor --pay BancolombiaSA,Nequi --amount 1000000 --min-finish-rate 95
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from jmcambios.alerts.channels import channels_from_settings
from jmcambios.alerts.manager import INFO, Alert, AlertManager
from jmcambios.analysis.crossing import parse_my_methods, taker_fees_from_orders
from jmcambios.analysis.filters import AdFilter
from jmcambios.config import Settings, effective_mode
from jmcambios.connectors.binance.account import BinanceAccount
from jmcambios.connectors.binance.client import BinanceP2PClient
from jmcambios.connectors.binance.market import BinanceMarketSource
from jmcambios.dashboard import server as panel
from jmcambios.logging_utils import setup_logging
from jmcambios.monitor.advisor import Advisor
from jmcambios.monitor.recorder import SnapshotRecorder
from jmcambios.monitor.report import BOGOTA, render
from jmcambios.monitor.service import Monitor
from jmcambios.storage.history import HistoryStore
from jmcambios.tools.panel_cli import ensure_token

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
    p.add_argument("--panel", action="store_true", help="Abrir el panel web para el celular (Fase 6)")
    p.add_argument("--panel-port", type=int, default=8765, help="Puerto del panel")
    p.add_argument("--estado", default="data/estado.json", help="Archivo de estado que lee el panel")
    p.add_argument("--anuncios-cada", type=int, default=5, help="Leer mis anuncios cada N ciclos (0 = nunca)")
    p.add_argument("--margen-min", help="Margen mínimo del ciclo en %% (por defecto JMC_MARGEN_MIN de .env)")
    p.add_argument("--ordenes-cada", type=int, default=15, help="Descargar mis órdenes cada N ciclos (0 = nunca)")
    p.add_argument("--cruce-min", default="10.000", help="Ganancia total mínima en COP para alertar un cruce")
    p.add_argument("--sin-alertas", action="store_true", help="No enviar alertas por Telegram/correo")
    return p.parse_args(argv)


def _start_dt(settings: Settings):
    """Inicio como comerciante COP (00:00 hora Colombia) o None."""
    if settings.merchant_start is None:
        return None
    return datetime(settings.merchant_start.year, settings.merchant_start.month, settings.merchant_start.day,
                    tzinfo=BOGOTA).astimezone(UTC)


def _start_panel(settings: Settings, args: argparse.Namespace):
    token = ensure_token(settings)
    data = panel.PanelData(
        Path(args.db), Path(args.estado), venue="binance_p2p", market=f"{settings.asset}/{settings.fiat}",
        fiat=settings.fiat, asset=settings.asset, cost_config=panel.cost_config(parse_my_methods(settings.my_pay_methods)),
        start=_start_dt(settings),
    )
    try:
        server = panel.start(data, token, port=args.panel_port)
    except OSError as exc:
        print(f"✘ No se pudo abrir el panel en el puerto {args.panel_port}: {exc}")
        return None
    print("Panel para el celular (misma red Wi-Fi). Abre este enlace en el celular y guárdalo:")
    print(f"  http://{panel.lan_ip()}:{args.panel_port}/?t={token}")
    print("  Si Windows pregunta por el firewall, permite solo 'Redes privadas'. No compartas este enlace.\n")
    return server


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.interval < MIN_INTERVAL_S:
        print(f"--interval mínimo es {MIN_INTERVAL_S} s para respetar los límites de Binance.")
        return 2

    settings = Settings()
    setup_logging(logging.WARNING, settings.secret_values())
    ad_filter = build_filter(args)
    recorder = None if args.no_record else SnapshotRecorder(Path(args.data_dir))
    store = None if args.no_record else HistoryStore(args.db)
    fees = taker_fees_from_orders(store.load_orders(), settings.fiat) if store else {}

    if not settings.has_read_credentials:
        print("Aviso: sin API key → solo 20 anuncios por lado (lista pública). Ejecuta set_keys para ver el libro completo.\n")

    min_margin = (_decimal(args.margen_min, "--margen-min") or settings.min_margin_pct) / 100
    channels = [] if args.sin_alertas else channels_from_settings(settings)
    alerts = AlertManager(channels, store) if store is not None else None
    mode, _ = effective_mode(settings)
    if store is not None:
        print(f"Alertas: {', '.join(c.name for c in channels) or 'solo en pantalla y en la base (configura Telegram con: jmcambios-alertas configurar)'}")

    def show(result) -> None:
        print(render(result, ad_filter, detail=not args.brief), flush=True)
        if advisor is not None:
            now_ts = int(datetime.now(UTC).timestamp())
            try:
                out = advisor.process(result, monitor.consecutive_failures, now_ts)
            except Exception as exc:  # el asesor no debe tumbar el monitor
                logging.getLogger(__name__).exception("error en el asesor")
                print(f"  ✘ asesor: {type(exc).__name__}: {exc}")
            else:
                for d in out.deliveries:
                    if d.suppressed:
                        continue
                    where = ", ".join(d.sent_to) or "registrada"
                    print(f"  🔔 ALERTA ({where}): {d.alert.title}" + (f" · ✘ {'; '.join(d.errors)}" if d.errors else ""))
                for n in out.notes:
                    print(f"  ⚠ {n}")
        print()

    cycles = 1 if args.once else args.cycles
    advisor = None
    server = None
    with BinanceP2PClient(settings, allow_write=False) as client:
        if store is not None:
            account = BinanceAccount(client) if settings.has_read_credentials and args.anuncios_cada > 0 else None
            reader = BinanceAccount(client) if settings.has_read_credentials and args.ordenes_cada > 0 else None

            def sync_orders():
                fetched = reader.fetch_orders(datetime.now(UTC) - timedelta(days=2))
                store.upsert_orders(fetched.orders, int(datetime.now(UTC).timestamp()))
                return store.load_orders()

            advisor = Advisor(
                orders=store.load_orders(), fiat=settings.fiat, gmf_by_account=parse_my_methods(settings.my_pay_methods),
                min_margin=min_margin, mode=mode, fetch_my_ads=account.fetch_my_ads if account else None,
                ads_every=args.anuncios_cada or 1, alerts=alerts, state_path=Path(args.estado),
                cross_min_total=_decimal(args.cruce_min, "--cruce-min") or Decimal("0"),
                merchants_only=settings.merchants_only,
                fetch_orders=sync_orders if reader else None, orders_every=args.ordenes_cada or 1,
                daily_goal=settings.daily_goal, exempt_cap=settings.exempt_cap,
                exempt_accounts=tuple(a.strip() for a in settings.exempt_accounts.split(",") if a.strip())
                if settings.exempt_accounts else None,
                merchant_start=_start_dt(settings),
                summary_hours=tuple(int(h) for h in settings.summary_hours.replace(" ", "").split(",")
                                    if h.isdigit() and 0 <= int(h) <= 23),
            )
        if args.panel and store is not None:
            server = _start_panel(settings, args)
        if alerts is not None:
            alerts.notify(Alert("inicio", INFO, "Monitor iniciado", f"Leyendo {settings.asset}/{settings.fiat} cada {args.interval:g} s.", 0),
                          int(datetime.now(UTC).timestamp()))
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
            if alerts is not None:
                alerts.notify(Alert("detenido", INFO, "Monitor detenido", "Se detuvo a mano en el computador. No se guardan datos hasta que lo arranques.", 0),
                              int(datetime.now(UTC).timestamp()))
        finally:
            if server is not None:
                server.shutdown()
    if store is not None:
        store.close()
    if recorder is not None:
        print(f"Snapshots guardados en: {Path(args.data_dir).resolve()}")
        print(f"Base histórica: {Path(args.db).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
