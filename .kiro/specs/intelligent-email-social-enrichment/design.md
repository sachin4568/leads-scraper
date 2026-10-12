# Intelligent Email & Social Enrichment Bugfix Design

## Overview

The lead enrichment pipeline has four interconnected gaps that cause the sales team to receive
low-quality contact data. This document formalises the fix for all four gaps in implementation
order, from the database outward to the orchestration layer:

1. **DB schema migration** — add `email_type`, `email_confidence`, `instagram_url`,
   `facebook_url`, `instagram_followers`, `facebook_followers` to `RawLead`; add `email_type`,
   `email_confidence`, `instagram_followers`, `facebook_followers` to `SegregatedLead`.
2. **Email classifier integration** — call `classify_email()` from inside
   `_extract_contacts_from_html()` so every email dict carries `email_type` and
   `email_confidence` before it is returned; persist the top-ranked email's type/confidence
   to `RawLead` and forward it through segregation to `SegregatedLead`.
3. **Social email extraction** — add `fetch_instagram_bio_link_email()` and
   `fetch_linkedin_owner_email()` methods to `ProductionWebsiteEnricher`; call them from
   `stage_2_enrich_and_verify` after the website crawl only when no owner-quality email was
   found; promote any `owner` / `personal_business` result to `effective_email`.
4. **Social follower count pipeline** — call `SocialScraper.fetch_profile()` for discovered
   Instagram and Facebook URLs inside `stage_2_enrich_and_verify`; carry the counts through
   `verified_results`; write them to `RawLead` in the immediate-persist block; copy them to
   `SegregatedLead` inside `public_segregate_job()`.

The fix is targeted and minimal. Every existing function signature, return type, and API
response field is preserved unchanged.

---

## Glossary

- **Bug_Condition (C)**: The set of inputs that trigger one or more of the four gaps. An input
  triggers the bug when: an email is extracted but not classified; OR a social profile has a
  follower count that is silently discarded; OR an Instagram bio link / LinkedIn page is never
  followed to find an owner email; OR the new columns do not yet exist in the schema.
- **Property (P)**: The desired outcome — every email extracted by `_extract_contacts_from_html`
  carries `email_type` and `email_confidence`; every lead whose social profile returns a follower
  count has that count persisted; every Instagram bio link and LinkedIn page is followed when no
  owner email was found from the website crawl.
- **Preservation**: All existing function signatures, return shapes, API responses, and pipeline
  behaviour for inputs that do NOT trigger any of the four gaps remain byte-for-byte identical.
- **`_extract_contacts_from_html`**: The method in `backend/app/enrichment/website_enricher.py`
  responsible for extracting emails, phones, addresses, and WhatsApp links from raw HTML. Returns
  `ExtractedContacts`, whose `emails` list currently contains plain `{"email": ..., "source_page": ...}` dicts.
- **`classify_email`**: The function in `backend/app/enrichment/email_pipeline.py` with signature
  `classify_email(email: str, business_domain: str) -> Tuple[str, bool]`. Returns
  `(classification, domain_match)`. Classifications: `INVALID`, `GENERIC_PROVIDER`, `ROLE_BASED`,
  `PERSONAL_BUSINESS`, `UNKNOWN`. Signature and return type are not changed by this fix.
- **`SocialScraper.fetch_profile`**: The method in `backend/app/enrichment/social_providers.py`
  that fetches a social profile page and returns a dict with keys `status`, `followers`,
  `followers_status`, `profile_name`, `website_url`, `description`. Already returns follower
  counts; they are simply never persisted today.
- **`stage_2_enrich_and_verify`**: The orchestrator method in
  `backend/app/orchestration/discovery_orchestrator.py` that enriches each discovered candidate.
  Builds a `verified_results` list of dicts passed onward to stages 3 and 4. Contains the
  immediate-persist block that writes `effective_email` and `effective_website` to `RawLead`.
- **`public_segregate_job`**: The FastAPI endpoint in `backend/app/api_services.py` that creates
  `SegregatedLead` records by copying fields from `RawLead`. Currently copies `business_name`,
  `website`, `email`, `phone`, `location`, `source`, `notes` only.
- **`email_type`**: A five-tier string classification stored alongside each email:
  `"owner"`, `"personal_business"`, `"generic"`, `"role"`, `"unknown"`.
- **`email_confidence`**: An integer 0–100 expressing confidence in the classification.

---

## Bug Details

### Bug Condition

The bug manifests across four codepaths that share a common root: the enrichment pipeline
extracts valuable signals (email classification, social follower counts, owner emails from
secondary social sources) but discards them before they reach the database or the sales team.

**Formal Specification:**

```
FUNCTION isBugCondition(input)
  INPUT: input of type EnrichmentPipelineRun
  OUTPUT: boolean

  RETURN (
    emailExtracted(input)
      AND NOT emailTypeAttachedToEmailDict(input)        -- gap 1: classifier not called
  ) OR (
    socialProfileFound(input)
      AND followerCountReturned(input)
      AND NOT followerCountPersisted(input)              -- gap 2: count discarded
  ) OR (
    socialProfileFound(input)
      AND instagramBioLinkPresent(input)
      AND NOT bioLinkFollowed(input)                     -- gap 3a: bio link not crawled
  ) OR (
    socialProfileFound(input)
      AND linkedinHandleKnown(input)
      AND NOT linkedinAboutPageFetched(input)            -- gap 3b: LinkedIn not fetched
  ) OR (
    NOT schemaColumnsExist(input)                        -- gap 4: columns missing
  )
END FUNCTION
```

### Examples

- **Email classification not persisted**: `_extract_contacts_from_html` finds `john@acme.com` on
  `/team`. The email dict is `{"email": "john@acme.com", "source_page": "…/team"}`. No
  `email_type` or `email_confidence` key. The orchestrator cannot distinguish this owner email
  from `info@acme.com`.
- **Follower count silently dropped**: `SocialScraper.fetch_profile("instagram", "https://instagram.com/acmeplumbing")`
  returns `{"status": "FOUND", "followers": 4200, ...}`. The orchestrator appends
  `discovered_socials = {"instagram": "https://instagram.com/acmeplumbing"}` to `verified_results`
  but the follower count never reaches `RawLead.instagram_followers` because the column and the
  write statement do not exist.
- **Bio link not followed**: Instagram profile contains `"Linktree: https://linktr.ee/acmeplumbing"`.
  The enricher never fetches that URL to find `owner@acmeplumbing.com` hidden on the landing page.
- **LinkedIn not fetched**: `discovered_socials["linkedin"] = "https://linkedin.com/company/acmeplumbing"`.
  The about page at `/about` lists `owner@acmeplumbing.com`. The orchestrator never fetches it.
- **Segregation copies nothing new**: After fixing gaps 1-4, `public_segregate_job()` still does
  not copy `email_type`, `email_confidence`, `instagram_followers`, `facebook_followers` from
  `RawLead` to `SegregatedLead` because those attributes are not referenced in the copy loop.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- `classify_email(email, business_domain)` in `email_pipeline.py` SHALL continue to return the
  same `Tuple[str, bool]` with the same five classification strings. Its signature is not touched.
- `_extract_contacts_from_html(html, page_url)` SHALL continue to return an `ExtractedContacts`
  object. The `emails` list structure is extended (new keys added to each dict) but never
  restructured — callers iterating `contacts.emails` and reading `item["email"]` are unaffected.
- `enrich_website(target_url, ...)` SHALL continue to return `EnrichedWebsiteResult` with the
  same fields. No fields are removed or renamed.
- `SocialScraper.fetch_profile(platform, url)` SHALL continue to return the same dict shape. Its
  signature is not changed.
- The `stage_2_enrich_and_verify` immediate-persist block SHALL continue to write `effective_email`
  and `effective_website` to `RawLead` exactly as before. The new writes for follower counts and
  social URLs are appended to the same `db_update` session block.
- `public_segregate_job()` SHALL continue to produce the same `SegregatedLead` records with all
  existing fields. The new columns are additive.
- All API response shapes (`/scrape-jobs/{id}/leads`, `/sheets`, `/sheets/{id}`) SHALL continue
  to include all previously existing fields.
- Alembic migration SHALL leave all existing rows with NULL in the new columns (no backfill).
- Leads with no social profiles SHALL continue to complete enrichment without errors; the new
  follower-count columns remain NULL.
- When `SocialScraper.fetch_profile` returns `status == "UNAVAILABLE"` or `"NOT_FOUND"`, the
  corresponding follower-count column SHALL remain NULL with no exception raised.
- When the Instagram bio-link fetch or LinkedIn fetch times out or returns a non-200 response,
  the orchestrator SHALL continue with whatever emails were already extracted, without retrying
  or failing the overall enrichment job.
- When a lead already has an email with `email_type == "owner"` from the website crawl, the
  Instagram bio-link and LinkedIn fetches SHALL be skipped to avoid unnecessary network requests.

**Scope:** All inputs that do NOT involve extracting an email, discovering a social profile, or
running the segregation step are completely unaffected by this fix.

---

## Hypothesized Root Cause

1. **Classifier isolation**: `classify_email()` in `email_pipeline.py` is a well-tested standalone
   function but is never imported into `website_enricher.py`. The enricher builds its own scoring
   heuristic to rank emails yet never attaches a formal type/confidence label. The two
   implementations coexist in parallel without integration.

2. **No columns to write to**: `RawLead` and `SegregatedLead` in `models.py` have no
   `email_type`, `email_confidence`, `instagram_followers`, `facebook_followers`,
   `instagram_url`, or `facebook_url` columns. Even if the orchestrator attempted to assign
   these values the SQLAlchemy ORM would silently ignore them or raise an `AttributeError`.

3. **`verified_results` dict carries socials but not follower counts**: `stage_2_enrich_and_verify`
   populates `discovered_socials` (a `dict[str, str]` of `{platform: url}`) and places it in the
   `verified_results` dict. The follower count returned by `fetch_profile()` is never called —
   only the URL is stored. So the count is structurally unavailable even before it reaches the
   persist step.

4. **No secondary social crawl methods exist**: `ProductionWebsiteEnricher` has
   `scrape_facebook_about()` but no equivalent for Instagram bio links or LinkedIn. The
   orchestrator has a conditional for the Facebook fallback but no code path for the other two
   secondary sources.

5. **Segregation copies a hardcoded field list**: `public_segregate_job()` constructs
   `SegregatedLead(...)` with an explicit list of keyword arguments. Any new `RawLead` columns
   are silently omitted unless they are explicitly added to the constructor call.

---

## Correctness Properties

Property 1: Bug Condition — Email Type Attached to Every Extracted Email Dict

_For any_ HTML page processed by `_extract_contacts_from_html` that yields at least one non-role,
non-invalid email address, the fixed method SHALL attach `email_type` (one of `"owner"`,
`"personal_business"`, `"generic"`, `"role"`, `"unknown"`) and `email_confidence` (integer 0–100)
to every email dict in the returned `ExtractedContacts.emails` list, and SHALL sort that list
`owner → personal_business → generic → role → unknown`.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition — Email Type/Confidence Written to RawLead

_For any_ enrichment run where `enr_res.contacts.emails` is non-empty after
`stage_2_enrich_and_verify`, the fixed orchestrator SHALL write `email_type` and
`email_confidence` from the first (top-ranked) email dict to `RawLead.email_type` and
`RawLead.email_confidence` in the immediate-persist block.

**Validates: Requirements 2.3**

Property 3: Bug Condition — Email Type/Confidence Copied to SegregatedLead

_For any_ `RawLead` that has a non-NULL `email_type`, the fixed `public_segregate_job()` SHALL
copy `email_type` and `email_confidence` to the resulting `SegregatedLead` record.

**Validates: Requirements 2.4**

Property 4: Bug Condition — Follower Counts Persisted to RawLead

_For any_ enrichment run where `SocialScraper.fetch_profile()` returns `status == "FOUND"` with
a non-NULL `followers` value for Instagram or Facebook, the fixed orchestrator SHALL write that
count to `RawLead.instagram_followers` or `RawLead.facebook_followers` (matching the platform) in
the immediate-persist block of `stage_2_enrich_and_verify`.

**Validates: Requirements 2.5**

Property 5: Bug Condition — Follower Counts Copied to SegregatedLead

_For any_ `RawLead` with a non-NULL `instagram_followers` or `facebook_followers`, the fixed
`public_segregate_job()` SHALL copy those values to `SegregatedLead.instagram_followers` and
`SegregatedLead.facebook_followers`.

**Validates: Requirements 2.6**

Property 6: Bug Condition — Instagram Bio Link Followed for Owner Email

_For any_ enrichment run where `discovered_socials["instagram"]` is set AND no owner-quality
email (`email_type` in `{"owner", "personal_business"}`) was found from the website crawl, the
fixed enricher SHALL fetch the Instagram profile page, extract the bio link URL, fetch that URL,
and run `_extract_contacts_from_html` on the landing page HTML. If an owner/personal-business
email is found, it SHALL be promoted to `effective_email`.

**Validates: Requirements 2.7, 2.9**

Property 7: Bug Condition — LinkedIn About Page Fetched for Owner Email

_For any_ enrichment run where `discovered_socials["linkedin"]` is set AND no owner-quality email
was found, the fixed enricher SHALL fetch `https://www.linkedin.com/company/{handle}/about`
(best-effort, single attempt), scan it for email addresses using `_extract_contacts_from_html`,
and promote any `owner`/`personal_business` result to `effective_email`.

**Validates: Requirements 2.8, 2.9**

Property 2P: Preservation — Non-Buggy Inputs Produce Identical Results

_For any_ enrichment run where the bug condition does NOT hold (no social profiles found, no
emails extracted, social profiles found but `fetch_profile` returns non-FOUND status), the fixed
pipeline SHALL produce the same `verified_results`, `RawLead`, and `SegregatedLead` state as the
original unfixed pipeline.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10**

---

## Fix Implementation

### Change 1: Alembic Migration — New Columns

**File**: `alembic/versions/<timestamp>_add_email_type_social_columns.py`

**Operation**: Create a new Alembic migration that adds the following columns with no server
default other than NULL so existing rows are unaffected.

```
RawLead (raw_leads table):
  email_type          VARCHAR(32)     NULL
  email_confidence    INTEGER         NULL
  instagram_url       VARCHAR(2048)   NULL
  facebook_url        VARCHAR(2048)   NULL
  instagram_followers INTEGER         NULL
  facebook_followers  INTEGER         NULL

SegregatedLead (segregated_leads table):
  email_type          VARCHAR(32)     NULL
  email_confidence    INTEGER         NULL
  instagram_followers INTEGER         NULL
  facebook_followers  INTEGER         NULL
```

**SQLAlchemy model additions** in `backend/app/models.py`:

```python
# RawLead additions
email_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
email_confidence: Mapped[int | None] = mapped_column(nullable=True)
instagram_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
facebook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
instagram_followers: Mapped[int | None] = mapped_column(nullable=True)
facebook_followers: Mapped[int | None] = mapped_column(nullable=True)

# SegregatedLead additions
email_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
email_confidence: Mapped[int | None] = mapped_column(nullable=True)
instagram_followers: Mapped[int | None] = mapped_column(nullable=True)
facebook_followers: Mapped[int | None] = mapped_column(nullable=True)
```

---

### Change 2: Email Classifier Integration

**File**: `backend/app/enrichment/website_enricher.py`

**Function**: `ProductionWebsiteEnricher._extract_contacts_from_html`

The five-tier type system maps the existing score-based ranking to formal labels compatible
with `classify_email()`. The domain for classification is derived from the `page_url` argument
(the netloc of the crawled page, which equals the business domain for all internal pages).

**Type/Confidence mapping**:

| Condition | `email_type` | `email_confidence` |
|---|---|---|
| Free-mail provider domain (gmail, yahoo, hotmail, outlook, hotmail, icloud, etc.) | `"generic"` | 30 |
| Local part matches a role prefix from `role_prefixes` set | `"role"` | 10 |
| `first.last` / `first_last` pattern AND page context is team/about/owner/founder | `"owner"` | 95 |
| `first.last` / `first_last` pattern AND company domain match | `"personal_business"` | 80 |
| Company domain match (local part does not match role or name pattern) | `"personal_business"` | 60 |
| Domain does not match company domain and no free-mail match | `"unknown"` | 20 |

**Specific Changes**:

1. **Import `classify_email` at module top**: Add
   `from backend.app.enrichment.email_pipeline import classify_email` to
   `website_enricher.py`. This is a module-level import — no circular dependency because
   `email_pipeline.py` does not import from `website_enricher.py`.

2. **Derive business domain inside `_extract_contacts_from_html`**: After the existing
   `page_lower` assignment, extract:
   ```python
   business_domain = urlparse(page_url).netloc.lower().lstrip("www.")
   ```

3. **Attach type/confidence after scoring loop**: After the `scored_emails.sort(...)` call and
   before appending to `contacts.emails`, call `classify_email(em_val, business_domain)` for
   each email and add the result to the email dict:
   ```python
   cls, domain_match = classify_email(em_val, business_domain)
   # Map classify_email classifications to the 5-tier type system
   email_type = _classify_to_type(cls, domain_match, em_val, local_part, page_lower)
   email_confidence = _type_to_confidence(email_type)
   contacts.emails.append({
       "email": em_val,
       "source_page": page_url,
       "email_type": email_type,
       "email_confidence": email_confidence,
   })
   ```

4. **Add helper functions** `_classify_to_type` and `_type_to_confidence` (module-level,
   not methods) that implement the mapping table above. These are pure functions with no I/O.

5. **Sort order**: After all emails are appended, re-sort `contacts.emails` by
   `email_type` priority: `owner(0) → personal_business(1) → generic(2) → role(3) → unknown(4)`.
   This replaces the score-based sort for the final list order (the score is still used to
   select among multiple emails of the same type).

**Orchestrator persist block** (`stage_2_enrich_and_verify`, immediate-persist section):

Add to the existing `if rl:` block in the `db_update` session:
```python
if enr_res and enr_res.contacts and enr_res.contacts.emails:
    top_email = enr_res.contacts.emails[0]
    rl.email_type = top_email.get("email_type")
    rl.email_confidence = top_email.get("email_confidence")
```

**Segregation step** (`public_segregate_job`, `api_services.py`):

In the `for rl in raw_leads:` loop, add to the `SegregatedLead(...)` constructor:
```python
email_type=rl.email_type,
email_confidence=rl.email_confidence,
```

---

### Change 3: Social Email Extraction

**File**: `backend/app/enrichment/website_enricher.py`

**New Methods** on `ProductionWebsiteEnricher`:

#### `fetch_instagram_bio_link_email(instagram_url: str) -> list[dict]`

```
FUNCTION fetch_instagram_bio_link_email(instagram_url)
  INPUT: instagram_url — the Instagram profile URL
  OUTPUT: list of email dicts (same shape as ExtractedContacts.emails) or []

  1. Fetch instagram_url using _fetch_page()
  2. IF status_code not 200 OR html is empty: RETURN []
  3. Search html for bio link patterns:
       - <a> href matching linktree.com, beacons.ai, bio.link, direct external URLs
         in the bio section identified by og:description or JSON-LD
       - Raw regex: href="(https?://[^"]+)" near text containing "linktr", "bio.link",
         "beacons", or within the first 3000 chars of body
  4. IF no bio link found: RETURN []
  5. Fetch bio_link_url using _fetch_page() with SSRF guard (validate_outbound_url)
  6. IF status_code not 200 OR html is empty: RETURN []
  7. contacts = _extract_contacts_from_html(bio_page.html, bio_page.url)
  8. Tag each email dict: email_dict["source"] = "instagram_bio_link"
  9. RETURN contacts.emails
END FUNCTION
```

#### `fetch_linkedin_owner_email(linkedin_url: str) -> list[dict]`

```
FUNCTION fetch_linkedin_owner_email(linkedin_url)
  INPUT: linkedin_url — the LinkedIn company page URL
  OUTPUT: list of email dicts or []

  1. Parse handle from linkedin_url:
       parsed = urlparse(linkedin_url)
       parts = parsed.path.strip("/").split("/")  # ["company", "acmeplumbing"]
       handle = parts[-1] if len(parts) >= 2 else None
  2. IF handle is None: RETURN []
  3. about_url = f"https://www.linkedin.com/company/{handle}/about"
  4. Fetch about_url using _fetch_page()
  5. IF status_code not 200 OR html is empty: RETURN []
  6. contacts = _extract_contacts_from_html(page.html, about_url)
  7. Tag each email dict: email_dict["source"] = "linkedin_about"
  8. RETURN contacts.emails
END FUNCTION
```

**Integration point in `stage_2_enrich_and_verify`** (`discovery_orchestrator.py`):

After the existing Step 2b website crawl block (after the `scrape_facebook_about` fallback),
add Step 2c — secondary social email hunt:

```
STEP 2c: Secondary social email hunt
  IF no owner-quality email found yet:
    -- Define: owner_found = any(e.get("email_type") in ("owner", "personal_business")
    --                           for e in (enr_res.contacts.emails if enr_res else []))
    --         AND effective_email is not None

    IF NOT owner_found AND "instagram" in discovered_socials:
      ig_emails = enricher.fetch_instagram_bio_link_email(discovered_socials["instagram"])
      IF ig_emails and ig_emails[0].get("email_type") in ("owner", "personal_business"):
        effective_email = ig_emails[0]["email"]
        IF enr_res: enr_res.contacts.emails = ig_emails + enr_res.contacts.emails

    IF NOT owner_found AND "linkedin" in discovered_socials:
      li_emails = enricher.fetch_linkedin_owner_email(discovered_socials["linkedin"])
      IF li_emails and li_emails[0].get("email_type") in ("owner", "personal_business"):
        effective_email = li_emails[0]["email"]
        IF enr_res: enr_res.contacts.emails = li_emails + enr_res.contacts.emails

  Each fetch is wrapped in try/except; any exception logs a warning and continues.
```

---

### Change 4: Social Follower Count Pipeline

**File**: `backend/app/orchestration/discovery_orchestrator.py`

**Function**: `DiscoveryOrchestrator.stage_2_enrich_and_verify`

**Step 2d — Follower count fetch** (new block, after Step 2c):

The `SocialScraper` already exists in `social_providers.py`. It is instantiated once per
`stage_2_enrich_and_verify` call (or once per orchestrator instance) to avoid repeated object
construction.

```
STEP 2d: Social follower count fetch
  instagram_followers = None
  facebook_followers  = None

  IF "instagram" in discovered_socials:
    TRY:
      ig_result = SocialScraper().fetch_profile("instagram", discovered_socials["instagram"])
      IF ig_result.get("status") == "FOUND":
        instagram_followers = ig_result.get("followers")  # may be None if not parseable
    EXCEPT: log warning, continue

  IF "facebook" in discovered_socials:
    TRY:
      fb_result = SocialScraper().fetch_profile("facebook", discovered_socials["facebook"])
      IF fb_result.get("status") == "FOUND":
        facebook_followers = fb_result.get("followers")
    EXCEPT: log warning, continue
```

**verified_results dict extension**:

Add the new keys to the dict appended to `verified_results`:
```python
verified_results.append({
    ...existing keys...,
    "instagram_followers": instagram_followers,
    "facebook_followers": facebook_followers,
    "discovered_instagram_url": discovered_socials.get("instagram"),
    "discovered_facebook_url": discovered_socials.get("facebook"),
})
```

**Immediate-persist block extension** (same `db_update` session block that already writes
`effective_email` and `effective_website`):

```python
if rl:
    if effective_email:
        rl.email = effective_email
    if effective_website:
        rl.website = effective_website
    # NEW: email classification
    if enr_res and enr_res.contacts and enr_res.contacts.emails:
        top = enr_res.contacts.emails[0]
        rl.email_type = top.get("email_type")
        rl.email_confidence = top.get("email_confidence")
    # NEW: social URLs
    if item.get("discovered_instagram_url"):
        rl.instagram_url = item["discovered_instagram_url"]
    if item.get("discovered_facebook_url"):
        rl.facebook_url = item["discovered_facebook_url"]
    # NEW: follower counts
    if item.get("instagram_followers") is not None:
        rl.instagram_followers = item["instagram_followers"]
    if item.get("facebook_followers") is not None:
        rl.facebook_followers = item["facebook_followers"]
    db_update.commit()
```

Note: `item` refers to the current `verified_results` dict entry. The immediate-persist block
must be refactored to iterate `verified_results` inline (it currently queries `RawLead` by
`business_name` inline); the follower counts and social URLs must be passed into the block from
the current loop iteration's local variables.

**Segregation step** (`public_segregate_job`, `api_services.py`):

In the `for rl in raw_leads:` loop, add to the `SegregatedLead(...)` constructor:
```python
email_type=rl.email_type,
email_confidence=rl.email_confidence,
instagram_followers=rl.instagram_followers,
facebook_followers=rl.facebook_followers,
```

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples on the unfixed
code to confirm root cause analysis; then verify the fix works correctly and preserves existing
behaviour.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each of the four gaps BEFORE implementing the
fix. Confirm or refute the root cause analysis.

**Test Plan**: Write unit tests that exercise each gap directly against the existing codebase.
Run these on UNFIXED code to observe failures.

**Test Cases**:

1. **Email type missing**: Call `_extract_contacts_from_html` with HTML containing
   `mailto:john.doe@acmeplumbing.com` on a `/team` page. Assert that
   `contacts.emails[0].get("email_type")` is not None. Will fail on unfixed code — key absent.

2. **Follower count not persisted**: Mock `SocialScraper.fetch_profile` to return
   `{"status": "FOUND", "followers": 1500}`. Run `stage_2_enrich_and_verify` with a candidate
   that has an Instagram URL. Query the `RawLead` record after the run. Assert
   `raw_lead.instagram_followers == 1500`. Will fail on unfixed code — column absent.

3. **Instagram bio link not followed**: Provide HTML for an Instagram profile that contains
   a Linktree URL. Call `enricher.fetch_instagram_bio_link_email(instagram_url)`. Assert method
   exists and returns a non-empty list. Will fail on unfixed code — method does not exist
   (`AttributeError`).

4. **LinkedIn not fetched**: Provide a LinkedIn company URL. Call
   `enricher.fetch_linkedin_owner_email(linkedin_url)`. Assert method exists. Will fail on
   unfixed code — method does not exist (`AttributeError`).

5. **Segregation drops new columns**: Create a `RawLead` with `email_type="owner"` and
   `instagram_followers=800`. Run `public_segregate_job`. Query the resulting `SegregatedLead`.
   Assert `seg_lead.email_type == "owner"`. Will fail on unfixed code — column absent.

**Expected Counterexamples**:
- `KeyError` / `None` when accessing `email_type` on email dicts from `_extract_contacts_from_html`.
- `AttributeError: type object 'RawLead' has no attribute 'instagram_followers'` when the
  orchestrator tries to write to the missing column.
- `AttributeError: 'ProductionWebsiteEnricher' object has no attribute 'fetch_instagram_bio_link_email'`.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed pipeline produces
the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := run_enrichment_pipeline_fixed(input)
  ASSERT expectedBehavior(result)  -- email dicts have type/confidence,
                                   -- follower counts persisted,
                                   -- secondary email sources tried,
                                   -- segregation copies all new fields
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed pipeline
produces the same result as the original pipeline.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT run_enrichment_pipeline_original(input)
       = run_enrichment_pipeline_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (varied HTML, varied social
  profile states, varied email patterns).
- It catches edge cases that manual unit tests might miss (empty HTML, HTML with only role emails,
  profiles returning `UNAVAILABLE`).
- It provides strong guarantees that the existing scoring heuristic in `_extract_contacts_from_html`
  still produces the same ranked output for inputs that have no owner-context pages.

**Test Cases**:

1. **No-social-profile preservation**: Run `stage_2_enrich_and_verify` on a candidate with no
   `discovered_socials`. Verify `verified_results` dict is identical to pre-fix output (no new
   keys with non-None values). Verify `RawLead` has NULL follower counts.

2. **Role-email-only preservation**: Call `_extract_contacts_from_html` with HTML containing
   only `info@acme.com`. Verify the email is still returned (not silently dropped) with
   `email_type="role"` and `email_confidence=10`. Verify the existing caller path in the
   orchestrator still picks `effective_email = None` (since no personal email was found).

3. **`classify_email` signature preservation**: Call `classify_email("john@acme.com", "acme.com")`
   before and after the fix. Assert the return value is identical (`("PERSONAL_BUSINESS", True)`).

4. **`scrape_facebook_about` preservation**: Call `scrape_facebook_about(fb_url)` before and
   after. Assert same return shape `list[dict]` with `"email"` and `"source"` keys.

5. **Timeout/error fallback**: Mock `_fetch_page` to raise `httpx.TimeoutException` for
   Instagram bio-link URL. Assert `stage_2_enrich_and_verify` completes normally using the
   website-crawl email as `effective_email`.

### Unit Tests

- Test `_classify_to_type` and `_type_to_confidence` helpers with all five classification paths.
- Test `_extract_contacts_from_html` returns dicts with `email_type` and `email_confidence` keys.
- Test sort order: verify emails are sorted `owner → personal_business → generic → role → unknown`.
- Test `fetch_instagram_bio_link_email` with mocked HTML containing a Linktree link.
- Test `fetch_instagram_bio_link_email` returns `[]` on non-200 response.
- Test `fetch_linkedin_owner_email` with mocked LinkedIn `/about` HTML.
- Test `fetch_linkedin_owner_email` returns `[]` when handle cannot be parsed.
- Test the Alembic migration up/down round-trip (no data loss, NULL defaults).

### Property-Based Tests

- Generate random HTML strings and assert that `_extract_contacts_from_html` always returns
  `email_type` for every email dict (never absent key).
- Generate random email strings with varied local parts and domains; assert
  `classify_email` and `_classify_to_type` agree on classification for the shared cases
  (`GENERIC_PROVIDER → "generic"`, `PERSONAL_BUSINESS → "personal_business"`,
  `ROLE_BASED → "role"`, `UNKNOWN → "unknown"`).
- Generate random `verified_results` dicts (with and without follower counts); assert that
  `public_segregate_job` copies the four new fields faithfully when non-None and leaves them
  NULL when None, across many varied inputs.
- Generate random `SocialScraper.fetch_profile` return dicts; assert that status values other
  than `"FOUND"` never write anything to `RawLead`.

### Integration Tests

- End-to-end: run a full `stage_2_enrich_and_verify` with a mocked enricher that returns
  an Instagram URL; assert the `RawLead` in the test DB has a non-NULL `instagram_followers`
  after the run.
- Segregation round-trip: create a `RawLead` with all six new columns populated; call
  `public_segregate_job`; assert the resulting `SegregatedLead` has the four new columns
  copied correctly.
- Classifier end-to-end: serve a mock HTML page with a `/team` path containing
  `john.doe@acme.com`; run `enrich_website`; assert `enr_res.contacts.emails[0]["email_type"] == "owner"`.
