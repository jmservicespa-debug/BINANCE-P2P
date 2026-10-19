import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from jmcambios.alerts import rules
from jmcambios.alerts.channels import ChannelError, EmailChannel, MemoryChannel, TelegramChannel
from jmcambios.alerts.manager import IMPORTANT, INFO, Alert, AlertManager
from jmcambios.analysis import crossing
from jmcambios.analysis.competition import position
from jmcambios.analysis.market_stats import spread, summarize
from jmcambios.analysis.pressure import PressureReport
from jmcambios.config import Mode, Settings
from jmcambios.dashboard import server as panel
from jmcambios.domain import MarketSnapshot, Side
from jmcambios.domain.account import MyAd, OrderSide
from jmcambios.monitor.advisor import Advisor
from jmcambios.monitor.service import CycleResult
from jmcambios.pricing.engine import AdProfile, Costs, plan
from jmcambios.storage.history import HistoryStore
from tests.fixtures import make_ad

D = Decimal
T0 = datetime(2026, 10, 19, 16, 0, tzinfo=UTC)
TOKEN = "123456789:AAHabcdefghijklmnopqrstuvwxyz012345"
METHODS = {"DaviviendaSA": D("0"), "Nequi": D("0.004")}


def ask(i, price, methods=("DaviviendaSA",), user=None):
    return make_ad(f"a{i}", price, "1000", side=Side.ASK, methods=methods, user=user or f"s{i}", lo="100000", hi="5000000")


def bid(i, price, methods=("DaviviendaSA",), user=None):
    return make_ad(f"b{i}", price, "1000", side=Side.BID, methods=methods, user=user or f"b{i}", lo="100000", hi="5000000")


def my_ad(side, price, status=1, ad_id="473152"):
    return MyAd(venue="binance_p2p", ad_id=ad_id, side=side, asset="USDT", fiat="COP", price=D(price), price_type=1,
                floating_ratio=None, available_qty=D("500"), min_fiat=D("200000"), max_fiat=D("3000000"),
                payment_methods=("DaviviendaSA",), status=status, commission_rate=D("0.002"))


def cycle(asks, bids, *, errors=(), pressure=None):
    r = CycleResult(started_at=T0)
    for side, ads in ((Side.ASK, asks), (Side.BID, bids)):
        if ads is None:
            continue
        r.snapshots[side] = MarketSnapshot(venue="binance_p2p", asset="USDT", fiat="COP", side=side, taken_at=T0,
                                           ads=ads, source="test", reported_total=len(ads), complete=True)
        r.stats[side] = summarize(side, ads)
    if asks is not None and bids is not None:
        r.spread = spread(r.stats[Side.ASK], r.stats[Side.BID])
        r.cross = crossing.analyze(asks, bids, METHODS)
    r.errors = list(errors)
    r.pressure = pressure
    return r


# ------------------------------------------------------------------ canales
def test_telegram_send_and_errors_never_leak_token():
    seen = []

    def handler(req):
        seen.append(req)
        if b"falla" in req.content:
            return httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})
        return httpx.Response(200, json={"ok": True})

    ch = TelegramChannel(TOKEN, "42", transport=httpx.MockTransport(handler))
    ch.send("Título", "cuerpo")
    assert seen[0].url.path == f"/bot{TOKEN}/sendMessage"
    assert json.loads(seen[0].content) == {"chat_id": "42", "text": "Título\n\ncuerpo", "disable_web_page_preview": True}
    with pytest.raises(ChannelError) as e:
        ch.send("falla", "x")
    assert "chat not found" in str(e.value) and TOKEN not in str(e.value)

    def boom(req):
        raise httpx.ConnectError(f"no route to {req.url}")

    with pytest.raises(ChannelError) as e:
        TelegramChannel(TOKEN, "42", transport=httpx.MockTransport(boom)).send("t", "b")
    assert TOKEN not in str(e.value) and e.value.__cause__ is None


def test_telegram_get_me():
    ok = TelegramChannel(TOKEN, "", transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"ok": True, "result": {"username": "jmcambios_bot"}})))
    assert ok.bot_username() == "jmcambios_bot"
    bad = TelegramChannel(TOKEN, "", transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"ok": False})))
    with pytest.raises(ChannelError):
        bad.bot_username()


def test_telegram_chat_ids():
    payload = {"ok": True, "result": [
        {"message": {"chat": {"id": 42, "first_name": "Jamer"}}},
        {"message": {"chat": {"id": 42, "first_name": "Jamer"}}},
        {"my_chat_member": {"chat": {"id": -100, "title": "Grupo"}}},
        {"edited_message": {"chat": {"id": 7, "first_name": "Otro"}}},
    ]}
    ch = TelegramChannel(TOKEN, "", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    assert ch.chat_ids() == [("42", "Jamer"), ("-100", "Grupo"), ("7", "Otro")]
    bad = TelegramChannel(TOKEN, "", transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"ok": False})))
    with pytest.raises(ChannelError):
        bad.chat_ids()


class FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.calls = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.calls.append("tls")

    def login(self, user, pw):
        self.calls.append(("login", user))

    def send_message(self, msg):
        self.calls.append(("send", msg["Subject"], msg["To"]))


def test_email_channel():
    EmailChannel("smtp.x", 587, "yo@x.com", "pw", "yo@x.com", smtp_factory=FakeSMTP).send("Hola", "cuerpo")
    assert FakeSMTP.instances[-1].calls == ["tls", ("login", "yo@x.com"), ("send", "[JM Cambios] Hola", "yo@x.com")]


# ------------------------------------------------------------------ gestor
def test_manager_cooldown_records_and_survives_channel_errors():
    store = HistoryStore(":memory:")
    ok, broken = MemoryChannel("a"), MemoryChannel("b", fail=True)
    mgr = AlertManager([ok, broken], store)
    a = Alert("cruce", IMPORTANT, "Cruce", "detalle", cooldown_s=600)
    d1 = mgr.notify(a, 1000)
    assert d1.sent_to == ["a"] and d1.errors and not d1.suppressed
    assert ok.sent == [("🔔 Cruce", "detalle")]
    assert mgr.notify(a, 1300).suppressed  # dentro del enfriamiento
    assert not mgr.notify(a, 1700).suppressed
    rows = store.recent_alerts()
    assert len(rows) == 2 and rows[0]["errors"].startswith("b:")
    assert not AlertManager([ok]).notify(Alert("x", INFO, "t", "b", cooldown_s=0), 1).suppressed  # sin base


# ------------------------------------------------------------------ reglas
def test_cross_and_pressure_rules():
    r = cycle([ask(1, "3150")], [bid(1, "3170", methods=("Nequi",))])
    alert = rules.cross_alert(r.cross)
    assert alert and alert.key == "cruce" and "DaviviendaSA" in alert.body and "Nequi" in alert.body
    assert rules.cross_alert(cycle([ask(1, "3170")], [bid(1, "3160")]).cross) is None
    assert rules.pressure_alert(PressureReport(score=55, confidence=70, label="")).key == "presion:alcista"
    assert rules.pressure_alert(PressureReport(score=-55, confidence=70, label="")).key == "presion:bajista"
    assert rules.pressure_alert(PressureReport(score=55, confidence=40, label="")) is None
    assert rules.pressure_alert(PressureReport(score=20, confidence=90, label="")) is None


def test_error_rules():
    assert [a.key for a in rules.error_alerts(["AUTH_ERROR -2015"], 1, False)] == ["auth"]
    assert [a.key for a in rules.error_alerts(["NETWORK_ERROR"], 3, False)] == ["fallas"]
    assert rules.error_alerts(["NETWORK_ERROR"], 2, False) == []
    assert [a.key for a in rules.error_alerts([], 0, True)] == ["recuperado"]


COSTS = Costs(maker_buy=D("0.00181"), maker_sell=D("0.00008"), gmf=D("0"), gmf_worst=D("0.004"), min_margin=D("0.003"))
PROFILE = AdProfile(("DaviviendaSA",), D("200000"), D("3000000"))


def _setup_ads():
    asks = [ask(i, str(3200 + i)) for i in range(10)]
    bids = [bid(i, str(3150 - i)) for i in range(10)]
    return asks, bids, plan(asks, bids, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS)


def test_my_ad_rules():
    asks, bids, pp = _setup_ads()
    target = pp.scenarios[1].buy.price  # equilibrado
    keys = lambda ads: [a.key for a in rules.my_ad_alerts([position(m, bids) for m in ads], pp)]  # noqa: E731
    assert keys([my_ad(OrderSide.BUY, "3160")]) == ["anuncio:473152:regalando"]  # 10 COP sobre el mejor
    assert keys([my_ad(OrderSide.BUY, str(target + D("0.5")))]) == []  # dentro de la tolerancia: sin aviso
    assert keys([my_ad(OrderSide.BUY, str(target - 20))]) == ["anuncio:473152:atras"]
    assert keys([my_ad(OrderSide.BUY, "3160", status=3)]) == []  # fuera de línea
    sell = my_ad(OrderSide.SELL, "3150", ad_id="838528")  # muy por debajo del mejor vendedor (3200)
    assert [a.key for a in rules.my_ad_alerts([position(sell, asks)], pp)] == ["anuncio:838528:regalando"]


def test_my_ad_margin_rule():
    asks, bids, pp = _setup_ads()
    # Un anuncio de compra más caro que el objetivo, sin pasar al mejor del mercado.
    bids2 = [bid(99, "3170")] + bids
    pp2 = plan(asks, bids2, buy_profile=PROFILE, sell_profile=PROFILE, costs=COSTS)
    tgt = next(s for s in pp2.scenarios if s.name == "equilibrado").buy.price
    mine = my_ad(OrderSide.BUY, str(tgt + 5))
    assert mine.price < D("3170")
    assert [a.key for a in rules.my_ad_alerts([position(mine, bids2)], pp2)] == ["anuncio:473152:margen"]


# ------------------------------------------------------------------ asesor
def test_advisor_state_alerts_and_ad_cadence(tmp_path):
    store = HistoryStore(":memory:")
    chan = MemoryChannel()
    calls = []

    def fetch():
        calls.append(1)
        return [my_ad(OrderSide.BUY, "3160")]

    state = tmp_path / "estado.json"
    adv = Advisor(orders=[], fiat="COP", gmf_by_account=METHODS, mode=Mode.RECOMMENDATION, fetch_my_ads=fetch,
                  ads_every=3, alerts=AlertManager([chan], store), state_path=state)
    asks, bids, _ = _setup_ads()
    for i in range(4):
        out = adv.process(cycle(asks, bids), 0, 1000 + i * 60)
    assert len(calls) == 2  # ciclos 1 y 4
    assert out.plan and [s.name for s in out.plan.scenarios] == ["conservador", "equilibrado", "agresivo"]
    s = json.loads(state.read_text(encoding="utf-8"))
    assert s["mode"] == "RECOMMENDATION" and s["market"]["ask"]["best"] == 3200.0 and s["market"]["bid"]["best"] == 3150.0
    assert len(s["plan"]["scenarios"]) == 3 and s["my_ads"][0]["suggested"] is not None
    assert s["costs"]["maker_buy"] == 0.002  # sin órdenes: tasa del anuncio
    assert [t for t, _ in chan.sent] == ["🔔 Tu anuncio de COMPRA está regalando margen"]  # una sola vez (enfriamiento)


def test_advisor_observation_mode_and_errors(tmp_path):
    chan = MemoryChannel()
    adv = Advisor(orders=[], fiat="COP", gmf_by_account=METHODS, mode=Mode.OBSERVATION,
                  fetch_my_ads=lambda: [my_ad(OrderSide.BUY, "3160")], alerts=AlertManager([chan]),
                  state_path=tmp_path / "e.json")
    asks, bids, _ = _setup_ads()
    adv.process(cycle(asks, bids), 0, 1000)
    assert chan.sent == []  # en observación no sugiere precios
    s = json.loads((tmp_path / "e.json").read_text(encoding="utf-8"))
    assert s["my_ads"][0]["suggested"] is None
    adv.process(cycle(None, None, errors=["NETWORK_ERROR"]), 3, 2000)
    adv.process(cycle(asks, bids), 0, 2060)
    assert [t for t, _ in chan.sent] == ["🚨 El monitor lleva 3 ciclos con errores", "ℹ️ Monitor recuperado"]


# ------------------------------------------------------------------ panel
@pytest.fixture
def running_panel(tmp_path):
    db, state = tmp_path / "h.db", tmp_path / "estado.json"
    with HistoryStore(db) as st:
        st.record_cycle("binance_p2p", "USDT/COP", 1000, None, D("3170"), D("3160"), None)
        st.record_alert(1000, "cruce", "importante", "Cruce", "detalle", ["telegram"], False, [])
    state.write_text(json.dumps({"generated_ts": int(datetime.now(UTC).timestamp()), "cycle_ts": 1000, "mode": "OBSERVATION",
                                 "market": {}, "my_ads": []}), encoding="utf-8")
    data = panel.PanelData(db, state, venue="binance_p2p", market="USDT/COP", fiat="COP", asset="USDT",
                           cost_config=panel.cost_config(METHODS))
    srv = panel.start(data, "clave", host="127.0.0.1", port=0)
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.headers.get("Content-Type"), r.read().decode("utf-8")


def test_panel_requires_token(running_panel):
    for path in ("/", "/api/estado", "/?t=otra"):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(running_panel + path)
        assert e.value.code == 403


def test_panel_icon_is_public(running_panel):
    with urllib.request.urlopen(running_panel + "/icon.png", timeout=5) as r:
        assert r.status == 200 and r.headers.get("Content-Type") == "image/png"
        assert r.read()[:4] == b"\x89PNG"


def test_panel_pages_and_api(running_panel):
    code, ctype, body = _get(running_panel + "/?t=clave")
    assert code == 200 and ctype.startswith("text/html") and "JM CAMBIOS" in body
    _, ctype, body = _get(running_panel + "/api/estado?t=clave")
    est = json.loads(body)
    assert ctype.startswith("application/json") and est["available"] and est["age_s"] < 60
    serie = json.loads(_get(running_panel + "/api/serie?horas=999999&t=clave")[2])
    assert serie["hours"] == 72
    rent = json.loads(_get(running_panel + "/api/rentabilidad?t=clave")[2])
    assert rent["buys"] == 0 and rent["realized"] == 0.0
    al = json.loads(_get(running_panel + "/api/alertas?t=clave")[2])
    assert al == [{"ts": 1000, "severity": "importante", "title": "Cruce", "body": "detalle"}]
    req = urllib.request.Request(running_panel + "/api/estado?t=clave", data=b"x", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 405


def test_despike_and_downsample(tmp_path):
    vals = [3150.0, 3151.0, 3150.5, 2800.0, 3151.0, 3150.0, None, 3152.0]
    clean = panel.despike(vals)
    assert clean[3] == pytest.approx(3150.25) and clean[:3] == vals[:3] and clean[6] is None
    # Un cambio sostenido (no aislado) se conserva.
    step = [3150.0] * 5 + [3170.0] * 5
    assert panel.despike(step) == step
    db = tmp_path / "h.db"
    with HistoryStore(db) as st:
        for i in range(1000):
            st.record_cycle("binance_p2p", "USDT/COP", 1000 + i * 60, None, D("3170"), D("3160"), None)
    data = panel.PanelData(db, tmp_path / "e.json", venue="binance_p2p", market="USDT/COP", fiat="COP", asset="USDT",
                           cost_config=panel.cost_config(METHODS))
    pts = data.serie(72, 1000 + 1000 * 60)["points"]
    assert len(pts) <= panel.MAX_POINTS and pts[0][1:] == [3170.0, 3160.0]


def test_panel_without_state(tmp_path):
    data = panel.PanelData(tmp_path / "h.db", tmp_path / "nada.json", venue="v", market="m", fiat="COP", asset="USDT",
                           cost_config=panel.cost_config(METHODS))
    assert data.estado(0)["available"] is False


# ------------------------------------------------------------------ CLIs y configuración
def test_ensure_token_creates_and_reuses(tmp_path, monkeypatch):
    from jmcambios.tools.panel_cli import ensure_token

    monkeypatch.delenv("JMC_DASHBOARD_TOKEN", raising=False)
    env = tmp_path / ".env"
    env.write_text("JMC_MODE=RECOMMENDATION\n", encoding="utf-8")
    tok = ensure_token(Settings(_env_file=None), env)
    assert len(tok) >= 20 and f"JMC_DASHBOARD_TOKEN={tok}" in env.read_text(encoding="utf-8")
    assert "JMC_MODE=RECOMMENDATION" in env.read_text(encoding="utf-8")
    monkeypatch.setenv("JMC_DASHBOARD_TOKEN", "fija")
    assert ensure_token(Settings(_env_file=None), env) == "fija"


def test_secret_values_include_alert_secrets(monkeypatch):
    monkeypatch.setenv("JMC_TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("JMC_TELEGRAM_CHAT_ID", "42")
    s = Settings(_env_file=None)
    assert s.has_telegram and TOKEN in s.secret_values()


class FakeBot:
    sent = []

    def __init__(self, token, chat_id):
        self.token, self.chat_id = token, chat_id

    def bot_username(self):
        return "jmcambios_bot"

    def chat_ids(self):
        return [("42", "Jamer")]

    def send(self, title, body):
        FakeBot.sent.append((self.chat_id, title))


def test_alertas_configurar(tmp_path, capsys):
    from jmcambios.tools import alerts_cli

    env = tmp_path / ".env"
    env.write_text("BINANCE_API_KEY=abc\n", encoding="utf-8")
    prompts = iter(["no-es-token", TOKEN])
    rc = alerts_cli.configurar(prompt=lambda _: next(prompts), read=lambda _: "", env_path=env, make=FakeBot)
    out = capsys.readouterr().out
    assert rc == 0 and TOKEN not in out and "no parece un token" in out and "https://t.me/jmcambios_bot" in out
    text = env.read_text(encoding="utf-8")
    assert f"JMC_TELEGRAM_BOT_TOKEN={TOKEN}" in text and "JMC_TELEGRAM_CHAT_ID=42" in text and "BINANCE_API_KEY=abc" in text
    assert FakeBot.sent[-1][0] == "42"



def test_alertas_probar_without_channels(capsys, monkeypatch):
    from jmcambios.tools import alerts_cli

    for v in ("JMC_TELEGRAM_BOT_TOKEN", "JMC_TELEGRAM_CHAT_ID", "JMC_EMAIL_SMTP_HOST"):
        monkeypatch.delenv(v, raising=False)
    assert alerts_cli.probar(Settings(_env_file=None)) == 1
    assert "jmcambios-alertas configurar" in capsys.readouterr().out
