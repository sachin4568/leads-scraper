from __future__ import annotations

from functools import lru_cache
from typing import Literal

import boto3
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: Literal["local", "test", "production"] = "production"

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: Any) -> str:
        if value is None:
            return "production"
        if isinstance(value, str):
            val_str = value.strip()
            if not val_str:
                return "production"
            if val_str not in {"local", "test", "production"}:
                raise ValueError("APP_ENV must be one of: local, test, production")
            return val_str
        return value
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/lead_db"
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    jwt_secret: SecretStr = SecretStr("dev-local-jwt-secret-change-in-prod")

    # =========================================================================
    # MULTI-PROVIDER LEAD SOURCES (API KEYS)
    # =========================================================================
    google_maps_api_key: str | None = None
    google_places_api_key: str | None = None
    foursquare_api_key: str | None = None
    data_axle_api_key: str | None = None
    data_axle_base_url: str = "https://api.data-axle.com/v1/places"
    yelp_api_key: str | None = None
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"

    # =========================================================================
    # AUTHENTICATION & SECURITY
    # =========================================================================
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None

    # =========================================================================
    # MONITORING & CLOUD INFRASTRUCTURE
    # =========================================================================
    sentry_dsn: SecretStr | None = None
    aws_region: str = "ap-south-1"
    secrets_manager_secret_id: str | None = None

    def production_secret(self, name: str) -> SecretStr:
        if self.app_env != "production":
            value = getattr(self, name)
            if not isinstance(value, SecretStr):
                raise RuntimeError(f"{name} is not a secret setting")
            return value
        if not self.secrets_manager_secret_id:
            raise RuntimeError("SECRETS_MANAGER_SECRET_ID is required in production")
        response = boto3.client("secretsmanager", region_name=self.aws_region).get_secret_value(
            SecretId=self.secrets_manager_secret_id
        )
        import json

        value = json.loads(response["SecretString"]).get(name.upper())
        if not value:
            raise RuntimeError(f"Missing {name.upper()} in Secrets Manager")
        return SecretStr(value)

    @property
    def resolved_jwt_secret(self) -> str:
        return self.production_secret("jwt_secret").get_secret_value()

    @property
    def resolved_google_places_key(self) -> str | None:
        return self.google_places_api_key or self.google_maps_api_key


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    import sys
    print(f"APP_ENV configured: {bool(settings.app_env)}", file=sys.stderr)
    print(f"APP_ENV value category: {settings.app_env}", file=sys.stderr)
    print(f"DATABASE_URL configured: {bool(settings.database_url)}", file=sys.stderr)
    return settings
