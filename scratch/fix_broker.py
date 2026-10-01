import re

with open('backend/app/worker.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('''def get_broker_url() -> str:
    try:
        url = settings.redis_url.get_secret_value()
        import redis
        r = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
        r.ping()
        return url
    except Exception:
        return "memory://"''', '''def get_broker_url() -> str:
    return "sqla+" + settings.database_url''')

with open('backend/app/worker.py', 'w', encoding='utf-8') as f:
    f.write(content)
