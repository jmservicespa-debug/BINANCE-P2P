"""Reglas de alerta: qué merece un aviso y con qué clave se agrupa.

Ninguna regla actúa sobre Binance: solo describen lo observado/calculado y,
en modo RECOMENDACIÓN, sugieren un precio que el usuario cambia a mano.
"""

from __future__ import annotations

from decimal import Decimal

from jmcambios.alerts.manager import IMPORTANT, INFO, URGENT, Alert
from jmcambios.analysis.competition import AdPosition
from jmcambios.analysis.crossing import CrossReport
from jmcambios.analysis.pressure import PressureReport
from jmcambios.domain.account import OrderSide
from jmcambios.monitor.report import money
from jmcambios.pricing.engine import PricePlan

STRONG_SCORE = 40
STRONG_CONFIDENCE = 60
AD_TOLERANCE = Decimal("1")  # COP de diferencia con lo recomendado antes de avisar
FAILURES_ALERT = 3
CROSS_MIN_TOTAL = Decimal("10000")  # COP: por debajo no vale el riesgo de operar el cruce


def cross_alert(cross: CrossReport | None, min_total: Decimal = CROSS_MIN_TOTAL) -> Alert | None:
    if cross is None or not cross.executable or cross.best is None:
        return None
    b = cross.best
    if b.net_total_max < min_total:
        return None
    return Alert(
        key="cruce", severity=IMPORTANT, cooldown_s=600,
        title="Cruce de precios aprovechable",
        body=(f"Comprar a {money(b.buy_ad.price)} pagando por {b.pay_method} y vender a {money(b.sell_ad.price)} "
              f"cobrando por {b.receive_method}.\n"
              f"Neto ≈ {money(b.net_per_unit)} COP/USDT ({money(b.net_pct, 3)} %) · {money(b.min_qty)}–{money(b.max_qty)} USDT"
              f" · hasta ≈ {money(b.net_total_max, 0)} COP.\n"
              "Los anuncios pueden desaparecer en segundos. Verifica en la app antes de operar."),
    )


def pressure_alert(pr: PressureReport | None) -> Alert | None:
    if pr is None or abs(pr.score) < STRONG_SCORE or pr.confidence < STRONG_CONFIDENCE:
        return None
    up = pr.score > 0
    return Alert(
        key=f"presion:{'alcista' if up else 'bajista'}", severity=INFO, cooldown_s=3600,
        title=f"Presión {'alcista' if up else 'bajista'} fuerte",
        body=(f"Puntaje {pr.score:+.0f} · confianza {pr.confidence}/100.\n"
              + ("El USDT tiende a subir: prioriza comprar." if up else "El USDT tiende a bajar: prioriza vender.")
              + "\nLectura de corto plazo, no garantizada."),
    )


def exempt_alert(usage) -> Alert | None:
    """Aviso al 80 % y al 100 % del tope mensual exento de 4x1000 (una vez por mes y nivel)."""
    if usage is None or usage.cap <= 0:
        return None
    month_s = 32 * 86400
    if usage.exceeded:
        return Alert(
            key=f"tope:{usage.month}:100", severity=URGENT, cooldown_s=month_s,
            title="Llegaste al tope exento de 4x1000",
            body=(f"Pagos P2P este mes desde {', '.join(usage.accounts)}: {money(usage.used, 0)} de {money(usage.cap, 0)} COP.\n"
                  "Desde ahora cada pago paga 0,4 %: los escenarios ya lo incluyen. Estimado por el método de pago de cada orden."),
        )
    if usage.ratio >= Decimal("0.8"):
        return Alert(
            key=f"tope:{usage.month}:80", severity=IMPORTANT, cooldown_s=month_s,
            title="Vas en el 80 % del tope exento de 4x1000",
            body=(f"Usado {money(usage.used, 0)} de {money(usage.cap, 0)} COP este mes; quedan {money(usage.remaining, 0)}.\n"
                  "Estimado por el método de pago de cada orden; otros débitos de esas cuentas también cuentan."),
        )
    return None


def opportunity_alert(opps, best) -> Alert | None:
    """Un tramo de montos da el margen mínimo estando de primero en compra y venta."""
    if best is None or not opps[best].meets_min:
        return None
    o = opps[best]
    return Alert(
        key=f"oportunidad:{o.label}", severity=IMPORTANT, cooldown_s=1800,
        title=f"Oportunidad de margen: {o.label}",
        body=(f"Comprar a {money(o.best_bid + Decimal('0.01'))} y vender a {money(o.best_ask - Decimal('0.01'))}"
              f" → {money(o.margin * 100, 2)} % libre siendo #1 en los dos lados ({o.competitors_buy + o.competitors_sell} competidores).\n"
              f"Pon tus anuncios con límites dentro de ese tramo. Verifica en la app antes de cambiar precios."),
    )


def ladder_alert(step) -> Alert | None:
    """Escalera de margen: subir o bajar un escalón según lo rápido que se llenó el anuncio."""
    if step.action not in ("subir", "bajar") or step.suggested is None:
        return None
    lado = "COMPRA" if step.side == "BUY" else "VENTA"
    margin = ""
    if step.margin_now is not None and step.margin_after is not None:
        margin = f"\nMargen del par: {money(step.margin_now * 100, 2)} % → {money(step.margin_after * 100, 2)} %."
        if step.below_min:
            margin += " ⚠ Queda por debajo de tu margen mínimo."
    verbo = "Sube el margen" if step.action == "subir" else "Baja el margen"
    return Alert(
        key=f"escalera:{step.side}:{step.action}:{step.since_ts}", severity=IMPORTANT, cooldown_s=3600,
        title=f"Escalera: {verbo.lower()} de tu anuncio de {lado.lower()}",
        body=(f"{step.reason[0].upper()}{step.reason[1:]}. {verbo}: {money(step.price)} → {money(step.suggested)}.{margin}\n"
              "Es una sugerencia: cambia el precio tú en Binance si estás de acuerdo."),
    )


def summary_alert(key: str, lines: list[str]) -> Alert:
    return Alert(key=key, severity=INFO, cooldown_s=3 * 3600, title="Resumen del mercado", body="\n".join(lines))


def goal_alert(today) -> Alert | None:
    if today is None or not today.goal or today.realized < today.goal:
        return None
    return Alert(key=f"meta:{today.day.isoformat()}", severity=INFO, cooldown_s=2 * 86400,
                 title="¡Meta del día cumplida!",
                 body=f"Ganancia realizada hoy: {money(today.realized, 0)} COP (meta {money(today.goal, 0)}).")


def error_alerts(errors: list[str], consecutive_failures: int, recovered: bool) -> list[Alert]:
    out = []
    if any("AUTH_ERROR" in e for e in errors):
        out.append(Alert(
            key="auth", severity=URGENT, cooldown_s=3600,
            title="Binance rechazó la API key",
            body=("Causa más común: cambió tu IP pública (p. ej. tras un corte de internet). "
                  "Actualízala en Binance → Gestión de API. Mientras tanto no se guardan datos."),
        ))
    elif consecutive_failures >= FAILURES_ALERT:
        out.append(Alert(
            key="fallas", severity=URGENT, cooldown_s=3600,
            title=f"El monitor lleva {consecutive_failures} ciclos con errores",
            body="Último error: " + (errors[-1] if errors else "desconocido") + "\nRevisa el internet del computador.",
        ))
    if recovered:
        out.append(Alert(key="recuperado", severity=INFO, cooldown_s=0, title="Monitor recuperado",
                         body="Volvió a leer el mercado con normalidad."))
    return out


def my_ad_alerts(positions: list[AdPosition], plan: PricePlan | None) -> list[Alert]:
    """Solo anuncios EN LÍNEA. Compara con el escenario equilibrado."""
    bal = next((s for s in plan.scenarios if s.name == "equilibrado"), None) if plan else None
    out = []
    for p in positions:
        ad = p.ad
        if not ad.online:
            continue
        buying = ad.side is OrderSide.BUY
        kind = "COMPRA" if buying else "VENTA"
        where = f"Puesto estimado #{p.estimated_rank} de {p.total_competitors + 1}."
        if p.gap_to_best is not None and p.gap_to_best <= -AD_TOLERANCE:
            better = p.best_price + Decimal("0.01") if buying else p.best_price - Decimal("0.01")
            out.append(Alert(
                key=f"anuncio:{ad.ad_id}:regalando", severity=IMPORTANT,
                title=f"Tu anuncio de {kind} está regalando margen",
                body=(f"Está en {money(ad.price)}, {money(-p.gap_to_best)} COP mejor que el siguiente ({money(p.best_price)}). "
                      f"Con {money(better)} seguirías de primero. {where}\nCámbialo en la app de Binance."),
            ))
            continue
        if bal is None:
            continue
        target = bal.buy if buying else bal.sell
        too_generous = ad.price > target.price + AD_TOLERANCE if buying else ad.price < target.price - AD_TOLERANCE
        too_far = ad.price < target.price - AD_TOLERANCE if buying else ad.price > target.price + AD_TOLERANCE
        if too_generous:
            out.append(Alert(
                key=f"anuncio:{ad.ad_id}:margen", severity=IMPORTANT,
                title=f"Tu anuncio de {kind} deja menos margen del objetivo",
                body=(f"Está en {money(ad.price)}; el escenario equilibrado sugiere {money(target.price)} "
                      f"(margen del ciclo {money(bal.margin * 100, 3)} %). {where}\nCámbialo en la app de Binance."),
            ))
        elif too_far:
            out.append(Alert(
                key=f"anuncio:{ad.ad_id}:atras", severity=INFO,
                title=f"Tu anuncio de {kind} quedó atrás",
                body=(f"Está en {money(ad.price)}; el equilibrado sugiere {money(target.price)} "
                      f"(puesto ≈ #{target.rank_compatible} entre compatibles). {where}"),
            ))
    return out
