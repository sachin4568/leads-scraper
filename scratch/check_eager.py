from backend.app.worker import celery_app
print(f"always_eager: {celery_app.conf.task_always_eager}")
