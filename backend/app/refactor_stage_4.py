import re

filepath = 'backend/app/orchestration/discovery_orchestrator.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the entire stage_4_persist_leads method
start_idx = content.find('    def stage_4_persist_leads(self, qualified_candidates: list[dict[str, Any]]) -> None:')
end_idx = content.find('    def _process_candidate_record', start_idx)

new_stage_4 = '''    def stage_4_persist_leads(self, qualified_candidates: list[dict[str, Any]]) -> None:
        """Stage 4: Canonical Identity Resolution, Evidence Persistence & Lead Creation."""
        total = len(qualified_candidates)
        target = self.metrics.requested

        self._update_job_progress(current_source=f"Stage 4/4: Finalizing & saving leads (0/{total})")

        import uuid
        from backend.app.models import Lead, SourceRecord, EvidenceRecord, RawLeadSheet, RawLead as DbRawLead
        
        with SessionLocal() as db:
            for idx, item in enumerate(qualified_candidates):
                if self._is_job_cancelled():
                    return

                rec = item["rec"]
                effective_website = item["effective_website"]
                effective_phone = item["effective_phone"]
                effective_email = item["effective_email"]
                v_res = item["v_res"]
                intel_report = item["intel_report"]
                gate_res = item["gate_res"]

                # Resolve accurate canonical location
                c_norm = LocationValidator.normalize_country(self.job_state["country"])
                loc_resolved = LocationValidator.resolve_candidate_location(
                    candidate_address=rec.address,
                    candidate_phone=effective_phone or rec.phone,
                    candidate_website=effective_website or rec.website,
                    candidate_coords=(float(rec.latitude), float(rec.longitude)) if rec.latitude is not None and rec.longitude is not None else None,
                    raw_place_data=rec.raw_data,
                    requested_country_code=c_norm[1] if c_norm else None,
                )

                final_country = loc_resolved.country if loc_resolved.country != "Unknown" else (self.job_state["country"] or "United Kingdom")
                final_region = loc_resolved.region or self.job_state["region"]
                final_city = loc_resolved.city or rec.city or (self.job_state["state"] if self.job_state["state"] != self.job_state["region"] else None)
                final_address = loc_resolved.formatted_address or rec.address

                raw_lead = RawLead(
                    source_name=rec.source,
                    source_record_id=rec.source_id,
                    business_name=rec.business_name,
                    industry=rec.category or self.job_state["niche"] or "General",
                    address=final_address,
                    city=final_city,
                    state=final_region,
                    country=final_country,
                    website=effective_website,
                    phone=effective_phone,
                    raw_payload=rec.raw_data or {},
                )

                lock_key = self._acquire_lock(rec.business_name, effective_phone, effective_website)
                canonical_lead = None
                try:
                    canonical_lead, obs, l_state = self.resolver.process_observation(db, raw_lead)
                    if canonical_lead and effective_website:
                        canonical_lead.canonical_domain = effective_website
                        canonical_lead.website_state = "VERIFIED"
                finally:
                    self._release_lock(lock_key)

                if l_state == LifecycleState.DUPLICATE:
                    self.metrics.duplicate_count += 1
                    continue

                # Persist Lead Entity
                persisted_lead = db.scalar(
                    select(Lead).where(
                        Lead.workspace_id == self.job_state["workspace_id"],
                        Lead.business_name == rec.business_name,
                        Lead.job_id == self.job_state["id"],
                    )
                )
                if not persisted_lead:
                    persisted_lead = Lead(
                        workspace_id=self.job_state["workspace_id"],
                        job_id=self.job_state["id"],
                        business_name=rec.business_name,
                        website=effective_website,
                        email=effective_email,
                        phone=effective_phone,
                        notes=final_address,
                        raw_status="PERSISTED",
                        verification_status="VERIFIED" if (gate_res.decision == QualityGateDecision.ACCEPT and v_res.decision == "ACCEPT") else "UNVERIFIED",
                        genuineness_score=v_res.composite_confidence,
                        workflow_status="NEW",
                    )
                    db.add(persisted_lead)
                    db.flush()
                else:
                    persisted_lead.website = effective_website
                    persisted_lead.email = effective_email
                    persisted_lead.phone = effective_phone
                    persisted_lead.verification_status = "VERIFIED" if (gate_res.decision == QualityGateDecision.ACCEPT and v_res.decision == "ACCEPT") else "UNVERIFIED"
                    persisted_lead.genuineness_score = v_res.composite_confidence

                # Link SourceRecord
                src_id = rec.source_id or rec.business_name
                src_rec = db.scalar(
                    select(SourceRecord).where(
                        SourceRecord.source == rec.source,
                        SourceRecord.source_id == src_id,
                    )
                )
                if not src_rec:
                    src_rec = SourceRecord(
                        workspace_id=self.job_state["workspace_id"],
                        lead_id=persisted_lead.id,
                        source=rec.source,
                        source_id=src_id,
                        raw_data=rec.raw_data or {},
                    )
                    db.add(src_rec)
                else:
                    src_rec.lead_id = persisted_lead.id
                    if rec.raw_data:
                        src_rec.raw_data = rec.raw_data

                # Upsert Evidence Records directly using db session instead of self._upsert_evidence 
                # (which uses its own short session and we want to batch this)
                for ev_rec in v_res.evidence_records:
                    ev = db.scalar(select(EvidenceRecord).where(EvidenceRecord.lead_id == persisted_lead.id, EvidenceRecord.field_name == ev_rec["field_name"]))
                    if ev:
                        ev.status = ev_rec["status"]
                        ev.confidence_score = ev_rec["confidence_score"]
                        ev.source = ev_rec["source"]
                        ev.details = ev_rec["details"]
                        ev.canonical_lead_id = str(canonical_lead.id) if canonical_lead else None
                    else:
                        db.add(EvidenceRecord(
                            workspace_id=self.job_state["workspace_id"],
                            lead_id=persisted_lead.id,
                            canonical_lead_id=str(canonical_lead.id) if canonical_lead else None,
                            field_name=ev_rec["field_name"],
                            status=ev_rec["status"],
                            confidence_score=ev_rec["confidence_score"],
                            source=ev_rec["source"],
                            details=ev_rec["details"],
                        ))

                # Lead Intelligence evidence
                ev = db.scalar(select(EvidenceRecord).where(EvidenceRecord.lead_id == persisted_lead.id, EvidenceRecord.field_name == "lead_intelligence"))
                if ev:
                    ev.status = intel_report.opportunity_category.value
                    ev.confidence_score = intel_report.overall_opportunity_score
                    ev.source = "LEAD_INTELLIGENCE_ENGINE"
                    ev.details = {
                        "overall_opportunity_score": intel_report.overall_opportunity_score,
                        "opportunity_category": intel_report.opportunity_category.value,
                        "confidence_score": intel_report.confidence_score,
                        "contactability_score": intel_report.contactability_score,
                        "top_reasons": intel_report.top_reasons,
                    }
                    ev.canonical_lead_id = str(canonical_lead.id) if canonical_lead else None
                else:
                    db.add(EvidenceRecord(
                        workspace_id=self.job_state["workspace_id"],
                        lead_id=persisted_lead.id,
                        canonical_lead_id=str(canonical_lead.id) if canonical_lead else None,
                        field_name="lead_intelligence",
                        status=intel_report.opportunity_category.value,
                        confidence_score=intel_report.overall_opportunity_score,
                        source="LEAD_INTELLIGENCE_ENGINE",
                        details={
                            "overall_opportunity_score": intel_report.overall_opportunity_score,
                            "opportunity_category": intel_report.opportunity_category.value,
                            "confidence_score": intel_report.confidence_score,
                            "contactability_score": intel_report.contactability_score,
                            "top_reasons": intel_report.top_reasons,
                        },
                    ))

                # Sync with dedicated RawLeadSheet & RawLead database tables
                raw_sheet = db.get(RawLeadSheet, self.job_state["id"])
                if raw_sheet:
                    raw_sheet.leads_scraped = self.metrics.saved_count + 1
                    raw_sheet.discovered_count = self.metrics.fetched_count
                    raw_sheet.valid_count = self.job_state["valid_count"]
                    raw_sheet.progress_percent = self.job_state["progress_percent"]
                    raw_sheet.current_source = self.job_state.get("current_source")

                    existing_raw_lead = db.scalar(
                        select(DbRawLead).where(
                            DbRawLead.sheet_id == self.job_state["id"],
                            DbRawLead.business_name == rec.business_name,
                        )
                    )
                    if not existing_raw_lead:
                        r_lead = DbRawLead(
                            id=uuid.uuid4(),
                            sheet_id=self.job_state["id"],
                            lead_number=self.metrics.saved_count + 1,
                            business_name=rec.business_name,
                            website=rec.website,
                            email=rec.email,
                            phone=rec.phone,
                            location=f"{rec.city or ''}, {rec.state or rec.country or ''}".strip(", "),
                            source=rec.source,
                            notes=rec.address,
                            raw_data=rec.raw_data or {},
                        )
                        db.add(r_lead)
                    else:
                        existing_raw_lead.website = effective_website
                        existing_raw_lead.email = effective_email
                        existing_raw_lead.phone = effective_phone

                self.metrics.saved_count += 1
                self.job_state["leads_scraped"] = self.metrics.saved_count
                self.job_state["progress_percent"] = 90.0 + min(10.0, round((self.metrics.saved_count / (total or 1)) * 10.0, 1))
                
                # Commit the current batch unit
                db.commit()
                
                # Update progress outside the transaction via orchestrator mechanism
                self._update_job_progress(current_source=f"Stage 4/4: Persisted {self.metrics.saved_count}/{total} leads ({rec.business_name[:25]})")

        logger.info(f"[DiscoveryOrchestrator] Stage 4 Completed: Persisted {self.metrics.saved_count} leads in database.")

'''

new_content = content[:start_idx] + new_stage_4 + content[end_idx:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)
