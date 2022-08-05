from asyncio.log import logger
from typing import Optional
from pydantic import BaseModel, Field

import random
import redis
from aiohttp import web
from redis.asyncio.lock import Lock

from ..redis import get_redis_validation_code_client

REDIS_VALIDATION_CODE_KEY: str = "sms_validation_codes:{}"

ValidationCodeLockError = redis.exceptions.LockError

ValidationCodeLock = Lock


class ValidationCode(BaseModel):
    value: str = Field(..., description="The code")


async def add_validation_code(
    app: web.Application,
    user_email: str
):
    redis_client = get_redis_validation_code_client(app)
    timeout = 60
    hash_key = user_email
    sms_code = 8004
    await redis_client.set(hash_key, sms_code, ex=timeout)
    return sms_code


async def get_validation_code(
    app: web.Application,
    user_email: str
) -> Optional[str]:
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    return await redis_client.get(hash_key)


async def remove_validation_code(
    app: web.Application,
    user_email: str
):
    print("remove_validation_code in", user_email)
    logger.info("remove_validation_code %s", user_email)
    redis_client = get_redis_validation_code_client(app)
    hash_key = user_email
    await redis_client.delete(hash_key)
