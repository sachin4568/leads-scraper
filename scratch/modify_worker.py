with open('backend/app/worker.py', 'r', encoding='utf-8') as f:
    text = f.read()

task_code = '''
@celery_app.task(name="backend.app.worker.enrich_raw_lead_task")
def enrich_raw_lead_task(raw_lead_id_str: str, service: str) -> None:
    """Asynchronous background task for executing Phase 2 enrichment on a RawLead."""
    import uuid
    from backend.app.database import SessionLocal
    from backend.app.enrichment.raw_lead_enricher import RawLeadEnricher

    raw_lead_id = uuid.UUID(raw_lead_id_str)
    with SessionLocal() as db:
        enricher = RawLeadEnricher(db)
        enricher.enrich_raw_lead(raw_lead_id, service)
'''

if "def enrich_raw_lead_task" not in text:
    text += task_code

with open('backend/app/worker.py', 'w', encoding='utf-8') as f:
    f.write(text)
