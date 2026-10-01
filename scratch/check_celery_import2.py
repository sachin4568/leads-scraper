from backend.app.worker import get_broker_url
try:
    from celery import Celery
    Celery('test', broker=get_broker_url())
    print('No error')
except Exception as e:
    import traceback
    traceback.print_exc()
