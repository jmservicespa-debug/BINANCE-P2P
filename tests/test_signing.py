import hashlib
import hmac

from jmcambios.connectors.binance.signing import encode_query, sign, signed_query

# Vector de ejemplo de la documentación oficial de firma de Binance (HMAC SHA256).
DOC_SECRET = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
DOC_QUERY = "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1&recvWindow=5000&timestamp=1499827319559"
DOC_SIGNATURE = "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"


def test_sign_matches_binance_documentation_vector():
    assert sign(DOC_QUERY, DOC_SECRET) == DOC_SIGNATURE


def test_encode_query_keeps_insertion_order():
    assert encode_query({"rows": 20, "page": 1, "a": "x"}) == "rows=20&page=1&a=x"


def test_encode_query_rfc3986_and_skips_none():
    assert encode_query({"q": "a b/ñ", "skip": None, "t": "-_.~"}) == "q=a%20b%2F%C3%B1&t=-_.~"


def test_encode_query_bools_lowercase():
    assert encode_query({"onlineNow": True}) == "onlineNow=true"


def test_signed_query_appends_recvwindow_timestamp_then_signature():
    q = signed_query({"page": 1, "rows": 20}, "secret", 1710460800000, 60000)
    unsigned = "page=1&rows=20&recvWindow=60000&timestamp=1710460800000"
    expected = hmac.new(b"secret", unsigned.encode(), hashlib.sha256).hexdigest()
    assert q == f"{unsigned}&signature={expected}"
