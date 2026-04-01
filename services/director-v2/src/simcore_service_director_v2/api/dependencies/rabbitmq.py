from fastapi import Request
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.redis import RedisClientsManager

from ...modules.rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client
from ...modules.redis import get_redis_client_manager


def get_rabbitmq_client_from_request(request: Request):
    return get_rabbitmq_client(request.app)


def rabbitmq_rpc_client(request: Request) -> RabbitMQRPCClient:
    return get_rabbitmq_rpc_client(request.app)


def get_redis_client_manager_from_request(request: Request) -> RedisClientsManager:
    return get_redis_client_manager(request.app)
