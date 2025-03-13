from datetime import timedelta

from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
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
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("create_api_key"),
        user_id=user_id,
        display_name=display_name,
        expiration=expiration,
        product_name=product_name,
        raise_on_conflict=False,
    )
    return ApiKeyGet.model_validate(result)
