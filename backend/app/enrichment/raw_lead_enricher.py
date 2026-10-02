from sqlalchemy.orm import Session
import uuid
import logging
from datetime import datetime, UTC
from sqlalchemy.dialects.postgresql import insert
import urllib.parse
from sqlalchemy import select

from backend.app.models import RawLead, EvidenceRecord, ServiceOpportunity
from backend.app.enrichment.website_enricher import ProductionWebsiteEnricher, ExtractedContacts
from backend.app.enrichment.email_verifier import EmailVerifier

logger = logging.getLogger(__name__)

class RawLeadEnricher:
    def __init__(self, db: Session):
        self.db = db
        self.website_enricher = ProductionWebsiteEnricher()
        self.email_verifier = EmailVerifier()

    def enrich_raw_lead(self, raw_lead_id: uuid.UUID, service: str) -> None:
        raw_lead = self.db.scalar(select(RawLead).where(RawLead.id == raw_lead_id))
        if not raw_lead:
            logger.warning(f"RawLead {raw_lead_id} not found for enrichment.")
            return

        signals = {}
        missing = []
        reasons = []

        # Determine website URL
        website_url = str(raw_lead.website or "")
        domain_match_base = ""

        if website_url:
            signals["website_exists"] = True
            parsed = urllib.parse.urlparse(website_url if '://' in website_url else f"http://{website_url}")
            domain_match_base = (parsed.netloc or "").replace("www.", "")

            # 1. Fetch & Enrich Website
            enrichment_res = self.website_enricher.enrich_website(website_url)
            if enrichment_res.health.is_reachable:
                signals["website_status"] = "WORKING"
            else:
                signals["website_status"] = "BROKEN"

            self._record_evidence(raw_lead, "website", "WORKING" if enrichment_res.health.is_reachable else "BROKEN", 
                                  "website_enricher", {"url": website_url, "status_code": enrichment_res.health.http_status})
            
            # 2. Extract Emails
            emails_extracted = enrichment_res.contacts.emails
            emails_found = []
            
            if emails_extracted:
                for e_dict in emails_extracted:
                    raw_email = e_dict["email"].lower().strip()
                    if raw_email not in emails_found:
                        emails_found.append(raw_email)
                        
                        # Verify
                        ver_result = self.email_verifier.verify(raw_email, website=website_url)
                        
                        domain_match = False
                        if domain_match_base and domain_match_base in raw_email:
                            domain_match = True

                        email_type = "BUSINESS_EMAIL" if domain_match else (
                            "ROLE_EMAIL" if raw_email.split('@')[0] in ['info', 'sales', 'contact', 'admin'] else "PERSONAL_EMAIL"
                        )
                        
                        evidence_details = {
                            "email": raw_email,
                            "domain_match": domain_match,
                            "is_disposable": ver_result.is_disposable,
                            "email_type": email_type,
                            "source_page": e_dict.get("source_page")
                        }
                        
                        self._record_evidence(raw_lead, "email", "VERIFIED" if ver_result.is_valid else "INVALID", 
                                              "website_enricher", evidence_details)
                
                signals["emails_found"] = len(emails_found)
                signals["best_email"] = emails_found[0]
                raw_lead.email = emails_found[0]
                self.db.add(raw_lead)
                self.db.commit()
            else:
                signals["emails_found"] = 0
                missing.append("business_email")
                
            # Basic SEO mapping for Website SEO service
            if service == "website_seo":
                signals["missing_title"] = not bool(enrichment_res.seo.title)
                signals["missing_meta"] = not bool(enrichment_res.seo.meta_description)
                
        else:
            signals["website_exists"] = False
            signals["website_status"] = "NO_WEBSITE"
            signals["emails_found"] = 0
            missing.append("website")
            missing.append("business_email")

        # Opportunity evaluation
        opportunity_score = 0
        confidence = 50
        status = "INSUFFICIENT_DATA"
        priority = "LOW"

        if service == "website_dev":
            if not signals["website_exists"] or signals["website_status"] in ["BROKEN", "NO_WEBSITE"]:
                opportunity_score = 95
                status = "HIGH"
                priority = "HIGH"
                reasons.append("No active website detected.")
                confidence = 90
            else:
                opportunity_score = 10
                status = "LOW"
                reasons.append("Modern website appears to exist.")
                confidence = 80
        elif service == "website_seo":
            if not signals["website_exists"]:
                opportunity_score = 0
                status = "NOT_APPLICABLE"
                reasons.append("No website to optimize.")
                confidence = 100
            else:
                if signals.get("missing_title") or signals.get("missing_meta"):
                    opportunity_score = 80
                    status = "HIGH"
                    priority = "MEDIUM"
                    reasons.append("Missing crucial on-page SEO elements.")
                else:
                    opportunity_score = 40
                    status = "MEDIUM"
                    reasons.append("Website exists, deep SEO audit needed.")
                confidence = 75

        # Upsert Opportunity
        stmt = insert(ServiceOpportunity).values(
            id=uuid.uuid4(),
            raw_lead_id=raw_lead.id,
            service=service,
            status=status,
            opportunity_score=opportunity_score,
            confidence_score=confidence,
            priority=priority,
            reasons=reasons,
            signals=signals,
            missing_data=missing,
            evaluated_at=datetime.now(UTC)
        )
        
        stmt = stmt.on_conflict_do_update(
            index_elements=['raw_lead_id', 'service'],
            set_={
                'status': stmt.excluded.status,
                'opportunity_score': stmt.excluded.opportunity_score,
                'confidence_score': stmt.excluded.confidence_score,
                'priority': stmt.excluded.priority,
                'reasons': stmt.excluded.reasons,
                'signals': stmt.excluded.signals,
                'missing_data': stmt.excluded.missing_data,
                'evaluated_at': stmt.excluded.evaluated_at
            }
        )
        self.db.execute(stmt)
        self.db.commit()

    def _record_evidence(self, raw_lead, field_name: str, status: str, source: str, details: dict):
        ev = EvidenceRecord(
            workspace_id=raw_lead.sheet_id, # Using sheet_id for workspace context briefly if needed, actually it should be workspace_id, but raw_lead doesnt have workspace_id natively. Let's just lookup sheet -> job -> workspace
            # Wait, raw_lead -> sheet -> workspace
            raw_lead_id=raw_lead.id,
            field_name=field_name,
            status=status,
            source=source,
            details=details,
            confidence_score=90
        )
        # Fix workspace_id
        from backend.app.models import RawLeadSheet
        sheet = self.db.scalar(select(RawLeadSheet).where(RawLeadSheet.id == raw_lead.sheet_id))
        if sheet:
            ev.workspace_id = sheet.workspace_id
        
        self.db.add(ev)

