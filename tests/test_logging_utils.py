import logging

from jmcambios.logging_utils import RedactingFilter, mask_key, redact


def test_mask_key():
    assert mask_key("abcdefghijklmnop") == "abcde...mnop"
    assert mask_key("short") == "***"
    assert mask_key(None) == ""


def test_redact_query_and_json():
    text = 'GET /x?page=1&signature=deadbeef {"payId": 123, "secret":"s3"}'
    out = redact(text)
    assert "deadbeef" not in out and "123" not in out and "s3" not in out
    assert "signature=***" in out


def test_redact_known_secrets():
    assert "MYAPIKEY1234567" not in redact("key=MYAPIKEY1234567", ["MYAPIKEY1234567"])


def test_filter_redacts_log_record():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "url %s", ("a?signature=abc",), None)
    RedactingFilter(["xyz"]).filter(record)
    assert "abc" not in record.getMessage()
