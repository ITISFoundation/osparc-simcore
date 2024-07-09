from fastapi import Request
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from servicelib.redis import RedisClientSDK
from simcore_service_dynamic_scheduler.services.redis import get_redis_client

from ...services.rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_server

assert get_app  # nosec
assert get_reverse_url_mapper  # nosec


def get_rabbitmq_client_from_request(request: Request) -> RabbitMQClient:
    return get_rabbitmq_client(request.app)


def get_rabbitmq_rpc_server_from_request(request: Request) -> RabbitMQRPCClient:
    return get_rabbitmq_rpc_server(request.app)


def get_redis_client_from_request(request: Request) -> RedisClientSDK:
    return get_redis_client(request.app)


__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
