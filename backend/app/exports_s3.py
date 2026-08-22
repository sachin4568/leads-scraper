from __future__ import annotations

import logging
import time
from urllib.parse import urlencode

from backend.app.config import get_settings
from backend.app.security import create_access_token

logger = logging.getLogger(__name__)


class S3ExportService:
    """Service for generating signed pre-authenticated download URLs for export files."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_signed_export_url(
        self, workspace_id: str, filename: str, expires_in: int = 900
    ) -> str:
        """Generates a signed download URL valid for `expires_in` seconds (default 15 minutes)."""
        exp_timestamp = int(time.time()) + expires_in
        sig_token = create_access_token(
            user_id=filename,
            workspace_id=workspace_id,
        )

        query_params = urlencode({"token": sig_token, "expires": exp_timestamp})
        signed_url = f"https://s3.amazonaws.com/lead-platform-exports/{workspace_id}/{filename}?{query_params}"
        logger.info(f"Generated signed S3 URL for {filename} (expires in {expires_in}s)")
        return signed_url
