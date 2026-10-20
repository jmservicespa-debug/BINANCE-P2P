"""Fuente de datos de mercado Binance P2P (módulo 1, solo lectura).

Con credenciales usa `ads/search` (SAPI) y recorre todas las páginas del libro.
Sin credenciales usa la lista pública, limitada a 20 anuncios por lado
(el snapshot se marca como incompleto).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from jmcambios.config import Settings
from jmcambios.connectors.binance import endpoints as ep
from jmcambios.connectors.binance.client import ApiResult, BinanceP2PClient
from jmcambios.domain import Ad, MarketSnapshot, RejectedAd, Side
from jmcambios.normalizer import binance_p2p as norm

log = logging.getLogger(__name__)

PUBLIC_LIMIT = 20


class MarketDataError(RuntimeError):
    """No se pudo obtener un snapshot utilizable."""


class MarketSource(Protocol):
    venue: str

    def fetch(self, side: Side) -> MarketSnapshot: ...


def _items(data: object) -> list[object]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "data", "rows", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


class BinanceMarketSource:
    venue = norm.VENUE

    def __init__(
        self,
        client: BinanceP2PClient,
        settings: Settings,
        *,
        rows: int = 20,
        max_pages: int = 30,  # el lado de compra ya pasa de 400 anuncios (20 por página)
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._rows = rows
        self._max_pages = max_pages
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def authenticated(self) -> bool:
        return self._settings.has_read_credentials

    def fetch(self, side: Side) -> MarketSnapshot:
        if self.authenticated:
            return self._fetch_search(side)
        return self._fetch_public(side)

    def _fail(self, side: Side, result: ApiResult) -> MarketDataError:
        return MarketDataError(f"{result.endpoint} {side.value}: {result.outcome.value} {result.code or ''} {result.message or ''}".strip())

    def _fetch_search(self, side: Side) -> MarketSnapshot:
        s = self._settings
        query = norm.query_for_side(side)
        taken_at = self._clock()
        ads: dict[str, Ad] = {}
        rejected: list[RejectedAd] = []
        notes: list[str] = []
        total: int | None = None
        complete = False
        side_mismatch = 0

        for page in range(1, self._max_pages + 1):
            body = {"fiat": s.fiat, "asset": s.asset, "tradeType": query, "page": page, "rows": self._rows}
            r = self._client.call(ep.ADS_SEARCH, body=body)
            if not r.ok:
                if page == 1:
                    raise self._fail(side, r)
                notes.append(f"página {page} falló ({r.outcome.value}); snapshot incompleto")
                break
            total = r.total if r.total is not None else total
            items = _items(r.data)
            side_mismatch += sum(1 for i in items if norm.reported_side(i) not in (None, side))
            page_ads, page_rejected = norm.normalize_many(items, norm.from_sapi_search, query, s.asset, s.fiat)
            rejected.extend(page_rejected)
            for ad in page_ads:
                ads.setdefault(ad.ad_id, ad)  # el libro se mueve entre páginas: sin duplicados
            seen = (page - 1) * self._rows + len(items)
            if not items or len(items) < self._rows or (total is not None and seen >= total):
                complete = True
                break
        else:
            notes.append(f"se alcanzó el máximo de {self._max_pages} páginas")

        if side_mismatch:
            notes.append(f"{side_mismatch} anuncios declaran un lado distinto al esperado para tradeType={query}")
        return MarketSnapshot(
            venue=self.venue,
            asset=s.asset,
            fiat=s.fiat,
            side=side,
            taken_at=taken_at,
            ads=list(ads.values()),
            source=ep.ADS_SEARCH.name,
            reported_total=total,
            complete=complete,
            rejected=rejected,
            notes=notes,
        )

    def _fetch_public(self, side: Side) -> MarketSnapshot:
        s = self._settings
        query = norm.query_for_side(side)
        taken_at = self._clock()
        r = self._client.call(ep.PUBLIC_AD_LIST, {"fiat": s.fiat, "asset": s.asset, "tradeType": query, "limit": PUBLIC_LIMIT})
        if not r.ok:
            raise self._fail(side, r)
        ads, rejected = norm.normalize_many(_items(r.data), norm.from_public_ad_list, query, s.asset, s.fiat)
        return MarketSnapshot(
            venue=self.venue,
            asset=s.asset,
            fiat=s.fiat,
            side=side,
            taken_at=taken_at,
            ads=ads,
            source=ep.PUBLIC_AD_LIST.name,
            reported_total=None,
            complete=False,
            rejected=rejected,
            notes=[f"sin API key: solo los primeros {PUBLIC_LIMIT} anuncios (profundidad limitada)"],
        )
