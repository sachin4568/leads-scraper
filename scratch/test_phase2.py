import requests
import time

url = "http://localhost:8000/api/v1/scrape-jobs"
payload = {
    "niche": "Medspa",
    "city": "Fairbanks",
    "region": "Alaska",
    "country": "United States",
    "target_lead_count": 5,
    "service": "website_dev"
}
print("Starting POST request for Medspa website_dev...")
response = requests.post(url, json=payload)
job_data = response.json()
job_id = job_data['id']
print(f"Job ID: {job_id}")

while True:
    res = requests.get(f"http://localhost:8000/api/v1/scraping/jobs/{job_id}")
    prog = res.json()
    print(f"Status: {prog['status']} | Scraped: {prog.get('leads_scraped', 0)} / {prog['requested']} | Valid: {prog['valid']} | Failed: {prog['failed']}")
    
    enrich = requests.get(f"http://localhost:8000/api/v1/scrape-jobs/{job_id}/enrichment-status")
    if enrich.status_code == 200:
        print(f"Enrichment -> {enrich.json()}")
    else:
        pass # print(f"Enrichment status {enrich.status_code}")

    if prog['status'] in ['COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED']:
        print("Scrape finished!")
        break
    time.sleep(2)

print("\n--- RESULTS ---")
from backend.app.database import SessionLocal
from backend.app.models import RawLeadSheet, RawLead, ServiceOpportunity, EvidenceRecord
from sqlalchemy import select

with SessionLocal() as db:
    sheet = db.scalar(select(RawLeadSheet).where(RawLeadSheet.job_id == job_id))
    if sheet:
        leads = db.scalars(select(RawLead).where(RawLead.sheet_id == sheet.id)).all()
        for l in leads:
            print(f"Lead: {l.business_name} (Email: {l.email})")
            opps = db.scalars(select(ServiceOpportunity).where(ServiceOpportunity.raw_lead_id == l.id)).all()
            for o in opps:
                print(f"  Opportunity: {o.service} - {o.status} ({o.opportunity_score}) - {o.reasons}")
                print(f"  Signals: {o.signals}")
            
            evs = db.scalars(select(EvidenceRecord).where(EvidenceRecord.raw_lead_id == l.id)).all()
            for e in evs:
                print(f"  Evidence: {e.field_name} - {e.status} - {e.details}")
    else:
        print("No sheet found!")
