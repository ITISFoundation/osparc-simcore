from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Protocol

from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

if TYPE_CHECKING:
    from servicelib.rabbitmq import RabbitMQClient
    from servicelib.redis import RedisClientSDK


class _ClientWithPingProtocol(Protocol):
    async def ping(self) -> bool: ...


@asynccontextmanager
async def _paused_container(
    paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    container_name: str,
    client: _ClientWithPingProtocol,
) -> AsyncIterator[None]:
    async with paused_container(container_name):
        yield

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert await client.ping() is True


@asynccontextmanager
async def pause_rabbit(
    paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    rabbit_client: "RabbitMQClient",
) -> AsyncIterator[None]:
    async with _paused_container(paused_container, "rabbit", rabbit_client):
        yield


@asynccontextmanager
async def pause_redis(
    paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    redis_client: "RedisClientSDK",
) -> AsyncIterator[None]:
    # save db for clean restore point
    await redis_client.redis.save()
    async with _paused_container(paused_container, "redis", redis_client):
        yield
