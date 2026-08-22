# Lead Intelligence & Agency Qualification Platform

An enterprise-grade, multi-tenant B2B Lead Scraping, Verification, Service Opportunity Qualification, and Cold Outreach Platform built for digital marketing agencies (SMMA).

---

## Architecture Overview

```
                          ┌───────────────────────────┐
                          │   Next.js / React UI      │
                          │   (Frontend Dashboard)    │
                          └─────────────┬─────────────┘
                                        │ REST / WebSockets
                                        ▼
                          ┌───────────────────────────┐
                          │   FastAPI Web Server      │
                          │   (Async Python 3.12)     │
                          └─────────────┬─────────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             ▼                          ▼                          ▼
┌─────────────────────────┐┌─────────────────────────┐┌─────────────────────────┐
│ PostgreSQL (RLS Tenant) ││ Redis & Celery Workers  ││ Prometheus & Sentry PII │
│ Multi-Tenant Isolation  ││ Rate Limiting & Jobs    ││ Observability           │
└─────────────────────────┘└─────────────────────────┘└─────────────────────────┘
```

---

## Complete Feature Matrix

### Phase 1 — Platform Foundation

- [x] **PostgreSQL Row-Level Security (RLS)**: Database-enforced workspace tenant isolation (`app.current_workspace_id`).
- [x] **JWT Authentication & Tenant Claims**: Multi-tenant authorization middleware.
- [x] **Lead Management CRUD**: Workspace-scoped Lead REST API endpoints.
- [x] **Formula Injection Sanitization**: Safe CSV & XLSX export generation stripping dangerous formula prefixes (`=`, `+`, `-`, `@`).
- [x] **Google OAuth 2.0 & Sheets Sync**: Background task syncing leads directly to Google Sheets spreadsheets.
- [x] **PII Scrubbing & Monitoring**: Sentry SDK and Structlog middleware sanitizing email, phone, and name attributes.

### Phase 2 — Lead Discovery & Collection

- [x] **SSRF Protection Module**: Validates outbound URLs preventing private IP (`10.x`, `127.x`) and cloud metadata (`169.254.169.254`) security exploits.
- [x] **Multi-Source Connectors**: Integrated scraping connectors for:
  - **Google Maps** (location & ratings)
  - **Yelp** (reviews & business info)
  - **Google Search** (organic search presence)
  - **LinkedIn** (company profiles & size)
  - **Meta Ads** (active ad creatives & provenance data)
- [x] **Resilience Architecture**: Per-source Token Bucket Rate Limiting and Circuit Breaker pattern.
- [x] **Redis Concurrency Limiter**: Sliding window concurrency guard capping parallel scraping tasks per workspace.
- [x] **Real-Time WebSockets**: Live progress streaming (`WS /api/scrape-jobs/{id}/ws`) with **Stop & Save** and **Cancel** controls.

### Phase 3 — Enrichment, Verification & Entity Resolution

- [x] **Triple Verification Engine**:
  - `WebsiteValidator`: DNS resolution, HTTP status verification (GET 2xx), and SSL certificate validation.
  - `EmailVerifier`: RFC 5322 regex syntax, disposable domain filtering (`mailinator.com`, etc.), and DNS MX record lookup.
  - `PhoneValidator`: ITU-T E.164 standardization (`+1...`), multi-country code parsing, and toll-free line classification.
- [x] **Entity Resolution Engine**: Canonical domain/name normalization, corporate suffix removal, multi-factor match scoring, candidate discovery, pointer reassignment (`SourceRecord`, `EvidenceRecord`), and duplicate soft-deletion.
- [x] **Confidence Scoring Engine**: Field-level confidence scores (0–100) + multi-source verification bonus.
- [x] **Audit Logger Middleware**: Captures mutating HTTP requests (`POST`, `PATCH`, `DELETE`) and exports into `audit_logs` table.
- [x] **Suppression List Enforcement**: Workspace do-not-contact opt-out filtering for emails, domains, and phone numbers.

### Phase 4 — Service Intelligence & Qualification

- [x] **5 Service Opportunity Analyzers**:
  - `WebsiteOpportunityAnalyzer`: Web design opportunity scoring (missing website = 95, SSL absence, mobile viewport missing, analytics missing).
  - `SEOOpportunityAnalyzer`: Title tag length, meta descriptions, `<h1>` heading hierarchy, and Schema.org markup.
  - `SocialSignalAnalyzer`: Detects Facebook, Instagram, LinkedIn, X, and YouTube profile presence and flags gaps.
  - `AdsOpportunityAnalyzer`: Scans for Meta Pixel, Google Ads conversion tags, and active Meta Ad Library campaigns.
  - `SMMAOpportunityAnalyzer`: Unified SMMA agency sales opportunity score (0–100) and priority rank (`HIGH`, `MEDIUM`, `LOW`).
- [x] **Deterministic Rule Engine**: Scores lead opportunities and persists records into `service_scores` table with Postgres RLS.
- [x] **Machine Learning Scorer**: Feature extraction and baseline conversion probability model (`MLScorer`).
- [x] **LLM Explanation Generator**: Structured JSON agency pitch summaries, output validation against hallucination, and Redis per-workspace daily token budget limiter (50,000 max tokens).

### Phase 5 — Outreach & Pipeline Orchestration

- [x] **Cold Email Campaign Dispatcher**: Provider-abstracted email engine (SMTP / SendGrid / Resend / Mock) with template variable interpolation (`{{ business_name }}`) and opt-out suppression verification.
- [x] **Webhook HMAC Signature Guard**: Constant-time SHA-256 HMAC payload verification (`verify_hmac_signature`).
- [x] **Signed S3 Export Service**: Pre-authenticated S3 download link generation with 15-minute expiration windows.
- [x] **Prometheus Observability**: `/metrics` endpoint exporting counters (`scrape_jobs_total`, `leads_scraped_total`, `email_dispatches_total`, `ssrf_blocked_total`).
- [x] **CRM Integration Sync**: Lead payload sync service for HubSpot, Salesforce, and Custom Webhooks.

### Phase 6 — Frontend & User Experience

- [x] **Modern Dashboard UI**: Next.js / React glassmorphism dashboard UI (`frontend/app/page.tsx`).
- [x] **Interactive Components**: Real-time Lead Explorer Table, Scrape Job Progress Modal, Qualification & AI Pitch Widget, and Cold Email Campaign Manager.

---

## Directory Structure Audit

```
Leads/
├── alembic/                      # Database migrations
│   └── versions/                 # RLS migrations (20260810_0001 to 0005)
├── backend/                      # Python FastAPI Application
│   └── app/
│       ├── enrichment/           # Website, Email, Phone, Entity Resolution, Suppression
│       ├── intelligence/         # Website, SEO, Social, Ads, SMMA Analyzers, ML & LLM
│       ├── middleware/           # API Rate Limiter, Audit Logger Middleware
│       ├── outreach/             # Cold Email Dispatcher, CRM Sync Service
│       ├── security/             # SSRF Guard, HMAC Guard, JWT Security
│       ├── sources/              # Google Maps, Yelp, Google Search, LinkedIn, Meta
│       ├── api.py                # REST Endpoints & WebSockets
│       ├── config.py             # Settings & Environment Variables
│       ├── database.py           # SQLAlchemy Engine & Base
│       ├── exports.py            # CSV & XLSX Exporters
│       ├── exports_s3.py         # Signed S3 Export URLs
│       ├── google_sheets.py      # Google Sheets Sync Service
│       ├── main.py               # FastAPI Application & Prometheus /metrics
│       ├── metrics.py            # Prometheus Metrics Collector
│       ├── models.py             # SQLAlchemy ORM Models with RLS
│       ├── schemas.py            # Pydantic Schemas
│       ├── websockets.py         # WebSocket Connection Manager
│       ├── worker.py             # Celery Background Worker Tasks
│       └── worker_concurrency.py # Redis Concurrency Guard
├── frontend/                     # Next.js / React UI Dashboard
│   └── app/
│       ├── globals.css           # Styling & Theme Tokens
│       ├── layout.tsx            # Root Layout
│       └── page.tsx              # Interactive Dashboard App
├── tests/                        # 92 Passing Unit Tests
└── pyproject.toml                # Project Dependencies & Configurations
```

---

## System Execution & Verification

### Running Automated Tests

```bash
.venv/bin/python -m pytest
```

_Result: 92 passed in ~2.20s_

### Running Code Formatting & Linting

```bash
.venv/bin/ruff check --fix . && .venv/bin/ruff format .
```

_Result: Clean (0 errors)_

How to run->

````

**For Mac/Linux:**

```bash
# Terminal 1: Backend API
.venv/bin/uvicorn backend.app.main:app --port 8000
# Terminal 2: Celery Worker
.venv/bin/celery -A backend.app.worker.celery_app worker --loglevel=info
# Terminal 3: Frontend Dev Server
cd frontend && npm run dev
````

**For Windows:**

```powershell
# Terminal 1: Backend API
.\.venv\Scripts\uvicorn backend.app.main:app --port 8000
# Terminal 2: Celery Worker
.\.venv\Scripts\celery -A backend.app.worker.celery_app worker --loglevel=info --pool=solo
# Terminal 3: Frontend Dev Server
cd frontend; npm run dev
```
