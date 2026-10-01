import re

with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

trigger_code = '''
                    db.commit()
                    try:
                        from backend.app.worker import celery_app
                        if self.job_state.get("service"):
                            celery_app.send_task("backend.app.worker.enrich_raw_lead_task", args=[str(r_lead.id), self.job_state["service"]])
                    except Exception as e:
                        logger.error(f"Failed to queue enrichment: {e}")
'''
text = re.sub(r'db\.add\(r_lead\)\s+db\.commit\(\)', r'db.add(r_lead)' + trigger_code, text)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)
