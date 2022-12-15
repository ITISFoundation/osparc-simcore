from dataclasses import dataclass, field

import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import BusyLoadingError, ConnectionError, TimeoutError
from redis.retry import Retry


@dataclass
class RedisClient:
    redis_dsn: str
    _client: redis.Redis = field(init=False)

    @property
    def redis(self) -> redis.Redis:
        return self._client

    def __post_init__(self):
        # Run 3 retries with exponential backoff strategy source: https://redis.readthedocs.io/en/stable/backoff.html
        retry = Retry(ExponentialBackoff(cap=0.512, base=0.008), retries=3)
        self._client = redis.from_url(
            self.redis_dsn,
            retry=retry,
            retry_on_error=[BusyLoadingError, ConnectionError, TimeoutError],
            encoding="utf-8",
            decode_responses=True,
        )

    async def close(self) -> None:
        await self._client.close(close_connection_pool=True)

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except ConnectionError:
            return False
