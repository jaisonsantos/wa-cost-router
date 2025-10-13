import redis
from rq import Worker, Queue, Connection
from app.core.config import settings

listen = ["default", "message_send", "crm_sync"]

redis_conn = redis.from_url(settings.REDIS_URL)

if __name__ == '__main__':
    with Connection(redis_conn):
        worker = Worker(list(map(Queue, listen)))
        worker.work()
