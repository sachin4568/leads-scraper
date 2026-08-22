from __future__ import annotations

from backend.app.enrichment.phone_validator import PhoneValidator


def test_phone_validator_us_domestic_formatting() -> None:
    validator = PhoneValidator()
    res = validator.validate("(415) 555-2671")
    assert res.is_valid is True
    assert res.e164_format == "+14155552671"
    assert res.country_code == "1"
    assert res.national_number == "4155552671"


def test_phone_validator_international_formatting() -> None:
    validator = PhoneValidator()
    res = validator.validate("+91 98765 43210")
    assert res.is_valid is True
    assert res.e164_format == "+919876543210"
    assert res.country_code == "91"
    assert res.national_number == "9876543210"


def test_phone_validator_toll_free_classification() -> None:
    validator = PhoneValidator()
    res = validator.validate("+1 (800) 555-0199")
    assert res.is_valid is True
    assert res.e164_format == "+18005550199"
    assert res.line_type == "toll_free"


def test_phone_validator_rejects_invalid_digit_length() -> None:
    validator = PhoneValidator()

    # Too short
    res1 = validator.validate("1234")
    assert res1.is_valid is False
    assert "length" in res1.error_message.lower()

    # Too long
    res2 = validator.validate("+1 999 888 777 666 555 444 333")
    assert res2.is_valid is False
    assert "length" in res2.error_message.lower()
