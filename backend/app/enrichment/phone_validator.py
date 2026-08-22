from __future__ import annotations

import logging
import re
from typing import ClassVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PhoneValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Overall phone validity status")
    original_phone: str = Field(..., description="The original input phone string")
    e164_format: str | None = Field(
        default=None, description="Standardized E.164 formatted phone number"
    )
    country_code: str | None = Field(
        default=None, description="Extracted country calling code e.g. '1', '91'"
    )
    national_number: str | None = Field(default=None, description="National subscriber number")
    line_type: str | None = Field(
        default=None, description="Line classification: mobile, landline, toll_free, unknown"
    )
    error_message: str | None = Field(default=None, description="Error detail if validation failed")


class PhoneValidator:
    COUNTRY_CODES: ClassVar[dict[str, str]] = {
        "1": "US/CA",
        "91": "IN",
        "44": "UK",
        "61": "AU",
        "49": "DE",
        "33": "FR",
        "81": "JP",
        "86": "CN",
    }

    TOLL_FREE_PREFIXES: ClassVar[set[str]] = {"800", "888", "877", "866", "855", "844", "833"}

    def validate(self, phone: str, default_country_code: str = "1") -> PhoneValidationResult:
        if not phone or not phone.strip():
            return PhoneValidationResult(
                is_valid=False,
                original_phone=phone or "",
                error_message="Empty phone number provided",
            )

        clean_input = phone.strip()
        has_leading_plus = clean_input.startswith("+")

        # Strip everything except digits
        digits_only = re.sub(r"\D", "", clean_input)

        if not digits_only:
            return PhoneValidationResult(
                is_valid=False,
                original_phone=clean_input,
                error_message="No numeric digits found in phone string",
            )

        # Parse country code vs national number
        if has_leading_plus:
            # Match known multi-digit country codes or single digit
            country_code = None
            for cc in ("91", "44", "61", "49", "33", "81", "86", "1"):
                if digits_only.startswith(cc):
                    country_code = cc
                    national_number = digits_only[len(cc) :]
                    break
            if not country_code:
                country_code = digits_only[:1]
                national_number = digits_only[1:]
        else:
            if len(digits_only) == 10:
                country_code = default_country_code
                national_number = digits_only
            elif len(digits_only) == 11 and digits_only.startswith("1"):
                country_code = "1"
                national_number = digits_only[1:]
            else:
                country_code = default_country_code
                national_number = digits_only

        total_digits = len(country_code) + len(national_number)
        if total_digits < 7 or total_digits > 15:
            return PhoneValidationResult(
                is_valid=False,
                original_phone=clean_input,
                error_message=f"Invalid digit length ({total_digits}). E.164 numbers must be between 7 and 15 digits.",
            )

        e164 = f"+{country_code}{national_number}"

        # Determine line classification
        line_type = "unknown"
        if country_code == "1" and len(national_number) >= 3:
            area_code = national_number[:3]
            if area_code in self.TOLL_FREE_PREFIXES:
                line_type = "toll_free"
            else:
                line_type = "fixed_or_mobile"
        else:
            line_type = "fixed_or_mobile"

        return PhoneValidationResult(
            is_valid=True,
            original_phone=clean_input,
            e164_format=e164,
            country_code=country_code,
            national_number=national_number,
            line_type=line_type,
        )
