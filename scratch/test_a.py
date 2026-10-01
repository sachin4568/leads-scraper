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
print("Starting POST request...")
response = requests.post(url, json=payload)
print(f"Status Code: {response.status_code}")
job_data = response.json()
print(f"Response: {job_data}")
job_id = job_data['id']
print(f"Job ID: {job_id}")

while True:
    res = requests.get(f"http://localhost:8000/api/v1/scraping/jobs/{job_id}")
    prog = res.json()
    print(f"Status: {prog['status']} | Scraped: {prog['scraped_count'] if 'scraped_count' in prog else prog.get('leads_scraped', 0)} / {prog['requested']} | Valid: {prog['valid']} | Failed: {prog['failed']}")
    if prog['status'] in ['COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED']:
        print("Scrape finished!")
        break
    time.sleep(2)
