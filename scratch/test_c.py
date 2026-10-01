import requests
import time

url = "http://localhost:8000/api/v1/scrape-jobs"
payload = {
    "niche": "HVAC",
    "city": "Anchorage",
    "region": "Alaska",
    "country": "United States",
    "target_lead_count": 25,
    "service": "website_dev"
}
print("Starting POST request for Cancellation test...")
response = requests.post(url, json=payload)
job_data = response.json()
job_id = job_data['id']
print(f"Job ID: {job_id}")

loops = 0
while True:
    res = requests.get(f"http://localhost:8000/api/v1/scraping/jobs/{job_id}")
    prog = res.json()
    print(f"Status: {prog['status']} | Scraped: {prog['scraped_count'] if 'scraped_count' in prog else prog.get('leads_scraped', 0)} / {prog['requested']} | Valid: {prog['valid']} | Failed: {prog['failed']}")
    if prog['status'] in ['COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED']:
        print("Scrape finished!")
        break
    
    loops += 1
    if loops == 10:
        print("CANCELLING JOB...")
        cancel_res = requests.post(f"http://localhost:8000/api/v1/scrape-jobs/{job_id}/cancel")
        print(f"Cancel Response: {cancel_res.status_code}")
        
    time.sleep(1)
