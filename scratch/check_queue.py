from backend.app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
res = db.execute(text("SELECT count(*) FROM kombu_message"))
print(f"Messages in queue: {res.scalar()}")
