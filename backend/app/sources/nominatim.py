from backend.app.sources.base import SourceConnector, NormalizedLeadRecord
import httpx
import logging
from typing import Any

logger = logging.getLogger(__name__)

class NominatimConnector(SourceConnector):
    @property
    def source_name(self) -> str:
        return "nominatim"

    def search_leads(self, query: str, location: str | None = None, limit: int = 100, page: int = 1, pagination_state: dict[str, Any] | None = None) -> list[NormalizedLeadRecord]:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "LeadIntelligencePlatform/1.0 (info@leadsplatform.com)"}
        search_query = f"{query} in {location}" if location else query
        params = {"q": search_query, "format": "json", "limit": min(limit, 50), "addressdetails": 1, "extratags": 1}
        
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                records = []
                for item in data:
                    name = item.get("name") or item.get("display_name", "").split(",")[0]
                    if not name:
                        continue
                        
                    address_parts = item.get("address", {})
                    city = address_parts.get("city") or address_parts.get("town") or address_parts.get("village")
                    
                    phone = item.get("extratags", {}).get("phone") or item.get("extratags", {}).get("contact:phone")
                    website = item.get("extratags", {}).get("website") or item.get("extratags", {}).get("contact:website")
                    
                    records.append(NormalizedLeadRecord(
                        source=self.source_name,
                        source_id=str(item.get("place_id")),
                        business_name=name,
                        website=website,
                        phone=phone,
                        address=item.get("display_name"),
                        category=item.get("class"),
                        raw_data=item
                    ))
                self.record_success()
                return records
        except Exception as e:
            self.record_failure()
            logger.error(f"Nominatim error: {e}")
            return []

    def health_check(self) -> bool:
        return True
