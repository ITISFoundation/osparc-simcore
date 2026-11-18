from typing import Any

from aiohttp import web
from models_library.products import ProductName
from models_library.user_preferences import FrontendUserPreference, PreferenceName
from models_library.users import UserID
from pydantic import ValidationError, validate_call
from servicelib.rabbitmq import RPCRouter

from ...application_settings import get_application_settings
from ...rabbitmq import get_rabbitmq_rpc_client
from .. import _service

router = RPCRouter()


@router.expose(reraise_if_error_type=(ValidationError,))
@validate_call(config={"arbitrary_types_allowed": True})
async def get_frontend_user_preference(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    preference_name: PreferenceName,
) -> dict[str, Any] | None:
    preference_class = FrontendUserPreference.get_preference_class_from_name(preference_name)
    if not issubclass(preference_class, FrontendUserPreference):
        msg = f"{preference_name=} is not a frontend preference"
        raise TypeError(msg)

    preference = await _service.get_frontend_user_preference(
        app,
        user_id=user_id,
        product_name=product_name,
        preference_class=preference_class,
    )
    return None if preference is None else preference.model_dump(mode="json")


async def register_rpc_routes_on_startup(app: web.Application) -> None:
    rpc_client = get_rabbitmq_rpc_client(app)
    settings = get_application_settings(app)
    if not settings.WEBSERVER_RPC_NAMESPACE:
        msg = "RPC namespace is not configured"
        raise ValueError(msg)

    await rpc_client.register_router(router, settings.WEBSERVER_RPC_NAMESPACE, app)
