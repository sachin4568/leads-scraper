# Bugfix Requirements Document

## Introduction

The lead enrichment pipeline has four interconnected gaps that cause the sales team to receive low-quality contact data. Email classifications computed during scraping are never persisted to the database, so the team cannot distinguish between an owner email and a generic `info@` address. Social follower counts are scraped but thrown away, preventing leads from being filtered by audience size. Owner emails hidden behind Instagram bio links and LinkedIn company pages are never followed. Together these gaps mean the pipeline silently discards its most valuable signals every time a lead is processed.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `website_enricher.py` extracts emails from a business website THEN the system does not classify each email as owner / personal_business / role / generic / unknown before storing it

1.2 WHEN an email is classified inside `email_pipeline.classify_email()` THEN the system never calls that function from within `website_enricher._extract_contacts_from_html`, so the classification is computed in isolation and never merged back

1.3 WHEN the orchestrator saves a `RawLead` record after enrichment THEN the system stores no `email_type` or `email_confidence` values because those columns do not exist on the model

1.4 WHEN the orchestrator saves a `SegregatedLead` record after segregation THEN the system stores no `email_type` or `email_confidence` values because those columns do not exist on the model

1.5 WHEN `SocialScraper.fetch_profile()` returns a follower count for an Instagram or Facebook profile THEN the system discards that count instead of persisting it to the `RawLead` or `SegregatedLead` record

1.6 WHEN `RawLead` and `SegregatedLead` are queried THEN the system cannot filter or sort by Instagram or Facebook follower count because those columns do not exist in the schema

1.7 WHEN a business has an Instagram profile with a bio link (e.g. a Linktree landing page) THEN the system never follows that link to find an owner email hidden on the landing page

1.8 WHEN a business has a LinkedIn company page THEN the system never fetches that page to look for an owner email in the about section

1.9 WHEN `scrape_facebook_about()` is available on `ProductionWebsiteEnricher` THEN the system only calls it as a last-resort fallback in the orchestrator rather than integrating it into the enrichment pipeline alongside the new social sources

### Expected Behavior (Correct)

2.1 WHEN `_extract_contacts_from_html` processes emails THEN the system SHALL classify each email using the rules below and attach `email_type` and `email_confidence` to every email dict before returning it:
- gmail / yahoo / outlook / hotmail domain → `"generic"`, confidence 30
- local part matches a role prefix (info, sales, contact, admin, support, etc.) → `"role"`, confidence 10
- `first.last@<company-domain>` pattern → `"personal_business"`, confidence 80
- `first.last@` local part AND page context is `/team`, `/about`, or `/owner` → `"owner"`, confidence 95
- any other email on the company domain → `"personal_business"`, confidence 60
- domain does not match company domain → `"unknown"`, confidence 20

2.2 WHEN multiple emails are found on a page THEN the system SHALL sort them owner → personal_business → generic → role → unknown before returning the list

2.3 WHEN the orchestrator persists a `RawLead` after enrichment THEN the system SHALL write `email_type` and `email_confidence` from the top-ranked email into the new `RawLead.email_type` and `RawLead.email_confidence` columns

2.4 WHEN the segregation step creates or updates a `SegregatedLead` THEN the system SHALL copy `email_type` and `email_confidence` from the source `RawLead` into the new `SegregatedLead.email_type` and `SegregatedLead.email_confidence` columns

2.5 WHEN `SocialScraper.fetch_profile()` returns `status == "FOUND"` with a follower count THEN the system SHALL persist that count to `RawLead.instagram_followers` or `RawLead.facebook_followers` (matching the platform) in the same immediate-persist update that already stores other enrichment fields

2.6 WHEN follower counts are stored on `RawLead` THEN the system SHALL copy `instagram_followers` and `facebook_followers` through the verified_results dict so the segregation step can write them to `SegregatedLead.instagram_followers` and `SegregatedLead.facebook_followers`

2.7 WHEN an Instagram profile URL is discovered during enrichment THEN the system SHALL fetch the profile page, locate the bio link, follow it, and run `_extract_contacts_from_html` on the landing page to find owner emails not present on the business website

2.8 WHEN a LinkedIn company handle or name is known THEN the system SHALL make a best-effort fetch of `https://www.linkedin.com/company/{handle}/about` and scan the about section for email addresses

2.9 WHEN either the Instagram bio-link crawl or the LinkedIn fetch produces an email with `email_type == "owner"` or `"personal_business"` THEN the system SHALL promote that email to the stored `RawLead.email`, replacing a lower-quality email that was stored previously

2.10 WHEN the `RawLead` model is migrated THEN the system SHALL add columns: `email_type VARCHAR(32)`, `email_confidence INTEGER`, `instagram_url VARCHAR(2048)`, `facebook_url VARCHAR(2048)`, `instagram_followers INTEGER`, `facebook_followers INTEGER`

2.11 WHEN the `SegregatedLead` model is migrated THEN the system SHALL add columns: `email_type VARCHAR(32)`, `email_confidence INTEGER`, `instagram_followers INTEGER`, `facebook_followers INTEGER`

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a lead has no social profiles THEN the system SHALL CONTINUE TO complete enrichment without errors, leaving the new follower-count columns as NULL

3.2 WHEN `SocialScraper.fetch_profile()` returns `status == "UNAVAILABLE"` or `"NOT_FOUND"` THEN the system SHALL CONTINUE TO store NULL for the corresponding follower-count column rather than raising an exception

3.3 WHEN the website enricher crawls a business website and finds a valid email THEN the system SHALL CONTINUE TO store that email even if classification returns `"unknown"` or `"generic"`, so no leads are silently dropped

3.4 WHEN the Instagram bio-link fetch or LinkedIn fetch times out or returns a non-200 response THEN the system SHALL CONTINUE TO proceed with whatever emails were already extracted from the business website, without retrying or failing the overall enrichment job

3.5 WHEN a lead already has an email classified as `"owner"` from the website crawl THEN the system SHALL CONTINUE TO skip the Instagram bio-link and LinkedIn fallback steps to avoid unnecessary network requests

3.6 WHEN the orchestrator's existing immediate-persist logic runs for non-social fields (website, phone, notes) THEN the system SHALL CONTINUE TO write those fields unchanged, with the new social columns appended to the same update statement

3.7 WHEN `classify_email()` in `email_pipeline.py` is called from other parts of the system THEN the system SHALL CONTINUE TO return the same `(classification, domain_match)` tuple it returns today, with no signature changes

3.8 WHEN a `SegregatedLead` is exported or displayed in the API THEN the system SHALL CONTINUE TO include all previously existing fields (`instagram_handle`, `facebook_handle`, `social_score`, etc.) alongside the newly added columns

3.9 WHEN the Alembic migration runs THEN the system SHALL CONTINUE TO leave existing rows with NULL in the new columns, with no backfill required

3.10 WHEN `scrape_facebook_about()` is called directly THEN the system SHALL CONTINUE TO return the same list-of-email-dicts format it currently returns, with no signature changes
