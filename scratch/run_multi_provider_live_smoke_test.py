from __future__ import annotations

import logging

from backend.app.config import get_settings
from backend.app.database import SessionLocal
from backend.app.ingestion.lifecycle import LifecycleResolver
from backend.app.sources.data_axle import DataAxleConnector
from backend.app.sources.foursquare import FoursquareConnector
from backend.app.sources.google_maps import GooglePlacesConnector
from backend.app.sources.yelp import YelpConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("multi_provider_smoke_test")


def main() -> None:
    logger.info("Starting Multi-Provider Production Readiness Smoke Test...")
    settings = get_settings()

    providers = {
        "GOOGLE_PLACES": {
            "connector": GooglePlacesConnector(),
            "key_present": bool(getattr(settings, "google_maps_api_key", None)),
        },
        "FOURSQUARE": {
            "connector": FoursquareConnector(),
            "key_present": bool(getattr(settings, "foursquare_api_key", None)),
        },
        "DATA_AXLE": {
            "connector": DataAxleConnector(),
            "key_present": bool(getattr(settings, "data_axle_api_key", None)),
        },
        "YELP": {
            "connector": YelpConnector(),
            "key_present": bool(getattr(settings, "yelp_api_key", None)),
        },
    }

    logger.info("\n=== PROVIDER CREDENTIAL & HEALTH STATUS ===")
    for pname, info in providers.items():
        conn = info["connector"]
        key_status = "PRESENT" if info["key_present"] else "MISSING_CREDENTIAL"
        health = conn.health_check()
        health_status = (
            "HEALTHY"
            if health
            else ("CREDENTIAL_MISSING" if not info["key_present"] else "UNAVAILABLE")
        )
        logger.info(
            f"Provider: {pname:<15} | Credential: {key_status:<20} | Status: {health_status}"
        )

    logger.info("\n=== CONTROLLED MINIMAL QUERY TEST ===")
    resolver = LifecycleResolver()
    db = SessionLocal()

    total_scraped = 0
    total_canonicals_created = 0

    try:
        for pname, info in providers.items():
            conn = info["connector"]
            if not info["key_present"]:
                logger.info(f"Skipping live query for {pname}: CREDENTIAL_MISSING")
                continue

            logger.info(f"Executing controlled query on {pname}...")
            records = conn.search_leads(query="Solar", location="Austin, TX", limit=2)
            logger.info(f"{pname} returned {len(records)} normalized records.")
            total_scraped += len(records)

            for rec in records:
                canonical, obs, state = resolver.process_observation(db, rec)
                logger.info(
                    f"  -> Lead '{rec.business_name}' [{rec.source}] resolved to Canonical ID: {canonical.id} ({state.value})"
                )
                if state.value == "NEW":
                    total_canonicals_created += 1

        logger.info("\n=== SMOKE TEST SUMMARY ===")
        logger.info(f"Total Provider Records Ingested: {total_scraped}")
        logger.info(f"New Canonical Leads Created: {total_canonicals_created}")
        logger.info("Smoke test complete.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
