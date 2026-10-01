from typing import Dict, Any, List, Optional
from datetime import datetime, UTC
from backend.app.enrichment.scoring_config import derive_priority

class OpportunityEngine:
    @staticmethod
    def evaluate_all(lead: Any, evidence_records: List[Any]) -> List[Dict[str, Any]]:
        """
        Evaluates a RawLead independently across all 4 services using Phase 2-5 evidence.
        Returns a list of 4 dictionary payloads matching the ServiceOpportunity model.
        """
        ev_map = {}
        for ev in evidence_records:
            if ev.evidence_type:
                ev_map.setdefault(ev.evidence_type, []).append(ev)
            if ev.field_name:
                ev_map.setdefault(ev.field_name, []).append(ev)

        website_ev = (ev_map.get("WEBSITE") or ev_map.get("website") or [None])[0]
        email_evs = ev_map.get("EMAIL_DISCOVERY") or ev_map.get("email") or []
        social_evs = ev_map.get("SOCIAL_PROFILE") or []
        seo_ev = (ev_map.get("SEO_AUDIT") or ev_map.get("seo") or [None])[0]

        results = []
        results.append(OpportunityEngine.evaluate_website_dev(lead, website_ev, email_evs, social_evs))
        results.append(OpportunityEngine.evaluate_website_seo(lead, website_ev, seo_ev))
        results.append(OpportunityEngine.evaluate_social_management(lead, social_evs))
        results.append(OpportunityEngine.evaluate_social_marketing(lead, website_ev, social_evs))
        
        return results

    @staticmethod
    def evaluate_website_dev(lead: Any, website_ev: Optional[Any], email_evs: List[Any], social_evs: List[Any]) -> Dict[str, Any]:
        service = "website_dev"
        reasons = []
        signals = {}
        missing_data = []

        has_email = len(email_evs) > 0 or bool(lead.email)
        has_phone = bool(lead.phone)
        has_social = len(social_evs) > 0
        
        signals["has_business_email"] = has_email
        signals["has_phone"] = has_phone
        signals["has_social_presence"] = has_social

        if website_ev:
            web_class = website_ev.classification or ""
            web_status = website_ev.status or ""
            signals["website_classification"] = web_class
            
            if web_class == "NO_WEBSITE" or web_status == "NO_WEBSITE":
                opp = 90
                conf = 90 if (has_email or has_phone) else 65
                reasons.append("No verified business website was found")
                if has_email:
                    reasons.append("Public business email is available for outreach")
            elif web_class in ("BROKEN", "UNREACHABLE") or web_status in ("BROKEN", "UNREACHABLE"):
                opp = 85
                conf = 85
                reasons.append("Existing business website is broken or unreachable")
            elif web_class in ("VERIFIED_BUSINESS_WEBSITE", "LIKELY_BUSINESS_WEBSITE"):
                opp = 30
                conf = 95
                reasons.append("Verified modern business website exists")
            else:
                opp = 60
                conf = 50
                reasons.append("Business website status is unverified")
        else:
            if lead.website:
                opp = 65
                conf = 50
                signals["website_classification"] = "UNVERIFIED"
                reasons.append("Unverified website link provided")
            else:
                opp = 90
                conf = 85 if (has_email or has_phone) else 60
                signals["website_classification"] = "NO_WEBSITE"
                reasons.append("No business website is associated with this lead")

        priority = derive_priority(opp, conf)
        
        return {
            "service": service,
            "status": "EVALUATED",
            "opportunity_score": opp,
            "confidence_score": conf,
            "priority": priority,
            "reasons": reasons,
            "signals": signals,
            "missing_data": missing_data,
            "evaluated_at": datetime.now(UTC)
        }

    @staticmethod
    def evaluate_website_seo(lead: Any, website_ev: Optional[Any], seo_ev: Optional[Any]) -> Dict[str, Any]:
        service = "website_seo"
        reasons = []
        signals = {"ranking_data": "UNKNOWN"} # Explicit: No fake ranking logic!
        missing_data = []

        has_verified_web = False
        if website_ev and website_ev.classification in ("VERIFIED_BUSINESS_WEBSITE", "LIKELY_BUSINESS_WEBSITE"):
            has_verified_web = True
        elif lead.website:
            has_verified_web = True

        if not has_verified_web:
            missing_data.append("verified_website")
            reasons.append("Requires a verified website to perform an SEO evaluation")
            return {
                "service": service,
                "status": "INSUFFICIENT_DATA",
                "opportunity_score": 0,
                "confidence_score": 0,
                "priority": "UNKNOWN",
                "reasons": reasons,
                "signals": signals,
                "missing_data": missing_data,
                "evaluated_at": datetime.now(UTC)
            }

        reasons.append("Verified business website is available for SEO evaluation")
        signals["website_verified"] = True
        
        opp = 40
        conf = 70
        
        if seo_ev and seo_ev.details and "findings" in seo_ev.details:
            findings = seo_ev.details["findings"]
            
            has_title = findings.get("has_title", False)
            has_meta_desc = findings.get("has_meta_description", False)
            h1_count = findings.get("h1_count", 0)
            has_canonical = findings.get("has_canonical", False)
            has_viewport = findings.get("has_viewport_tag", False)
            has_schema = findings.get("has_jsonld_schema", False)
            has_og = findings.get("has_opengraph", False)
            
            signals.update({
                "title_present": has_title,
                "meta_description_present": has_meta_desc,
                "h1_count": h1_count,
                "canonical_present": has_canonical,
                "viewport_present": has_viewport,
                "schema_present": has_schema,
                "opengraph_present": has_og
            })

            issues_count = 0
            if not has_meta_desc:
                issues_count += 1
                reasons.append("Meta description is missing")
            if not has_title or findings.get("title_length", 0) < 10:
                issues_count += 1
                reasons.append("Meta title is missing or insufficient")
            if h1_count == 0:
                issues_count += 1
                reasons.append("H1 heading tag is missing")
            elif h1_count > 1:
                issues_count += 1
                reasons.append("Multiple H1 tags detected")
            if not has_viewport:
                issues_count += 1
                reasons.append("Mobile viewport meta tag is missing")
            if not has_schema:
                issues_count += 1
                reasons.append("Structured data (Schema.org) was not detected")

            opp = min(95, 30 + (issues_count * 12))
            conf = 90
        else:
            missing_data.append("seo_audit_details")
            reasons.append("SEO technical details are incomplete or unavailable")
            conf = 50

        priority = derive_priority(opp, conf)

        return {
            "service": service,
            "status": "EVALUATED",
            "opportunity_score": opp,
            "confidence_score": conf,
            "priority": priority,
            "reasons": reasons,
            "signals": signals,
            "missing_data": missing_data,
            "evaluated_at": datetime.now(UTC)
        }

    @staticmethod
    def evaluate_social_management(lead: Any, social_evs: List[Any]) -> Dict[str, Any]:
        """
        EVALUATION GATES FOR SOCIAL MEDIA MANAGEMENT:
        1. Social presence alone is NOT proof of management opportunity.
        2. If profiles unavailable or activity/posting metrics missing:
           status = INSUFFICIENT_DATA, priority = UNKNOWN, opp_score = 0.
        3. High/Medium opportunity requires observable management gaps (e.g., weak/inconsistent posting).
        """
        service = "social_media_management"
        reasons = []
        signals = {}
        missing_data = []

        if not social_evs:
            missing_data.append("social_profiles")
            reasons.append("No social media profiles observed")
            return {
                "service": service,
                "status": "INSUFFICIENT_DATA",
                "opportunity_score": 0,
                "confidence_score": 20,
                "priority": "UNKNOWN",
                "reasons": reasons,
                "signals": signals,
                "missing_data": missing_data,
                "evaluated_at": datetime.now(UTC)
            }

        unavail_count = 0
        observed_gap = False
        observed_active = False
        has_activity_data = False

        for ev in social_evs:
            plat = ev.field_name or "social"
            st = ev.status or "UNKNOWN"
            cl = ev.classification or "UNKNOWN"
            details = ev.details or {}
            
            if st == "UNAVAILABLE" or cl == "UNAVAILABLE":
                unavail_count += 1
                signals[f"{plat}_status"] = "UNAVAILABLE"
            else:
                signals[f"{plat}_status"] = st
                
                # Check for explicit activity/posting metrics
                act_status = details.get("activity_status")
                post_freq = details.get("posting_frequency")
                
                if act_status == "OBSERVED" or post_freq:
                    has_activity_data = True
                    if post_freq == "WEAK" or act_status == "INACTIVE":
                        observed_gap = True
                    elif post_freq == "ACTIVE" or act_status == "ACTIVE":
                        observed_active = True

        if unavail_count == len(social_evs):
            missing_data.append("social_profile_access")
            reasons.append("Social media platform access was blocked or unavailable")
            return {
                "service": service,
                "status": "INSUFFICIENT_DATA",
                "opportunity_score": 0,
                "confidence_score": 25,
                "priority": "UNKNOWN",
                "reasons": reasons,
                "signals": signals,
                "missing_data": missing_data,
                "evaluated_at": datetime.now(UTC)
            }

        # Profile exists, but activity/posting/engagement metrics are unavailable
        if not has_activity_data:
            missing_data.append("social_activity_metrics")
            reasons.append("Social media profiles observed, but posting activity and engagement metrics were unavailable")
            return {
                "service": service,
                "status": "INSUFFICIENT_DATA",
                "opportunity_score": 0,
                "confidence_score": 40,
                "priority": "UNKNOWN",
                "reasons": reasons,
                "signals": signals,
                "missing_data": missing_data,
                "evaluated_at": datetime.now(UTC)
            }

        # Activity evidence IS available
        if observed_gap:
            opp = 80
            conf = 85
            reasons.append("Observed weak or inconsistent social posting activity")
        elif observed_active:
            opp = 25
            conf = 90
            reasons.append("Observed consistent and active social posting schedule")
        else:
            opp = 50
            conf = 70
            reasons.append("Social media activity evaluated")

        priority = derive_priority(opp, conf)

        return {
            "service": service,
            "status": "EVALUATED",
            "opportunity_score": opp,
            "confidence_score": conf,
            "priority": priority,
            "reasons": reasons,
            "signals": signals,
            "missing_data": missing_data,
            "evaluated_at": datetime.now(UTC)
        }

    @staticmethod
    def evaluate_social_marketing(lead: Any, website_ev: Optional[Any], social_evs: List[Any]) -> Dict[str, Any]:
        """
        EVALUATION GATES FOR SOCIAL MEDIA MARKETING:
        1. Social profile presence alone is NOT proof of marketing opportunity.
        2. Ads NOT_OBSERVED remains neutral (0 score impact).
        3. If audience/engagement/marketing evidence is unavailable:
           status = INSUFFICIENT_DATA, priority = UNKNOWN, opp_score = 0.
        """
        service = "social_media_marketing"
        reasons = []
        signals = {
            "ads_status": "NOT_OBSERVED" # Explicit: NOT_OBSERVED is neutral!
        }
        missing_data = []

        valid_socials = [ev for ev in social_evs if ev.status not in ("UNAVAILABLE", "NOT_FOUND") and ev.classification not in ("UNAVAILABLE", "NOT_FOUND")]
        has_web = bool(website_ev) or bool(lead.website)

        signals["has_social_presence"] = len(valid_socials) > 0
        signals["has_destination_website"] = has_web

        # Evidence Gate: Require observed audience or marketing signals to evaluate growth opportunity
        has_marketing_evidence = False
        observed_audience_gap = False
        
        for ev in valid_socials:
            details = ev.details or {}
            followers = details.get("followers")
            followers_st = details.get("followers_status")
            mkt_signals = details.get("marketing_signals")
            
            if followers_st == "OBSERVED" or followers is not None or mkt_signals:
                has_marketing_evidence = True
                if followers is not None and followers < 1000:
                    observed_audience_gap = True

        if not has_marketing_evidence:
            missing_data.append("marketing_evidence")
            reasons.append("Insufficient social audience and marketing evidence to evaluate growth marketing need")
            return {
                "service": service,
                "status": "INSUFFICIENT_DATA",
                "opportunity_score": 0,
                "confidence_score": 20,
                "priority": "UNKNOWN",
                "reasons": reasons,
                "signals": signals,
                "missing_data": missing_data,
                "evaluated_at": datetime.now(UTC)
            }

        reasons.append("Social marketing evidence observed")
        reasons.append("Advertising data was not observed in public evidence (neutral)")
        
        if observed_audience_gap and has_web:
            opp = 75
            conf = 85
            reasons.append("Verified destination website exists with low social audience reach")
        else:
            opp = 35
            conf = 80
            reasons.append("Social audience and marketing signals evaluated")

        priority = derive_priority(opp, conf)

        return {
            "service": service,
            "status": "EVALUATED",
            "opportunity_score": opp,
            "confidence_score": conf,
            "priority": priority,
            "reasons": reasons,
            "signals": signals,
            "missing_data": missing_data,
            "evaluated_at": datetime.now(UTC)
        }
