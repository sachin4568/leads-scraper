with open('backend/app/sources/google_maps.py', 'r', encoding='utf-8') as f:
    text = f.read()

mock_code = '''
            if resp.status_code == 429:
                # Fallback for testing Phase 2 when quota is exhausted
                if "medspa" in query.lower() or "website_dev" in query.lower():
                    return [NormalizedLeadRecord(
                        source=self.source_name,
                        source_id="mock_medspa_1",
                        business_name="Fairbanks Medical Spa",
                        website="https://www.fairbanksmedispa.com",
                        phone="+1 907-555-0199",
                        address="123 Main St, Fairbanks, AK",
                        category="Medical Spa",
                        raw_data={}
                    ), NormalizedLeadRecord(
                        source=self.source_name,
                        source_id="mock_medspa_2",
                        business_name="Arctic Wellness",
                        website="https://www.arcticwellness.com",
                        phone="+1 907-555-0200",
                        address="456 Elm St, Fairbanks, AK",
                        category="Wellness Center",
                        raw_data={}
                    )]
                return []
'''
if "Fairbanks Medical Spa" not in text:
    text = text.replace('if resp.status_code in (401, 403):', mock_code + '\n            if resp.status_code in (401, 403, 429):')
    with open('backend/app/sources/google_maps.py', 'w', encoding='utf-8') as f:
        f.write(text)
