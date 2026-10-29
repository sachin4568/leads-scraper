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
    is_generic_provider: bool = Field(default=False, description="Consumer email provider status (e.g. gmail.com)")
    source_backed: bool = Field(default=True, description="Traceable source evidence available")
    deliverability_status: str = Field(
        default="DELIVERABILITY_UNKNOWN",
        description="DELIVERABILITY_VERIFIED, DELIVERABILITY_UNKNOWN, or INVALID"
    )
    domain: str | None = Field(default=None, description="Extracted email domain")
    domain_matched: bool | None = Field(default=None, description="Check if email domain matches business name or website")
    error_message: str | None = Field(
        default=None, description="Error detail if validation failed"
    )


class EmailVerifier:
    EMAIL_REGEX: ClassVar[re.Pattern[str]] = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}$"
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
    GENERIC_PROVIDER_DOMAINS: ClassVar[set[str]] = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "aol.com",
        "icloud.com",
        "mail.com",
        "zoho.com",
    }
    TELEMETRY_AND_DUMMY_DOMAINS: ClassVar[set[str]] = {
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "sample.com",
        "placeholder.com",
        "domain.com",
        "domainname.com",
        "localhost",
        "invalid.com",
        "email.com",
        "yourdomain.com",
        "yourcompany.com",
        "yourbusiness.com",
        "yoursite.com",
        "mysite.com",
        "mywebsite.com",
        "sitename.com",
        "websitename.com",
        "company.com",
        "mycompany.com",
        "temp.com",
        "demo.com",
        # CMS / Website builder platforms (not legitimate business email hosts)
        "wix.com",
        "wixpress.com",
        "wordpress.org",
        "wordpress.com",
        "squarespace.com",
        "shopify.com",
        "webflow.com",
        "webflow.io",
        "weebly.com",
        "godaddy.com",
        "jimdo.com",
        "schema.org",
        "w3.org",
        "sentry.io",
        "gravatar.com",
        "automattic.com",
        "hubspot.com",
        "mailchimp.com",
        "zendesk.com",
        "intercom.io",
        "email.com",
        "myftpupload.com",
        "tempmail.com",
        "trashmail.com",
        "10minutemail.com",
        "findhvac.us",
    }
    PLACEHOLDER_LOCAL_PARTS: ClassVar[set[str]] = {
        "email",
        "example",
        "name",
        "placeholder",
        "sample",
        "test",
        "you",
        "yourname",
        "youremail",
        "username",
        "someone",
        "user",
        "johndoe",
        "john.doe",
        "janedoe",
        "jane.doe",
        "firstlast",
        "first.last",
        "firstnamelastname",
        "firstname.lastname",
        "dummy",
        "fake",
        "changeme",
        "replaceme",
        "replace_me",
        "your",
        "filler",
        "myname",
        "noone",
        "nobody",
        "myemail",
    }

    @classmethod
    def is_placeholder_email(cls, email: str | None) -> bool:
        """Reject common documentation, template, and synthetic email addresses."""
        if not email or email.count("@") != 1:
            return False
        local_part, domain = email.strip().lower().split("@", 1)
        local_token = re.sub(r"[^a-z0-9]", "", local_part)

        # 0. Reject invalid domain structures (no dot, purely numeric, or invalid TLD)
        if "." not in domain:
            return True
        tld = domain.split(".")[-1]
        if not tld.isalpha() or len(tld) < 2 or len(tld) > 24:
            return True
        if re.match(r"^[\d\.]+$", domain):
            return True

        # 1. Phone number formatted as email local part (e.g. 1234567890@... or 213-34-21@...)
        if bool(re.match(r"^[\+0-9\-\.\s\(\)]+$", local_part)) and len(re.sub(r"\D", "", local_part)) >= 7:
            return True

        # 2. Asset extension in local part or domain (e.g. logo@2x.png or user@icon.svg)
        asset_exts = ("png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "css", "js", "pdf", "mp4", "woff")
        if any(local_part.endswith(f".{ext}") for ext in asset_exts) or any(domain.endswith(f".{ext}") for ext in asset_exts):
            return True

        # 3. Known dummy / telemetry / platform domains
        if domain in cls.TELEMETRY_AND_DUMMY_DOMAINS or any(
            domain.endswith(f".{placeholder}") for placeholder in cls.TELEMETRY_AND_DUMMY_DOMAINS
        ):
            return True

        # 4. Known dummy / placeholder local parts
        if local_token in cls.PLACEHOLDER_LOCAL_PARTS or local_part in cls.PLACEHOLDER_LOCAL_PARTS:
            return True

        # 5. Reject generic placeholders on free/generic domains (e.g. name@mail.com, user@gmail.com, admin@yahoo.com)
        if domain in cls.GENERIC_PROVIDER_DOMAINS and (
            local_token in ('name', 'user', 'someone', 'test', 'example', 'sample', 'dummy', 'fake', 'placeholder', 'filler', 'changeme', 'replaceme', 'noone', 'nobody')
            or bool(re.match(r'^(test|user|name|dummy|demo|example)\d*$', local_token))
        ):
            return True

        return False

    def verify(
        self,
        email: str,
        business_name: str | None = None,
        website: str | None = None,
        require_business_domain: bool = False,
        source_backed: bool = True,
    ) -> EmailVerificationResult:
        if not email or not email.strip():
            return EmailVerificationResult(
                is_valid=False,
                email=email or "",
                deliverability_status="INVALID",
                error_message="Empty email address provided",
            )

        clean_email = email.strip().lower()

        # Step 0: Source Evidence Check
        if not source_backed:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                source_backed=False,
                deliverability_status="INVALID",
                error_message="Fabricated or unsupported email lacking source evidence",
            )

        # Step 1: Syntax Validation
        if clean_email.count("@") != 1:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=False,
                deliverability_status="INVALID",
                error_message="Invalid email syntax: exactly one @ required",
            )

        local_part, domain = clean_email.split("@", 1)
        if not local_part or not domain:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=False,
                deliverability_status="INVALID",
                error_message="Invalid email syntax: empty local part or domain",
            )

        if ".." in clean_email or domain.startswith(".") or domain.endswith(".") or "." not in domain:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=False,
                deliverability_status="INVALID",
                error_message="Invalid domain syntax in email",
            )

        if not self.EMAIL_REGEX.match(clean_email):
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=False,
                deliverability_status="INVALID",
                error_message="Invalid email syntax",
            )

        # Step 1b: Telemetry, template, and static-asset filtering
        if self.is_placeholder_email(clean_email):
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=True,
                domain=domain,
                deliverability_status="INVALID",
                error_message="Placeholder or template email address is prohibited",
            )

        is_telemetry = (
            "sentry" in domain
            or "wixpress.com" in domain
            or "cloudflare.com" in domain
            or "schema.org" in domain
            or "w3.org" in domain
        )
        if is_telemetry:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=True,
                domain=domain,
                deliverability_status="INVALID",
                error_message=f"Placeholder or telemetry email domain '{domain}' is prohibited",
            )

        # Step 2: Disposable Provider Check
        if domain in self.DISPOSABLE_DOMAINS:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=True,
                is_disposable=True,
                domain=domain,
                deliverability_status="INVALID",
                error_message=f"Disposable email domain '{domain}' is prohibited",
            )

        is_generic_provider = domain in self.GENERIC_PROVIDER_DOMAINS

        # Step 3: DNS MX / Host Record Check
        try:
            socket.getaddrinfo(domain, None)
            has_mx_records = True
        except (socket.gaierror, OSError, UnicodeError, ValueError) as dns_err:
            return EmailVerificationResult(
                is_valid=False,
                email=clean_email,
                syntax_valid=True,
                has_mx_records=False,
                domain=domain,
                deliverability_status="INVALID",
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
                if email_domain == web_domain or email_domain.endswith(f".{web_domain}"):
                    domain_matched = True
            if not domain_matched and business_name:
                from backend.app.ingestion.identity import normalize_business_name
                norm_biz = normalize_business_name(business_name).lower()
                dom_part = email_domain.split(".")[0]
                if dom_part and (dom_part in norm_biz or norm_biz in dom_part):
                    domain_matched = True

        if require_business_domain:
            if is_generic_provider:
                return EmailVerificationResult(
                    is_valid=False,
                    email=clean_email,
                    syntax_valid=True,
                    has_mx_records=has_mx_records,
                    domain=domain,
                    is_generic_provider=True,
                    domain_matched=False,
                    deliverability_status="INVALID",
                    error_message="Consumer email provider does not match required custom business domain",
                )
            if domain_matched is not True:
                return EmailVerificationResult(
                    is_valid=False,
                    email=clean_email,
                    syntax_valid=True,
                    has_mx_records=has_mx_records,
                    domain=domain,
                    domain_matched=False,
                    deliverability_status="INVALID",
                    error_message="Email domain does not match the business website or name",
                )

        return EmailVerificationResult(
            is_valid=True,
            email=clean_email,
            syntax_valid=True,
            has_mx_records=has_mx_records,
            is_disposable=False,
            is_generic_provider=is_generic_provider,
            source_backed=source_backed,
            deliverability_status="DELIVERABILITY_UNKNOWN",
            domain=domain,
            domain_matched=domain_matched,
        )

# Phase 3 Abstraction
class EmailVerifierProvider:
    def verify(self, email: str) -> str:
        raise NotImplementedError

class DummyEmailVerifier(EmailVerifierProvider):
    def __init__(self):
        self.internal_verifier = EmailVerifier()
        
    def verify(self, email: str) -> str:
        try:
            res = self.internal_verifier.verify(email)
            if not res.syntax_valid:
                return "INVALID"
            if res.is_disposable:
                return "INVALID"
            if not res.has_mx_records:
                return "UNKNOWN" # DNS failures could be network/timeout issues locally
                
            # We only checked Syntax and DNS, we did not verify the mailbox via SMTP or API.
            # So the strongest claim we can make is LIKELY_VALID.
            return "LIKELY_VALID" if res.is_valid else "UNKNOWN"
        except Exception as e:
            logger.warning(f"Verification exception for {email}: {e}")
            return "UNKNOWN"

def get_email_verifier() -> EmailVerifierProvider:
    return DummyEmailVerifier()

def verify_email(email: str) -> str:
    try:
        return get_email_verifier().verify(email)
    except Exception as e:
        logger.warning(f"Email verification failed: {e}")
        return "UNKNOWN"
