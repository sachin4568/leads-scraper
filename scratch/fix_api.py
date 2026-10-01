with open('backend/app/api.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('(\\n    ServiceOpportunityRead', '(\n    ServiceOpportunityRead')

with open('backend/app/api.py', 'w', encoding='utf-8') as f:
    f.write(text)
