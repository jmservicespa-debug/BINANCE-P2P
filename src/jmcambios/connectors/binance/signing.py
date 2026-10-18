"""Firma HMAC-SHA256 para la C2C Agent SAPI de Binance.

Particularidades documentadas por Binance para SAPI C2C:
- NO se ordenan los parámetros: se respeta el orden de inserción.
- Nombres y valores se codifican en UTF-8 según RFC 3986 (no reservados: A-Z a-z 0-9 - _ . ~).
- La cadena codificada exacta se usa para firmar y para la petición.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from urllib.parse import quote


def encode_query(params: Mapping[str, object]) -> str:
    parts = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        parts.append(f"{quote(str(key), safe='-_.~')}={quote(str(value), safe='-_.~')}")
    return "&".join(parts)


def sign(query_string: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()


def signed_query(params: Mapping[str, object], secret: str, timestamp_ms: int, recv_window_ms: int) -> str:
    """Construye `params&recvWindow=..&timestamp=..&signature=..` sin reordenar."""
    full = dict(params)
    full["recvWindow"] = recv_window_ms
    full["timestamp"] = timestamp_ms
    query = encode_query(full)
    return f"{query}&signature={sign(query, secret)}"
