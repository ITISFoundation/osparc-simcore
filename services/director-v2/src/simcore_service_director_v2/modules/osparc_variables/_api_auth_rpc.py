from datetime import timedelta

from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from pydantic import TypeAdapter

from ..rabbitmq import get_rabbitmq_rpc_client

#
# RPC interface
#


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
        TypeAdapter(RPCMethodName).validate_python("get_or_create_api_keys"),
        product_name=product_name,
        user_id=user_id,
        name=name,
        expiration=expiration,
    )
    return ApiKeyGet.model_validate(result)
