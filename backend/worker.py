import redis
from rq import Worker, Queue, Connection
from app.core.config import settings

listen = ['default']

redis_conn = redis.from_url(settings.REDIS_URL)

if __name__ == '__main__':
    with Connection(redis_conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()
