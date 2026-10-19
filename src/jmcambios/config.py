"""Configuración del sistema y resolución del modo de operación efectivo.

El modo AUTOMATIC nunca se activa solo por configurarlo: `effective_mode` lo
degrada si falta cualquiera de las condiciones de seguridad.
"""

from __future__ import annotations

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
