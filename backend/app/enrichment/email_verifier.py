from __future__ import annotations

import logging
import re
import socket
from typing import ClassVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EmailVerificationResult(BaseModel):
    is_valid: bool = Field(..., description="Overall email validity status")
    email: str = Field(..., description="The verified email address")
    syntax_valid: bool = Field(default=False, description="RFC 5322 syntax validity")
    has_mx_records: bool = Field(default=False, description="Presence of DNS MX or A records")
    is_disposable: bool = Field(default=False, description="Disposable email provider status")
    domain: str | None = Field(default=None, description="Extracted email domain")
    domain_matched: bool | None = Field(default=None, description="Check if email domain matches business name or website")
    error_message: str | None = Field(
        default=None, description="Error detail if validation failed"
    )


class EmailVerifier:
    EMAIL_REGEX: ClassVar[re.Pattern[str]] = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    DISPOSABLE_DOMAINS: ClassVar[set[str]] = {
        "mailinator.com",
        "tempmail.com",
        "10minutemail.com",
        "guerrillamail.com",
        "trashmail.com",
        "dispostable.com",
        "getairmail.com",
        "yopmail.com",
        "sharklasers.com",
    }

    def verify(
        self, email: str, business_name: str | None = None, website: str | None = None
    ) -> EmailVerificationResult:
        if not email or not email.strip():
            return EmailVerificationResult(
                is_valid=False, email=email or "", error_message="Empty email address provided"
            )

        clean_email = email.strip().lower()

        # Step 1: Syntax Validation
        if not self.EMAIL_REGEX.match(clean_email):
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=False,
                error_message="Invalid email syntax",
            )

        domain = clean_email.split("@")[-1]

        # Step 2: Disposable Provider Check
        if domain in self.DISPOSABLE_DOMAINS:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=True,
                is_disposable=True,
                domain=domain,
                error_message=f"Disposable email domain '{domain}' is prohibited",
            )

        # Step 3: DNS MX / Host Record Check
        try:
            socket.getaddrinfo(domain, None)
            has_mx_records = True
        except (socket.gaierror, OSError) as dns_err:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=True,
                has_mx_records=False,
                domain=domain,
                error_message=f"Domain DNS lookup failed: {dns_err}",
            )

        # Step 4: Business-Domain association check
        domain_matched = None
        if business_name or website:
            domain_matched = False
            email_domain = domain.lower()
            if website:
                from backend.app.ingestion.identity import normalize_domain
                web_domain = normalize_domain(website).lower()
                if email_domain == web_domain:
                    domain_matched = True
            if not domain_matched and business_name:
                from backend.app.ingestion.identity import normalize_business_name
                norm_biz = normalize_business_name(business_name).lower()
                dom_part = email_domain.split(".")[0]
                if dom_part in norm_biz or norm_biz in dom_part:
                    domain_matched = True

        return EmailVerificationResult(
            is_valid=True,
            email=clean_email,
            syntax_valid=True,
            has_mx_records=has_mx_records,
            is_disposable=False,
            domain=domain,
            domain_matched=domain_matched,
        )
