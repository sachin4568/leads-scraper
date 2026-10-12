# Email Enrichment Deep Scrape Fix — Bugfix Design

## Overview

The EMAIL column in the leads table shows phone numbers or is empty for the majority of
scraped leads. The root cause is a three-part defect:

1. **Enrichment gate** — `stage_2_enrich_and_verify` in `discovery_orchestrator.py`
   checks `enrichment_enabled = bool(job_state.get("enrichments"))` and returns early
   for every lead when that flag is falsy, bypassing all website crawling and email
   extraction entirely.

2. **Shallow crawl** — `ProductionWebsiteEnricher` in `website_enricher.py` is
   initialised with `max_pages=5` and `_discover_internal_links` only returns
   keyword-matched URLs; when no priority pages exist the crawler visits only the
   homepage and stops.

3. **No Facebook About scraping** — Leads with a Facebook Business page URL receive no
   attempt to extract the owner/manager email from the About tab.

4. **No retroactive path** — There is no API endpoint to re-run email discovery on leads
   that were scraped before the fix.

The fix decouples email crawl from `enrichment_enabled`, raises `max_pages` to 10, adds a
generic-internal-link fallback in `_discover_internal_links`, adds a
`_scrape_facebook_about` method to `ProductionWebsiteEnricher`, and exposes a new
`POST /scrape-jobs/{job_id}/re-enrich-emails` endpoint.

---

## Glossary

- **Bug_Condition (C)**: The set of inputs that trigger the defective email-column behaviour — a scrape job that has a lead with a website URL where the email crawl is either skipped (enrichment_enabled = False) or terminates early (no priority-keyword pages, max_pages ≤ 5, no Facebook fallback).
- **Property (P)**: The correct post-fix behaviour — when isBugCondition(X) is true, the system SHALL attempt email crawl, store the best discovered email, and never write a phone number into the email column.
- **Preservation**: Existing correct behaviours — cached enrichment results, phone validation logic, conflict recording, and email addresses already found — that must not change after the fix.
- **enrichment_enabled**: `bool(job_state.get("enrichments"))` — flag that controls optional ML/verification features. After the fix it no longer gates unconditional email crawl.
- **email_crawl_enabled**: New derived flag — `True` whenever a lead has a non-empty `website` field, regardless of `enrichment_enabled`.
- **stage_2_enrich_and_verify**: Method in `DiscoveryOrchestrator` (line 821) that runs website discovery, contact crawling, and verification for each viable candidate.
- **ProductionWebsiteEnricher**: Class in `website_enricher.py` responsible for bounded multi-page HTML crawl and contact extraction.
- **_discover_internal_links**: Method inside `ProductionWebsiteEnricher` that returns only keyword-matched URLs (the buggy restriction that needs the fallback).
- **enrich_email_pipeline**: Standalone function in `email_pipeline.py` — the engine used by the new re-enrichment endpoint.

---

## Bug Details

### Bug Condition

The bug manifests in two entry paths:

**Path A — enrichment gate fires:** `job_state.get("enrichments")` is falsy (empty list,
`None`, or not present) so `enrichment_enabled = False`. The early-return block on line
832–849 of `discovery_orchestrator.py` constructs baseline results using raw provider
data (`rec.email`) directly, never calling `enrich_website`. Because Google Maps returns
the phone number in the email column for some sources, the raw `rec.email` is a phone
number, and that phone number propagates to the leads table.

**Path B — shallow crawl fires:** Even when `enrichment_enabled = True`, if the business
website contains no pages whose path matches the priority keywords (`team`, `about`,
`contact`, etc.), `_discover_internal_links` returns an empty list. The enricher then
fetches only the homepage; if the owner email is on a page like `/our-story` or
`/pricing`, it is never visited.

**Formal Specification:**

```
FUNCTION isBugCondition(X)
  INPUT: X of type ScrapeJobInput
  OUTPUT: boolean

  RETURN (NOT bool(X.job_state.get("enrichments")))          // Path A – gate fires
      OR (X.website_has_no_priority_keyword_pages
          AND X.max_pages <= 5)                              // Path B – shallow crawl
      OR (X.lead_has_facebook_url
          AND NOT facebook_about_scraping_implemented())     // Path C – no FB fallback
      OR (X.lead.email IS NULL OR is_phone_number(X.lead.email)
          AND NOT reenrichment_endpoint_exists())            // Path D – no retro fix
END FUNCTION
```

### Examples

- **Bug manifests (Path A):** User submits job with no enrichment services selected.
  Lead for "Joe's Plumbing" has `website = "https://joesplumbing.com"` and
  `email = "(905) 334-0732"` from Google Maps. The early-return fires; email column
  stores "(905) 334-0732".

- **Bug manifests (Path B):** User submits job with enrichment enabled. "Sunrise Dental"
  has `website = "https://sunrisedental.ca"`. Homepage contains no `/about`, `/contact`,
  or `/team` links — only `/our-story`, `/treatments`, and `/blog`. Crawler fetches only
  homepage; owner email on `/our-story` is never discovered.

- **Bug manifests (Path C):** Lead has `facebook_url = "https://facebook.com/sunrisedental"`.
  Facebook About page lists `owner@sunrisedental.ca`. No scraping logic exists; email
  remains empty.

- **Preserved (no bug):** Lead for "ABC Corp" was scraped with enrichment enabled, has
  `email = "info@abccorp.com"` already discovered from `/contact` page. After the fix,
  re-running enrichment for this lead should not overwrite the existing valid email.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- Leads where the email was already correctly populated via website crawl SHALL NOT have
  their email overwritten (req 3.1, 3.2).
- When `provider_email` conflicts with a website-crawled email, the conflict SHALL
  continue to be recorded in the conflicts dictionary without silent overwrite (req 3.3).
- When priority keyword pages exist, they SHALL continue to be crawled before any generic
  internal links (req 3.4).
- When a lead has no website URL, website enrichment SHALL continue to be skipped (req 3.5).
- The global domain cache SHALL continue to be respected; a cached result SHALL be
  returned without re-fetching (req 3.6).
- Phone validation and rejection logic SHALL run independently of email crawl (req 3.7).

**Scope:**

All inputs that do NOT satisfy `isBugCondition(X)` — i.e., leads that already have a
correct email, leads with no website, and all non-website-crawl code paths — must produce
byte-for-byte identical results before and after the fix.

---

## Hypothesized Root Cause

1. **Incorrect enrichment flag semantics (primary):** `enrichment_enabled` was designed to
   control optional ML classification and scoring features. It was also used — incorrectly —
   to gate the fundamental email crawl step. No comment or documentation distinguishes
   "optional scoring" from "unconditional contact extraction", so the gate was applied too
   broadly.
   - Specific location: `discovery_orchestrator.py` lines 832–849 (early return) and
     lines 890, 908 (`if enrichment_enabled and ...` guards on steps 2a and 2b).

2. **No fallback in `_discover_internal_links` (secondary):** The method collects only
   links whose path contains a keyword. If `candidate_links` is empty, the function
   returns an empty list — no generic same-domain links are included as a fallback.
   - Specific location: `website_enricher.py` lines 184–226, return on line 225.

3. **Missing Facebook About scraper (tertiary):** No method exists to fetch
   `https://www.facebook.com/{page}/about` and parse the email field from the About tab.
   The `_extract_social_profiles` method records the Facebook URL but does not follow it.

4. **No batch re-enrichment endpoint:** The `enrich_email_pipeline` function exists in
   `email_pipeline.py` but is not exposed via any HTTP route. Leads scraped before the
   fix have no automated path to get their emails re-populated.

---

## Correctness Properties

Property 1: Bug Condition — Email Crawl Runs Unconditionally for Website Leads

_For any_ scrape job input where `isBugCondition(X)` is true (enrichment_enabled is
falsy OR no priority keyword pages exist OR lead has Facebook URL with no About scraper OR
lead has no email and no re-enrichment path), the fixed system SHALL attempt email
discovery via `enrich_website` whenever `rec.website` is non-empty, and SHALL NOT store a
phone number in the email column.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation — Non-Buggy Lead Behaviour Is Unchanged

_For any_ lead where `isBugCondition(X)` is false (enrichment_enabled is true AND
priority keyword pages were found AND email was already correctly extracted), the fixed
`stage_2_enrich_and_verify` SHALL produce the same `effective_email`, `effective_phone`,
`effective_website`, and `discovered_socials` as the original function, preserving all
existing contact resolution logic.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

---

## Fix Implementation

### Changes Required

#### File 1: `backend/app/orchestration/discovery_orchestrator.py`

**Function:** `stage_2_enrich_and_verify` (line 821)

**Change 1 — Remove the early-return block that bypasses all enrichment:**

```python
# REMOVE (lines 832–849):
if not enrichment_enabled:
    baseline_result = OverallVerificationResult(...)
    return [{"rec": rec, "effective_website": rec.website, ...} for rec in viable_candidates]
```

Replace with no early return. The loop body already handles the per-lead logic.

**Change 2 — Introduce `email_crawl_enabled` independent flag:**

```python
enrichment_enabled = bool(self.job_state.get("enrichments"))
# Email crawling is unconditional — runs whenever a website URL is available
email_crawl_enabled = True
```

**Change 3 — Decouple Step 2a and 2b guards:**

```python
# Step 2a: Zero-Budget Website Discovery — only if full enrichment is enabled
if enrichment_enabled and not has_website:
    ...  # unchanged

# Step 2b: Email crawl — runs unconditionally when website is present
if email_crawl_enabled and has_website:  # was: if enrichment_enabled and has_website
    enr_res = self.enricher.enrich_website(...)
    # merge contacts as before — unchanged

    # NEW: Facebook About scrape as fallback when no email was found
    if enr_res and not enr_res.contacts.emails:
        fb_url = discovered_socials.get("facebook") or (
            rec.raw_data.get("facebook_url") if isinstance(rec.raw_data, dict) else None
        )
        if fb_url:
            fb_emails = self.enricher.scrape_facebook_about(fb_url)
            if fb_emails:
                enr_res.contacts.emails = fb_emails
```

**Change 4 — Keep verification and field-rejection gated on `enrichment_enabled`:**

```python
if enrichment_enabled:
    v_res = VerificationAndEvidenceEngine.verify_candidate(...)
else:
    v_res = OverallVerificationResult(
        decision="ACCEPT",
        composite_confidence=0.5,
        is_verified_entity=False,
        has_verified_contact=bool(effective_phone or effective_email or effective_website),
    )

# Sanitize rejected fields — only when full verification ran
if enrichment_enabled and v_res.field_results["email"].verification_status == VerificationStatus.REJECTED:
    effective_email = None
```

---

#### File 2: `backend/app/enrichment/website_enricher.py`

**Class:** `ProductionWebsiteEnricher`

**Change 1 — Raise default `max_pages` from 5 to 10:**

```python
def __init__(self, timeout_seconds: float = 5.0, max_pages: int = 10, ...) -> None:
```

All callers that do not override `max_pages` will automatically use 10.

**Change 2 — Add generic-link fallback in `_discover_internal_links`:**

```python
# After the existing keyword-priority loop, before the return:

# Fallback: if no priority keyword pages were found, include any same-domain
# internal links (up to max_pages) as generic candidates.
if not candidate_links:
    for href in raw_hrefs:
        href_clean = href.strip()
        if not href_clean or href_clean.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urljoin(base_url, href_clean)
        parsed = urlparse(full_url)
        if parsed.netloc.lower() != base_domain:
            continue
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if clean_url in seen:
            continue
        seen.add(clean_url)
        # Assign a low priority (len(priority_keywords)) so keyword matches always
        # win when candidate_links is non-empty.
        candidate_links.append((len(priority_keywords), clean_url))

candidate_links.sort(key=lambda x: x[0])
return [url for _, url in candidate_links]
```

**Change 3 — Add `scrape_facebook_about` method:**

```python
def scrape_facebook_about(self, facebook_url: str) -> list[dict[str, Any]]:
    """
    Attempts to fetch the Facebook Business About page and extract email addresses.
    Facebook aggressively blocks bots; this is a best-effort, single-fetch attempt.
    Returns a list of email dicts in the same format as ExtractedContacts.emails.
    """
    # Normalise to the /about path
    parsed = urlparse(facebook_url)
    about_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/about"

    try:
        page = self._fetch_page(about_url)
        if not page.html:
            return []
        return self._extract_contacts_from_html(page.html, about_url).emails
    except Exception as fb_err:
        logger.warning(f"[WebsiteEnricher] Facebook About scrape failed for {facebook_url}: {fb_err}")
        return []
```

---

#### File 3: `backend/app/api_services.py` (new endpoint)

**New Route:** `POST /scrape-jobs/{job_id}/re-enrich-emails`

**Design:**

```python
@router.post("/scrape-jobs/{job_id}/re-enrich-emails")
def re_enrich_job_emails(job_id: str) -> dict[str, Any]:
    """
    Re-runs email discovery for all leads in a job that have a missing or
    phone-number email field. Uses the existing enrich_email_pipeline.
    Safe to call multiple times (idempotent: does not overwrite valid emails).
    """
    import uuid, re as _re
    from backend.app.models import RawLead, RawLeadSheet
    from backend.app.enrichment.email_pipeline import enrich_email_pipeline
    from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher

    PHONE_PATTERN = _re.compile(r"^\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}$")

    def needs_email_enrich(email: str | None) -> bool:
        if not email:
            return True
        return bool(PHONE_PATTERN.match(email.strip()))

    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    with SessionLocal() as db:
        job = db.scalar(select(RawLeadSheet).where(RawLeadSheet.id == job_uuid))
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        leads = db.scalars(
            select(RawLead).where(RawLead.sheet_id == job_uuid)
        ).all()

    enricher = ProductionWebsiteEnricher(max_pages=10)
    updated, skipped, failed = 0, 0, 0

    for lead in leads:
        if not needs_email_enrich(lead.email):
            skipped += 1
            continue
        if not lead.website:
            skipped += 1
            continue
        try:
            enr_res = enricher.enrich_website(
                target_url=lead.website,
                provider_email=lead.email if not needs_email_enrich(lead.email) else None,
            )
            if enr_res and enr_res.contacts.emails:
                best_email = enr_res.contacts.emails[0]["email"]
                with SessionLocal() as db2:
                    rl = db2.get(RawLead, lead.id)
                    if rl:
                        rl.email = best_email
                        db2.commit()
                updated += 1
            else:
                skipped += 1
        except Exception as err:
            logger.warning(f"[re-enrich-emails] Failed for lead {lead.id}: {err}")
            failed += 1

    return {"job_id": job_id, "updated": updated, "skipped": skipped, "failed": failed}
```

---

## Testing Strategy

### Validation Approach

Testing follows a two-phase approach: first surface counterexamples that demonstrate each
of the four bug paths on unfixed code, then verify the fix resolves them and preserves all
existing behaviour.

---

### Exploratory Bug Condition Checking

**Goal:** Run tests against the UNFIXED code to confirm observed failures match the
hypothesized root causes. If a test does not fail, the root cause analysis for that path
must be revised.

**Test Cases:**

1. **Gate bypass test (Path A):** Call `stage_2_enrich_and_verify` with
   `job_state["enrichments"] = []` and a candidate that has a website URL known to
   contain an email. Assert that the returned `effective_email` is a real email address.
   *(Will fail on unfixed code — early return fires, returns `rec.email` which is a
   phone number.)*

2. **Shallow crawl test (Path B):** Instantiate `ProductionWebsiteEnricher(max_pages=5)`.
   Call `enrich_website` with a mock site that has no keyword-matched paths but has a
   generic `/our-story` page containing an email. Assert that the email is discovered.
   *(Will fail on unfixed code — `_discover_internal_links` returns [] for no keyword
   matches; only homepage is crawled.)*

3. **Facebook About test (Path C):** Call `enricher.scrape_facebook_about(fb_url)` on
   unfixed code. Assert that the method exists and returns emails.
   *(Will fail on unfixed code — method does not exist.)*

4. **Re-enrichment endpoint test (Path D):** Call
   `POST /scrape-jobs/{job_id}/re-enrich-emails` on unfixed code. Assert HTTP 200 with
   update counts.
   *(Will fail on unfixed code — route does not exist.)*

**Expected Counterexamples:**

- Path A: `effective_email` contains a phone number string (e.g., "(905) 334-0732").
- Path B: `enr_res.contacts.emails == []` despite email being present on a non-keyword page.
- Path C: `AttributeError: 'ProductionWebsiteEnricher' object has no attribute 'scrape_facebook_about'`.
- Path D: HTTP 404 or 405 on the endpoint.

---

### Fix Checking

**Goal:** Verify that for all inputs where `isBugCondition(X)` is true, the fixed system
produces the expected behaviour.

**Pseudocode:**

```
FOR ALL X WHERE isBugCondition(X) DO
  result := stage_2_enrich_and_verify_fixed(X)
  ASSERT result.effective_email IS NOT a phone number
  ASSERT result.crawl_attempted = true   // enr_res is not None
END FOR
```

**Test Cases:**

1. **Gate removed (Path A fix):** Same test as exploration test 1 but on fixed code.
   Assert `effective_email` is either a real email or `None` (not a phone number).

2. **Fallback crawl (Path B fix):** Same test as exploration test 2 with `max_pages=10`.
   Assert `/our-story` email is discovered.

3. **Facebook About (Path C fix):** Mock `_fetch_page` to return Facebook About HTML
   with an email address. Assert `scrape_facebook_about` returns that email.

4. **Re-enrichment endpoint (Path D fix):** Seed a lead with
   `email="(905) 334-0732"`, `website="https://example.com"`. Call endpoint. Assert
   `updated >= 1` and lead's email field is a valid email address.

---

### Preservation Checking

**Goal:** Verify that for all inputs where `isBugCondition(X)` is false, the fixed
function produces the same result as the original.

**Pseudocode:**

```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT stage_2_original(X) = stage_2_fixed(X)
END FOR
```

**Testing Approach:** Property-based testing is recommended here because:
- It generates many random combinations of `enrichment_enabled`, website presence, and
  email state automatically.
- It catches edge cases where the new `email_crawl_enabled` flag accidentally changes
  behaviour for leads that already had correct emails.
- It provides strong guarantees over the full non-buggy input domain.

**Test Cases:**

1. **Cache preservation:** Seed the global domain cache with a valid enrichment result.
   Call `enrich_website` on fixed code. Assert the cached result is returned without
   re-fetching (pages_fetched_count unchanged).

2. **Conflict recording preservation:** Provide a `provider_email` that differs from the
   crawled email. Assert the `conflicts` dict is populated on fixed code exactly as on
   unfixed code.

3. **Phone validation independence:** After the fix, assert that phone rejection
   (`VerificationStatus.REJECTED` on phone field) still nullifies `effective_phone` and
   does NOT affect `effective_email`.

4. **No-website skip preservation:** Lead with `rec.website = None`. Assert
   `enrich_website` is never called and `effective_email = rec.email` (unchanged).

5. **Enrichment-off verification passthrough:** With `enrichment_enabled = False`, assert
   that `v_res` is still a baseline `OverallVerificationResult` (not a full verification
   run), preserving the original verification path for non-enrichment jobs.

---

### Unit Tests

- Test `_discover_internal_links` with HTML containing only non-keyword links — assert
  fallback returns generic internal links.
- Test `_discover_internal_links` with HTML containing both keyword and non-keyword links —
  assert keyword links come first, generic links come after.
- Test `scrape_facebook_about` with mocked `_fetch_page` returning HTML with an email.
- Test `scrape_facebook_about` with a Facebook URL that returns a non-HTML response —
  assert empty list returned gracefully.
- Test `stage_2_enrich_and_verify` with `enrichment_enabled = False` and a lead with a
  website — assert `enr_res` is not `None`.
- Test `stage_2_enrich_and_verify` with `enrichment_enabled = False` and no website —
  assert `enr_res` is `None` (no unnecessary HTTP calls).
- Test `re_enrich_job_emails` endpoint with a mix of leads: some with valid emails
  (skipped), some with phone numbers (updated), some with no website (skipped).

### Property-Based Tests

- Generate random `job_state` dicts with varying `enrichments` values, paired with
  leads that have non-empty website URLs. Assert that for every generated input, the
  fixed `stage_2_enrich_and_verify` never returns a phone number in `effective_email`.
- Generate random `max_pages` values (1–20) and random site HTML structures. Assert that
  `_discover_internal_links` always returns at most `max_pages - 1` links, always
  prioritises keyword-matched links when present, and always returns at least one link
  when any internal same-domain link exists.
- Generate random lead records where `isBugCondition` is false. Assert that
  `stage_2_fixed(X) == stage_2_original(X)` for effective_email, effective_phone, and
  effective_website (preservation property).

### Integration Tests

- Full scrape job with `enrichments = []`: submit a job, run discovery, assert that all
  leads with website URLs have their email column populated (or `None`, never a phone
  number).
- Full scrape job with `enrichments = ["email"]`: assert existing path continues to work
  and emails are still discovered.
- Re-enrichment endpoint integration: seed a completed job with 10 leads, 5 of which have
  phone numbers in the email field. Call the endpoint. Assert exactly 5 are updated and 5
  are skipped.
- Cache integration: run enrichment twice for the same domain. Assert only one HTTP fetch
  occurs (cache hit on second call).
