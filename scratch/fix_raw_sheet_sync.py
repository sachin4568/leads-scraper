# Patch discovery_orchestrator.py to ensure raw_sheet exists
with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_stage1_sheet = """                    raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
                    if raw_sheet:
                        raw_sheet.leads_scraped = len(viable_candidates)
                        raw_sheet.discovered_count = self.metrics.fetched_count
                        raw_sheet.valid_count = len(viable_candidates)
                        raw_sheet.progress_percent = self.job_state["progress_percent"]
                        raw_sheet.current_source = self.job_state["current_source"]

                    # Check for duplicate RawLead"""

new_stage1_sheet = """                    raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
                    if not raw_sheet:
                        from backend.app.models import get_next_raw_sheet_number
                        raw_sheet = app_models.RawLeadSheet(
                            id=self.job_state["id"],
                            workspace_id=self.job_state["workspace_id"],
                            sheet_number=get_next_raw_sheet_number(db),
                            name=f"{self.job_state.get('niche') or 'Leads'} - {self.job_state.get('state') or 'Area'}",
                            niche=self.job_state.get("niche") or "General",
                            country=self.job_state.get("country"),
                            region=self.job_state.get("region"),
                            state=self.job_state.get("state"),
                            target_lead_count=self.metrics.requested,
                            service=self.job_state.get("service"),
                            status="RUNNING",
                            sources=self.job_state.get("sources"),
                            enrichments=self.job_state.get("enrichments"),
                            leads_scraped=len(viable_candidates),
                            discovered_count=self.metrics.fetched_count,
                            valid_count=len(viable_candidates),
                            progress_percent=self.job_state["progress_percent"],
                            current_source=self.job_state["current_source"],
                        )
                        db.add(raw_sheet)
                        db.flush()
                    else:
                        raw_sheet.leads_scraped = len(viable_candidates)
                        raw_sheet.discovered_count = self.metrics.fetched_count
                        raw_sheet.valid_count = len(viable_candidates)
                        raw_sheet.progress_percent = self.job_state["progress_percent"]
                        raw_sheet.current_source = self.job_state["current_source"]

                    # Check for duplicate RawLead"""

content = content.replace(old_stage1_sheet, new_stage1_sheet)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("discovery_orchestrator.py updated with auto-creation of RawLeadSheet!")

# Also patch backend/app/api.py in create_scrape_job
with open('backend/app/api.py', 'r', encoding='utf-8') as f:
    api_content = f.read()

old_api_job = """    job = ScrapeJob(workspace_id=workspace_id, **job_data)
    db.add(job)
    db.commit()
    db.refresh(job)"""

new_api_job = """    from backend.app.models import RawLeadSheet, get_next_raw_sheet_number
    job = ScrapeJob(workspace_id=workspace_id, **job_data)
    db.add(job)
    db.flush()

    raw_sheet = RawLeadSheet(
        id=job.id,
        workspace_id=workspace_id,
        sheet_number=get_next_raw_sheet_number(db),
        name=f"{job.niche} - {job.state or job.region or 'Leads'}",
        niche=job.niche,
        country=job.country,
        region=job.region,
        state=job.state,
        target_lead_count=job.target_lead_count,
        service=job.service,
        status="PENDING",
        sources=job.sources,
        enrichments=job.enrichments,
        leads_scraped=0,
        discovered_count=0,
        valid_count=0,
        progress_percent=0.0,
    )
    db.add(raw_sheet)
    db.commit()
    db.refresh(job)"""

api_content = api_content.replace(old_api_job, new_api_job)

with open('backend/app/api.py', 'w', encoding='utf-8') as f:
    f.write(api_content)

print("backend/app/api.py updated with RawLeadSheet creation in create_scrape_job!")
