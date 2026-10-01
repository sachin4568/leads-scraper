import asyncio
from backend.app.enrichment.website_pipeline import fetch_and_evaluate_website

def run_benchmark():
    test_cases = [
        {
            "name": "1. Genuine business with working website (Apple)",
            "url": "apple.com",
            "bname": "Apple Inc",
            "phone": "800-692-7753",
            "address": "One Apple Park Way Cupertino"
        },
        {
            "name": "2. Business with no website",
            "url": "",
            "bname": "Acme Corp",
            "phone": "555-0000",
            "address": "123 Main St"
        },
        {
            "name": "3. Business with poor/outdated website (neverssl.com)",
            "url": "neverssl.com",
            "bname": "Never SSL",
            "phone": "1234567890",
            "address": "internet"
        },
        {
            "name": "4. Broken website (httpstat.us/404)",
            "url": "httpstat.us/404",
            "bname": "Broken Co",
            "phone": "123",
            "address": "nowhere"
        },
        {
            "name": "5. Wrong/platform website candidate (google.com)",
            "url": "google.com",
            "bname": "Google",
            "phone": "123",
            "address": "mountain view"
        },
        {
            "name": "6. Website with ONLY name match (httpbin.org - mocked)",
            "url": "httpbin.org/html",
            "bname": "Herman Melville",  # httpbin/html contains Moby Dick extract
            "phone": "999-999-9999",     # Wrong phone
            "address": "Not in the book" # Wrong address
        },
        {
            "name": "7. Genuine business with redirect and full match (Microsoft)",
            "url": "microsoft.com",
            "bname": "Microsoft Corporation",
            "phone": "800-642-7676",
            "address": "One Microsoft Way Redmond"
        }
    ]

    for tc in test_cases:
        print(f"\\n--- {tc['name']} ---")
        try:
            cls, conf, details = fetch_and_evaluate_website(tc["url"], tc["bname"], tc["phone"], tc["address"])
            
            print(f"Business: {tc['bname']}")
            print(f"Candidate URL: {tc['url']}")
            print(f"Final URL: {details.get('final_url')}")
            print(f"HTTP result: {details.get('http_status')}")
            print(f"\\nIdentity:")
            sigs = details.get('identity_signals', {})
            print(f"Name match: {sigs.get('name_match')}")
            print(f"Phone match: {sigs.get('phone_match')}")
            print(f"Address match: {sigs.get('address_match')}")
            print(f"Domain relationship: {sigs.get('domain_relationship')}")
            print(f"Structured data: {sigs.get('structured_data')}")
            
            print(f"\\nIdentity score: {conf}")
            print(f"Classification: {cls}")
            
            print(f"\\nQuality signals: {details.get('quality_signals')}")
            if details.get("reason"):
                print(f"Reason: {details['reason']}")
            print("EvidenceRecord: created (simulated)")
            print(f"EnrichmentState: {'COMPLETED' if cls not in ['FAILED', 'UNREACHABLE'] else 'UNKNOWN/FAILED'}")
            
        except Exception as e:
            print(f"Error during eval: {e}")

if __name__ == "__main__":
    run_benchmark()
