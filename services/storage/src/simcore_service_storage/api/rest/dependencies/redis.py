from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app
from servicelib.redis import RedisClientsManager

from ....modules.redis import get_redis_client_manager


def get_redis_client_manager_from_request(app: Annotated[FastAPI, Depends(get_app)]) -> RedisClientsManager:
    return get_redis_client_manager(app)
