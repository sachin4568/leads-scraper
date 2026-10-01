with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# find finalize_discovery
# we need to wrap the whole method with SessionLocal()
text = re.sub(
    r'def finalize_discovery\(self\) -> None:\s*"""Finalizes job status and assigns deterministic completion states\."""\s*if self._is_job_cancelled\(\):\s*return\s*# Double check actual persisted database count\s*with SessionLocal\(\) as db:',
    '''def finalize_discovery(self) -> None:
        """Finalizes job status and assigns deterministic completion states."""
        if self._is_job_cancelled():
            return

        # Double check actual persisted database count
        with SessionLocal() as db:''',
    text
)

text = text.replace(
'''        self.job_state["duplicate_count"] = self.metrics.duplicate_count
        self.job_state["fetched_count"] = self.job_state.get('fetched_count', 0) + self.metrics.fetched_count

        import backend.app.models as app_models
        raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])''',
'''        self.job_state["duplicate_count"] = self.metrics.duplicate_count
        self.job_state["fetched_count"] = self.job_state.get('fetched_count', 0) + self.metrics.fetched_count

        with SessionLocal() as db:
            import backend.app.models as app_models
            raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])'''
)

text = text.replace(
'''            if raw_sheet:
                raw_sheet.status = self.job_state["status"]
                raw_sheet.completion_reason = self.job_state["completion_reason"]
                raw_sheet.error_message = self.job_state["error_message"]
                raw_sheet.leads_scraped = self.job_state["leads_scraped"]
                raw_sheet.progress_percent = self.job_state["progress_percent"]
                raw_sheet.discovered_count = self.metrics.fetched_count
                raw_sheet.valid_count = self.metrics.validated_count
                raw_sheet.duplicate_count = self.metrics.duplicate_count
                raw_sheet.failed_count = self.metrics.rejected_count''',
'''            if raw_sheet:
                raw_sheet.status = self.job_state["status"]
                raw_sheet.completion_reason = self.job_state["completion_reason"]
                raw_sheet.error_message = self.job_state["error_message"]
                raw_sheet.leads_scraped = self.job_state["leads_scraped"]
                raw_sheet.progress_percent = self.job_state["progress_percent"]
                raw_sheet.discovered_count = self.metrics.fetched_count
                raw_sheet.valid_count = self.metrics.validated_count
                raw_sheet.duplicate_count = self.metrics.duplicate_count
                raw_sheet.failed_count = self.metrics.rejected_count
            
            job = db.get(app_models.ScrapeJob, self.job_state["id"])
            if job:
                job.status = self.job_state["status"]
                job.completion_reason = self.job_state["completion_reason"]
                job.error_message = self.job_state["error_message"]
                job.leads_scraped = self.job_state["leads_scraped"]
                job.progress_percent = self.job_state["progress_percent"]

            db.commit()'''
)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)
