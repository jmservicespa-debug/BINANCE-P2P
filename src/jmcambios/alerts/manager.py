"""Gestor de alertas: evita repetir el mismo aviso y registra todo en la base."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from jmcambios.alerts.channels import Channel, ChannelError
from jmcambios.storage.history import HistoryStore

log = logging.getLogger(__name__)

INFO, IMPORTANT, URGENT = "info", "importante", "urgente"
ICONS = {INFO: "ℹ️", IMPORTANT: "🔔", URGENT: "🚨"}


@dataclass(frozen=True)
class Alert:
    key: str  # misma clave = mismo asunto (no se repite dentro de `cooldown_s`)
    severity: str
    title: str
    body: str
    cooldown_s: int = 1800


@dataclass(frozen=True)
class Delivery:
    alert: Alert
    sent_to: list[str]
    suppressed: bool
    errors: list[str]


class AlertManager:
    def __init__(self, channels: list[Channel], store: HistoryStore | None = None) -> None:
        self.channels = channels
        self._store = store
        self._last: dict[str, int] = {}  # respaldo en memoria si no hay base

    def _last_ts(self, key: str) -> int | None:
        if self._store is not None:
            return self._store.last_alert_ts(key)
        return self._last.get(key)

    def notify(self, alert: Alert, now_ts: int) -> Delivery:
        last = self._last_ts(alert.key)
        if last is not None and now_ts - last < alert.cooldown_s:
            return Delivery(alert, [], True, [])
        sent, errors = [], []
        title = f"{ICONS.get(alert.severity, '')} {alert.title}".strip()
        for ch in self.channels:
            try:
                ch.send(title, alert.body)
                sent.append(ch.name)
            except ChannelError as exc:
                errors.append(f"{ch.name}: {exc}")
                log.warning("no se pudo enviar la alerta por %s: %s", ch.name, exc)
        self._last[alert.key] = now_ts
        if self._store is not None:
            self._store.record_alert(now_ts, alert.key, alert.severity, alert.title, alert.body, sent, False, errors)
        return Delivery(alert, sent, False, errors)
