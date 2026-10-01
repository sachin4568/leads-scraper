from backend.app.worker import get_broker_url, celery_app
print(get_broker_url())
print(celery_app.conf.task_always_eager)
