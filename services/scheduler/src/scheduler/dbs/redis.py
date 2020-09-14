# return a connection to the database on demand
import asyncio
from contextlib import asynccontextmanager

import aioredis
from aioredis import Redis
from tenacity import retry, stop_after_delay, wait_random_exponential

from scheduler import config


@retry(wait=wait_random_exponential(multiplier=1, max=3), stop=stop_after_delay(5))
async def make_redis_pool() -> Redis:
    return await aioredis.create_redis_pool(
        (config.redis_host, config.redis_port), loop=asyncio.get_event_loop()
    )


async def close_redis_pool(redis_pool: Redis):
    redis_pool.close()
    await redis_pool.wait_closed()


@asynccontextmanager
async def get_redis_pool() -> Redis:
    redis = await make_redis_pool()
    try:
        yield redis
    finally:
        await close_redis_pool(redis)
