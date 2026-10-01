with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('                    raw_sheet.leads_scraped = '):
        line = '                        raw_sheet.leads_scraped = ' + line.split(' = ')[1]
    if line.startswith('                    raw_sheet.discovered_count = '):
        line = '                        raw_sheet.discovered_count = ' + line.split(' = ')[1]
    if line.startswith('                    raw_sheet.valid_count = '):
        line = '                        raw_sheet.valid_count = ' + line.split(' = ')[1]
    if line.startswith('                    raw_sheet.progress_percent = '):
        line = '                        raw_sheet.progress_percent = ' + line.split(' = ')[1]
    if line.startswith('                    raw_sheet.current_source = '):
        line = '                        raw_sheet.current_source = ' + line.split(' = ')[1]
    new_lines.append(line)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
