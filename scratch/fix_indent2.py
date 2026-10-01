import re

with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
'''                with SessionLocal() as db:
                # Immediately persist to RawLeadSheet & RawLead so UI displays leads in real time
                import backend.app.models as app_models
                raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
                if raw_sheet:
                    raw_sheet.leads_scraped = len(viable_candidates)
                    raw_sheet.discovered_count = self.metrics.fetched_count
                    raw_sheet.valid_count = len(viable_candidates)
                    raw_sheet.progress_percent = self.job_state["progress_percent"]
                    raw_sheet.current_source = self.job_state["current_source"]

                    existing_raw_lead = db.scalar(
                        select(app_models.RawLead).where(
                            app_models.RawLead.sheet_id == self.job_state["id"],
                            app_models.RawLead.business_name == rec.business_name,
                        )
                    )
                    if not existing_raw_lead:
                        r_lead = app_models.RawLead(
                            sheet_id=self.job_state["id"],
                            business_name=rec.business_name,
                            website=rec.website,
                            phone=rec.phone,
                            email=rec.email,
                            category=rec.category or self.job_state["niche"],
                            address=rec.address,
                            city=rec.city,
                            state=rec.state,
                            country=rec.country,
                            notes=rec.address,
                            raw_data=rec.raw_data or {},
                        )
                        db.add(r_lead)
                    db.commit()''',
'''                with SessionLocal() as db:
                    # Immediately persist to RawLeadSheet & RawLead so UI displays leads in real time
                    import backend.app.models as app_models
                    raw_sheet = db.get(app_models.RawLeadSheet, self.job_state["id"])
                    if raw_sheet:
                        raw_sheet.leads_scraped = len(viable_candidates)
                        raw_sheet.discovered_count = self.metrics.fetched_count
                        raw_sheet.valid_count = len(viable_candidates)
                        raw_sheet.progress_percent = self.job_state["progress_percent"]
                        raw_sheet.current_source = self.job_state["current_source"]

                        existing_raw_lead = db.scalar(
                            select(app_models.RawLead).where(
                                app_models.RawLead.sheet_id == self.job_state["id"],
                                app_models.RawLead.business_name == rec.business_name,
                            )
                        )
                        if not existing_raw_lead:
                            r_lead = app_models.RawLead(
                                sheet_id=self.job_state["id"],
                                business_name=rec.business_name,
                                website=rec.website,
                                phone=rec.phone,
                                email=rec.email,
                                category=rec.category or self.job_state["niche"],
                                address=rec.address,
                                city=rec.city,
                                state=rec.state,
                                country=rec.country,
                                notes=rec.address,
                                raw_data=rec.raw_data or {},
                            )
                            db.add(r_lead)
                        db.commit()'''
)

text = text.replace(
'''            with SessionLocal() as db:
            canonical_lead, obs, l_state = self.resolver.process_observation(db, raw_lead)''',
'''            with SessionLocal() as db:
                canonical_lead, obs, l_state = self.resolver.process_observation(db, raw_lead)'''
)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)
