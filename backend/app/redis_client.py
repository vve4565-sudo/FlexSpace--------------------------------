from redis.asyncio import Redis

from .config.config import settings

redis = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    password=settings.REDIS_PASSWORD,
    ssl=settings.REDIS_SSL,
    decode_responses=True,
)
