with open('backend/app/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add logging and logger
if "import logging" not in content:
    content = content.replace("import uuid", "import logging\nimport uuid")
    content = content.replace(
        "bearer = HTTPBearer(auto_error=False)",
        "logger = logging.getLogger(__name__)\n\nbearer = HTTPBearer(auto_error=False)"
    )

# 2. Add ServiceOpportunity to models import
content = content.replace(
    "    ScrapeJob,\n    ServiceScore,",
    "    ScrapeJob,\n    ServiceOpportunity,\n    ServiceScore,"
)

# 3. Fix pipeline import
content = content.replace(
    "from backend.app.enrichment.pipelines import enrich_website_pipeline",
    "from backend.app.enrichment.website_pipeline import enrich_website_pipeline"
)

# 4. Clean up create_scrape_job
old_block = """    print('DEBUG: Received scrape payload:', payload.model_dump())
    from backend.app.ingestion.canonical_location import LocationValidator
    is_valid_loc, loc_err, loc_scope = LocationValidator.validate_requested_configuration(
        country=payload.country,
        region=payload.region,
        city=payload.city,
        locations=payload.locations,
    )
    if not is_valid_loc or not loc_scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=loc_err or "Invalid location configuration.",
        )

    payload_dict = payload.model_dump()
    payload_dict["country"] = loc_scope.country
    payload_dict["region"] = loc_scope.region
    if loc_scope.city:
        payload_dict["state"] = loc_scope.city
    elif payload.locations and len(payload.locations) > 0:
        payload_dict["state"] = payload.locations[0]"""

new_block = """    from backend.app.ingestion.canonical_location import LocationValidator
    is_valid_loc, loc_err, loc_scope = LocationValidator.validate_requested_configuration(
        country=payload.country,
        region=payload.region,
        city=payload.city,
        locations=payload.locations,
    )
    if not is_valid_loc or loc_scope is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=loc_err or "Invalid location configuration.",
        )

    payload_dict = payload.model_dump()
    payload_dict["country"] = loc_scope.country
    payload_dict["region"] = loc_scope.region
    if loc_scope.city:
        payload_dict["state"] = loc_scope.city
    elif payload.locations and len(payload.locations) > 0:
        payload_dict["state"] = payload.locations[0]"""

content = content.replace(old_block, new_block)

with open('backend/app/api.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("api.py successfully updated and written!")
