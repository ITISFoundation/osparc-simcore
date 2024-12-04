import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.rest_base import StrictRequestParameters
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from simcore_service_webserver.api_keys._exceptions_handlers import (
    handle_plugin_requests_exceptions,
)
from simcore_service_webserver.api_keys._models import ApiKey

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..models import RequestContext
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _api

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


class ApiKeysPathParams(StrictRequestParameters):
    api_key_id: int


@routes.post(f"/{API_VTAG}/auth/api-keys", name="create_api_key")
@login_required
@permission_required("user.apikey.*")
@handle_plugin_requests_exceptions
async def create_api_key(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    new_api_key = await parse_request_body_as(ApiKeyCreate, request)

    created_api_key: ApiKey = await _api.create_api_key(
        request.app,
        display_name=new_api_key.display_name,
        expiration=new_api_key.expiration,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    api_key = ApiKeyGet.model_validate(created_api_key)
    # api_key.api_base_url = TODO: https://github.com/ITISFoundation/osparc-simcore/issues/6340 # @pcrespov

    return envelope_json_response(api_key)


@routes.get(f"/{API_VTAG}/auth/api-keys", name="get_api_keys")
@login_required
@permission_required("user.apikey.*")
@handle_plugin_requests_exceptions
async def get_api_keys(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    api_keys = await _api.get_api_keys(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(
        TypeAdapter(list[ApiKeyGet]).validate_python(api_keys)
    )


@routes.get(f"/{API_VTAG}/auth/api-keys/{{api_key_id}}", name="get_api_key")
@login_required
@permission_required("user.apikey.*")
@handle_plugin_requests_exceptions
async def get_api_key(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ApiKeysPathParams, request)
    api_key: ApiKey = await _api.get_api_key(
        request.app,
        api_key_id=path_params.api_key_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(ApiKeyGet.model_validate(api_key))


@routes.delete(f"/{API_VTAG}/auth/api-keys/{{api_key_id}}", name="delete_api_key")
@login_required
@permission_required("user.apikey.*")
@handle_plugin_requests_exceptions
async def delete_api_key(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ApiKeysPathParams, request)

    await _api.delete_api_key(
        request.app,
        api_key_id=path_params.api_key_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
