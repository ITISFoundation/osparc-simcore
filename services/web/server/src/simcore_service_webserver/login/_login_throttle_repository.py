"""Redis storage of failed-login counters and temporary blocks, keyed by an email digest"""

from typing import Final

from aiohttp import web

from ..redis import get_redis_login_throttle_client

_FAILURES_KEY_FORMAT: Final[str] = "login-throttle:failures:{digest}"
_BLOCK_KEY_FORMAT: Final[str] = "login-throttle:blocked:{digest}"


async def get_block_ttl_ms(app: web.Application, *, digest: str) -> int:
    """Remaining block time in ms (0 if not blocked)"""
    redis_client = get_redis_login_throttle_client(app)
    ttl_ms: int = await redis_client.pttl(_BLOCK_KEY_FORMAT.format(digest=digest))
    return max(ttl_ms, 0)


async def increment_failures(app: web.Application, *, digest: str, window_sec: int) -> int:
    """Counts one more failure; the counter is forgotten after `window_sec` without new failures"""
    redis_client = get_redis_login_throttle_client(app)
    key = _FAILURES_KEY_FORMAT.format(digest=digest)
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_sec)
        failures, _ = await pipe.execute()
    return int(failures)


async def block(app: web.Application, *, digest: str, duration_ms: int) -> None:
    """Blocks for at least `duration_ms`; an existing longer block is never shortened"""
    redis_client = get_redis_login_throttle_client(app)
    key = _BLOCK_KEY_FORMAT.format(digest=digest)
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.set(key, 1, px=duration_ms, nx=True)
        pipe.pexpire(key, duration_ms, gt=True)
        await pipe.execute()


async def clear(app: web.Application, *, digest: str) -> None:
    redis_client = get_redis_login_throttle_client(app)
    await redis_client.delete(
        _FAILURES_KEY_FORMAT.format(digest=digest),
        _BLOCK_KEY_FORMAT.format(digest=digest),
    )
