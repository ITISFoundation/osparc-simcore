from datetime import timedelta

from fastapi import FastAPI
from models_library.products import ProductName
from models_library.rpc.webserver.auth.api_keys import ApiKeyCreate, ApiKeyGet
from models_library.users import UserID
from servicelib.rabbitmq.rpc_interfaces.webserver.auth import (
    api_keys as webserver_auth_api_keys_rpc,
)

from ..rabbitmq import get_rabbitmq_rpc_client


async def create_api_key(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    display_name: str,
    expiration: timedelta | None = None,
) -> ApiKeyGet:
    rpc_client = get_rabbitmq_rpc_client(app)

    return await webserver_auth_api_keys_rpc.create_api_key(
        rpc_client,
        user_id=user_id,
        product_name=product_name,
        api_key=ApiKeyCreate(display_name=display_name, expiration=expiration),
    )


async def delete_api_key_by_key(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    api_key: str,
) -> None:
    rpc_client = get_rabbitmq_rpc_client(app)

    result = await webserver_auth_api_keys_rpc.delete_api_key_by_key(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        api_key=api_key,
    )

    assert result is None
