import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from pydantic import HttpUrl, TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.errors import DatabaseError
from simcore_service_webserver.api_keys._exceptions_handlers import (
    handle_plugin_requests_exceptions,
)
from simcore_service_webserver.api_keys._models import ApiKeysPathParams

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..models import RequestContext
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _api

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


@routes.get(f"/{API_VTAG}/auth/api-keys", name="list_api_keys")
@login_required
@permission_required("user.apikey.*")
@handle_plugin_requests_exceptions
async def list_api_keys(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    api_keys_names = await _api.list_api_keys(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(api_keys_names)


@routes.get(f"/{API_VTAG}/auth/api-keys/{{api_key_id}}", name="api_key_get")
@login_required
@permission_required("user.apikey.*")
@handle_plugin_requests_exceptions
async def api_key_get(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ApiKeysPathParams, request)
    key = await _api.get_api_key(
        request.app,
        api_key_id=path_params.api_key_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(key)


@routes.post(f"/{API_VTAG}/auth/api-keys", name="create_api_key")
@login_required
@permission_required("user.apikey.*")
@handle_plugin_requests_exceptions
async def create_api_key(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    new = await parse_request_body_as(ApiKeyCreate, request)
    try:
        resp: ApiKeyGet = await _api.create_api_key(
            request.app,
            new=new,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
        )
        api_base_url = request.url.with_host(f"api.{request.url.host}").with_path("")
        resp.api_base_url = TypeAdapter(HttpUrl).validate_python(f"{api_base_url}")
    except DatabaseError as err:
        raise web.HTTPBadRequest(
            reason="Invalid API key name: already exists",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err

    return envelope_json_response(resp)


@routes.delete(f"/{API_VTAG}/auth/api-keys/{{api_key_id}}", name="delete_api_key")
@login_required
@permission_required("user.apikey.*")
@handle_plugin_requests_exceptions
async def delete_api_key(request: web.Request):
    req_ctx = RequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(ApiKeysPathParams, request)

    try:
        await _api.delete_api_key(
            request.app,
            api_key_id=path_params.api_key_id,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
        )
    except DatabaseError as err:
        _logger.warning(
            "Failed to delete API key with ID: %s. Ignoring error",
            path_params.api_key_id,
            exc_info=err,
        )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
