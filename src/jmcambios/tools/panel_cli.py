"""Panel web para el celular — FASE 6 (solo lectura).

  jmcambios-panel                 # abre el panel con los datos que va guardando el monitor
  jmcambios-panel --puerto 8765

Lo normal es arrancarlo junto con el monitor:  jmcambios-monitor --interval 60 --brief --panel
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from jmcambios.analysis.crossing import parse_my_methods
from jmcambios.config import Settings
from jmcambios.dashboard import server as panel
from jmcambios.logging_utils import setup_logging
from jmcambios.tools.set_keys import upsert_env


def ensure_token(settings: Settings, env_path: Path = Path(".env")) -> str:
    """Devuelve la clave del panel; si no existe, la crea y la guarda en `.env`."""
    if settings.dashboard_token is not None and settings.dashboard_token.get_secret_value().strip():
        return settings.dashboard_token.get_secret_value().strip()
    token = panel.new_token()
    text = env_path.read_text(encoding="utf-8-sig") if env_path.exists() else ""
    env_path.write_text(upsert_env(text, {"JMC_DASHBOARD_TOKEN": token}), encoding="utf-8")
    return token


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Panel web de solo lectura (Fase 6)")
    p.add_argument("--db", default="data/history.db")
    p.add_argument("--estado", default="data/estado.json")
    p.add_argument("--puerto", type=int, default=8765)
    args = p.parse_args(argv)
    settings = Settings()
    setup_logging(logging.WARNING, settings.secret_values())
    token = ensure_token(settings)
    data = panel.PanelData(
        Path(args.db), Path(args.estado), venue="binance_p2p", market=f"{settings.asset}/{settings.fiat}",
        fiat=settings.fiat, asset=settings.asset, cost_config=panel.cost_config(parse_my_methods(settings.my_pay_methods)),
    )
    try:
        server = panel.start(data, token, port=args.puerto)
    except OSError as exc:
        print(f"✘ No se pudo abrir el puerto {args.puerto}: {exc}")
        return 1
    print("Panel abierto. En el celular (misma red Wi-Fi) abre:")
    print(f"  http://{panel.lan_ip()}:{args.puerto}/?t={token}")
    print("Ctrl + C para cerrarlo.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()
        print("\nPanel cerrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
