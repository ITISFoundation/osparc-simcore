from datetime import timedelta

from aiohttp import web
from models_library.products import ProductName
from models_library.rpc.webserver.auth.api_keys import ApiKeyGet
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ...application_settings import get_application_settings
from ...rabbitmq import get_rabbitmq_rpc_server
from .. import _service
from ..errors import ApiKeyNotFoundError
from ..models import ApiKey

router = RPCRouter()


@router.expose()
async def create_api_key(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    display_name: str,
    expiration: timedelta | None = None,
) -> ApiKeyGet:
    created_api_key: ApiKey = await _service.create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=display_name,
        expiration=expiration,
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
    settings = get_application_settings(app)
    if not settings.WEBSERVER_RPC_NAMESPACE:
        msg = "RPC namespace is not configured"
        raise ValueError(msg)

    await rpc_server.register_router(router, settings.WEBSERVER_RPC_NAMESPACE, app)
