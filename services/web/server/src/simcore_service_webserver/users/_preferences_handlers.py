import functools

from aiohttp import web
from models_library.api_schemas_webserver.users_preferences import (
    FrontendUserPreferencePatchPathParams,
    FrontendUserPreferencePatchRequestBody,
    FrontendUserPreferencesGet,
)
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from simcore_postgres_database.utils_user_preferences import (
    CouldNotCreateOrUpdateUserPreferenceError,
)

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG
from ..login.decorators import login_required
from ..utils_aiohttp import envelope_json_response
from . import _preferences_api

routes = web.RouteTableDef()


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[pydantic-alias]
    product_name: ProductName = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[pydantic-alias]


def _handle_users_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (
            CouldNotCreateOrUpdateUserPreferenceError,
            _preferences_api.FrontendUserPreferenceIsNotDefinedError,
        ) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

    return wrapper


@routes.get(f"/{API_VTAG}/me/preferences", name="get_user_preferences")
@login_required
@_handle_users_exceptions
async def get_user_preferences(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)

    user_preferences_get: FrontendUserPreferencesGet = (
        await _preferences_api.get_frontend_user_preferences(
            request.app, user_id=req_ctx.user_id, product_name=req_ctx.product_name
        )
    )
    return envelope_json_response(user_preferences_get)


@routes.patch(
    f"/{API_VTAG}/me/preferences/{{preference}}",
    name="set_frontend_preference",
)
@login_required
@_handle_users_exceptions
async def set_frontend_preference(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    req_body = await parse_request_body_as(
        FrontendUserPreferencePatchRequestBody, request
    )
    req_path_params = parse_request_path_parameters_as(
        FrontendUserPreferencePatchPathParams, request
    )

    await _preferences_api.set_frontend_user_preference(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        frontend_preference_identifier=req_path_params.preference,
        value=req_body.value,
    )
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
