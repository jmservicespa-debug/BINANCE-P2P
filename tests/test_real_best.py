from decimal import Decimal

from jmcambios.analysis.bait import real_best
from jmcambios.analysis.filters import AdFilter
from jmcambios.domain import Side
from jmcambios.monitor.report import money, render
from tests.fixtures import make_ad
from tests.test_phase6 import cycle

D = Decimal


def bid(i, price, qty, user=None):
    return make_ad(f"b{i}", price, qty, side=Side.BID, user=user or f"b{i}")


def ask(i, price, qty):
    return make_ad(f"a{i}", price, qty, side=Side.ASK, user=f"s{i}")


def test_bait_on_top_is_skipped_for_buyers():
    # 3.190 con 50 USDT (≈160 mil) y 3.175 con 30 USDT: carnada; el real está donde se juntan 2 millones.
    book = [bid(1, "3190", "50"), bid(2, "3175", "30"), bid(3, "3160", "800"), bid(4, "3150", "2000")]
    r = real_best(Side.BID, book)
    assert r.best == D("3190") and r.price == D("3160") and r.distorted
    assert [a.ad_id for a in r.bait] == ["b1", "b2"] and r.bait_fiat == D("3190") * 50 + D("3175") * 30


def test_sellers_side_and_honest_top():
    book = [ask(1, "3200", "1000"), ask(2, "3210", "50")]
    r = real_best(Side.ASK, book)
    assert r.price == r.best == D("3200") and not r.bait and not r.distorted
    r = real_best(Side.ASK, [ask(2, "3210", "50"), ask(1, "3195", "20"), ask(3, "3220", "900")])
    assert r.best == D("3195") and r.price == D("3220") and len(r.bait) == 2


def test_thin_book_and_own_ads_excluded():
    assert real_best(Side.BID, [bid(1, "3190", "10")]).price is None
    assert real_best(Side.BID, []).best is None
    # mi propio anuncio no cuenta ni como carnada ni como liquidez
    r = real_best(Side.BID, [bid(1, "3190", "5000", user="yo"), bid(2, "3160", "1000")], exclude_users={"yo"})
    assert r.best == r.price == D("3160")


def test_same_price_as_real_is_not_bait():
    r = real_best(Side.BID, [bid(1, "3160", "100"), bid(2, "3160", "900")])
    assert r.price == D("3160") and not r.bait


def test_console_shows_real_best_and_pc_time():
    out = render(cycle([ask(1, "3200", "1000")], [bid(1, "3190", "50"), bid(2, "3160", "1000")]), AdFilter())
    assert "hora de tu computador; Colombia" in out
    assert "Mejor precio REAL para vender" in out and "posible carnada" in out and money(D("3160")) in out
    assert "Mejor precio REAL para comprar" in out and "el primero ya tiene plata detrás" in out


def test_small_gap_is_not_bait():
    # Caso real del 22-10: vendedores a 3.167,98 y 3.169 con poca plata, real 3.169 → 1 peso: no es carnada.
    r = real_best(Side.ASK, [ask(1, "3167.98", "300"), ask(2, "3169", "1000")])
    assert r.price == D("3169") and r.bait and not r.distorted
    from jmcambios.analysis.bait import describe
    assert "sin carnada" in describe(r, money)


def test_panel_disconnect_is_quiet(capsys):
    from jmcambios.dashboard.server import _Server
    srv = _Server.__new__(_Server)
    try:
        raise ConnectionAbortedError("celular cerró")
    except ConnectionAbortedError:
        srv.handle_error(None, ("1.2.3.4", 1))
    assert capsys.readouterr().err == ""
