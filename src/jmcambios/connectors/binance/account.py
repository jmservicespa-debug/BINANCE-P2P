"""Lectura de la cuenta propia en Binance P2P: historial de órdenes y anuncios propios.

Usa los endpoints agent (peso por IP 1). El historial se pide en ventanas de
30 días (máximo permitido) y solo cubre los últimos 6 meses.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from jmcambios.connectors.binance import endpoints as ep
from jmcambios.connectors.binance.client import BinanceP2PClient
from jmcambios.connectors.binance.market import MarketDataError, _items
from jmcambios.domain.account import MyAd, Order
from jmcambios.normalizer.binance_account import InvalidOrder, my_ad_from_detail, order_from_history
from jmcambios.normalizer.binance_p2p import InvalidAd

WINDOW = timedelta(days=30)
MAX_LOOKBACK = timedelta(days=180)
ROWS = 50  # Binance devuelve máx. 50 por página (observado); pedir más desalinea la paginación


@dataclass
class OrderFetch:
    orders: list[Order] = field(default_factory=list)
    rejected: int = 0
    requests: int = 0
    reported_totals: list[int] = field(default_factory=list)


class BinanceAccount:
    def __init__(self, client: BinanceP2PClient, *, clock: Callable[[], datetime] | None = None, max_pages: int = 50) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_pages = max_pages

    def _windows(self, since: datetime) -> Iterator[tuple[int, int]]:
        end = self._clock()
        start_limit = max(since, end - MAX_LOOKBACK)
        while end > start_limit:
            start = max(end - WINDOW, start_limit)
            yield int(start.timestamp() * 1000), int(end.timestamp() * 1000)
            end = start - timedelta(milliseconds=1)

    def fetch_orders(self, since: datetime, on_progress: Callable[[str], None] | None = None) -> OrderFetch:
        out = OrderFetch()
        seen: set[str] = set()
        for start_ms, end_ms in self._windows(since):
            got = 0
            for page in range(1, self._max_pages + 1):
                params = {"startTimestamp": start_ms, "endTimestamp": end_ms, "page": page, "rows": ROWS}
                r = self._client.call(ep.ORDER_HISTORY, params)
                out.requests += 1
                if not r.ok:
                    raise MarketDataError(f"historial de órdenes: {r.outcome.value} {r.code or ''} {r.message or ''}".strip())
                items = _items(r.data)
                got += len(items)
                if page == 1 and r.total is not None:
                    out.reported_totals.append(r.total)
                for item in items:
                    try:
                        order = order_from_history(item)
                    except InvalidOrder:
                        out.rejected += 1
                        continue
                    if order.order_id not in seen:
                        seen.add(order.order_id)
                        out.orders.append(order)
                if on_progress:
                    day = datetime.fromtimestamp(start_ms / 1000, UTC).date()
                    on_progress(f"ventana desde {day}: página {page}, {len(out.orders)} órdenes")
                # Cortar solo cuando no llegan más filas o ya se tiene el total informado.
                if not items or (r.total is not None and got >= r.total) or (r.total is None and len(items) < ROWS):
                    break
        return out

    def fetch_my_ads(self) -> list[MyAd]:
        ads: list[MyAd] = []
        for page in range(1, 11):
            r = self._client.call(ep.MY_ADS, body={"page": page, "rows": 20})
            if not r.ok:
                raise MarketDataError(f"mis anuncios: {r.outcome.value} {r.code or ''} {r.message or ''}".strip())
            items = _items(r.data)
            for item in items:
                try:
                    ads.append(my_ad_from_detail(item))
                except InvalidAd:
                    continue
            if len(items) < 20:
                break
        return ads
