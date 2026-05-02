import redis.asyncio as aioredis
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

# Connection pool
redis_client = None


async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return redis_client


async def publish_log(channel: str, message: str):
    try:
        client = await get_redis()
        await client.publish(channel, message)
    except Exception as e:
        logger.error("redis_publish_failed", error=str(e))


async def subscribe_logs(channel: str = "task:logs"):
    client = await get_redis()
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)
    return pubsub
