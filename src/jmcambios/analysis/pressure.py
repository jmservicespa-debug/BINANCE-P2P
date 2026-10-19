"""Detector de presión del mercado (módulo 5, segunda parte).

Combina los cambios de las ventanas 5/15/30/60 min en un puntaje de dirección
del precio del USDT y un nivel de confianza. Cada señal declara su procedencia:

- OBSERVADO: movimiento del mejor precio o de la liquidez anunciada (dato publicado).
- INFERIDO: cantidad que baja sin cambio de precio → posible ejecución (también
  puede ser el anunciante reduciéndola a mano).
- NO VERIFICABLE: el volumen realmente ejecutado por el mercado (Binance no lo publica).

Convención: puntaje > 0 = presión ALCISTA (más demanda de USDT / menos oferta);
puntaje < 0 = presión BAJISTA. Rango −100..100; confianza 0..100.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jmcambios.analysis.liquidity import WindowChange, window_changes
from jmcambios.domain import Side
from jmcambios.storage.history import HistoryStore

OBSERVED, INFERRED, UNVERIFIABLE = "observado", "inferido", "no verificable"

WINDOW_WEIGHTS = {5: 0.15, 15: 0.30, 30: 0.30, 60: 0.25}
PRICE_FULL_SCALE = 0.001  # un movimiento de 0,1 % del mejor precio cuenta como señal completa
QTY_FULL_SCALE = 0.10  # 10 % de la liquidez anunciada
EXEC_FULL_SCALE = 0.01  # 1 % de la liquidez anunciada consumida sin cambio de precio
STALE_AFTER_S = 600

NEUTRAL_BELOW = 15
STRONG_FROM = 40


@dataclass(frozen=True)
class Signal:
    name: str
    window_min: int
    direction: float  # −1..1, positivo = alcista
    weight: float
    provenance: str
    detail: str


@dataclass(frozen=True)
class SideActivity:
    """Lo que pasó en un lado del libro en la ventana más larga disponible."""

    side: Side
    window_min: int
    best_price_delta: float | None
    announced_qty_pct: float | None
    ads_appeared: int
    ads_disappeared: int
    repriced: int
    possible_executed_qty: float  # INFERIDO


@dataclass
class PressureReport:
    score: float  # −100..100
    confidence: int  # 0..100
    label: str
    signals: list[Signal] = field(default_factory=list)
    sides: dict[Side, SideActivity] = field(default_factory=dict)
    windows: list[int] = field(default_factory=list)
    data_age_s: int | None = None
    notes: list[str] = field(default_factory=list)
    unverifiable: list[str] = field(default_factory=list)

    @property
    def direction(self) -> int:
        if abs(self.score) < NEUTRAL_BELOW:
            return 0
        return 1 if self.score > 0 else -1


def _num(x: float, decimals: int = 2) -> str:
    """Formato colombiano con signo: +1.234,56."""
    text = f"{x:+,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _clip(x: float) -> float:
    return max(-1.0, min(1.0, x))


def label_for(score: float) -> str:
    if abs(score) < NEUTRAL_BELOW:
        return "neutral"
    kind = "alcista (demanda de USDT)" if score > 0 else "bajista (oferta de USDT)"
    return f"{'fuerte' if abs(score) >= STRONG_FROM else 'moderada'} {kind}"


def _window_signals(
    w_ask: WindowChange | None, w_bid: WindowChange | None, base: dict[Side, dict | None], minutes: int
) -> list[Signal]:
    sigs: list[Signal] = []
    for side, wc in ((Side.ASK, w_ask), (Side.BID, w_bid)):
        if wc is None:
            continue
        snap = base.get(side) or {}
        who = "vendedores" if side is Side.ASK else "compradores"
        price = snap.get("best_price")
        if wc.best_price_delta is not None and price:
            d = wc.best_price_delta / price
            sigs.append(Signal(f"mejor precio de {who}", minutes, _clip(d / PRICE_FULL_SCALE), 1.0, OBSERVED,
                               f"{_num(wc.best_price_delta)} COP ({_num(d * 100, 3)} %)"))
        qty = snap.get("announced_qty")
        if wc.announced_qty_delta is not None and qty:
            d = wc.announced_qty_delta / qty
            # Menos oferta (ASK) o más demanda (BID) empujan el precio hacia arriba.
            sign = -1 if side is Side.ASK else 1
            sigs.append(Signal(f"liquidez anunciada de {who}", minutes, _clip(sign * d / QTY_FULL_SCALE), 0.6, OBSERVED,
                               f"{_num(d * 100, 1)} %"))
    # Consumo sin cambio de precio: en ASK = alguien compró USDT; en BID = alguien vendió USDT.
    if w_ask is not None and w_bid is not None:
        ask_q = (base.get(Side.ASK) or {}).get("announced_qty") or 0
        bid_q = (base.get(Side.BID) or {}).get("announced_qty") or 0
        ask_c = w_ask.qty_reduced_same_price / ask_q if ask_q else 0.0
        bid_c = w_bid.qty_reduced_same_price / bid_q if bid_q else 0.0
        if ask_c or bid_c:
            sigs.append(Signal("posibles ejecuciones (compras − ventas de USDT)", minutes,
                               _clip((ask_c - bid_c) / EXEC_FULL_SCALE), 0.8, INFERRED,
                               f"vendedores −{_num(w_ask.qty_reduced_same_price, 0)[1:]} USDT · compradores −{_num(w_bid.qty_reduced_same_price, 0)[1:]} USDT"))
    return sigs


def analyze(store: HistoryStore, venue: str, market: str, now_ts: int | None = None) -> PressureReport:
    latest = store.latest_ts(venue, market)
    report = PressureReport(score=0.0, confidence=0, label="sin datos")
    report.unverifiable.append("volumen realmente ejecutado por el mercado: Binance no lo publica")
    if latest is None:
        report.notes.append("no hay historial: deja el monitor corriendo para medir la presión")
        return report
    now_ts = now_ts if now_ts is not None else latest
    report.data_age_s = max(0, now_ts - latest)
    changes = window_changes(store, venue, market, latest)
    by_min = {s: {w.minutes: w for w in changes[s]} for s in (Side.ASK, Side.BID)}
    windows = sorted(set(by_min[Side.ASK]) | set(by_min[Side.BID]))
    report.windows = windows
    if not windows:
        report.notes.append("historial insuficiente (se necesitan al menos 5 minutos de datos)")
        return report

    incomplete = False
    total, wsum = 0.0, 0.0
    for m in windows:
        wa, wb = by_min[Side.ASK].get(m), by_min[Side.BID].get(m)
        base = {}
        for side, wc in ((Side.ASK, wa), (Side.BID, wb)):
            row = store.snapshot_at(venue, market, side, wc.from_ts) if wc else None
            base[side] = dict(row) if row is not None else None
            incomplete |= bool(wc and any("incompleto" in n for n in wc.notes))
        sigs = _window_signals(wa, wb, base, m)
        report.signals.extend(sigs)
        sw = sum(s.weight for s in sigs)
        if sw:
            total += WINDOW_WEIGHTS[m] * sum(s.direction * s.weight for s in sigs) / sw
            wsum += WINDOW_WEIGHTS[m]
    report.score = round(100 * total / wsum, 1) if wsum else 0.0
    report.label = label_for(report.score)

    # Confianza = cobertura de ventanas × acuerdo entre señales × calidad de datos.
    coverage = sum(WINDOW_WEIGHTS[m] for m in windows)
    active = [s for s in report.signals if abs(s.direction) > 0.05]
    weight = sum(s.weight * abs(s.direction) for s in active)
    agreement = abs(sum(s.weight * s.direction for s in active)) / weight if weight else 0.0
    conf = 100 * coverage ** 0.5 * (0.3 + 0.7 * agreement)
    if not any(s.provenance == OBSERVED for s in active):
        conf = min(conf, 50)
        if active:
            report.notes.append("solo hay señales inferidas: la confianza se limita a 50")
    if incomplete:
        conf *= 0.8
        report.notes.append("algún snapshot estaba incompleto")
    if report.data_age_s > STALE_AFTER_S:
        conf = min(conf, 20)
        report.notes.append(f"datos de hace {report.data_age_s // 60} min: ¿está corriendo el monitor?")
    report.confidence = int(round(conf))

    longest = windows[-1]
    for side in (Side.ASK, Side.BID):
        wc = by_min[side].get(longest)
        if wc is None:
            continue
        row = store.snapshot_at(venue, market, side, wc.from_ts)
        q0 = row["announced_qty"] if row is not None else None
        report.sides[side] = SideActivity(
            side=side, window_min=longest, best_price_delta=wc.best_price_delta,
            announced_qty_pct=(wc.announced_qty_delta / q0 * 100) if wc.announced_qty_delta is not None and q0 else None,
            ads_appeared=wc.ads_appeared, ads_disappeared=wc.ads_disappeared, repriced=wc.repriced,
            possible_executed_qty=wc.qty_reduced_same_price,
        )
    return report
