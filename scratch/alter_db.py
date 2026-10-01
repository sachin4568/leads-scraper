from backend.app.database import engine
from sqlalchemy import text

with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE evidence_records ADD COLUMN raw_lead_id UUID REFERENCES raw_leads(id) ON DELETE CASCADE;"))
        print("Altered evidence_records")
    except Exception as e:
        print(e)
        
    try:
        conn.execute(text("ALTER TABLE evidence_records ALTER COLUMN lead_id DROP NOT NULL;"))
        print("Altered evidence_records lead_id")
    except Exception as e:
        print(e)

    try:
        conn.execute(text("DROP TABLE IF EXISTS service_opportunities CASCADE;"))
        print("Dropped service_opportunities")
    except Exception as e:
        print(e)

