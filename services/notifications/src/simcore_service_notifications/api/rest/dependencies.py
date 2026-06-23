# pylint:disable=unused-import

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from models_library.healthchecks import LivenessResult
from servicelib.db_asyncpg_utils import check_postgres_liveness
from servicelib.fastapi.db_asyncpg_engine import get_engine
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.redis import RedisClientSDK

from ...clients import redis


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_rabbitmq_rpc_client(
    app: Annotated[FastAPI, Depends(get_application)],
) -> RabbitMQRPCClient:
    assert isinstance(app.state.rabbitmq_rpc_client, RabbitMQRPCClient)  # nosec
    return app.state.rabbitmq_rpc_client


async def get_postgres_liveness(
    app: Annotated[FastAPI, Depends(get_application)],
) -> LivenessResult:
    return await check_postgres_liveness(get_engine(app))


def get_redis_client(app: Annotated[FastAPI, Depends(get_application)]) -> RedisClientSDK:
    return redis.get_redis_client(app)
