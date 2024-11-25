import functools

from aiohttp import web
from models_library.api_schemas_webserver.users_preferences import (
    PatchPathParams,
    PatchRequestBody,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from simcore_postgres_database.utils_user_preferences import (
    CouldNotCreateOrUpdateUserPreferenceError,
)

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..models import RequestContext
from . import _preferences_api
from .exceptions import FrontendUserPreferenceIsNotDefinedError

routes = web.RouteTableDef()


def _handle_users_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (
            CouldNotCreateOrUpdateUserPreferenceError,
            FrontendUserPreferenceIsNotDefinedError,
        ) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

    return wrapper


@routes.patch(
    f"/{API_VTAG}/me/preferences/{{preference_id}}",
    name="set_frontend_preference",
)
@login_required
@_handle_users_exceptions
async def set_frontend_preference(request: web.Request) -> web.Response:
    req_ctx = RequestContext.model_validate(request)
    req_body = await parse_request_body_as(PatchRequestBody, request)
    req_path_params = parse_request_path_parameters_as(PatchPathParams, request)

    await _preferences_api.set_frontend_user_preference(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        frontend_preference_identifier=req_path_params.preference_id,
        value=req_body.value,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
