"""Canales de envío de alertas.

Telegram usa la Bot API oficial (`POST https://api.telegram.org/bot<token>/sendMessage`).
El bot solo ENVÍA mensajes: el sistema no lee ni ejecuta nada que llegue por Telegram.
Ningún mensaje incluye claves, firmas ni datos de pago.
"""

from __future__ import annotations

import smtplib
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

import httpx

TELEGRAM_API = "https://api.telegram.org"


class ChannelError(Exception):
    pass


class Channel(Protocol):
    name: str

    def send(self, title: str, body: str) -> None: ...


class TelegramChannel:
    name = "telegram"

    def __init__(self, token: str, chat_id: str, *, transport: httpx.BaseTransport | None = None, timeout_s: float = 10.0) -> None:
        self._token = token
        self._chat_id = chat_id
        self._http = httpx.Client(transport=transport, timeout=timeout_s)

    def _url(self, method: str) -> str:
        return f"{TELEGRAM_API}/bot{self._token}/{method}"

    def send(self, title: str, body: str) -> None:
        try:
            r = self._http.post(self._url("sendMessage"), json={
                "chat_id": self._chat_id, "text": f"{title}\n\n{body}", "disable_web_page_preview": True,
            })
        except httpx.HTTPError as exc:
            # El mensaje de httpx puede incluir la URL con el token: no se propaga.
            raise ChannelError(f"Telegram no respondió ({type(exc).__name__})") from None
        if r.status_code != 200 or not r.json().get("ok"):
            desc = r.json().get("description", "") if r.headers.get("content-type", "").startswith("application/json") else ""
            raise ChannelError(f"Telegram rechazó el mensaje (HTTP {r.status_code}) {desc}".strip())

    def bot_username(self) -> str:
        """Usuario del bot dueño del token (valida el token y evita escribirle al bot equivocado)."""
        try:
            r = self._http.get(self._url("getMe"))
        except httpx.HTTPError as exc:
            raise ChannelError(f"Telegram no respondió ({type(exc).__name__})") from None
        data = r.json() if r.status_code == 200 else {}
        if not data.get("ok"):
            raise ChannelError(f"Telegram rechazó el token (HTTP {r.status_code}). Revisa que lo copiaste completo.")
        return data["result"].get("username", "")

    def chat_ids(self) -> list[tuple[str, str]]:
        """Chats que escribieron al bot (para configurar). Devuelve (chat_id, nombre)."""
        try:
            r = self._http.get(self._url("getUpdates"))
        except httpx.HTTPError as exc:
            raise ChannelError(f"Telegram no respondió ({type(exc).__name__})") from None
        data = r.json() if r.status_code == 200 else {}
        if not data.get("ok"):
            raise ChannelError(f"Telegram rechazó el token (HTTP {r.status_code}). Revisa que lo copiaste completo.")
        seen: dict[str, str] = {}
        for upd in data.get("result", []):
            holder = (upd.get("message") or upd.get("edited_message") or upd.get("my_chat_member")
                      or (upd.get("callback_query") or {}).get("message") or {})
            chat = holder.get("chat") or {}
            if "id" in chat:
                seen[str(chat["id"])] = chat.get("first_name") or chat.get("title") or chat.get("username") or ""
        return list(seen.items())

    def close(self) -> None:
        self._http.close()


class EmailChannel:
    name = "correo"

    def __init__(self, host: str, port: int, user: str, password: str, to: str,
                 *, smtp_factory: Callable[[str, int], smtplib.SMTP] | None = None) -> None:
        self._host, self._port, self._user, self._password, self._to = host, port, user, password, to
        self._factory = smtp_factory or (lambda h, p: smtplib.SMTP(h, p, timeout=15))

    def send(self, title: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = f"[JM Cambios] {title}"
        msg["From"] = self._user
        msg["To"] = self._to
        msg.set_content(body)
        try:
            with self._factory(self._host, self._port) as smtp:
                smtp.starttls()
                smtp.login(self._user, self._password)
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            raise ChannelError(f"no se pudo enviar el correo ({type(exc).__name__})") from None


@dataclass
class MemoryChannel:
    """Canal de pruebas: guarda los mensajes en memoria."""

    name: str = "memoria"
    sent: list[tuple[str, str]] = field(default_factory=list)
    fail: bool = False

    def send(self, title: str, body: str) -> None:
        if self.fail:
            raise ChannelError("falla simulada")
        self.sent.append((title, body))


def channels_from_settings(settings) -> list[Channel]:
    """Canales configurados en `.env` (Telegram y/o correo)."""
    out: list[Channel] = []
    if settings.has_telegram:
        out.append(TelegramChannel(settings.telegram_bot_token.get_secret_value(), settings.telegram_chat_id.strip()))
    if settings.has_email:
        out.append(EmailChannel(settings.email_smtp_host, settings.email_smtp_port, settings.email_user,
                                settings.email_password.get_secret_value(), settings.email_to))
    return out
