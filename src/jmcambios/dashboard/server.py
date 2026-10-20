"""Servidor del panel: solo lectura, protegido por una clave en el enlace.

- No tiene botones que actúen sobre Binance: solo muestra datos.
- Pensado para la red Wi-Fi de la casa. NO abrir el puerto a internet.
- Lee `estado.json` (lo escribe el monitor cada ciclo) y la base histórica.
"""

from __future__ import annotations

import hmac
import json
import logging
import secrets
import socket
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from jmcambios.analysis import merchants
from jmcambios.analysis.amounts import tranche_views
from jmcambios.analysis.pressure import PressureReport
from jmcambios.dashboard.icon import ICON_PNG
from jmcambios.domain import Ad, Advertiser, Side
from jmcambios.pricing.engine import DEFAULT_LIMITS, AdProfile, Costs, plan, tranche_opportunities
from jmcambios.dashboard.page import PAGE
from jmcambios.profitability.calculator import calculate
from jmcambios.profitability.costs import CostConfig
from jmcambios.storage.history import HistoryStore

log = logging.getLogger(__name__)

MAX_POINTS = 360
MAX_MARGIN_PCT = Decimal("10")


def _limits(q: dict) -> tuple[Decimal, Decimal] | None | str:
    lo, hi = (q.get("min") or [""])[0], (q.get("max") or [""])[0]
    if not lo and not hi:
        return None
    try:
        a, b = Decimal(lo.replace(".", "").replace(",", ".")), Decimal(hi.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return "bad"
    return (a, b) if Decimal("0") < a < b <= Decimal("1e10") else "bad"


def new_token() -> str:
    return secrets.token_urlsafe(18)


def lan_ip() -> str:
    """IP del computador en la red local (no envía nada: solo elige la interfaz de salida)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


SPIKE_WINDOW = 3  # vecinos a cada lado
SPIKE_PCT = 0.003  # un minuto que se aleja > 0,3 % de sus vecinos es un dato aislado


def _median(values: list[float | None]) -> float | None:
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def despike(values: list[float | None]) -> list[float | None]:
    """Solo para el gráfico: reemplaza picos de un ciclo (p. ej. un anuncio con precio absurdo
    o un libro incompleto) por la mediana de sus vecinos. Los datos guardados no se tocan."""
    out = list(values)
    for i, v in enumerate(values):
        if v is None:
            continue
        med = _median(values[max(0, i - SPIKE_WINDOW): i + SPIKE_WINDOW + 1])
        if med and abs(v - med) > med * SPIKE_PCT:
            out[i] = med
    return out


class PanelData:
    def __init__(self, db_path: Path, state_path: Path, *, venue: str, market: str, fiat: str, asset: str,
                 cost_config: CostConfig, start: datetime | None = None) -> None:
        self.start = start
        self._cache: dict = {}
        self._lock = threading.Lock()
        self.db_path, self.state_path = db_path, state_path
        self.venue, self.market, self.fiat, self.asset = venue, market, fiat, asset
        self.cost_config = cost_config

    def _store(self) -> HistoryStore:
        return HistoryStore(self.db_path)  # una conexión por consulta: seguro entre hilos

    def estado(self, now_ts: int) -> dict[str, Any]:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"available": False, "message": "Aún no hay datos: arranca el monitor (jmcambios-monitor)."}
        data["available"] = True
        data["age_s"] = max(0, now_ts - int(data.get("generated_ts", now_ts)))
        return data

    def serie(self, hours: int, now_ts: int) -> dict[str, Any]:
        hours = max(1, min(hours, 72))
        with self._store() as st:
            rows = st.query(
                "SELECT cycle_ts, ask_best, bid_best FROM cycles WHERE venue=? AND market=? AND cycle_ts>=? ORDER BY cycle_ts",
                (self.venue, self.market, now_ts - hours * 3600),
            )
        ts = [r["cycle_ts"] for r in rows]
        ask = despike([r["ask_best"] for r in rows])
        bid = despike([r["bid_best"] for r in rows])
        step = max(1, -(-len(rows) // MAX_POINTS))
        pts = [[ts[i], _median(ask[i:i + step]), _median(bid[i:i + step])] for i in range(0, len(rows), step)]
        return {"hours": hours, "points": pts}

    def rentabilidad(self, now: datetime) -> dict[str, Any]:
        with self._store() as st:
            orders = st.load_orders(fiat=self.fiat, asset=self.asset)
        start = max(self.start, now - timedelta(days=30)) if self.start else now - timedelta(days=30)
        rep = calculate(orders, self.cost_config, fiat=self.fiat, asset=self.asset, start=start, end=now)
        f = lambda v: None if v is None else float(v)  # noqa: E731
        return {
            "days": 30, "buys": rep.buys, "sells": rep.sells, "realized": f(rep.realized),
            "realized_qty": f(rep.realized_qty), "margin_per_unit": f(rep.gross_margin_per_unit),
            "bought_fiat": f(rep.bought_fiat), "sold_fiat": f(rep.sold_fiat),
            "by_day": [{"day": d.day.isoformat(), "realized": f(d.realized), "buys": d.buys, "sells": d.sells}
                       for d in rep.by_day[-14:]],
            "warnings": rep.warnings,
        }

    def _book(self, st: HistoryStore, side: Side) -> list[Ad]:
        ts = st.latest_ts(self.venue, self.market)
        snap = st.snapshot_at(self.venue, self.market, side, ts) if ts else None
        if snap is None:
            return []
        rows = st.ads_at(self.venue, self.market, side, snap["taken_ts"]).values()
        D = lambda v: Decimal(str(v))  # noqa: E731
        return [
            Ad(venue=self.venue, ad_id=r["ad_id"], side=side, asset=self.asset, fiat=self.fiat, price=D(r["price"]),
               available_qty=D(r["qty"]), min_fiat=D(r["min_fiat"]), max_fiat=D(r["max_fiat"]),
               payment_methods=tuple(m for m in (r["methods"] or "").split(",") if m),
               advertiser=Advertiser(user_id=r["user_id"] or "", nickname=r["nickname"] or "", user_type=r["user_type"],
                                     month_orders=r["month_orders"],
                                     month_finish_rate=None if r["finish_rate"] is None else D(r["finish_rate"])))
            for r in rows
        ]

    def escenarios(self, margin_pct: Decimal, now_ts: int, merchants_only: bool | None = None,
                   limits: tuple[Decimal, Decimal] | None = None) -> dict[str, Any]:
        """Recalcula los 3 escenarios con otro margen mínimo, usando el último libro guardado. Solo lectura."""
        state = self.estado(now_ts)
        if not state.get("available") or not state.get("costs"):
            return {"available": False}
        c = state["costs"]
        D = lambda v: Decimal(str(v))  # noqa: E731
        costs = Costs(maker_buy=D(c["maker_buy"]), maker_sell=D(c["maker_sell"]), gmf=D(c["gmf"]),
                      gmf_worst=D(c["gmf_worst"]), min_margin=margin_pct / 100)
        profiles = {}
        for k in ("buy", "sell"):
            p = (state.get("profiles") or {}).get(k)
            profiles[k] = (AdProfile(tuple(p["methods"]), D(p["min_fiat"]), D(p["max_fiat"])) if p
                           else AdProfile(tuple(self.cost_config.gmf_by_account), *DEFAULT_LIMITS))
            if limits is not None:  # estrategia para el rango de montos elegido
                profiles[k] = AdProfile(profiles[k].methods, *limits)
        pr = state.get("pressure") or {}
        pressure = PressureReport(score=pr.get("score", 0.0), confidence=pr.get("confidence", 0), label="")
        with self._store() as st:
            asks, bids = self._book(st, Side.ASK), self._book(st, Side.BID)
        ver = bool(state.get("merchants_only", True)) if merchants_only is None else merchants_only
        pattern = self.comerciantes(now_ts, ver).get("pattern") or {}
        leaders = ((D(round(pattern["gap_buy"], 2)), D(round(pattern["gap_sell"], 2)))
                   if pattern.get("gap_buy") is not None and pattern.get("gap_sell") is not None else None)
        pp = plan(asks, bids, buy_profile=profiles["buy"], sell_profile=profiles["sell"], costs=costs, leader_gaps=leaders,
                  pressure=pressure, exclude_users=set(state.get("my_users") or []),
                  merchants_only=bool(state.get("merchants_only", True)) if merchants_only is None else merchants_only)
        f = lambda v: None if v is None else float(v)  # noqa: E731
        return {
            "available": True, "min_margin": float(margin_pct) / 100, "priority": pp.priority, "warnings": pp.warnings,
            "merchants_only": pp.merchants_only,
            "leader_gaps": [float(x) for x in leaders] if leaders else None,
            "limits": [float(profiles["buy"].min_fiat), float(profiles["buy"].max_fiat)],
            "scenarios": [{
                "name": sc.name, "target_margin": f(sc.target_margin), "margin": f(sc.margin),
                "margin_worst": f(sc.margin_worst), "net_per_unit": f(sc.net_per_unit),
                **{k: {"price": f(sp.price), "rank": sp.rank, "rank_compatible": sp.rank_compatible,
                       "compatible_total": sp.compatible_total, "adjusted": sp.adjusted}
                   for k, sp in (("buy", sc.buy), ("sell", sc.sell))},
            } for sc in pp.scenarios],
        }

    def tramos(self, now_ts: int, merchants_only: bool | None = None) -> dict[str, Any]:
        """Competencia por tramo de monto, por lado, con tus métodos y el precio de tus anuncios."""
        state = self.estado(now_ts)
        ver = bool(state.get("merchants_only", True)) if merchants_only is None else merchants_only
        mine = {a["side"]: a["price"] for a in state.get("my_ads") or []}
        methods = {k: tuple((state.get("profiles") or {}).get(k, {}).get("methods") or self.cost_config.gmf_by_account)
                   for k in ("buy", "sell")}
        out: dict[str, Any] = {"merchants_only": ver}
        views: dict[str, list] = {}
        with self._store() as st:
            for side, key, my_key in ((Side.BID, "buy", "BUY"), (Side.ASK, "sell", "SELL")):
                ads = [a for a in self._book(st, side) if a.advertiser.user_id not in set(state.get("my_users") or [])]
                if ver:
                    ads = [a for a in ads if a.advertiser.is_merchant] or ads
                price = mine.get(my_key)
                views[key] = tranche_views(side, ads, methods[key])
                out[key] = [{"label": v.label, "ads": v.ads, "best": None if v.best_price is None else float(v.best_price),
                             "qty": float(v.qty), "my_rank": v.my_rank}
                            for v in tranche_views(side, ads, methods[key], None if price is None else Decimal(str(price)))]
        c = state.get("costs")
        if c:
            D = lambda v: Decimal(str(v))  # noqa: E731
            costs = Costs(D(c["maker_buy"]), D(c["maker_sell"]), D(c["gmf"]), D(c["gmf_worst"]), D(c["min_margin"]))
            opps, best = tranche_opportunities(views["buy"], views["sell"], costs)
            out["opportunities"] = [{"label": o.label, "gap": None if o.gap is None else float(o.gap),
                                     "margin": None if o.margin is None else float(o.margin),
                                     "buy_at": None if o.best_bid is None else float(o.best_bid + Decimal("0.01")),
                                     "sell_at": None if o.best_ask is None else float(o.best_ask - Decimal("0.01")),
                                     "competitors": o.competitors_buy + o.competitors_sell, "meets_min": o.meets_min}
                                    for o in opps]
            out["suggested"] = best
            out["min_margin"] = float(c["min_margin"])
        return out

    def comerciantes(self, now_ts: int, merchants_only: bool | None = None) -> dict[str, Any]:
        """Estudio de los mejores comerciantes (últimos 3 días). Se guarda 10 min: tarda unos segundos."""
        state = self.estado(now_ts)
        ver = bool(state.get("merchants_only", True)) if merchants_only is None else merchants_only
        with self._lock:
            hit = self._cache.get(("comerciantes", ver))
            if hit and now_ts - hit[0] < 600:
                return hit[1]
        with self._store() as st:
            study = merchants.study(st, self.venue, self.market, days=3, top=10, merchants_only=ver)
        c = state.get("costs")
        costs = None
        if c:
            D = lambda v: Decimal(str(v))  # noqa: E731
            costs = Costs(D(c["maker_buy"]), D(c["maker_sell"]), D(c["gmf"]), D(c["gmf_worst"]), D(c["min_margin"]))
        rows = []
        for m in study.merchants:
            net = (float(merchants.net_margin_with_costs(*m.both_prices, costs))
                   if costs is not None and m.both_prices else None)
            rows.append({"nickname": m.nickname, "orders": m.month_orders, "sides": m.sides, "presence": m.presence,
                         "rank_buy": m.rank_buy, "rank_sell": m.rank_sell, "own_spread": m.own_spread,
                         "own_spread_pct": m.own_spread_pct, "net_with_my_costs": net,
                         "min_fiat": m.min_fiat, "max_fiat": m.max_fiat, "methods": list(m.methods),
                         "active_hours": list(m.active_hours), "reprices_per_hour": m.reprices_per_hour})
        out = {"merchants_only": ver, "samples": study.samples, "notes": study.notes, "merchants": rows,
               "pattern": merchants.summarize(study)}
        with self._lock:
            self._cache[("comerciantes", ver)] = (now_ts, out)
        return out

    def alertas(self) -> list[dict[str, Any]]:
        with self._store() as st:
            return [{"ts": r["ts"], "severity": r["severity"], "title": r["title"], "body": r["body"]}
                    for r in st.recent_alerts(30)]


def make_handler(data: PanelData, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "JMCambiosPanel"

        def log_message(self, fmt: str, *args: Any) -> None:  # la URL lleva la clave: no se registra
            return

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: Any) -> None:
            self._send(200, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            if url.path in ("/icon.png", "/favicon.ico"):  # el ícono no es información privada
                self._send(200, ICON_PNG, "image/png")
                return
            q = parse_qs(url.query)
            given = (q.get("t") or [""])[0]
            if not hmac.compare_digest(given.encode(), token.encode()):
                self._send(403, "Acceso denegado: abre el enlace completo que muestra el monitor.".encode(),
                           "text/plain; charset=utf-8")
                return
            now = datetime.now(UTC)
            ts = int(now.timestamp())
            try:
                if url.path == "/":
                    self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                elif url.path == "/api/estado":
                    self._json(data.estado(ts))
                elif url.path == "/api/serie":
                    self._json(data.serie(int((q.get("horas") or ["6"])[0] or 6), ts))
                elif url.path == "/api/escenarios":
                    try:
                        m = Decimal((q.get("margen") or [""])[0].replace(",", "."))
                    except InvalidOperation:
                        m = Decimal("-1")
                    if not (Decimal("0") <= m <= MAX_MARGIN_PCT):
                        self._send(400, "margen inválido".encode(), "text/plain; charset=utf-8")
                    else:
                        ver = (q.get("verificados") or [""])[0]
                        lim = _limits(q)
                        if lim == "bad":
                            self._send(400, "límites inválidos".encode(), "text/plain; charset=utf-8")
                        else:
                            self._json(data.escenarios(m, ts, None if ver not in ("0", "1") else ver == "1", lim))
                elif url.path == "/api/comerciantes":
                    ver = (q.get("verificados") or [""])[0]
                    self._json(data.comerciantes(ts, None if ver not in ("0", "1") else ver == "1"))
                elif url.path == "/api/tramos":
                    ver = (q.get("verificados") or [""])[0]
                    self._json(data.tramos(ts, None if ver not in ("0", "1") else ver == "1"))
                elif url.path == "/api/rentabilidad":
                    self._json(data.rentabilidad(now))
                elif url.path == "/api/alertas":
                    self._json(data.alertas())
                else:
                    self._send(404, b"no encontrado", "text/plain; charset=utf-8")
            except Exception:  # el panel no debe caerse por una consulta
                log.exception("error en el panel")
                self._send(500, "Error interno del panel".encode(), "text/plain; charset=utf-8")

        def do_POST(self) -> None:  # noqa: N802 — panel de solo lectura
            self._send(405, b"solo lectura", "text/plain; charset=utf-8")

    return Handler


def start(data: PanelData, token: str, host: str = "0.0.0.0", port: int = 8765) -> ThreadingHTTPServer:
    """Arranca el servidor en un hilo de fondo y lo devuelve (llamar .shutdown() para detenerlo)."""
    server = ThreadingHTTPServer((host, port), make_handler(data, token))
    threading.Thread(target=server.serve_forever, name="panel", daemon=True).start()
    return server


def cost_config(gmf_by_account: dict[str, Decimal]) -> CostConfig:
    return CostConfig(gmf_by_account=gmf_by_account)
