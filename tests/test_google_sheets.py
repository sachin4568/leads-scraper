from __future__ import annotations

import pytest

from backend.app.google_sheets import create_google_oauth_flow


def test_google_oauth_flow_raises_when_unconfigured(monkeypatch) -> None:
    from backend.app.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="Google OAuth is not configured"):
        create_google_oauth_flow("http://localhost/callback")
