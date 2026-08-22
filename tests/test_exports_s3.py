from __future__ import annotations

import uuid

from backend.app.exports_s3 import S3ExportService


def test_s3_export_service_url_generation() -> None:
    service = S3ExportService()
    ws_id = str(uuid.uuid4())
    url = service.generate_signed_export_url(ws_id, "leads_export.csv", expires_in=900)

    assert "s3.amazonaws.com" in url
    assert ws_id in url
    assert "leads_export.csv" in url
    assert "token=" in url
    assert "expires=" in url
