import asyncio
import uuid
import sys
import time
import os
from unittest.mock import patch

from backend.app.database import SessionLocal
from backend.app.models import ScrapeJob, Workspace
from backend.app.worker import process_scrape_job_task
import logging

logging.basicConfig(level=logging.INFO)

def run_test():
    with SessionLocal() as db:
        ws = db.query(Workspace).first()
        if not ws:
            ws = Workspace(name='E2E Test Workspace')
            db.add(ws)
            db.commit()
            
        job = ScrapeJob(
            workspace_id=ws.id,
            niche='Plumbers',
            country='United Kingdom',
            region='England',
            state='Manchester',
            sources=['google_maps', 'osm_overpass'],
            target_lead_count=5,
            status='PENDING'
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id_str = str(job.id)

    print(f'Starting test with Job ID: {job_id_str}')
    
    with patch("backend.app.worker_concurrency.workspace_concurrency_guard") as mock_guard, \
         patch("backend.app.websockets.publish_job_progress"):
        mock_guard.return_value.__enter__.return_value = None
        
        # Run synchronously
        process_scrape_job_task(job_id_str)
    
    with SessionLocal() as db:
        job = db.query(ScrapeJob).get(uuid.UUID(job_id_str))
        print('--- RESULTS ---')
        print(f'Target: {job.target_lead_count}')
        print(f'Fetched: {getattr(job, "fetched_count", 0)}')
        print(f'Discovered: {job.discovered_count}')
        print(f'Valid: {job.valid_count}')
        print(f'New: {job.new_count}')
        print(f'Duplicate: {job.duplicate_count}')
        print(f'Final Status: {job.status}')
        print(f'Completion Reason: {job.completion_reason}')
        print(f'Leads Scraped: {job.leads_scraped}')
        print(f'Error Message: {job.error_message}')

if __name__ == '__main__':
    run_test()
