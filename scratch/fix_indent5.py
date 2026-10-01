with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('                canonical_lead, obs, l_state = self.resolver.process_observation(db, raw_lead)'):
        line = '                    canonical_lead, obs, l_state = self.resolver.process_observation(db, raw_lead)\n'
    if line.startswith('                if canonical_lead and effective_website:'):
        line = '                    if canonical_lead and effective_website:\n'
    if line.startswith('                    canonical_lead.canonical_domain = effective_website'):
        line = '                        canonical_lead.canonical_domain = effective_website\n'
    if line.startswith('                    canonical_lead.website_state = "VERIFIED"'):
        line = '                        canonical_lead.website_state = "VERIFIED"\n'
    new_lines.append(line)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
