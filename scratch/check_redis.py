import redis
r = redis.Redis.from_url('redis://localhost:6379/0')
try:
    print('Redis Ping:', r.ping())
except Exception as e:
    print('Error:', e)
