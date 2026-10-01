import asyncio
from backend.app.enrichment.email_pipeline import run_email_discovery

def run_benchmark():
    test_cases = [
        {
            "name": "A. Real business with a visible email on homepage",
            "url": "https://www.djangoproject.com", 
            "domain": "djangoproject.com"
        },
        {
            "name": "B. Real business with email only on Contact page",
            "url": "https://www.eff.org", 
            "domain": "eff.org"
        },
        {
            "name": "C. Real business with email on About/Team page",
            "url": "https://www.fsf.org",
            "domain": "fsf.org"
        },
        {
            "name": "D. Real business with multiple public emails",
            "url": "https://www.aclu.org",
            "domain": "aclu.org"
        },
        {
            "name": "E. Real business using a Gmail/Yahoo/etc. business email",
            "url": "https://www.berkeleyside.org", # A local news org, often has tips@ or Gmails listed
            "domain": "berkeleyside.org"
        },
        {
            "name": "F. Real business where no public email is found",
            "url": "https://news.ycombinator.com", # Very minimalist, likely no email on homepage
            "domain": "ycombinator.com"
        },
        {
            "name": "G. Real business whose website is inaccessible/blocked",
            "url": "https://www.yelp.com", # Yelp 403s scrapers
            "domain": "yelp.com"
        },
    ]

    for tc in test_cases:
        print(f"\\n==================================================")
        print(f"Business: {tc['name']}")
        print(f"Candidate website: {tc['url']}")
        
        try:
            status, emails, pages_checked = run_email_discovery(tc["url"], tc["domain"])
            
            print(f"Website classification: (simulated from Phase 2 as VERIFIED_BUSINESS_WEBSITE)")
            final_url = pages_checked[0] if pages_checked else tc["url"]
            print(f"Final website URL: {final_url}")
            
            print(f"\\nPages checked:")
            for p in pages_checked:
                print(f"- {p}")
                
            print(f"\\nEmails discovered:")
            for e in emails:
                print(f"- email: {e['email']}")
                print(f"  classification: {e['classification']}")
                print(f"  domain: {e['domain']}")
                print(f"  domain_match: {e['domain_match']}")
                print(f"  source URL: {e['source_url']}")
                print(f"  source type: {e['source_type']}")
                print(f"  verification result: {e['verification_status']}")
                print("---")
            
            if emails:
                primary = emails[0]
                print(f"Primary email: {primary['email']}")
                print(f"Primary-email selection reason: Highest ranked ({primary['classification']} + domain_match={primary['domain_match']})")
            
            print(f"\\nPipeline status: {status}")
            
            if not emails and status == "COMPLETED":
                print("email finding = NO_PUBLIC_EMAIL_FOUND")

        except Exception as e:
            print(f"Error during eval: {e}")

if __name__ == "__main__":
    run_benchmark()
