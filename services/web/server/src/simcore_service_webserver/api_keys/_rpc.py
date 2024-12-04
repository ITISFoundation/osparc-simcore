from datetime import timedelta

from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter
from simcore_service_webserver.api_keys.errors import ApiKeyNotFoundError

from ..rabbitmq import get_rabbitmq_rpc_server
from . import _api

router = RPCRouter()


@router.expose()
async def create_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    api_key: ApiKeyCreate,
) -> ApiKeyGet:
    return await _api.create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=api_key.display_name,
        expiration=api_key.expiration,
    )


@router.expose(reraise_if_error_type=(ApiKeyNotFoundError,))
async def get_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    api_key_id: int,
) -> ApiKeyGet | None:
    return await _api.get_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        api_key_id=api_key_id,
    )


@router.expose()
async def get_or_create_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    display_name: str,
    expiration: timedelta | None = None,
) -> ApiKeyGet:
    return await _api.get_or_create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=display_name,
        expiration=expiration,
    )


@router.expose()
async def delete_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    api_key_id: int,
) -> None:
    await _api.delete_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        api_key_id=api_key_id,
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
