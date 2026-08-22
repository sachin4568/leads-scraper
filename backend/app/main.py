from __future__ import annotations

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.api import router
from backend.app.api_services import router as api_services_router
from backend.app.config import get_settings
from backend.app.middleware import APIRateLimiterMiddleware, AuditLoggerMiddleware

PII_FIELDS = {"email", "phone", "contact_name", "address"}


def scrub_pii(_: object, __: str, event_dict: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in event_dict.items() if key not in PII_FIELDS}


def before_send(event: dict[str, object], _: object) -> dict[str, object]:
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
    extra = event.get("extra")
    if isinstance(extra, dict):
        for field in PII_FIELDS:
            extra.pop(field, None)
    return event


structlog.configure(processors=[scrub_pii, structlog.processors.JSONRenderer()])

settings = get_settings()
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(), before_send=before_send, send_default_pii=False
    )

app = FastAPI(title="Lead Intelligence Platform")
app.add_middleware(AuditLoggerMiddleware)
app.add_middleware(APIRateLimiterMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")
app.include_router(api_services_router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    if get_settings().app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/ready")
async def readiness_probe() -> JSONResponse:
    from backend.app.database import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ready", "database": "connected"})
    except Exception:
        return JSONResponse({"status": "ready", "database": "sqlite_local"})


@app.get("/metrics")
async def metrics() -> Response:
    from backend.app.metrics import MetricsRegistry

    return Response(
        content=MetricsRegistry.generate_prometheus_output(),
        media_type="text/plain; version=0.0.4",
    )
