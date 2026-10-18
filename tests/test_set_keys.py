from jmcambios.config import Settings
from jmcambios.tools import set_keys

KEY = "A" * 32 + "b" * 32
SECRET = "C" * 32 + "d" * 32


def feeder(*values):
    it = iter(values)
    return lambda _prompt: next(it)


def test_upsert_replaces_existing_lines_and_keeps_trade_lines():
    text = "# c\r\nBINANCE_API_KEY=\r\nBINANCE_API_SECRET=\r\nBINANCE_TRADE_API_KEY=\r\n"
    out = set_keys.upsert_env(text, {"BINANCE_API_KEY": "k", "BINANCE_API_SECRET": "s"})
    assert out == "# c\nBINANCE_API_KEY=k\nBINANCE_API_SECRET=s\nBINANCE_TRADE_API_KEY=\n"


def test_upsert_appends_missing():
    assert set_keys.upsert_env("X=1", {"BINANCE_API_KEY": "k"}) == "X=1\nBINANCE_API_KEY=k\n"


def test_main_writes_env_readable_by_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for var in ("BINANCE_API_KEY", "BINANCE_API_SECRET"):
        monkeypatch.delenv(var, raising=False)
    env = tmp_path / ".env"
    env.write_bytes("﻿JMC_MODE=OBSERVATION\r\nBINANCE_API_KEY=\r\nBINANCE_API_SECRET=\r\n".encode())

    rc = set_keys.main(prompt=feeder(f"  {KEY} \n", f'"{SECRET}"'), env_path=env)

    assert rc == 0
    s = Settings(_env_file=str(env))
    assert s.api_key.get_secret_value() == KEY
    assert s.api_secret.get_secret_value() == SECRET


def test_empty_paste_retries_then_succeeds(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("BINANCE_API_KEY=\nBINANCE_API_SECRET=\n")
    assert set_keys.main(prompt=feeder("", KEY, SECRET), env_path=env) == 0
    assert "vacía" in capsys.readouterr().out


def test_gives_up_after_three_empty_and_writes_nothing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BINANCE_API_KEY=\n")
    assert set_keys.main(prompt=feeder("", "", ""), env_path=env) == 1
    assert env.read_text() == "BINANCE_API_KEY=\n"


def test_same_key_twice_rejected(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BINANCE_API_KEY=\n")
    assert set_keys.main(prompt=feeder(KEY, KEY), env_path=env) == 1
    assert env.read_text() == "BINANCE_API_KEY=\n"


def test_output_never_prints_full_key(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("")
    set_keys.main(prompt=feeder(KEY, SECRET), env_path=env)
    out = capsys.readouterr().out
    assert KEY not in out and SECRET not in out
