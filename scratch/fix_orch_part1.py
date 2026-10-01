import re

with open('backend/app/orchestration/discovery_orchestrator.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace all occurrences of self.db with db BUT we must wrap them.
# The easiest way is to add a db property to the orchestrator class? NO, because they don't commit it.
# Actually, the user's prompt says: "The scrape execution layer should operate primarily using: Short-lived DB sessions that are opened, used, and closed quickly."

# Let's fix _is_job_cancelled:
text = re.sub(r'self\.db\.refresh\(self\.job\)\s+if self\.job_state\["status"\] in \("STOPPED_SAVED", "CANCELLED"\):', r'if self._is_job_cancelled():', text)

with open('backend/app/orchestration/discovery_orchestrator.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("done")
