"""Configuración del sistema y resolución del modo de operación efectivo.

El modo AUTOMATIC nunca se activa solo por configurarlo: `effective_mode` lo
degrada si falta cualquiera de las condiciones de seguridad.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(str, Enum):
    OBSERVATION = "OBSERVATION"
    RECOMMENDATION = "RECOMMENDATION"
    AUTOMATIC = "AUTOMATIC"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mode: Mode = Field(default=Mode.OBSERVATION, alias="JMC_MODE")
    auto_mode_enabled: bool = Field(default=False, alias="JMC_AUTO_MODE_ENABLED")
    asset: str = Field(default="USDT", alias="JMC_ASSET")
    fiat: str = Field(default="COP", alias="JMC_FIAT")

    api_key: SecretStr | None = Field(default=None, alias="BINANCE_API_KEY")
    api_secret: SecretStr | None = Field(default=None, alias="BINANCE_API_SECRET")
    trade_api_key: SecretStr | None = Field(default=None, alias="BINANCE_TRADE_API_KEY")
    trade_api_secret: SecretStr | None = Field(default=None, alias="BINANCE_TRADE_API_SECRET")

    # Métodos con los que pago/recibo y su 4x1000: "DaviviendaSA:0,Daviplata:0,BancolombiaSA:0.004,Nequi:0.004"
    my_pay_methods: str | None = Field(default=None, alias="JMC_MY_PAY_METHODS")

    # Margen neto mínimo del ciclo compra→venta, en % (después de comisiones y 4x1000).
    min_margin_pct: Decimal = Field(default=Decimal("0.3"), alias="JMC_MARGEN_MIN", ge=0, lt=20)

    # Competencia = solo comerciantes verificados (los no verificados no compiten por los mismos clientes).
    merchants_only: bool = Field(default=True, alias="JMC_SOLO_VERIFICADOS")

    # Alertas (Fase 6). Solo envían avisos: no reciben órdenes ni comandos.
    telegram_bot_token: SecretStr | None = Field(default=None, alias="JMC_TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="JMC_TELEGRAM_CHAT_ID")
    email_smtp_host: str | None = Field(default=None, alias="JMC_EMAIL_SMTP_HOST")
    email_smtp_port: int = Field(default=587, alias="JMC_EMAIL_SMTP_PORT")
    email_user: str | None = Field(default=None, alias="JMC_EMAIL_USER")
    email_password: SecretStr | None = Field(default=None, alias="JMC_EMAIL_PASSWORD")
    email_to: str | None = Field(default=None, alias="JMC_EMAIL_TO")
    # Panel (Fase 6): clave de acceso que va en el enlace del celular.
    dashboard_token: SecretStr | None = Field(default=None, alias="JMC_DASHBOARD_TOKEN")

    recv_window_ms: int = Field(default=10_000, alias="BINANCE_RECV_WINDOW", ge=1000, le=60_000)
    http_timeout_s: float = Field(default=15.0, alias="BINANCE_HTTP_TIMEOUT", gt=0)

    sapi_base_url: str = "https://api.binance.com"
    public_base_url: str = "https://www.binance.com"

    @property
    def has_read_credentials(self) -> bool:
        return _present(self.api_key) and _present(self.api_secret)

    @property
    def has_trade_credentials(self) -> bool:
        return _present(self.trade_api_key) and _present(self.trade_api_secret)

    @property
    def has_telegram(self) -> bool:
        return _present(self.telegram_bot_token) and bool((self.telegram_chat_id or "").strip())

    @property
    def has_email(self) -> bool:
        return bool(self.email_smtp_host and self.email_user and self.email_to) and _present(self.email_password)

    def secret_values(self) -> list[str]:
        """Todos los secretos configurados, para redactarlos de los registros."""
        fields = (self.api_key, self.api_secret, self.trade_api_key, self.trade_api_secret,
                  self.telegram_bot_token, self.email_password, self.dashboard_token)
        return [f.get_secret_value() for f in fields if _present(f)]


def _present(value: SecretStr | None) -> bool:
    return value is not None and value.get_secret_value().strip() != ""


def effective_mode(
    settings: Settings,
    *,
    integration_verified: bool = False,
    risk_limits_configured: bool = False,
) -> tuple[Mode, list[str]]:
    """Devuelve el modo que realmente se aplicará y los motivos de cualquier degradación."""
    if settings.mode is not Mode.AUTOMATIC:
        return settings.mode, []

    reasons: list[str] = []
    if not settings.auto_mode_enabled:
        reasons.append("JMC_AUTO_MODE_ENABLED no está activado")
    if not settings.has_trade_credentials:
        reasons.append("faltan credenciales de gestión de anuncios (BINANCE_TRADE_API_*)")
    if not integration_verified:
        reasons.append("la integración de escritura no ha sido verificada")
    if not risk_limits_configured:
        reasons.append("los límites de riesgo no están configurados")

    if reasons:
        return Mode.RECOMMENDATION, reasons
    return Mode.AUTOMATIC, []
