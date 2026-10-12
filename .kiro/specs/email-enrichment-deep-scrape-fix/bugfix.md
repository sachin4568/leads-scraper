# Bugfix Requirements Document

## Introduction

The EMAIL column in the leads table displays phone numbers (e.g., "(905) 334-0732") instead of email addresses for the vast majority of scraped leads. This occurs because website email crawling is gated behind an optional user checkbox ("Verify Business Emails") in Advanced Tuning & Enrichment Options. When the checkbox is not ticked, the scraper only saves data returned by Google Maps/OSM, which includes phone numbers but no email addresses. Compounding this, even when crawling is enabled, the crawler is limited to 5 pages and only visits URL paths containing specific keywords (contact, about, team, etc.) with no fallback if those pages don't exist. Additionally, no Facebook Business About page scraping is performed, and there is no way to retroactively extract emails for leads already scraped without enrichment.

The fix ensures email crawling runs unconditionally for all scrape jobs, increases the page crawl limit, adds a fallback to any internal links when no priority pages are found, adds Facebook About page email scraping, and provides a re-enrichment endpoint for existing leads.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a scrape job is submitted without the "Verify Business Emails" checkbox selected THEN the system skips all website email crawling and stores only phone numbers in the email column

1.2 WHEN `enrichment_enabled` evaluates to `False` (i.e., `job_state.get("enrichments")` is falsy) THEN the system bypasses both zero-budget website discovery and field-aware contact crawling, leaving the email field empty or populated with phone numbers

1.3 WHEN website crawling runs but the target business site has no pages with URL paths matching keywords like /contact, /about, /team THEN the system scans only the homepage and stops, missing email addresses on other internal pages

1.4 WHEN `max_pages` is set to 5 and the priority keyword pages are exhausted early THEN the system stops crawling before reaching pages that may contain email addresses

1.5 WHEN a lead has a Facebook Business page URL but no email was found on the business website THEN the system does not scrape the Facebook About tab for email addresses

1.6 WHEN leads have already been scraped without enrichment and their email fields are empty or contain phone numbers THEN the system provides no mechanism to retroactively run email enrichment on those leads

### Expected Behavior (Correct)

2.1 WHEN a scrape job is submitted regardless of whether the "Verify Business Emails" checkbox is selected THEN the system SHALL run website email crawling for every lead that has a website URL

2.2 WHEN `job_state.get("enrichments")` is falsy THEN the system SHALL still execute zero-budget website discovery and field-aware contact crawling for email extraction, treating email crawl as unconditionally enabled

2.3 WHEN website crawling runs but the target business site has no pages with URL paths matching priority keywords THEN the system SHALL fall back to crawling any discovered internal links up to the `max_pages` limit

2.4 WHEN website crawling is performed THEN the system SHALL use a `max_pages` limit of 10 (increased from 5) to allow deeper coverage of small business sites

2.5 WHEN a lead has a Facebook Business page URL THEN the system SHALL scrape the Facebook About tab for email addresses and merge any found emails into the lead's contact record

2.6 WHEN a re-enrichment request is made for leads with missing or invalid email fields THEN the system SHALL provide a backend endpoint that re-runs email enrichment on those leads and updates their email fields with any discovered addresses

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a scrape job completes with enrichment fully enabled and email addresses were already found THEN the system SHALL CONTINUE TO preserve those email addresses without overwriting them

3.2 WHEN website crawling discovers a valid email address on a contact or about page THEN the system SHALL CONTINUE TO store and return that email as the primary contact email

3.3 WHEN `provider_email` is present and conflicts with a website-crawled email THEN the system SHALL CONTINUE TO record the conflict in the conflicts dictionary without silently overwriting either value

3.4 WHEN `max_pages` is increased to 10 and priority keyword pages are found THEN the system SHALL CONTINUE TO prioritize those keyword-matched pages before falling back to generic internal links

3.5 WHEN a lead has no website URL THEN the system SHALL CONTINUE TO skip website enrichment for that lead and leave the email field as-is from the original source data

3.6 WHEN the global domain cache contains a valid cached enrichment result for a domain THEN the system SHALL CONTINUE TO return the cached result without re-fetching, regardless of whether the cache was populated with or without email results

3.7 WHEN phone validation and rejection logic runs for a lead THEN the system SHALL CONTINUE TO apply phone rejection independently of the new unconditional email crawl behavior

---

## Bug Condition Pseudocode

**Bug Condition Function** — identifies inputs that trigger the defective behavior:

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type ScrapeJobInput
  OUTPUT: boolean

  // The bug fires whenever enrichment was not explicitly requested,
  // OR the crawler finds no priority keyword pages with no fallback.
  RETURN (X.job_state.get("enrichments") is falsy)
      OR (X.website_has_no_priority_keyword_pages AND X.max_pages <= 5)
      OR (X.lead_has_facebook_url AND no_facebook_about_scraping_exists)
      OR (X.lead.email IS NULL AND no_reenrichment_endpoint_exists)
END FUNCTION
```

**Fix Checking Property** — desired behavior for buggy inputs:

```pascal
// Property: Fix Checking — Email crawl runs unconditionally
FOR ALL X WHERE isBugCondition(X) DO
  result ← enrichLeadWithEmail'(X)
  ASSERT result.email IS NOT NULL
      OR result.crawl_attempted = true
      AND no_phone_number_in_email_field(result)
END FOR
```

**F**: `enrichLeadWithEmail` — current function that gates crawling behind `enrichment_enabled`
**F'**: `enrichLeadWithEmail'` — fixed function that always crawls for emails when a website URL is present

**Preservation Checking Property** — non-buggy inputs must be unaffected:

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT F(X) = F'(X)
END FOR
```
