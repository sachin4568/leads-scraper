from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawLead:
    """Source-agnostic normalized Raw Lead payload contract."""

    source_name: str
    business_name: str
    industry: str
    lead_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_record_id: str | None = None
    scrape_timestamp: float = field(default_factory=time.time)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    social_handles: dict[str, str] = field(default_factory=dict)
    source_url: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def get_idempotency_key(self) -> str:
        """Returns stable source idempotency key if source_record_id is present."""
        if self.source_record_id and str(self.source_record_id).strip():
            return f"{self.source_name}:{str(self.source_record_id).strip()}"
        return f"{self.source_name}:{self.lead_id}"


class BaseSourceAdapter(ABC):
    """Abstract base class for all source-agnostic lead ingestion adapters."""

    @abstractmethod
    def normalize_payload(self, raw_data: dict[str, Any]) -> RawLead:
        """Transforms provider-specific payload into a common RawLead contract."""
        pass


class GooglePlacesAdapter(BaseSourceAdapter):
    """Source adapter for Google Places / Maps API payload normalization."""

    def normalize_payload(self, raw_data: dict[str, Any]) -> RawLead:
        place_id = raw_data.get("place_id") or raw_data.get("id")
        return RawLead(
            source_name="google_places",
            source_record_id=str(place_id) if place_id else None,
            business_name=raw_data.get("name", "").strip(),
            industry=raw_data.get("types", ["General"])[0]
            if isinstance(raw_data.get("types"), list)
            else raw_data.get("industry", "General"),
            address=raw_data.get("formatted_address") or raw_data.get("address"),
            city=raw_data.get("city"),
            state=raw_data.get("state"),
            website=raw_data.get("website"),
            phone=raw_data.get("formatted_phone_number") or raw_data.get("phone"),
            email=raw_data.get("email"),
            source_url=raw_data.get("url"),
            raw_payload=raw_data,
        )


class YelpAdapter(BaseSourceAdapter):
    """Source adapter for Yelp Fusion API payload normalization."""

    def normalize_payload(self, raw_data: dict[str, Any]) -> RawLead:
        yelp_id = raw_data.get("id")
        loc = raw_data.get("location", {})
        return RawLead(
            source_name="yelp",
            source_record_id=str(yelp_id) if yelp_id else None,
            business_name=raw_data.get("name", "").strip(),
            industry=raw_data.get("categories", [{}])[0].get("title", "General")
            if isinstance(raw_data.get("categories"), list) and raw_data.get("categories")
            else "General",
            address=loc.get("address1") if isinstance(loc, dict) else None,
            city=loc.get("city") if isinstance(loc, dict) else None,
            state=loc.get("state") if isinstance(loc, dict) else None,
            website=raw_data.get("url"),
            phone=raw_data.get("display_phone") or raw_data.get("phone"),
            source_url=raw_data.get("url"),
            raw_payload=raw_data,
        )


class FacebookAdapter(BaseSourceAdapter):
    """Source adapter for Facebook Graph API / Pages payload normalization."""

    def normalize_payload(self, raw_data: dict[str, Any]) -> RawLead:
        page_id = raw_data.get("id") or raw_data.get("page_id")
        return RawLead(
            source_name="facebook",
            source_record_id=str(page_id) if page_id else None,
            business_name=raw_data.get("name", "").strip(),
            industry=raw_data.get("category", "General"),
            city=raw_data.get("location", {}).get("city")
            if isinstance(raw_data.get("location"), dict)
            else None,
            website=raw_data.get("website"),
            phone=raw_data.get("phone"),
            email=raw_data.get("emails", [None])[0]
            if isinstance(raw_data.get("emails"), list) and raw_data.get("emails")
            else raw_data.get("email"),
            social_handles={"facebook": raw_data.get("link", "")},
            raw_payload=raw_data,
        )


class LinkedInAdapter(BaseSourceAdapter):
    """Source adapter for LinkedIn Company Pages payload normalization."""

    def normalize_payload(self, raw_data: dict[str, Any]) -> RawLead:
        company_id = raw_data.get("id") or raw_data.get("vanity_name")
        return RawLead(
            source_name="linkedin",
            source_record_id=str(company_id) if company_id else None,
            business_name=raw_data.get("name", "").strip(),
            industry=raw_data.get("industry", "General"),
            city=raw_data.get("locations", [{}])[0].get("city")
            if isinstance(raw_data.get("locations"), list) and raw_data.get("locations")
            else None,
            website=raw_data.get("website"),
            social_handles={"linkedin": raw_data.get("vanity_name", "")},
            raw_payload=raw_data,
        )


class InstagramAdapter(BaseSourceAdapter):
    """Source adapter for Instagram Business Profiles payload normalization."""

    def normalize_payload(self, raw_data: dict[str, Any]) -> RawLead:
        ig_id = raw_data.get("id") or raw_data.get("username")
        return RawLead(
            source_name="instagram",
            source_record_id=str(ig_id) if ig_id else None,
            business_name=raw_data.get("name") or raw_data.get("username", "").strip(),
            industry=raw_data.get("category_name", "General"),
            website=raw_data.get("website"),
            email=raw_data.get("business_email"),
            phone=raw_data.get("business_phone_number"),
            social_handles={"instagram": raw_data.get("username", "")},
            raw_payload=raw_data,
        )


class DirectoryAdapter(BaseSourceAdapter):
    """Source adapter for general web directory payload normalization."""

    def normalize_payload(self, raw_data: dict[str, Any]) -> RawLead:
        return RawLead(
            source_name=raw_data.get("source_name", "directory"),
            source_record_id=raw_data.get("id"),
            business_name=raw_data.get("business_name", raw_data.get("name", "")).strip(),
            industry=raw_data.get("industry", "General"),
            address=raw_data.get("address"),
            city=raw_data.get("city"),
            state=raw_data.get("state"),
            website=raw_data.get("website"),
            email=raw_data.get("email"),
            phone=raw_data.get("formatted_phone_number") or raw_data.get("phone"),
            raw_payload=raw_data,
        )


class OSMOverpassAdapter(BaseSourceAdapter):
    """Source adapter for OpenStreetMap Overpass payload normalization."""

    def normalize_payload(self, raw_data: dict[str, Any]) -> RawLead:
        tags = raw_data.get("tags") or {}
        street = tags.get("addr:street")
        housenumber = tags.get("addr:housenumber")
        address_parts = [p for p in [housenumber, street] if p]
        address = " ".join(address_parts) if address_parts else None

        socials = {}
        for plat in ["facebook", "instagram", "twitter", "linkedin"]:
            val = tags.get(plat) or tags.get(f"contact:{plat}")
            if val:
                socials[plat] = val

        return RawLead(
            source_name="osm_overpass",
            source_record_id=str(raw_data.get("id")) if raw_data.get("id") else None,
            business_name=(tags.get("name") or tags.get("brand") or "Unknown Business").strip(),
            industry=tags.get("amenity") or tags.get("shop") or tags.get("tourism") or tags.get("craft") or "General",
            address=address,
            city=tags.get("addr:city"),
            state=tags.get("addr:state"),
            country=tags.get("addr:country") or "United Kingdom",
            website=tags.get("website") or tags.get("contact:website") or tags.get("url"),
            email=tags.get("email") or tags.get("contact:email"),
            phone=tags.get("phone") or tags.get("contact:phone"),
            social_handles=socials,
            raw_payload=raw_data,
        )
