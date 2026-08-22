from __future__ import annotations

from google_auth_oauthlib.flow import Flow

from backend.app.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def create_google_oauth_flow(redirect_uri: str) -> Flow:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("Google OAuth is not configured")
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict[str, str | None]:
    flow = create_google_oauth_flow(redirect_uri)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": ",".join(credentials.scopes or []),
    }


class GoogleSheetsSyncService:
    def __init__(self, token_info: dict[str, str | None]) -> None:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=token_info.get("token"),
            refresh_token=token_info.get("refresh_token"),
            token_uri=token_info.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_info.get("client_id"),
            client_secret=token_info.get("client_secret"),
            scopes=SCOPES,
        )
        self.service = build("sheets", "v4", credentials=creds)

    def sync_leads(
        self, spreadsheet_id: str, sheet_name: str, rows: list[list[str]]
    ) -> dict[str, object]:
        header = ["Business name", "Website", "Email", "Phone", "Notes"]
        values = [header] + rows
        body = {"values": values}
        range_name = f"{sheet_name}!A1"
        result = (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
        return result

    def sync_master_sheets(
        self, spreadsheet_id: str, tab_data_map: dict[str, list[list[str]]]
    ) -> dict[str, object]:
        """Syncs lead data across 10 dedicated Google Sheet tabs idempotently."""
        results: dict[str, object] = {}
        for tab_name, rows in tab_data_map.items():
            header = [
                "Lead ID",
                "Business Name",
                "Website",
                "Email",
                "Phone",
                "Status",
                "Discovered At",
            ]
            values = [header] + rows
            body = {"values": values}
            range_name = f"{tab_name}!A1"
            try:
                res = (
                    self.service.spreadsheets()
                    .values()
                    .update(
                        spreadsheetId=spreadsheet_id,
                        range=range_name,
                        valueInputOption="USER_ENTERED",
                        body=body,
                    )
                    .execute()
                )
                results[tab_name] = res
            except Exception as err:
                results[tab_name] = {"error": str(err)}
        return results
