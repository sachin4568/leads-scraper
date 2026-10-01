with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('                with SessionLocal() as db:\n                # Immediately persist', 
'                with SessionLocal() as db:\n                    # Immediately persist')
text = text.replace('                import backend.app.models as app_models\n                raw_sheet = db.get', 
'                    import backend.app.models as app_models\n                    raw_sheet = db.get')
text = text.replace('                if raw_sheet:\n                    raw_sheet.leads_scraped', 
'                    if raw_sheet:\n                        raw_sheet.leads_scraped')
# Wait, this is getting crazy, I'll just restore from orchestrator_copy.py and use a simple AST-based script or simply add a db to __init__!
