"""Catálogo de endpoints oficiales de Binance P2P/C2C.

Fuente: Binance Skills Hub, skill `p2p` v1.1.0 (references/agent-sapi-api.md) y
developers.binance.com/docs/c2c. Solo se usan endpoints documentados.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Base(str, Enum):
    PUBLIC = "public"  # https://www.binance.com — sin autenticación
    SAPI = "sapi"  # https://api.binance.com — HMAC


class BodyKind(str, Enum):
    NONE = "none"
    JSON = "json"


@dataclass(frozen=True)
class Endpoint:
    name: str
    method: str
    path: str
    base: Base
    signed: bool
    write: bool = False
    body: BodyKind = BodyKind.NONE
    merchant_only: bool = False


# --- Público (sin autenticación) ---
PUBLIC_QUOTE_PRICE = Endpoint("public.quote_price", "GET", "/bapi/c2c/v1/public/c2c/agent/quote-price", Base.PUBLIC, False)
PUBLIC_AD_LIST = Endpoint("public.ad_list", "GET", "/bapi/c2c/v1/public/c2c/agent/ad-list", Base.PUBLIC, False)
PUBLIC_TRADE_METHODS = Endpoint("public.trade_methods", "GET", "/bapi/c2c/v1/public/c2c/agent/trade-methods", Base.PUBLIC, False)

# --- SAPI lectura ---
ORDER_HISTORY = Endpoint("sapi.order_history", "GET", "/sapi/v1/c2c/agent/orderMatch/listUserOrderHistory", Base.SAPI, True)
LIST_ORDERS = Endpoint("sapi.list_orders", "POST", "/sapi/v1/c2c/agent/orderMatch/listOrders", Base.SAPI, True, body=BodyKind.JSON)
ORDER_DETAIL = Endpoint("sapi.order_detail", "POST", "/sapi/v1/c2c/agent/orderMatch/getUserOrderDetail", Base.SAPI, True, body=BodyKind.JSON)
QUERY_COMPLAINTS = Endpoint("sapi.query_complaints", "POST", "/sapi/v1/c2c/agent/complaint/query-complaints", Base.SAPI, True, body=BodyKind.JSON)
AD_DETAIL = Endpoint("sapi.ad_detail", "POST", "/sapi/v1/c2c/agent/ads/getDetailByNo", Base.SAPI, True)
MY_ADS = Endpoint("sapi.my_ads", "POST", "/sapi/v1/c2c/agent/ads/listWithPagination", Base.SAPI, True, body=BodyKind.JSON)
ADS_SEARCH = Endpoint("sapi.ads_search", "POST", "/sapi/v1/c2c/agent/ads/search", Base.SAPI, True, body=BodyKind.JSON)
REFERENCE_PRICE = Endpoint("sapi.reference_price", "POST", "/sapi/v1/c2c/agent/ads/getReferencePrice", Base.SAPI, True, body=BodyKind.JSON)
ADS_CATEGORY = Endpoint("sapi.ads_category", "GET", "/sapi/v1/c2c/agent/ads/getAvailableAdsCategory", Base.SAPI, True)
MY_PAY_METHODS = Endpoint("sapi.my_pay_methods", "GET", "/sapi/v1/c2c/agent/ads/getPayMethodByUserId", Base.SAPI, True)
ALL_TRADE_METHODS = Endpoint("sapi.all_trade_methods", "POST", "/sapi/v1/c2c/agent/ads/listAllTradeMethods", Base.SAPI, True)
MERCHANT_AD_DETAILS = Endpoint("sapi.merchant_ad_details", "GET", "/sapi/v1/c2c/agent/merchant/getAdDetails", Base.SAPI, True)

# --- SAPI escritura (Fase 9; requieren permiso de comerciante) ---
AD_POST = Endpoint("sapi.ad_post", "POST", "/sapi/v1/c2c/agent/ads/post", Base.SAPI, True, write=True, body=BodyKind.JSON, merchant_only=True)
AD_UPDATE = Endpoint("sapi.ad_update", "POST", "/sapi/v1/c2c/agent/ads/update", Base.SAPI, True, write=True, body=BodyKind.JSON, merchant_only=True)
AD_UPDATE_STATUS = Endpoint("sapi.ad_update_status", "POST", "/sapi/v1/c2c/agent/ads/updateStatus", Base.SAPI, True, write=True, body=BodyKind.JSON, merchant_only=True)

ALL_ENDPOINTS = [
    v for v in globals().copy().values() if isinstance(v, Endpoint)
]
