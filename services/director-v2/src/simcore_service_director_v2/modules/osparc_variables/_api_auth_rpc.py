from datetime import timedelta

from fastapi import FastAPI
from models_library.api_schemas_webserver import DEFAULT_WEBSERVER_RPC_NAMESPACE
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rpc.webserver.auth.api_keys import ApiKeyGet
from models_library.users import UserID
from pydantic import TypeAdapter

from ..rabbitmq import get_rabbitmq_rpc_client

#
# RPC interface
#


async def create_api_key(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    display_name: str,
    expiration: timedelta | None = None,
) -> ApiKeyGet:
    rpc_client = get_rabbitmq_rpc_client(app)
    result = await rpc_client.request(
        DEFAULT_WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("create_api_key"),
        product_name=product_name,
        user_id=user_id,
        display_name=display_name,
        expiration=expiration,
    )
    return ApiKeyGet.model_validate(result)


async def delete_api_key_by_key(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    api_key: str,
) -> None:
    rpc_client = get_rabbitmq_rpc_client(app)
    await rpc_client.request(
        DEFAULT_WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_api_key_by_key"),
        product_name=product_name,
        user_id=user_id,
        api_key=api_key,
    )
