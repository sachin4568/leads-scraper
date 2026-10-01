from backend.app.worker import get_broker_url
try:
    from celery import Celery
    Celery("lead_intelligence", broker=get_broker_url())
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
