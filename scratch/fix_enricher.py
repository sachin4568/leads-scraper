with open('backend/app/enrichment/raw_lead_enricher.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('''        # Fix workspace_id
        from backend.app.models import RawLeadSheet, ScrapeJob
        sheet = self.db.scalar(select(RawLeadSheet).where(RawLeadSheet.id == raw_lead.sheet_id))
        if sheet:
            job = self.db.scalar(select(ScrapeJob).where(ScrapeJob.id == sheet.job_id))
            if job:
                ev.workspace_id = job.workspace_id''', '''        # Fix workspace_id
        from backend.app.models import RawLeadSheet
        sheet = self.db.scalar(select(RawLeadSheet).where(RawLeadSheet.id == raw_lead.sheet_id))
        if sheet:
            ev.workspace_id = sheet.workspace_id''')

with open('backend/app/enrichment/raw_lead_enricher.py', 'w', encoding='utf-8') as f:
    f.write(text)
