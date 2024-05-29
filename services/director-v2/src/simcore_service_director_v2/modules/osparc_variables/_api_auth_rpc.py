from datetime import timedelta
from typing import Any

from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from pydantic import parse_obj_as

from ..rabbitmq import get_rabbitmq_rpc_client

#
# RPC interface
#


async def create_api_key_and_secret(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    name: str,
    expiration: timedelta | None = None,
) -> ApiKeyGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    result = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "create_api_keys"),
        product_name=product_name,
        user_id=user_id,
        new=ApiKeyCreate(display_name=name, expiration=expiration),
    )
    return ApiKeyGet.parse_obj(result)


async def get_api_key_and_secret(
    app: FastAPI, *, product_name: ProductName, user_id: UserID, name: str
) -> ApiKeyGet | None:
    rpc_client = get_rabbitmq_rpc_client(app)
    result: Any | None = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "api_key_get"),
        product_name=product_name,
        user_id=user_id,
        name=name,
    )
    return parse_obj_as(ApiKeyGet | None, result)


async def get_or_create_api_key_and_secret(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    name: str,
    expiration: timedelta | None = None,
) -> ApiKeyGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    result = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_or_create_api_keys"),
        product_name=product_name,
        user_id=user_id,
        name=name,
        expiration=expiration,
    )
    return ApiKeyGet.parse_obj(result)


async def delete_api_key_and_secret(
    app: FastAPI, *, product_name: ProductName, user_id: UserID, name: str
):
    rpc_client = get_rabbitmq_rpc_client(app)
    await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "delete_api_keys"),
        product_name=product_name,
        user_id=user_id,
        name=name,
    )
