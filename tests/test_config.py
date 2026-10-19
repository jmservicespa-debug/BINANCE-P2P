import pytest

from jmcambios.config import Mode, Settings, effective_mode


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("JMC_MODE", "JMC_AUTO_MODE_ENABLED", "BINANCE_API_KEY", "BINANCE_API_SECRET",
                "BINANCE_TRADE_API_KEY", "BINANCE_TRADE_API_SECRET"):
        monkeypatch.delenv(var, raising=False)


def make(**env) -> Settings:
    return Settings(_env_file=None, **env)


def test_default_mode_is_observation():
    s = make()
    assert s.mode is Mode.OBSERVATION
    assert effective_mode(s) == (Mode.OBSERVATION, [])


def test_automatic_degrades_without_all_conditions():
    s = make(JMC_MODE="AUTOMATIC")
    mode, reasons = effective_mode(s, integration_verified=True, risk_limits_configured=True)
    assert mode is Mode.RECOMMENDATION
    assert len(reasons) == 2  # flag desactivado + sin credenciales de escritura


def test_automatic_requires_verification_and_risk_limits():
    s = make(JMC_MODE="AUTOMATIC", JMC_AUTO_MODE_ENABLED=True,
             BINANCE_TRADE_API_KEY="k", BINANCE_TRADE_API_SECRET="s")
    assert effective_mode(s)[0] is Mode.RECOMMENDATION
    assert effective_mode(s, integration_verified=True)[0] is Mode.RECOMMENDATION
    assert effective_mode(s, integration_verified=True, risk_limits_configured=True) == (Mode.AUTOMATIC, [])


def test_blank_credentials_are_not_present():
    s = make(BINANCE_API_KEY="  ", BINANCE_API_SECRET="x")
    assert not s.has_read_credentials


def test_secrets_not_in_repr():
    s = make(BINANCE_API_KEY="AAAAAsupersecretZZZZ", BINANCE_API_SECRET="topsecret")
    assert "supersecret" not in repr(s)
    assert "topsecret" not in repr(s)


def test_min_margin_setting(monkeypatch):
    from decimal import Decimal

    from jmcambios.config import Settings

    monkeypatch.delenv("JMC_MARGEN_MIN", raising=False)
    assert Settings(_env_file=None).min_margin_pct == Decimal("0.3")
    monkeypatch.setenv("JMC_MARGEN_MIN", "1")
    assert Settings(_env_file=None).min_margin_pct == Decimal("1")
