import re
import os

filepath = 'backend/app/orchestration/discovery_orchestrator.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update `_upsert_evidence` to use its own db session
upsert_pattern = r'''    def _upsert_evidence\((.*?)\) -> None:\s+ev = self\.db\.scalar\((.*?)\)\s+if ev:\s+(.*?)\s+else:\s+ev = EvidenceRecord\((.*?)\)\s+self\.db\.add\(ev\)'''
new_upsert = '''    def _upsert_evidence(\\1) -> None:
        with SessionLocal() as db:
            ev = db.scalar(\\2)
            if ev:
                \\3
            else:
                ev = EvidenceRecord(\\4)
                db.add(ev)
            db.commit()'''
# Try to regex it, but it might be easier to replace the function entirely.
content = re.sub(
    r'    def _upsert_evidence\(.*?\) -> None:.*?self\.db\.add\(ev\)',
    '''    def _upsert_evidence(
        self,
        field_name: str,
        status: str,
        confidence_score: int,
        source: str,
        details: dict[str, Any] | None,
        lead_id: Any,
        canonical_lead_id: str | None,
    ) -> None:
        with SessionLocal() as db:
            ev = db.scalar(
                select(EvidenceRecord).where(
                    EvidenceRecord.lead_id == lead_id,
                    EvidenceRecord.field_name == field_name,
                )
            )
            if ev:
                ev.status = status
                ev.confidence_score = confidence_score
                ev.source = source
                ev.details = details
                ev.canonical_lead_id = canonical_lead_id
            else:
                ev = EvidenceRecord(
                    workspace_id=self.job_state["workspace_id"],
                    lead_id=lead_id,
                    canonical_lead_id=canonical_lead_id,
                    field_name=field_name,
                    status=status,
                    confidence_score=confidence_score,
                    source=source,
                    details=details,
                )
                db.add(ev)
            db.commit()''',
    content, flags=re.DOTALL
)

# 2. _build_initial_action_queue self.db replacements
content = content.replace('src_score = AdaptiveDiscoveryEngine.get_source_score(self.db, src)', 'with SessionLocal() as db:\n                src_score = AdaptiveDiscoveryEngine.get_source_score(db, src)')
content = content.replace('q_score = AdaptiveDiscoveryEngine.get_query_score(self.db, q_term)', 'with SessionLocal() as db:\n                        q_score = AdaptiveDiscoveryEngine.get_query_score(db, q_term)')

# 3. execute_discovery_action self.db replacements
content = content.replace('self.db.add(exec_log)\n            self.db.commit()', 'with SessionLocal() as db:\n                db.add(exec_log)\n                db.commit()')

# 4. Replace self.job... remaining ones
content = re.sub(r'self\.job\.current_source\s*=\s*(.*)', r'self._update_job_progress(current_source=\1)', content)
content = re.sub(r'self\.job\.current_query\s*=\s*(.*)', r'self._update_job_progress(current_query=\1)', content)
content = re.sub(r'self\.job\.progress_percent\s*=\s*(.*)', r'self.job_state["progress_percent"] = \1\n        self._update_job_progress()', content)
content = re.sub(r'self\.job\.([a-zA-Z0-9_]+)\s*=', r'self.job_state["\1"] =', content)

# 5. Remove self.db.commit() and publish_job_progress blocks in stages
content = re.sub(r'self\.db\.commit\(\)', '', content)
content = re.sub(r'publish_job_progress\(\s*str\(self\.job_state\["id"\]\).*?\}\s*,\s*\)', '', content, flags=re.DOTALL)
content = re.sub(r'publish_job_progress\(\s*str\(self\.job\.id\).*?\}\s*,\s*\)', '', content, flags=re.DOTALL)

# 6. stage_1_discover_viable_candidates raw_sheet block
raw_sheet_pattern = r'import backend\.app\.models as app_models\s+raw_sheet = self\.db\.get\(app_models\.RawLeadSheet, self\.job_state\["id"\]\).*?self\.db\.add\(r_lead\)'
new_raw_sheet = '''with SessionLocal() as db:
                    import backend.app.models as app_models
                    raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
                    if raw_sheet:
                        raw_sheet.leads_scraped = len(viable_candidates)
                        raw_sheet.discovered_count = self.metrics.fetched_count
                        raw_sheet.valid_count = len(viable_candidates)
                        raw_sheet.progress_percent = self.job_state["progress_percent"]
                        raw_sheet.current_source = self.job_state.get("current_source")

                        existing_raw_lead = db.scalar(
                            select(app_models.RawLead).where(
                                app_models.RawLead.sheet_id == self.job_state["id"],
                                app_models.RawLead.business_name == rec.business_name,
                            )
                        )
                        if not existing_raw_lead:
                            r_lead = app_models.RawLead(
                                id=uuid.uuid4(),
                                sheet_id=self.job_state["id"],
                                lead_number=len(viable_candidates),
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
                    db.commit()'''
content = re.sub(raw_sheet_pattern, new_raw_sheet, content, flags=re.DOTALL)

# 7. finalize_discovery
finalize_pattern = r'def finalize_discovery\(self\) -> None:.*?self\.db\.commit\(\)'
new_finalize = '''def finalize_discovery(self) -> None:
        with SessionLocal() as db:
            from backend.app.models import ScrapeJob, RawLeadSheet
            job = db.scalar(select(ScrapeJob).where(ScrapeJob.id == self.job_id))
            if job and job.status not in ("CANCELLED", "STOPPED_SAVED"):
                job.status = "COMPLETED"
                job.progress_percent = 100.0
                job.current_source = "Completed"
                
                raw_sheet = db.get(RawLeadSheet, job.id)
                if raw_sheet:
                    raw_sheet.progress_percent = 100.0
                    raw_sheet.current_source = "Completed"
                    
                db.commit()
                
                publish_job_progress(
                    str(job.id),
                    {
                        "event_type": "JOB_COMPLETED",
                        "job_id": str(job.id),
                        "status": job.status,
                        "leads_scraped": job.leads_scraped,
                        "target_lead_count": job.target_lead_count,
                        "progress_percent": 100.0,
                    }
                )'''
content = re.sub(r'def finalize_discovery\(self\) -> None:.*?(?=def |$)', new_finalize + '\n\n    ', content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
