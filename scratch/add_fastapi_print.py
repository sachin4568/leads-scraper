with open('backend/app/api.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
'''    process_scrape_job_task.delay(str(job.id))
    return job''',
'''    print("=== TYPE OF PROCESS_SCRAPE_JOB_TASK ===")
    print(type(process_scrape_job_task))
    print(getattr(process_scrape_job_task, 'delay', 'NO DELAY'))
    process_scrape_job_task.delay(str(job.id))
    return job'''
)

with open('backend/app/api.py', 'w', encoding='utf-8') as f:
    f.write(text)
