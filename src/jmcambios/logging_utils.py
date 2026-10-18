"""Registro estructurado (JSON) con redacción de secretos."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

_SENSITIVE_PARAM = re.compile(r"(?i)\b(signature|secret|api_secret|payId)=([^&\s\"']+)")
_SENSITIVE_JSON = re.compile(r"(?i)\"(signature|secret|api_secret|payId)\"\s*:\s*\"?[^,\"}]*\"?")


def mask_key(value: str | None) -> str:
    """Muestra solo los primeros 5 y últimos 4 caracteres de una API key."""
    if not value:
        return ""
    if len(value) <= 9:
        return "***"
    return f"{value[:5]}...{value[-4:]}"


def redact(text: str, secrets: list[str] | None = None) -> str:
    text = _SENSITIVE_PARAM.sub(lambda m: f"{m.group(1)}=***", text)
    text = _SENSITIVE_JSON.sub(lambda m: f'"{m.group(1)}": "***"', text)
    for secret in secrets or []:
        if secret:
            text = text.replace(secret, mask_key(secret))
    return text


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s]

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage(), self._secrets)
        record.args = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO, secrets: list[str] | None = None) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter(secrets))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
