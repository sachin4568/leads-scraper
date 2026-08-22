from backend.app.main import before_send, scrub_pii


def test_structlog_scrubber_removes_contact_fields() -> None:
    assert scrub_pii(None, "info", {"email": "x@example.com", "safe": "value"}) == {"safe": "value"}


def test_sentry_scrubber_removes_request_data_and_pii() -> None:
    event = {
        "request": {"data": {"email": "x@example.com"}},
        "extra": {"phone": "123", "safe": "value"},
    }
    assert before_send(event, None) == {"request": {}, "extra": {"safe": "value"}}
