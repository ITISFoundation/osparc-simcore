from datetime import timedelta

from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ..rabbitmq import get_rabbitmq_rpc_server
from . import _api

router = RPCRouter()


@router.expose()
async def create_api_keys(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    new: ApiKeyCreate,
) -> ApiKeyGet:
    return await _api.create_api_key(
        app, new=new, user_id=user_id, product_name=product_name
    )


@router.expose()
async def delete_api_keys(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    name: str,
) -> None:
    await _api.delete_api_key(
        app, name=name, user_id=user_id, product_name=product_name
    )


@router.expose()
async def api_key_get(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    name: str,
) -> ApiKeyGet | None:
    return await _api.get_api_key(
        app, name=name, user_id=user_id, product_name=product_name
    )


@router.expose()
async def get_or_create_api_keys(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    name: str,
    expiration: timedelta | None = None,
) -> ApiKeyGet:
    return await _api.get_or_create_api_key(
        app,
        name=name,
        user_id=user_id,
        product_name=product_name,
        expiration=expiration,
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)
