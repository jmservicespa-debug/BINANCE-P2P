"""Motor de precios (módulo 6): tres escenarios para mis anuncios de compra y venta.

Para cada escenario se busca el precio que me deja en un puesto objetivo entre
los competidores COMPATIBLES (comparten método de pago y sus límites se cruzan
con los míos), y luego se comprueba el ciclo completo compra→venta:

    margen = 1 − P_b·(1+c_s)·(1+gmf) / (P_s·(1−c_b))

Cada escenario exige su propio margen (el mínimo + un extra: más margen = peor
puesto = menos órdenes). Si el margen no llega, se abre la diferencia repartiendo la concesión
entre los dos lados según la presión del mercado:
- presión alcista (el USDT tiende a subir): comprar es urgente → se cede en la venta;
- presión bajista: vender es urgente → se cede en la compra;
- neutral o poca confianza: mitad y mitad.

Todo es [cálculo]: el puesto es una estimación por precio (Binance ordena
también por otros criterios) y no hay garantía de ejecución.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from jmcambios.analysis.amounts import competes
from jmcambios.analysis.pressure import PressureReport
from jmcambios.domain import Ad, Side
from jmcambios.domain.account import MyAd, Order, OrderSide
from jmcambios.profitability.costs import fraction, observed_fee

TICK = Decimal("0.01")
DEFAULT_LIMITS = (Decimal("200000"), Decimal("3000000"))  # límites por defecto si no tienes anuncio
DEFAULT_MAKER_RATE = Decimal("0.002")  # commissionRate de los anuncios COP observado en la verificación
MIN_PRESSURE_CONFIDENCE = 50

# (nombre, puesto objetivo entre competidores compatibles, margen extra sobre el mínimo)
SCENARIOS: tuple[tuple[str, int, Decimal], ...] = (
    ("conservador", 8, Decimal("0.003")),
    ("equilibrado", 3, Decimal("0.0015")),
    ("agresivo", 1, Decimal("0")),
)


@dataclass(frozen=True)
class AdProfile:
    """Lo que define a quién atiende mi anuncio."""

    methods: tuple[str, ...]
    min_fiat: Decimal
    max_fiat: Decimal


@dataclass(frozen=True)
class Costs:
    maker_buy: Decimal  # comisión maker al comprar (fracción)
    maker_sell: Decimal  # comisión maker al vender
    gmf: Decimal  # 4x1000 de la cuenta con la que pagaré (normalmente la exenta)
    gmf_worst: Decimal  # 4x1000 si pago desde una cuenta no exenta
    min_margin: Decimal  # margen neto mínimo del ciclo (fracción)


@dataclass(frozen=True)
class SidePrice:
    side: OrderSide
    price: Decimal
    competitive_price: Decimal  # el que daría el puesto objetivo, antes de proteger el margen
    rank: int  # puesto estimado entre todos los anuncios del lado
    rank_compatible: int  # puesto entre los compatibles conmigo
    compatible_total: int
    qty_ahead: Decimal  # liquidez anunciada por delante de mí
    adjusted: bool  # se movió para proteger el margen


@dataclass(frozen=True)
class Scenario:
    name: str
    target_rank: int
    target_margin: Decimal
    buy: SidePrice
    sell: SidePrice
    margin: Decimal  # margen neto del ciclo con `gmf`
    margin_worst: Decimal  # con `gmf_worst`
    net_per_unit: Decimal  # COP ganados por USDT vendido (con `gmf`)


@dataclass
class PricePlan:
    best_ask: Decimal | None
    best_bid: Decimal | None
    scenarios: list[Scenario] = field(default_factory=list)
    buy_concession: Decimal = Decimal("0.5")  # parte del ajuste que se carga a la compra
    priority: str = "equilibrado"  # "comprar", "vender" o "equilibrado"
    merchants_only: bool = False  # puestos y precios calculados solo contra comerciantes verificados
    warnings: list[str] = field(default_factory=list)


def maker_fees(orders: list[Order], my_ads: list[MyAd], fiat: str) -> dict[OrderSide, tuple[Decimal, str]]:
    """Comisión maker por lado: OBSERVADA en tus órdenes; si no hay suficientes, la tasa de tus anuncios."""
    rates = [fraction(a.commission_rate) for a in my_ads if a.commission_rate is not None]
    ad_rate = max(rates) if rates else DEFAULT_MAKER_RATE
    out = {}
    for side in (OrderSide.BUY, OrderSide.SELL):
        obs = observed_fee(orders, role="MAKER", side=side, fiat=fiat)
        out[side] = (obs.rate, f"observada en {obs.orders} órdenes ({obs.scope})") if obs else (ad_rate, "tasa de tus anuncios")
    return out


def build_costs(orders: list[Order], my_ads: list[MyAd], fiat: str, gmf_by_account: dict[str, Decimal],
                default_gmf: Decimal, min_margin: Decimal) -> Costs:
    fees = maker_fees(orders, my_ads, fiat)
    return Costs(
        maker_buy=fees[OrderSide.BUY][0], maker_sell=fees[OrderSide.SELL][0],
        gmf=min(gmf_by_account.values(), default=Decimal("0")),
        gmf_worst=max([*gmf_by_account.values(), default_gmf]),
        min_margin=min_margin,
    )


def profile_for(ad: MyAd | None, methods: dict[str, Decimal], limits: tuple[Decimal, Decimal]) -> AdProfile:
    if ad is not None:
        return AdProfile(ad.payment_methods, ad.min_fiat, ad.max_fiat)
    return AdProfile(tuple(methods), *limits)


def compatible(profile: AdProfile, ad: Ad) -> bool:
    """Competidor directo: comparte un método de pago y cubre al menos la mitad de mi rango de montos."""
    shares = bool(set(profile.methods) & set(ad.payment_methods))
    return shares and competes(profile.min_fiat, profile.max_fiat, ad)


def cycle_margin(buy: Decimal, sell: Decimal, c: Costs, gmf: Decimal | None = None) -> Decimal:
    g = c.gmf if gmf is None else gmf
    return 1 - buy * (1 + c.maker_sell) * (1 + g) / (sell * (1 - c.maker_buy))


def _better(book_side: Side, price: Decimal, mine: Decimal) -> bool:
    return price > mine if book_side is Side.BID else price < mine


def _place(book_side: Side, ads: list[Ad], profile: AdProfile, price: Decimal, competitive: Decimal,
           order_side: OrderSide, adjusted: bool) -> SidePrice:
    ahead = [a for a in ads if _better(book_side, a.price, price)]
    comp = [a for a in ads if compatible(profile, a)]
    return SidePrice(
        side=order_side, price=price, competitive_price=competitive,
        rank=len(ahead) + 1,
        rank_compatible=sum(1 for a in comp if _better(book_side, a.price, price)) + 1,
        compatible_total=len(comp),
        qty_ahead=sum((a.available_qty for a in ahead), Decimal(0)),
        adjusted=adjusted,
    )


def competitive_price(book_side: Side, ads: list[Ad], profile: AdProfile, target_rank: int) -> Decimal | None:
    """Precio para quedar justo por delante del competidor compatible nº `target_rank`."""
    pool = [a for a in ads if compatible(profile, a)] or ads
    if not pool:
        return None
    ordered = sorted(pool, key=lambda a: a.price, reverse=(book_side is Side.BID))
    ref = ordered[min(target_rank, len(ordered)) - 1].price
    return ref + TICK if book_side is Side.BID else ref - TICK


def concession_from_pressure(pressure: PressureReport | None) -> tuple[Decimal, str]:
    if pressure is None or pressure.confidence < MIN_PRESSURE_CONFIDENCE or pressure.direction == 0:
        return Decimal("0.5"), "equilibrado"
    if pressure.direction > 0:
        return Decimal("0.25"), "comprar"
    return Decimal("0.75"), "vender"


def plan(
    asks: list[Ad],
    bids: list[Ad],
    *,
    buy_profile: AdProfile,
    sell_profile: AdProfile,
    costs: Costs,
    pressure: PressureReport | None = None,
    exclude_users: set[str] | None = None,
    merchants_only: bool = False,
) -> PricePlan:
    """`asks` = anuncios de venta (compiten con mi VENTA); `bids` = de compra (compiten con mi COMPRA)."""
    ex = exclude_users or set()
    asks = [a for a in asks if a.advertiser.user_id not in ex]
    bids = [a for a in bids if a.advertiser.user_id not in ex]
    only_merchants = False
    if merchants_only:
        m_asks = [a for a in asks if a.advertiser.is_merchant]
        m_bids = [a for a in bids if a.advertiser.is_merchant]
        if m_asks and m_bids:
            asks, bids, only_merchants = m_asks, m_bids, True
    out = PricePlan(
        best_ask=min((a.price for a in asks), default=None),
        best_bid=max((a.price for a in bids), default=None),
        merchants_only=only_merchants,
    )
    if merchants_only and not only_merchants and asks and bids:
        out.warnings.append("no hay comerciantes verificados en uno de los lados: se usaron todos los anuncios")
    if not asks or not bids:
        out.warnings.append("falta uno de los dos lados del libro: no se pueden calcular escenarios")
        return out
    w, out.priority = concession_from_pressure(pressure)
    out.buy_concession = w
    if out.best_ask < out.best_bid:
        out.warnings.append(
            "mercado cruzado: el mejor vendedor está más barato que el mejor comprador; "
            "un anuncio de compra arriba pagaría más que tomar al mejor vendedor"
        )
    raw = []
    for name, target, extra in SCENARIOS:
        target_margin = costs.min_margin + extra
        required = (1 + costs.maker_sell) * (1 + costs.gmf) / ((1 - target_margin) * (1 - costs.maker_buy))
        b0 = competitive_price(Side.BID, bids, buy_profile, target)
        s0 = competitive_price(Side.ASK, asks, sell_profile, target)
        b, s = b0, s0
        if s / b < required:
            k = required * b / s  # cuánto hay que abrir la diferencia (>1)
            b = (b0 / k ** w).quantize(TICK, rounding=ROUND_FLOOR)
            s = (s0 * k ** (1 - w)).quantize(TICK, rounding=ROUND_CEILING)
        raw.append([name, target, target_margin, b0, s0, b, s])
    # Un escenario más prudente nunca compra más caro ni vende más barato que el siguiente
    # (solo puede ganar margen al aplicarlo).
    for i in range(len(raw) - 2, -1, -1):
        raw[i][5] = min(raw[i][5], raw[i + 1][5])
        raw[i][6] = max(raw[i][6], raw[i + 1][6])
    for name, target, target_margin, b0, s0, b, s in raw:
        buy = _place(Side.BID, bids, buy_profile, b, b0, OrderSide.BUY, b != b0)
        sell = _place(Side.ASK, asks, sell_profile, s, s0, OrderSide.SELL, s != s0)
        m = cycle_margin(b, s, costs)
        out.scenarios.append(Scenario(
            name=name, target_rank=target, target_margin=target_margin, buy=buy, sell=sell, margin=m,
            margin_worst=cycle_margin(b, s, costs, costs.gmf_worst),
            net_per_unit=s * m,
        ))
    return out


def daily_goal(net_per_unit: Decimal, goal_fiat: Decimal, buy_price: Decimal, capital: Decimal | None) -> tuple[Decimal, Decimal | None]:
    """USDT a rotar por día para la meta y cuántas veces el capital supone."""
    if net_per_unit <= 0:
        return Decimal("Infinity"), None
    qty = goal_fiat / net_per_unit
    return qty, (qty * buy_price / capital) if capital else None
