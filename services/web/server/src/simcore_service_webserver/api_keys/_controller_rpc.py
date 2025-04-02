from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyCreateRequest
from models_library.products import ProductName
from models_library.rpc.webserver.auth.api_keys import ApiKeyGet
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ..rabbitmq import get_rabbitmq_rpc_server
from . import _service
from .errors import ApiKeyNotFoundError
from .models import ApiKey

router = RPCRouter()


@router.expose()
async def create_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    api_key: ApiKeyCreateRequest,
) -> ApiKeyGet:
    created_api_key: ApiKey = await _service.create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=api_key.display_name,
        expiration=api_key.expiration,
    )

    return ApiKeyGet.model_validate(created_api_key)


@router.expose(reraise_if_error_type=(ApiKeyNotFoundError,))
async def get_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    api_key_id: str,
) -> ApiKeyGet:
    api_key: ApiKey = await _service.get_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        api_key_id=api_key_id,
    )
    return ApiKeyGet.model_validate(api_key)


@router.expose()
async def delete_api_key_by_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    api_key: str,
) -> None:
    await _service.delete_api_key_by_key(
        app,
        user_id=user_id,
        product_name=product_name,
        api_key=api_key,
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
