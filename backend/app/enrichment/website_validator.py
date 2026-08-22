from __future__ import annotations

import logging
import re
import socket
import ssl
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

from backend.app.security.ssrf_guard import validate_outbound_url

logger = logging.getLogger(__name__)


class WebsiteValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Overall website validity status")
    final_url: str | None = Field(default=None, description="Final URL after redirects")
    http_status: int | None = Field(default=None, description="HTTP response status code")
    dns_resolved: bool = Field(default=False, description="DNS host resolution status")
    ssl_valid: bool | None = Field(default=None, description="SSL certificate validation status")
    domain_token_match: bool | None = Field(default=None, description="Check if business name tokens exist in domain")
    error_message: str | None = Field(default=None, description="Error detail if validation failed")


class WebsiteValidator:
    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    def validate(self, url: str, business_name: str | None = None) -> WebsiteValidationResult:
        if not url or not url.strip():
            return WebsiteValidationResult(is_valid=False, error_message="Empty URL provided")

        target_url = url.strip()
        if not target_url.startswith(("http://", "https://")):
            target_url = f"https://{target_url}"

        # Step 1: SSRF Protection Guard Check
        try:
            validate_outbound_url(target_url, allow_http=True)
        except ValueError as ssrf_err:
            return WebsiteValidationResult(
                is_valid=False,
                dns_resolved=False,
                error_message=f"SSRF security violation: {ssrf_err}",
            )

        parsed = urlparse(target_url)
        hostname = parsed.hostname
        if not hostname:
            return WebsiteValidationResult(is_valid=False, error_message="Invalid hostname in URL")

        # Step 2: SSL Certificate Validation (for HTTPS)
        ssl_valid: bool | None = None
        if parsed.scheme == "https":
            try:
                context = ssl.create_default_context()
                with socket.create_connection(
                    (hostname, 443), timeout=self.timeout_seconds
                ) as sock:
                    with context.wrap_socket(sock, server_hostname=hostname):
                        ssl_valid = True
            except Exception as ssl_err:
                logger.debug(f"SSL certificate validation failed for {hostname}: {ssl_err}")
                ssl_valid = False

        # Step 3: HTTP Status Check with crawl budget redirect guard (max 3 redirects)
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                max_redirects=3,
                verify=False
            ) as client:
                response = client.get(target_url)
                http_status = response.status_code
                final_url = str(response.url)

                # Consider HTTP status 2xx and 3xx valid
                is_valid = 200 <= http_status < 400
                error_msg = None if is_valid else f"HTTP status error: {http_status}"

                domain_token_match = None
                if business_name and is_valid:
                    res_hostname = urlparse(final_url).hostname or hostname
                    domain_part = res_hostname.lower()
                    if domain_part.startswith("www."):
                        domain_part = domain_part[4:]
                    if "." in domain_part:
                        domain_part = domain_part.split(".")[0]
                    
                    name_clean = re.sub(r"[^\w\s]", "", business_name.lower())
                    tokens = [t for t in name_clean.split() if t not in ("ltd", "inc", "co", "llc", "corp", "company", "and", "the", "solutions", "services")]
                    if tokens:
                        domain_token_match = any(t in domain_part for t in tokens) or (domain_part in name_clean)
                    else:
                        domain_token_match = False

                return WebsiteValidationResult(
                    is_valid=is_valid,
                    final_url=final_url,
                    http_status=http_status,
                    dns_resolved=True,
                    ssl_valid=ssl_valid,
                    domain_token_match=domain_token_match,
                    error_message=error_msg,
                )
        except Exception as http_err:
            return WebsiteValidationResult(
                is_valid=False,
                dns_resolved=True,
                ssl_valid=ssl_valid,
                domain_token_match=None,
                error_message=f"HTTP request failed: {http_err}",
            )
